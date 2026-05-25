#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["boto3", "python-dotenv", "tqdm"]
# ///

import os
import sys
import json
import shutil
import hashlib
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

def upload_file_if_changed(s3_client, local_path, s3_key):
    if not os.path.exists(local_path):
        print(f"Error: Local file {local_path} not found.")
        return

    local_md5 = calculate_md5(local_path)
    
    # Check if remote file exists and has same MD5 (ETag)
    try:
        response = s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
        remote_etag = response.get('ETag', '').strip('"\'')
        
        if local_md5 == remote_etag:
            print(f"[Skipped] {s3_key} (Hash matched: {local_md5})")
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
        
        s3_client.upload_file(
            local_path,
            BUCKET_NAME,
            s3_key,
            Callback=progress_callback
        )
        print(f"[Success] Uploaded {s3_key}")
    except Exception as e:
        print(f"[Failed] to upload {local_path}: {e}")

def main():
    if not all([ENDPOINT_URL, ACCESS_KEY, SECRET_KEY, BUCKET_NAME]):
        print("Error: Missing R2 credentials in environment variables.")
        sys.exit(1)

    s3 = boto3.client(
        's3',
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name='auto'
    )

    print(f"Connected to R2 bucket: {BUCKET_NAME}")

    if not os.path.exists(CATALOG_FILE):
        print(f"Error: catalog.json not found at {CATALOG_FILE}")
        sys.exit(1)

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    models = catalog.get("models", [])
    print(f"Found {len(models)} models in catalog.json.")

    # 1. Process and zip folders according to catalog.json
    for model in models:
        urdf_rel_path = model.get("urdf")
        if not urdf_rel_path:
            continue

        # e.g., "Robots/UR10/UR10.urdf" -> parts: ["Robots", "UR10", "UR10.urdf"]
        parts = urdf_rel_path.replace("\\", "/").split("/")
        if len(parts) < 3:
            continue

        category = parts[0]
        model_folder_name = parts[1]

        # Define source and zip folders
        source_dir = os.path.join(DATA_DIR, category)
        zip_dir = os.path.join(DATA_DIR, f"{category}_Zips")
        os.makedirs(zip_dir, exist_ok=True)

        zip_base = os.path.join(zip_dir, model_folder_name)
        local_zip_path = f"{zip_base}.zip"
        
        print(f"Zipping {category}/{model_folder_name} -> {category}_Zips/{model_folder_name}.zip ...")
        shutil.make_archive(zip_base, 'zip', source_dir, model_folder_name)

        # 2. Upload to Cloudflare R2
        s3_key = f"{category}/{model_folder_name}.zip"
        upload_file_if_changed(s3, local_zip_path, s3_key)

    # 3. Upload catalog.json
    print("\nUploading catalog.json...")
    upload_file_if_changed(s3, CATALOG_FILE, "catalog.json")

    print("\nAll uploads complete.")

if __name__ == "__main__":
    main()
