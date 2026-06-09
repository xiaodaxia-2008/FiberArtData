#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3", "python-dotenv", "tqdm"]
# ///

import argparse
import hashlib
import os
import sys

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
LOCAL_DIR = os.path.join(DATA_DIR, "Installers")
REMOTE_PREFIX = "Installers/"
CUSTOM_DOMAIN = "https://storage.fiber-art.myshawn.com"


def build_download_url(s3_key):
    return f"{CUSTOM_DOMAIN}/{s3_key}"


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


def list_local_files(local_dir):
    """Return a dict {relative_key: absolute_path} for all files under local_dir."""
    result = {}
    if not os.path.isdir(local_dir):
        return result
    for root, _, files in os.walk(local_dir):
        for f in files:
            abs_path = os.path.join(root, f)
            rel = os.path.relpath(abs_path, local_dir).replace("\\", "/")
            result[rel] = abs_path
    return result


def list_remote_files(s3_client, prefix):
    """Return a set of relative keys for all non-folder objects under prefix."""
    result = set()
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            rel = key[len(prefix) :]
            result.add(rel)
    return result


def delete_remote_file(s3_client, s3_key, dry_run=False):
    if dry_run:
        print(f"[Dry-run] Would delete {s3_key}")
        return
    try:
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
        print(f"[Deleted] {s3_key}")
    except ClientError as e:
        print(f"[Failed] to delete {s3_key}: {e}")


def upload_file_if_changed(s3_client, local_path, s3_key, dry_run=False):
    if not os.path.exists(local_path):
        print(f"Error: Local file {local_path} not found.")
        return

    local_md5 = calculate_md5(local_path)
    download_url = build_download_url(s3_key)

    # Check if remote file exists and has the same Metadata MD5
    # Check remote hash regardless of dry-run mode
    try:
        response = s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
        remote_md5 = response.get("Metadata", {}).get("local-md5")

        if local_md5 == remote_md5:
            print(f"[Skipped] {s3_key} (Metadata MD5 matched: {local_md5})")
            print(f"  URL: {download_url}")
            return
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code != "404":
            print(f"Error checking {s3_key}: {e}")
            return

    if dry_run:
        print(f"[Dry-run] Would upload {s3_key} (local MD5: {local_md5})")
        print(f"  URL: {download_url}")
        return

    print(f"Uploading {s3_key}...")
    try:
        file_size = os.path.getsize(local_path)
        progress_callback = ProgressPercentage(local_path, file_size)

        # Prepare upload arguments with Metadata and ContentType
        extra_args = {"Metadata": {"local-md5": local_md5}}
        if s3_key.lower().endswith(".exe"):
            extra_args["ContentType"] = "application/x-msdownload"

        s3_client.upload_file(
            local_path,
            BUCKET_NAME,
            s3_key,
            ExtraArgs=extra_args,
            Callback=progress_callback,
        )
        print(f"[Success] Uploaded {s3_key}")
        print(f"  URL: {download_url}")
    except Exception as e:
        print(f"[Failed] to upload {local_path}: {e}")


def main():
    if not all([ENDPOINT_URL, ACCESS_KEY, SECRET_KEY, BUCKET_NAME]):
        print("Error: Missing R2 credentials in environment variables.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Sync local Installers/ to R2 Installers/ prefix (single direction: local -> remote)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded/deleted without transferring any files.",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete remote files that have no corresponding local file.",
    )
    args = parser.parse_args()

    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="auto",
    )

    print(f"Connected to R2 bucket: {BUCKET_NAME}")
    print(f"Local directory: {LOCAL_DIR}")
    print(f"Remote prefix:  {REMOTE_PREFIX}")
    if args.dry_run:
        print("[DRY-RUN] No files will be transferred.")
    if args.prune:
        print("[PRUNE] Remote files with no local counterpart will be deleted.")

    if not os.path.isdir(LOCAL_DIR):
        print(f"Error: Local directory {LOCAL_DIR} does not exist.")
        sys.exit(1)

    local_files = list_local_files(LOCAL_DIR)
    print(f"Found {len(local_files)} local file(s) under {LOCAL_DIR}.")

    # 1. Upload new/changed local files
    for rel_key in sorted(local_files):
        local_path = local_files[rel_key]
        s3_key = REMOTE_PREFIX + rel_key
        upload_file_if_changed(s3, local_path, s3_key, dry_run=args.dry_run)

    # 2. Optionally delete remote files that have no local counterpart
    if args.prune or args.dry_run:
        remote_files = list_remote_files(s3, REMOTE_PREFIX)
        orphans = sorted(remote_files - set(local_files))
        if args.prune:
            print(f"Found {len(orphans)} remote file(s) with no local counterpart.")
            for rel_key in orphans:
                delete_remote_file(s3, REMOTE_PREFIX + rel_key, dry_run=args.dry_run)
        else:
            # dry-run only: still report what *would* be pruned
            if orphans:
                print(
                    f"[Dry-run] {len(orphans)} remote file(s) have no local counterpart "
                    f"(run with --prune to delete):"
                )
                for rel_key in orphans:
                    print(f"[Dry-run] Would delete {REMOTE_PREFIX}{rel_key}")

    print("\nAll uploads complete.")


if __name__ == "__main__":
    main()
