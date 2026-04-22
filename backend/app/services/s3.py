from urllib.parse import quote
import os


def s3_bucket() -> str:
    return os.getenv("AWS_S3_BUCKET", "").strip()


def aws_region() -> str:
    return os.getenv("AWS_REGION", "ap-south-1").strip()


def using_real_s3() -> bool:
    return bool(s3_bucket())


def s3_client():
    import boto3

    return boto3.client("s3", region_name=aws_region())


def photo_s3_key(event_id: str, filename: str) -> str:
    safe_filename = filename.replace("\\", "/").split("/")[-1]
    return f"events/{event_id}/originals/{safe_filename}"


def create_upload_url(s3_key: str, content_type: str | None = None) -> str:
    bucket = s3_bucket()
    if bucket:
        params = {"Bucket": bucket, "Key": s3_key}
        if content_type:
            params["ContentType"] = content_type
        return s3_client().generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=900,
        )

    return f"https://mock-s3.local/upload/{quote(s3_key, safe='')}"


def create_photo_url(s3_key: str) -> str:
    bucket = s3_bucket()
    if bucket:
        return s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=3600,
        )

    return f"https://mock-s3.local/view/{quote(s3_key, safe='')}"


def upload_photo_bytes(s3_key: str, data: bytes, content_type: str | None = None) -> None:
    bucket = s3_bucket()
    if not bucket:
        return

    params: dict[str, object] = {
        "Bucket": bucket,
        "Key": s3_key,
        "Body": data,
    }
    if content_type:
        params["ContentType"] = content_type

    s3_client().put_object(**params)


def get_photo_object(s3_key: str) -> tuple[bytes, str]:
    bucket = s3_bucket()
    if not bucket:
        raise FileNotFoundError("S3 bucket is not configured")

    response = s3_client().get_object(Bucket=bucket, Key=s3_key)
    body = response["Body"].read()
    content_type = response.get("ContentType") or "image/jpeg"
    return body, content_type
