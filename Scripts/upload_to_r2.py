#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3", "python-dotenv", "tqdm", "lxml"]
# ///

import argparse
from collections import Counter
import hashlib
import json
import os
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from lxml import etree
from tqdm import tqdm

load_dotenv()

ENDPOINT_URL = os.environ.get("CloudFlareAPI_FiberArt_S3_API")
ACCESS_KEY = os.environ.get("CloudFlareAPI_FiberArt_S3_ID")
SECRET_KEY = os.environ.get("CloudFlareAPI_FiberArt_S3_SECRET")
BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "fiber-art")

DATA_DIR = r"C:\AppSource\FiberArtData"
CATALOG_FILE = os.path.join(DATA_DIR, "catalog.json")
R2_BASE_URL = "https://storage.fiber-art.myshawn.com/"
MESH_EXTENSIONS = (".dae", ".fbx", ".glb", ".gltf", ".obj", ".ply", ".stl")
CATEGORIES = [
    {"folder": "Robots", "exts": (".urdf",), "type": "Robot"},
    {"folder": "Tracks", "exts": (".track",), "type": "Track"},
    {"folder": "Positioners", "exts": (".positioner",), "type": "Positioner"},
    {"folder": "Tools", "exts": (".tool", ".jointed_tool"), "type": "Tool"},
    {"folder": "CADModels", "type": "CADModel", "individual_files": True},
    {
        "folder": "Models",
        "exts": MESH_EXTENSIONS,
        "type": "Model",
        "individual_files": True,
    },
]
_output_lock = threading.Lock()
_thread_local = threading.local()
tqdm.set_lock(_output_lock)


def log(message):
    """Write one complete status line when multiple uploads are active."""
    with _output_lock:
        print(message)


def create_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="auto",
    )


def get_thread_s3_client():
    """Keep one client per worker so transfers do not share client state."""
    if not hasattr(_thread_local, "s3"):
        _thread_local.s3 = create_s3_client()
    return _thread_local.s3


def upload_model_archive(local_zip_path, s3_key, remote_hash, local_hash=None):
    return upload_file_if_changed(
        get_thread_s3_client(), local_zip_path, s3_key, remote_hash, local_hash
    )


class ProgressPercentage(object):
    def __init__(self, filename, size):
        self._filename = filename
        self._size = size
        self._seen_so_far = 0
        self._pbar = tqdm(
            total=size,
            unit="B",
            unit_scale=True,
            desc=os.path.basename(filename),
            leave=False,
        )

    def __call__(self, bytes_amount):
        self._seen_so_far += bytes_amount
        self._pbar.update(bytes_amount)
        if self._seen_so_far >= self._size:
            self._pbar.close()


