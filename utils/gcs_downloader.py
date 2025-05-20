#!/usr/bin/env python
"""
Script to download files from a Google Cloud Storage bucket to the local directory.
The script only downloads files that don't already exist locally.
"""

import os
import logging
from pathlib import Path
from google.cloud import storage
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_gcs_files(bucket_name, prefix=""):
    """
    Get a list of all files in a GCS bucket with an optional prefix.
    
    Args:
        bucket_name: Name of the GCS bucket
        prefix: Optional prefix to filter files (folder path in the bucket)
        
    Returns:
        List of blob names in the bucket
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=prefix)
        return [blob.name for blob in blobs]
    except Exception as e:
        logger.error(f"Error listing files in GCS bucket: {e}")
        raise

def get_local_files(local_dir):
    """
    Get a list of all files in the local directory.
    
    Args:
        local_dir: Path to the local directory
        
    Returns:
        Set of filenames in the local directory
    """
    local_dir_path = Path(local_dir)
    if not local_dir_path.exists():
        logger.info(f"Creating local directory: {local_dir}")
        local_dir_path.mkdir(parents=True, exist_ok=True)
        return set()
    
    # Get all files in the directory
    files = set()
    for path in local_dir_path.rglob("*"):
        if path.is_file():
            # Store the relative path for comparison
            files.add(str(path.relative_to(local_dir_path)))
    
    return files

def download_files(bucket_name, local_dir, prefix=""):
    """
    Download files from GCS bucket to local directory,
    skipping files that already exist locally.
    
    Args:
        bucket_name: Name of the GCS bucket
        local_dir: Path to the local directory
        prefix: Optional prefix to filter files (folder path in the bucket)
    """
    # Get list of files in GCS bucket
    gcs_files = get_gcs_files(bucket_name, prefix)
    logger.info(f"Found {len(gcs_files)} files in GCS bucket {bucket_name}")
    
    # Get list of files in local directory
    local_files = get_local_files(local_dir)
    logger.info(f"Found {len(local_files)} files in local directory {local_dir}")
    
    # Filter out files that already exist locally
    files_to_download = []
    for gcs_file in gcs_files:
        # If prefix is specified, remove it from the comparison
        if prefix:
            local_file_path = gcs_file[len(prefix):].lstrip('/')
        else:
            local_file_path = gcs_file
            
        if local_file_path not in local_files:
            files_to_download.append(gcs_file)
    
    logger.info(f"Downloading {len(files_to_download)} new files")
    
    # Download new files
    if files_to_download:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        for gcs_file in files_to_download:
            # If prefix is specified, remove it from the local file path
            if prefix:
                local_file_path = os.path.join(local_dir, gcs_file[len(prefix):].lstrip('/'))
            else:
                local_file_path = os.path.join(local_dir, gcs_file)
            
            # Create directory structure if it doesn't exist
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            
            # Download the file
            blob = bucket.blob(gcs_file)
            blob.download_to_filename(local_file_path)
            logger.info(f"Downloaded: {gcs_file} -> {local_file_path}")
    else:
        logger.info("No new files to download")

def main():
    """Main function to execute the download process."""
    # Get bucket name from environment variables
    bucket_name = os.environ.get("GCS_BUCKET_NAME")
    if not bucket_name:
        logger.error("GCS_BUCKET_NAME environment variable not set")
        return
    
    # Local directory to download files to
    local_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "local")
    
    # Optional prefix (folder path in the bucket)
    prefix = os.environ.get("GCS_PREFIX", "")
    
    logger.info(f"Starting download from bucket: {bucket_name}, to: {local_dir}")
    download_files(bucket_name, local_dir, prefix)
    logger.info("Download process completed")

if __name__ == "__main__":
    main() 
