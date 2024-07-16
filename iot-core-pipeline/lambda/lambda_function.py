import os
import json
import gzip
import boto3
import base64
import logging
import pandas as pd
from io import StringIO, BytesIO
from datetime import datetime as dt

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TARGET_BUCKET = os.getenv("TARGET_BUCKET")

def decode_stream_batch(event: str) -> dict:

    decoded_records = []
    # keeping the originals for the return response
    original_records = []

    records = event["records"]

    for record in records:
        decoded_data = base64.b64decode(record["data"]).decode("utf-8")

        json_data = json.loads(decoded_data)

        decoded_records.append(json_data)
        original_records.append(record)

    return {
        "original_records": original_records,
        "decoded_records": decoded_records
    }

def data_to_df(decoded_data: list) -> pd.DataFrame:

    data_df = pd.DataFrame(decoded_data)

    return data_df

def parse_df(raw_data_df: pd.DataFrame) -> pd.DataFrame:

    # parsing logic here

    parsed_data_df = raw_data_df

    return parsed_data_df

def zip_csv(data: bytes) -> bytes:

    with BytesIO() as compressed_data:
        with gzip.GzipFile(fileobj=compressed_data, mode="wb") as f:
            f.write(data)
        return compressed_data.getvalue()
    
def create_csv(parsed_df: pd.DataFrame) -> bytes:

    file_bytes = parsed_df.to_csv(sep=";").encode("utf-8")
    compressed_csv_bytes = zip_csv(file_bytes)

    return compressed_csv_bytes

def upload_to_s3(compressed_bytes: bytes, bucket_name: str) -> None:

    unique_identifier = dt.now().strftime(format="%Y%m%d%m%f")
    file_name = f"test_csv_iot_{unique_identifier}.csv.gz"

    s3.put_object(Body=compressed_bytes, Bucket=bucket_name, Key=file_name)

    return None

def prepare_response(original_records: dict) -> str:

    response = {
        "records": [
            {
            "recordId": record["recordId"],
            "result": "Dropped",
            "data": record["data"]
            } for record in original_records
        ]
    }

    return response


def lambda_handler(event, context):

    global s3
    s3 = boto3.client("s3")
    
    logger.info(f"Received an event: {event}")

    json_data = decode_stream_batch(event=event)

    data_df = data_to_df(json_data["decoded_records"])

    logger.info(f"Read the following data to DF: {data_df}")

    parsed_data_df = parse_df(raw_data_df=data_df)

    compressed_csv_bytes = create_csv(parsed_data_df)

    upload_to_s3(compressed_bytes=compressed_csv_bytes, bucket_name=TARGET_BUCKET)

    return_response = prepare_response(json_data["original_records"])

    print(return_response)

    return return_response