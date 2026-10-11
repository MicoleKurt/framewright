"""Output storage: always local (`output/`); optionally mirrored to S3-compatible storage.

Set FS_S3_BUCKET (and the usual AWS_* credentials, or FS_S3_ENDPOINT for R2/MinIO) and
`pip install boto3`. Every file next to the finished mp4 (thumbnails, .srt, metadata) is uploaded.
"""
import glob
import os


def mirror(final_mp4: str) -> list[str]:
    bucket = os.getenv("FS_S3_BUCKET")
    if not bucket:
        return []
    try:
        import boto3
    except ImportError:
        print("[storage] FS_S3_BUCKET is set but boto3 is not installed; skipping upload")
        return []
    s3 = boto3.client("s3", endpoint_url=os.getenv("FS_S3_ENDPOINT") or None)
    prefix = os.getenv("FS_S3_PREFIX", "iframesco/")
    keys = []
    for path in glob.glob(glob.escape(final_mp4[:-4]) + ".*"):
        key = prefix + os.path.basename(path)
        s3.upload_file(path, bucket, key)
        keys.append(f"s3://{bucket}/{key}")
    return keys
