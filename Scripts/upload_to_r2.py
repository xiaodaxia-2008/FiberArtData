#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3", "python-dotenv", "tqdm"]
# ///

import os
import sys
import json
import shutil
import hashlib
import argparse
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

ENDPOINT_URL = os.environ.get("CloudFlareAPI_FiberArt_S3_API")
ACCESS_KEY = os.environ.get("CloudFlareAPI_FiberArt_S3_ID")
SECRET_KEY = os.environ.get("CloudFlareAPI_FiberArt_S3_SECRET")
BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "fiber-art")

DATA_DIR = r"C:\AppSource\FiberArtData"
CATALOG_FILE = os.path.join(DATA_DIR, "catalog.json")

class ProgressPercentage(object):
    def __init__(self, filename, size):
        self._filename = filename
        self._size = size
        self._seen_so_far = 0
        self._pbar = tqdm(
            total=size,
            unit='B',
            unit_scale=True,
            desc=os.path.basename(filename),
            leave=False
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

def upload_file_if_changed(s3_client, local_path, s3_key, remote_hash=None):
    if not os.path.exists(local_path):
        print(f"Error: Local file {local_path} not found.")
        return

    local_md5 = calculate_md5(local_path)
    
    # Check if remote file exists and has same Metadata MD5 or remote_hash
    if remote_hash is not None:
        if local_md5 == remote_hash:
            print(f"[Skipped] {s3_key} (Cloud catalog hash matched: {local_md5})")
            return
    else:
        try:
            response = s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
            remote_md5 = response.get('Metadata', {}).get('local-md5')
            
            if local_md5 == remote_md5:
                print(f"[Skipped] {s3_key} (Metadata MD5 matched: {local_md5})")
                return
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                pass # File does not exist, proceed to upload
            else:
                print(f"Error checking {s3_key}: {e}")
                return

    print(f"Uploading {s3_key}...")
    try:
        file_size = os.path.getsize(local_path)
        progress_callback = ProgressPercentage(local_path, file_size)
        
        # Prepare upload arguments with Metadata and ContentType
        extra_args = {
            'Metadata': {
                'local-md5': local_md5
            }
        }
        if s3_key.endswith('.zip'):
            extra_args['ContentType'] = 'application/zip'
        elif s3_key.endswith('.json'):
            extra_args['ContentType'] = 'application/json'
            
        s3_client.upload_file(
            local_path,
            BUCKET_NAME,
            s3_key,
            ExtraArgs=extra_args,
            Callback=progress_callback
        )
        print(f"[Success] Uploaded {s3_key}")
    except Exception as e:
        print(f"[Failed] to upload {local_path}: {e}")

def get_cloud_model_hash(cloud_catalog, category, model_folder_name):
    """Retrieve the model zip hash from the cloud catalog dictionary."""
    if not cloud_catalog:
        return None
    for model in cloud_catalog.get("models", []):
        urdf_rel_path = model.get("urdf")
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
        
        if cat.lower() == category.lower() and folder.lower() == model_folder_name.lower():
            return model.get("hash")
    return None

def main():
    if not all([ENDPOINT_URL, ACCESS_KEY, SECRET_KEY, BUCKET_NAME]):
        print("Error: Missing R2 credentials in environment variables.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Upload zips and catalog to R2")
    parser.add_argument("--update-file", help="Path to update.json filtering file")
    args = parser.parse_args()

    s3 = boto3.client(
        's3',
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name='auto'
    )

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
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print("Cloud catalog.json does not exist yet (first-time upload).")
        else:
            print(f"Warning: Failed to download cloud catalog.json: {e}")
    except Exception as e:
        print(f"Warning: Error parsing cloud catalog.json: {e}")

    # Load local catalog.json
    if not os.path.exists(CATALOG_FILE):
        print(f"Error: catalog.json not found at {CATALOG_FILE}")
        sys.exit(1)

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # Step 2: Compare local and cloud catalogs. If identical, exit early!
    if cloud_catalog is not None:
        if catalog == cloud_catalog:
            print("\n[Skipped] Local catalog.json is identical to cloud catalog.json. No uploads needed!")
            print("Early exit.")
            sys.exit(0)
        else:
            print("Local catalog.json and cloud catalog.json differ. Proceeding with upload process...")

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
            filter_models = {str(item).replace("\\", "/").lower() for item in update_list}
            print(f"Loaded filter from {args.update_file}. Will only process {len(filter_models)} specified models.")
        except Exception as e:
            print(f"Error parsing update file: {e}")
            sys.exit(1)

    processed_models = set()

    # 1. Process and zip folders according to catalog.json
    for model in models:
        urdf_rel_path = model.get("urdf")
        if not urdf_rel_path:
            continue

        # e.g., "Robots/UR10/UR10.urdf" -> parts: ["Robots", "UR10", "UR10.urdf"]
        # or "Robots/UR10.urdf" -> parts: ["Robots", "UR10.urdf"]
        parts = urdf_rel_path.replace("\\", "/").split("/")
        if len(parts) < 2:
            continue

        category = parts[0]
        if len(parts) >= 3:
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

        # Define source and zip folders
        source_dir = os.path.join(DATA_DIR, category)
        model_dir = os.path.join(source_dir, model_folder_name)
        
        # Verify source directory exists before zipping
        if not os.path.isdir(model_dir):
            print(f"Warning: Model directory {model_dir} does not exist. Skipping.")
            continue

        zip_dir = os.path.join(DATA_DIR, f"{category}_Zips")
        os.makedirs(zip_dir, exist_ok=True)

        zip_base = os.path.join(zip_dir, model_folder_name)
        local_zip_path = f"{zip_base}.zip"
        
        print(f"Zipping {category}/{model_folder_name} -> {category}_Zips/{model_folder_name}.zip ...")
        try:
            shutil.make_archive(zip_base, 'zip', source_dir, model_folder_name)
        except Exception as e:
            print(f"Error zipping {model_dir}: {e}. Skipping.")
            continue

        # 2. Upload to Cloudflare R2
        s3_key = f"{category}/{model_folder_name}.zip"
        remote_hash = get_cloud_model_hash(cloud_catalog, category, model_folder_name)
        upload_file_if_changed(s3, local_zip_path, s3_key, remote_hash=remote_hash)

    # 3. Upload catalog.json
    print("\nUploading catalog.json...")
    upload_file_if_changed(s3, CATALOG_FILE, "catalog.json")

    print("\nAll uploads complete.")

if __name__ == "__main__":
    main()
