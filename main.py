import io
import os
import time
import logging
from datetime import datetime, timezone

import boto3
import pandas as pd
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

API_URL = os.getenv("API_URL", "https://jsonplaceholder.typicode.com/posts")
S3_BUCKET = os.getenv("S3_BUCKET", "landing-zone")
S3_PREFIX = os.getenv("S3_PREFIX", "raw/")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin123")


def get_s3_client():
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def ensure_bucket_exists(s3):
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
        logging.info("Bucket already exists: %s", S3_BUCKET)
    except ClientError:
        logging.info("Creating bucket: %s", S3_BUCKET)
        if AWS_REGION == "us-east-1":
            s3.create_bucket(Bucket=S3_BUCKET)
        else:
            s3.create_bucket(
                Bucket=S3_BUCKET,
                CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
            )


def wait_for_api(max_retries=10, sleep_seconds=3):
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(API_URL, timeout=30)
            response.raise_for_status()
            return response
        except Exception as exc:
            logging.warning("API not ready yet (attempt %s/%s): %s", attempt, max_retries, exc)
            time.sleep(sleep_seconds)
    raise RuntimeError(f"API failed after {max_retries} attempts: {API_URL}")


def download_and_convert():
    response = wait_for_api()
    data = response.json()

    if isinstance(data, dict):
        data = [data]

    df = pd.DataFrame(data)
    if df.empty:
        raise ValueError("API returned no data")

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    return csv_buffer.getvalue()


def upload_csv_to_s3(s3, csv_data: str):
    file_name = f"posts_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    s3_key = f"{S3_PREFIX.rstrip('/')}/{file_name}"

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=csv_data.encode("utf-8"),
        ContentType="text/csv",
    )

    return s3_key


def main():
    logging.info("Starting API to S3 pipeline")
    s3 = get_s3_client()
    ensure_bucket_exists(s3)

    csv_data = download_and_convert()
    s3_key = upload_csv_to_s3(s3, csv_data)

    logging.info("Upload successful")
    logging.info("Bucket: %s", S3_BUCKET)
    logging.info("Object key: %s", s3_key)
    logging.info("S3 path: s3://%s/%s", S3_BUCKET, s3_key)


if __name__ == "__main__":
    main()