def calculate_md5(file_path):
    """Calculate the MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def md5_file(file_path):
    return calculate_md5(file_path)


def model_source_hash(path):
    """Deterministic content hash of an individual file or a model directory.

    Each file contributes its relative path, size and MD5, so the hash changes
    when any source file changes. This is the single source of truth used by
    both generate_catalog() and the upload skip-logic.
    """
    if os.path.isfile(path):
        return md5_file(path)
    entries = []
    for root_dir, dirs, files in os.walk(path):
        dirs.sort()
        for f in sorted(files):
            file_path = os.path.join(root_dir, f)
            rel = os.path.relpath(file_path, path).replace("\\", "/")
            entries.append((rel, os.path.getsize(file_path), md5_file(file_path)))
    blob = "\n".join(f"{rel}:{size}:{digest}" for rel, size, digest in entries)
    return hashlib.md5(blob.encode("utf-8")).hexdigest()


def generate_catalog():
    """Rebuild catalog.json, including a content hash for every model.

    The hash is computed with model_source_hash(), the same algorithm used at
    upload time, so the local/cloud catalog comparison and the per-model
    skip logic stay in sync with the actual source files.
    """
    catalog = {"version": "1.0", "models": []}

    for cat in CATEGORIES:
        source_dir = os.path.join(DATA_DIR, cat["folder"])

        if not os.path.exists(source_dir):
            print(f"Directory {source_dir} not found. Skipping.")
            continue

        if cat.get("individual_files"):
            for f in sorted(os.listdir(source_dir)):
                file_path = os.path.join(source_dir, f)
                if not os.path.isfile(file_path):
                    continue
                if "exts" in cat and not f.lower().endswith(cat["exts"]):
                    continue

                name_no_ext, _ = os.path.splitext(f)
                rel_path = os.path.relpath(file_path, DATA_DIR).replace("\\", "/")
                zip_url = f"{R2_BASE_URL}{cat['folder']}/{f}.zip"

                catalog["models"].append(
                    {
                        "type": cat["type"],
                        "name": name_no_ext,
                        "file": rel_path,
                        "urdf": rel_path,
                        "uri": zip_url,
                        "hash": model_source_hash(file_path),
                    }
                )
        else:
            for root_dir, dirs, files in os.walk(source_dir):
                for f in files:
                    if not f.endswith(cat["exts"]):
                        continue
                    urdf_path = os.path.join(root_dir, f)
                    rel_urdf = os.path.relpath(urdf_path, DATA_DIR).replace(
                        "\\", "/"
                    )

                    model_dir = root_dir
                    while (
                        os.path.dirname(model_dir) != source_dir
                        and model_dir != source_dir
                    ):
                        model_dir = os.path.dirname(model_dir)

                    model_folder_name = os.path.basename(model_dir)
                    zip_url = (
                        f"{R2_BASE_URL}{cat['folder']}/{model_folder_name}.zip"
                    )

                    try:
                        tree = etree.parse(urdf_path)
                        root = tree.getroot()

                        fallback_name = f
                        for ext in cat["exts"]:
                            if fallback_name.endswith(ext):
                                fallback_name = fallback_name[: -len(ext)]
                                break

                        model_entry = {
                            "type": cat["type"],
                            "name": root.get("name", fallback_name),
                            "file": rel_urdf,
                            "urdf": rel_urdf,
                            "uri": zip_url,
                            "hash": model_source_hash(model_dir),
                        }

                        brand = root.get("brand")
                        if brand is not None:
                            model_entry["brand"] = brand

                        payload = root.get("payload")
                        if payload is not None:
                            try:
                                model_entry["payload"] = float(payload)
                            except ValueError:
                                model_entry["payload"] = payload

                        reach = root.get("reach")
                        if reach is not None:
                            try:
                                model_entry["reach"] = float(reach)
                            except ValueError:
                                model_entry["reach"] = reach

                        xml_type = root.get("type")
                        if xml_type is not None:
                            model_entry["type"] = xml_type

                        catalog["models"].append(model_entry)
                    except Exception as e:
                        print(f"Error parsing {urdf_path}: {e}")

    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(
        f"Generated catalog.json at {CATALOG_FILE} "
        f"with {len(catalog['models'])} models."
    )
    return catalog


def upload_file_if_changed(
    s3_client, local_path, s3_key, remote_hash=None, local_hash=None
):
    if not os.path.exists(local_path):
        log(f"Error: Local file {local_path} not found.")
        return "failed"

    local_md5 = calculate_md5(local_path)

    # Check remote against the model source hash (cloud catalog hash).
    if remote_hash is not None and local_hash is not None:
        if local_hash == remote_hash:
            log(f"[Skipped] {s3_key} (Cloud catalog hash matched: {local_hash})")
            return "skipped"
    else:
        try:
            response = s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
            remote_md5 = response.get("Metadata", {}).get("local-md5")

            if local_md5 == remote_md5:
                log(f"[Skipped] {s3_key} (Metadata MD5 matched: {local_md5})")
                return "skipped"
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                pass  # File does not exist, proceed to upload
            else:
                log(f"Error checking {s3_key}: {e}")
                return "failed"

    log(f"Uploading {s3_key}...")
    try:
        file_size = os.path.getsize(local_path)
        progress_callback = ProgressPercentage(local_path, file_size)

        # Prepare upload arguments with Metadata and ContentType
        extra_args = {"Metadata": {"local-md5": local_md5}}
        if s3_key.endswith(".zip"):
            extra_args["ContentType"] = "application/zip"
        elif s3_key.endswith(".json"):
            extra_args["ContentType"] = "application/json"

        s3_client.upload_file(
            local_path,
            BUCKET_NAME,
            s3_key,
            ExtraArgs=extra_args,
            Callback=progress_callback,
        )
        log(f"[Success] Uploaded {s3_key}")
        return "uploaded"
    except Exception as e:
        log(f"[Failed] to upload {local_path}: {e}")
        return "failed"


def get_model_file_path(model):
    """Return the model's main file relative path ('file' preferred, 'urdf' fallback).

    'urdf' is kept for backward compatibility with older catalogs and
    downstream consumers that have not yet migrated to 'file'.
    """
    return model.get("file") or model.get("urdf")


def get_cloud_model_hash(cloud_catalog, category, model_folder_name):
    """Retrieve the model zip hash from the cloud catalog dictionary."""
    if not cloud_catalog:
        return None
    for model in cloud_catalog.get("models", []):
        urdf_rel_path = get_model_file_path(model)
        if not urdf_rel_path:
            continue
        # Normalize path for robust comparison
        parts = urdf_rel_path.replace("\\", "/").split("/")
        if len(parts) < 2:
            continue
        cat = parts[0]
        if len(parts) >= 3:
            folder = parts[1]
        else:
            folder = os.path.splitext(parts[1])[0]

        if (
            cat.lower() == category.lower()
            and folder.lower() == model_folder_name.lower()
        ):
            return model.get("hash")
    return None


def process_model(model, cloud_catalog, zip_dir):
    """Create and upload one catalog model from start to finish."""
    urdf_rel_path = get_model_file_path(model)
    model_type = model.get("type", "")
    is_individual_file = model_type in ("CADModel", "Model")
    parts = urdf_rel_path.replace("\\", "/").split("/")
    category = parts[0]

    if len(parts) >= 3:
        model_folder_name = parts[1]
    elif is_individual_file:
        model_folder_name = parts[1]
    else:
        model_folder_name = os.path.splitext(parts[1])[0]

    source_dir = os.path.join(DATA_DIR, category)
    if is_individual_file:
        filename = os.path.basename(urdf_rel_path)
        file_path = os.path.join(source_dir, filename)
        if not os.path.isfile(file_path):
            log(f"Warning: Model file not found at {file_path}. Skipping.")
            return "failed"
        archive_name = f"{category}_{filename}"
        archive_source = filename
        description = f"{category}/{filename}"
        s3_key = f"{category}/{filename}.zip"
        local_hash = model_source_hash(file_path)
        remote_hash = get_cloud_model_hash(
            cloud_catalog, category, model.get("name", "")
        )
    else:
        model_dir = os.path.join(source_dir, model_folder_name)
        if not os.path.isdir(model_dir):
            log(f"Warning: Model directory {model_dir} does not exist. Skipping.")
            return False
        archive_name = f"{category}_{model_folder_name}"
        archive_source = model_folder_name
        description = f"{category}/{model_folder_name}"
        s3_key = f"{category}/{model_folder_name}.zip"
        local_hash = model_source_hash(model_dir)
        remote_hash = get_cloud_model_hash(
            cloud_catalog, category, model_folder_name
        )

    zip_base = os.path.join(zip_dir, archive_name)
    local_zip_path = f"{zip_base}.zip"
    log(f"Zipping {description} -> temp/zips/{archive_name}.zip ...")
    try:
        shutil.make_archive(zip_base, "zip", source_dir, archive_source)
    except Exception as e:
        log(f"Error zipping {description}: {e}. Skipping.")
        return "failed"

    return upload_model_archive(local_zip_path, s3_key, remote_hash, local_hash)


def get_model_archive_info(model):
    """Return the expected R2 key and whether the local model source exists."""
    urdf_rel_path = get_model_file_path(model)
    if not urdf_rel_path:
        return None, False

    model_type = model.get("type", "")
    is_individual_file = model_type in ("CADModel", "Model")
    parts = urdf_rel_path.replace("\\", "/").split("/")
    if len(parts) < 2:
        return None, False

    category = parts[0]
    source_dir = os.path.join(DATA_DIR, category)
    if len(parts) >= 3:
        model_folder_name = parts[1]
    elif is_individual_file:
        model_folder_name = parts[1]
    else:
        model_folder_name = os.path.splitext(parts[1])[0]

    if is_individual_file:
        filename = os.path.basename(urdf_rel_path)
        source_exists = os.path.isfile(os.path.join(source_dir, filename))
        return f"{category}/{filename}.zip", source_exists

    source_exists = os.path.isdir(os.path.join(source_dir, model_folder_name))
    return f"{category}/{model_folder_name}.zip", source_exists


def prune_remote_model_archives(s3_client, models):
    """Delete remote model zips that have no corresponding local model source."""
    model_categories = {
        key.split("/", 1)[0]
        for model in models
        for key, _ in [get_model_archive_info(model)]
        if key
    }
    expected_keys = {
        key
        for model in models
        for key, source_exists in [get_model_archive_info(model)]
        if key and source_exists
    }
    remote_keys = []
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=BUCKET_NAME):
            remote_keys.extend(
                obj["Key"]
                for obj in page.get("Contents", [])
                if (
                    obj["Key"].lower().endswith(".zip")
                    and obj["Key"].split("/", 1)[0] in model_categories
                )
            )
    except Exception as e:
        log(f"[Failed] listing remote model archives for prune: {e}")
        return 0, 1

    stale_keys = [key for key in remote_keys if key not in expected_keys]
    deleted = 0
    failures = 0
    for start in range(0, len(stale_keys), 1000):
        batch = stale_keys[start : start + 1000]
        try:
            response = s3_client.delete_objects(
                Bucket=BUCKET_NAME,
                Delete={"Objects": [{"Key": key} for key in batch]},
            )
            deleted += len(response.get("Deleted", []))
            errors = response.get("Errors", [])
            failures += len(errors)
            for error in errors:
                log(f"[Failed] deleting {error.get('Key')}: {error.get('Message')}")
        except Exception as e:
            failures += len(batch)
            log(f"[Failed] deleting {len(batch)} remote archive(s): {e}")

    if stale_keys:
        log(f"Pruned {deleted} remote model archive(s).")
    else:
        log("No remote model archives need pruning.")
    return deleted, failures


def main():
    if not all([ENDPOINT_URL, ACCESS_KEY, SECRET_KEY, BUCKET_NAME]):
        print("Error: Missing R2 credentials in environment variables.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Upload zips and catalog to R2")
    parser.add_argument(
        "--generate-catalog",
        action="store_true",
        help="Rebuild catalog.json (with content hashes) before uploading",
    )
    parser.add_argument("--update-file", help="Path to update.json filtering file")
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of model uploads to run concurrently (default: 4)",
    )
    parser.add_argument(
        "--prune",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Delete remote model zips without a local model (default: enabled)",
    )
    args = parser.parse_args()

    if args.workers < 1:
        parser.error("--workers must be at least 1")

    s3 = create_s3_client()

    print(f"Connected to R2 bucket: {BUCKET_NAME}")

    # Step 1: Download cloud catalog.json to temp/cloud_catalog.json
    CLOUD_CATALOG_FILE = os.path.join(DATA_DIR, "temp", "cloud_catalog.json")
    cloud_catalog = None
    try:
        print("Downloading cloud catalog.json to temp/cloud_catalog.json...")
        s3.download_file(BUCKET_NAME, "catalog.json", CLOUD_CATALOG_FILE)
        with open(CLOUD_CATALOG_FILE, "r", encoding="utf-8") as f:
            cloud_catalog = json.load(f)
        print("Cloud catalog.json downloaded and parsed successfully.")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            print("Cloud catalog.json does not exist yet (first-time upload).")
        else:
            print(f"Warning: Failed to download cloud catalog.json: {e}")
    except Exception as e:
        print(f"Warning: Error parsing cloud catalog.json: {e}")

    # Optionally regenerate catalog.json (with content hashes) first
    if args.generate_catalog:
        generate_catalog()

    # Load local catalog.json
    if not os.path.exists(CATALOG_FILE):
        print(f"Error: catalog.json not found at {CATALOG_FILE}")
        sys.exit(1)

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Step 2: Compare local and cloud catalogs. If identical, exit early!
    if cloud_catalog is not None:
        if catalog == cloud_catalog:
            print(
                "\n[Skipped] Local catalog.json is identical to cloud catalog.json. No uploads needed!"
            )
            print("Early exit.")
            sys.exit(0)
        else:
            print(
                "Local catalog.json and cloud catalog.json differ. Proceeding with upload process..."
            )

    models = catalog.get("models", [])
    print(f"Found {len(models)} models in catalog.json.")

    # Load filter file if specified
    filter_models = None
    if args.update_file:
        if not os.path.exists(args.update_file):
            print(f"Error: Update file '{args.update_file}' not found.")
            sys.exit(1)
        try:
            with open(args.update_file, "r", encoding="utf-8") as f:
                update_list = json.load(f)
            if not isinstance(update_list, list):
                print("Error: Update file must be a JSON array of strings.")
                sys.exit(1)
            filter_models = {
                str(item).replace("\\", "/").lower() for item in update_list
            }
            print(
                f"Loaded filter from {args.update_file}. Will only process {len(filter_models)} specified models."
            )
        except Exception as e:
            print(f"Error parsing update file: {e}")
            sys.exit(1)

    processed_models = set()
    models_to_process = []

    # Select and deduplicate models before handing complete model jobs to workers.
    for model in models:
        urdf_rel_path = get_model_file_path(model)
        if not urdf_rel_path:
            continue

        model_type = model.get("type", "")
        is_individual_file = model_type in ("CADModel", "Model")

        # e.g., "Robots/UR10/UR10.urdf" -> parts: ["Robots", "UR10", "UR10.urdf"]
        # or "CADModels/CircleSurface.stp" -> parts: ["CADModels", "CircleSurface.stp"]
        parts = urdf_rel_path.replace("\\", "/").split("/")
        if len(parts) < 2:
            continue

        category = parts[0]
        if len(parts) >= 3:
            model_folder_name = parts[1]
        elif is_individual_file:
            # Individual-file categories keep the full filename to avoid collisions.
            model_folder_name = parts[1]
        else:
            # Fallback for shallow directory (e.g., Robots/UR10.urdf -> folder UR10)
            model_folder_name = os.path.splitext(parts[1])[0]

        # Prevent duplicate zipping/uploading for the same model in a single run
        model_key = (category, model_folder_name)
        if model_key in processed_models:
            continue
        processed_models.add(model_key)

        # Check if we should filter this model
        if filter_models is not None:
            model_path_str = f"{category}/{model_folder_name}".lower()
            folder_name_str = model_folder_name.lower()

            matched = False
            if model_path_str in filter_models:
                matched = True
            elif folder_name_str in filter_models:
                matched = True
            else:
                for entry in filter_models:
                    if entry.endswith(f"/{folder_name_str}"):
                        matched = True
                        break

            if not matched:
                continue

        models_to_process.append(model)

    zip_dir = os.path.join(DATA_DIR, "temp", "zips")
    os.makedirs(zip_dir, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as upload_pool:
        futures = {
            upload_pool.submit(process_model, model, cloud_catalog, zip_dir): model
            for model in models_to_process
        }
        model_results = Counter()
        for future in as_completed(futures):
            try:
                model_results[future.result()] += 1
            except Exception as e:
                model_name = futures[future].get("name", "unknown model")
                log(f"[Failed] model task {model_name}: {e}")
                model_results["failed"] += 1

    deleted_remote = 0
    prune_failures = 0
    if args.prune:
        deleted_remote, prune_failures = prune_remote_model_archives(s3, models)

    # 3. Upload catalog.json
    print("\nUploading catalog.json...")
    catalog_result = upload_file_if_changed(s3, CATALOG_FILE, "catalog.json")

    # 4. Clean up temp zips
    temp_zips = os.path.join(DATA_DIR, "temp", "zips")
    deleted_zips = 0
    if os.path.isdir(temp_zips):
        deleted_zips = sum(
            1
            for entry in os.scandir(temp_zips)
            if entry.is_file() and entry.name.lower().endswith(".zip")
        )
        shutil.rmtree(temp_zips)
        log(f"Cleaned up temp/zips/ ({deleted_zips} zip file(s)).")

    model_results[catalog_result] += 1
    log(
        "\nSummary: "
        f"uploaded={model_results['uploaded']}, "
        f"skipped={model_results['skipped']}, "
        f"failed={model_results['failed'] + prune_failures}, "
        f"deleted_remote_zips={deleted_remote}, "
        f"deleted_temp_zips={deleted_zips}"
    )

    if model_results["failed"] or prune_failures or catalog_result == "failed":
        log(
            "Uploads finished with errors."
        )
        sys.exit(1)

    log("\nAll uploads complete.")


if __name__ == "__main__":
    main()
