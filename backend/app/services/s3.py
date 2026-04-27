import math
import os
import re
from pathlib import Path
from urllib.parse import quote

from app.config import upload_multipart_part_size_bytes


def s3_bucket() -> str:
    return os.getenv("AWS_S3_BUCKET", "").strip()


def aws_region() -> str:
    return os.getenv("AWS_REGION", "ap-south-1").strip()


def using_real_s3() -> bool:
    return bool(s3_bucket())


def s3_client():
    import boto3

    return boto3.client("s3", region_name=aws_region())


def sanitize_upload_filename(filename: str) -> str:
    basename = Path(filename.replace("\\", "/")).name.strip()
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", basename).strip("._")
    return sanitized or "upload.bin"


def build_photo_s3_key(event_id: str, photo_id: str, filename: str) -> str:
    safe_filename = sanitize_upload_filename(filename)
    return f"events/{event_id}/originals/{photo_id}/{safe_filename}"


def single_put_part_count(_: int) -> int:
    return 1


def multipart_part_count(size_bytes: int) -> int:
    part_size = upload_multipart_part_size_bytes()
    return max(1, math.ceil(size_bytes / part_size))


def generate_single_put_upload_url(
    s3_key: str,
    content_type: str | None,
    expires_seconds: int,
) -> str:
    bucket = s3_bucket()
    if bucket:
        params = {"Bucket": bucket, "Key": s3_key}
        if content_type:
            params["ContentType"] = content_type
        return s3_client().generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expires_seconds,
        )
    return f"https://mock-s3.local/upload/{quote(s3_key, safe='')}"


def init_multipart_upload(s3_key: str, content_type: str | None) -> str:
    bucket = s3_bucket()
    if not bucket:
        return f"mock-upload-{quote(s3_key, safe='')}"
    params: dict[str, object] = {"Bucket": bucket, "Key": s3_key}
    if content_type:
        params["ContentType"] = content_type
    response = s3_client().create_multipart_upload(**params)
    return str(response["UploadId"])


def generate_multipart_part_url(
    s3_key: str,
    upload_id: str,
    part_number: int,
    expires_seconds: int,
) -> str:
    bucket = s3_bucket()
    if bucket:
        return s3_client().generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": bucket,
                "Key": s3_key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=expires_seconds,
        )
    return f"https://mock-s3.local/upload-part/{quote(s3_key, safe='')}?uploadId={quote(upload_id)}&partNumber={part_number}"


def complete_multipart_upload(
    s3_key: str,
    upload_id: str,
    parts: list[dict[str, object]],
) -> None:
    bucket = s3_bucket()
    if not bucket:
        return
    s3_client().complete_multipart_upload(
        Bucket=bucket,
        Key=s3_key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts},
    )


def abort_multipart_upload(s3_key: str, upload_id: str) -> None:
    bucket = s3_bucket()
    if not bucket:
        return
    s3_client().abort_multipart_upload(
        Bucket=bucket,
        Key=s3_key,
        UploadId=upload_id,
    )


def head_photo_object(s3_key: str) -> tuple[int | None, str | None, str | None]:
    bucket = s3_bucket()
    if not bucket:
        return None, None, None
    response = s3_client().head_object(Bucket=bucket, Key=s3_key)
    size = response.get("ContentLength")
    content_type = response.get("ContentType")
    etag = response.get("ETag")
    return int(size) if size is not None else None, content_type, str(etag) if etag is not None else None


def create_photo_url(s3_key: str) -> str:
    bucket = s3_bucket()
    if bucket:
        return s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": s3_key},
            ExpiresIn=3600,
        )
    return f"https://mock-s3.local/view/{quote(s3_key, safe='')}"


def get_photo_object(s3_key: str) -> tuple[bytes, str]:
    bucket = s3_bucket()
    if not bucket:
        raise FileNotFoundError("S3 bucket is not configured")
    response = s3_client().get_object(Bucket=bucket, Key=s3_key)
    body = response["Body"].read()
    content_type = response.get("ContentType") or "image/jpeg"
    return body, content_type
