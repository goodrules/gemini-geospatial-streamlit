#!/usr/bin/env python
"""
Wrapper script to run the GCS downloader.
This downloads files from the configured GCS bucket to data/local.
"""

import os
from utils.gcs_downloader import main as download_files

if __name__ == "__main__":
    print("Starting download process from GCS bucket...")
    download_files()
    print("Download process completed. Check logs for details.") 
