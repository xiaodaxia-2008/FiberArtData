#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["boto3", "python-dotenv"]
# ///

import os
import sys
import hashlib
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

load_dotenv(r"C:\AppSource\FiberArt\.env")

ENDPOINT_URL = os.environ.get("CloudFlareAPI_FiberArt_S3_API")
ACCESS_KEY = os.environ.get("CloudFlareAPI_FiberArt_S3_ID")
SECRET_KEY = os.environ.get("CloudFlareAPI_FiberArt_S3_SECRET")
BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "fiber-art")

DATA_DIR = r"C:\AppSource\FiberArtData"
CATEGORIES = ["Robots", "Tracks", "Positioners", "Tools"]
CATALOG_FILE = os.path.join(DATA_DIR, "catalog.json")

def calculate_md5(file_path):
    """Calculate the MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def upload_file_if_changed(s3_client, local_path, s3_key):
    if not os.path.exists(local_path):
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

    print(f"Uploading {local_path} -> {s3_key} ...")
    try:
        s3_client.upload_file(local_path, BUCKET_NAME, s3_key)
        print("Success.")
    except Exception as e:
        print(f"Failed to upload {local_path}: {e}")

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

    # 1. Upload ZIPs
    for cat in CATEGORIES:
        zip_dir = os.path.join(DATA_DIR, f"{cat}_Zip")
        if os.path.exists(zip_dir):
            for f in os.listdir(zip_dir):
                if f.endswith('.zip'):
                    local_zip = os.path.join(zip_dir, f)
                    s3_key = f"{cat}/{f}"
                    upload_file_if_changed(s3, local_zip, s3_key)

    # 2. Upload catalog.json
    upload_file_if_changed(s3, CATALOG_FILE, "catalog.json")

    print("All uploads complete.")

if __name__ == "__main__":
    main()
