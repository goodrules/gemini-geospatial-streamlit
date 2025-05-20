# GCS Data Downloader

This utility script downloads data from a Google Cloud Storage bucket to the local `data/local` directory. It is designed to be idempotent, meaning it only downloads files that don't already exist locally.

## Prerequisites

- Google Cloud credentials set up (authenticated via `gcloud auth application-default login` or service account key)
- Environment variables configured in `.env` file

## Configuration

Add the following to your `.env` file:

```
GCS_BUCKET_NAME=your-bucket-name
GCS_PREFIX=optional-folder-prefix
```

Where:
- `GCS_BUCKET_NAME`: The name of your GCS bucket
- `GCS_PREFIX` (optional): Folder path/prefix in the bucket to limit which files to download

## Usage

Run the script directly:

```bash
python download_gcs_data.py
```

Or import and use in your code:

```python
from utils.gcs_downloader import download_files

# Download all files from bucket that don't exist locally
download_files("your-bucket-name", "path/to/local/dir")

# Download files with a specific prefix
download_files("your-bucket-name", "path/to/local/dir", "folder/prefix/")
```

## Features

- Idempotent: Can be run multiple times without duplicating files
- Only downloads files that don't exist locally
- Preserves directory structure
- Logs all operations 
