import logging
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.config import (
    upload_max_batch_files,
    upload_max_file_size_bytes,
    upload_multipart_part_size_bytes,
    upload_multipart_threshold_bytes,
    upload_url_expires_seconds,
)
from app.models import (
    EventPhotoListItem,
    EventPhotoListResponse,
    MultipartUploadPartResponse,
    MultipartUploadPlanDetails,
    MultipartUploadPlanResponse,
    SinglePutUploadPlanResponse,
    UploadCompleteMultipartRequest,
    UploadCompleteSingleRequest,
    UploadCompleteResponse,
    UploadInitFileRequest,
    UploadInitResponse,
    UploadPartsResponse,
)
from app.repository import Repository, new_id
from app.services.s3 import (
    abort_multipart_upload,
    build_photo_s3_key,
    complete_multipart_upload,
    generate_multipart_part_url,
    generate_single_put_upload_url,
    head_photo_object,
    init_multipart_upload,
    multipart_part_count,
)

logger = logging.getLogger(__name__)


class UploadError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def upload_error(status_code: int, code: str, message: str) -> UploadError:
    return UploadError(status_code, code, message)


def choose_upload_mode(size_bytes: int) -> Literal["single_put", "multipart"]:
    if size_bytes < upload_multipart_threshold_bytes():
        return "single_put"
    return "multipart"


def expiration_time() -> str:
    return (datetime.now(UTC) + timedelta(seconds=upload_url_expires_seconds())).isoformat()


def validate_upload_batch(files: list[UploadInitFileRequest]) -> None:
    if len(files) > upload_max_batch_files():
        raise upload_error(413, "batch_too_large", "Too many files in upload batch.")
    for upload_file in files:
        if upload_file.size_bytes > upload_max_file_size_bytes():
            raise upload_error(413, "file_too_large", "One or more files exceed the maximum size.")


def plan_uploads(repo: Repository, event_id: str, files: list[UploadInitFileRequest]) -> UploadInitResponse:
    event = repo.get_event(event_id)
    if event is None:
        raise upload_error(404, "event_not_found", "Event not found.")

    validate_upload_batch(files)
    logger.info("upload_init_requested", extra={"event_id": event_id, "file_count": len(files)})

    uploads: list[SinglePutUploadPlanResponse | MultipartUploadPlanResponse] = []
    expires_in = upload_url_expires_seconds()
    for upload_file in files:
        upload_mode = choose_upload_mode(upload_file.size_bytes)
        photo_id = new_id()
        s3_key = build_photo_s3_key(event_id, photo_id, upload_file.filename)
        photo = repo.create_photo_upload(
            photo_id=photo_id,
            event_id=event_id,
            filename=upload_file.filename,
            s3_key=s3_key,
            content_type=upload_file.content_type,
            size_bytes=upload_file.size_bytes,
            upload_mode=upload_mode,
        )
        if upload_mode == "single_put":
            try:
                upload_url = generate_single_put_upload_url(s3_key, upload_file.content_type, expires_in)
            except Exception as error:
                logger.exception("single_put_upload_init_failed", extra={"event_id": event_id, "s3_key": s3_key})
                repo.mark_photo_upload_failed(photo.id, "s3_presign_failed", str(error))
                raise upload_error(503, "s3_presign_failed", "Could not initialize upload.") from error
            session = repo.create_upload_session(
                photo_id=photo.id,
                event_id=event_id,
                upload_mode="single_put",
                expires_at=expiration_time(),
            )
            uploads.append(
                SinglePutUploadPlanResponse(
                    photo_id=photo.id,
                    filename=photo.filename,
                    content_type=photo.content_type,
                    size_bytes=photo.size_bytes,
                    s3_key=s3_key,
                    status=photo.status,
                    upload_mode="single_put",
                    upload_session_id=session.id,
                    expires_in_seconds=expires_in,
                    upload_url=upload_url,
                )
            )
            logger.info(
                "upload_init_succeeded",
                extra={"event_id": event_id, "photo_id": photo.id, "upload_mode": "single_put", "s3_key": s3_key},
            )
            continue

        try:
            upload_id = init_multipart_upload(s3_key, upload_file.content_type)
        except Exception as error:
            logger.exception("multipart_upload_init_failed", extra={"event_id": event_id, "s3_key": s3_key})
            repo.mark_photo_upload_failed(photo.id, "s3_presign_failed", str(error))
            raise upload_error(503, "s3_presign_failed", "Could not initialize multipart upload.") from error

        part_size = upload_multipart_part_size_bytes()
        part_count = multipart_part_count(upload_file.size_bytes)
        session = repo.create_upload_session(
            photo_id=photo.id,
            event_id=event_id,
            upload_mode="multipart",
            expires_at=expiration_time(),
            s3_multipart_upload_id=upload_id,
            part_size_bytes=part_size,
            part_count=part_count,
        )
        parts = [
            MultipartUploadPartResponse(
                part_number=part_number,
                upload_url=generate_multipart_part_url(
                    s3_key=s3_key,
                    upload_id=upload_id,
                    part_number=part_number,
                    expires_seconds=expires_in,
                ),
            )
            for part_number in range(1, part_count + 1)
        ]
        uploads.append(
            MultipartUploadPlanResponse(
                photo_id=photo.id,
                filename=photo.filename,
                content_type=photo.content_type,
                size_bytes=photo.size_bytes,
                s3_key=s3_key,
                status=photo.status,
                upload_mode="multipart",
                upload_session_id=session.id,
                expires_in_seconds=expires_in,
                multipart=MultipartUploadPlanDetails(
                    upload_id=upload_id,
                    part_size_bytes=part_size,
                    part_count=part_count,
                    parts=parts,
                ),
            )
        )
        logger.info(
            "multipart_upload_initiated",
            extra={
                "event_id": event_id,
                "photo_id": photo.id,
                "upload_session_id": session.id,
                "upload_mode": "multipart",
                "s3_key": s3_key,
                "size_bytes": photo.size_bytes,
            },
        )

    return UploadInitResponse(uploads=uploads)


def generate_part_urls(
    repo: Repository,
    event_id: str,
    photo_id: str,
    part_numbers: list[int],
) -> UploadPartsResponse:
    photo = repo.get_photo_for_event(event_id, photo_id)
    if photo is None:
        raise upload_error(404, "photo_not_found", "Photo not found.")
    if photo.upload_mode != "multipart":
        raise upload_error(409, "invalid_upload_mode", "Photo is not configured for multipart upload.")
    if photo.status not in {"pending_upload", "uploading"}:
        raise upload_error(409, "invalid_upload_state", "Photo upload is not active.")
    if len(set(part_numbers)) != len(part_numbers) or any(part_number < 1 for part_number in part_numbers):
        raise upload_error(422, "invalid_part_numbers", "Part numbers must be unique positive integers.")

    session = repo.get_active_upload_session(photo.id)
    if session is None or session.status != "active" or session.s3_multipart_upload_id is None:
        raise upload_error(409, "upload_session_not_found", "No active multipart upload session found.")
    if session.part_count is not None and any(part_number > session.part_count for part_number in part_numbers):
        raise upload_error(422, "invalid_part_numbers", "Requested part number exceeds the upload part count.")

    if photo.status == "pending_upload":
        repo.mark_photo_uploading(photo.id)

    expires_in = upload_url_expires_seconds()
    parts = [
        MultipartUploadPartResponse(
            part_number=part_number,
            upload_url=generate_multipart_part_url(
                s3_key=photo.s3_key,
                upload_id=session.s3_multipart_upload_id,
                part_number=part_number,
                expires_seconds=expires_in,
            ),
        )
        for part_number in part_numbers
    ]
    logger.info(
        "multipart_part_urls_generated",
        extra={"event_id": event_id, "photo_id": photo.id, "upload_session_id": session.id},
    )
    return UploadPartsResponse(
        photo_id=photo.id,
        upload_session_id=session.id,
        upload_id=session.s3_multipart_upload_id,
        parts=parts,
    )


def complete_photo_upload(
    repo: Repository,
    event_id: str,
    photo_id: str,
    payload: UploadCompleteSingleRequest | UploadCompleteMultipartRequest,
) -> UploadCompleteResponse:
    photo = repo.get_photo_for_event(event_id, photo_id)
    if photo is None:
        raise upload_error(404, "photo_not_found", "Photo not found.")
    if photo.status == "uploaded":
        return UploadCompleteResponse(photo_id=photo.id, status="uploaded")
    if photo.status == "upload_aborted":
        raise upload_error(409, "invalid_upload_state", "Photo upload has already been aborted.")
    if payload.upload_mode != photo.upload_mode:
        raise upload_error(409, "invalid_upload_mode", "Upload mode does not match the photo record.")

    session = repo.get_active_upload_session(photo.id)
    if session is None:
        raise upload_error(409, "upload_session_not_found", "No active upload session found.")
    if session.status != "active":
        if session.status == "completed":
            return UploadCompleteResponse(photo_id=photo.id, status="uploaded")
        raise upload_error(409, "invalid_upload_state", "Upload session is not active.")

    repo.mark_photo_uploading(photo.id)
    logger.info(
        "upload_complete_attempted",
        extra={"event_id": event_id, "photo_id": photo.id, "upload_session_id": session.id, "upload_mode": photo.upload_mode},
    )
    try:
        if payload.upload_mode == "single_put":
            _verify_uploaded_object(photo.s3_key, photo.size_bytes)
        else:
            if session.s3_multipart_upload_id is None or payload.upload_id != session.s3_multipart_upload_id:
                raise upload_error(409, "multipart_upload_mismatch", "Multipart upload ID does not match the active session.")
            parts = sorted(payload.parts, key=lambda item: item.part_number)
            if len({part.part_number for part in parts}) != len(parts):
                raise upload_error(422, "invalid_part_numbers", "Multipart completion parts must be unique.")
            complete_multipart_upload(
                s3_key=photo.s3_key,
                upload_id=payload.upload_id,
                parts=[
                    {"PartNumber": part.part_number, "ETag": part.etag}
                    for part in parts
                ],
            )
            _verify_uploaded_object(photo.s3_key, photo.size_bytes)
    except UploadError:
        raise
    except Exception as error:
        repo.mark_photo_upload_failed(photo.id, "upload_verification_failed", str(error))
        repo.mark_upload_session_failed(session.id)
        logger.exception(
            "upload_complete_failed",
            extra={"event_id": event_id, "photo_id": photo.id, "upload_session_id": session.id},
        )
        raise upload_error(503, "upload_verification_failed", "Upload could not be finalized.") from error

    repo.mark_photo_uploaded(photo.id)
    repo.mark_upload_session_completed(session.id)
    logger.info(
        "upload_complete_succeeded",
        extra={"event_id": event_id, "photo_id": photo.id, "upload_session_id": session.id},
    )
    return UploadCompleteResponse(photo_id=photo.id, status="uploaded")


def abort_photo_upload(repo: Repository, event_id: str, photo_id: str) -> tuple[str, str]:
    photo = repo.get_photo_for_event(event_id, photo_id)
    if photo is None:
        raise upload_error(404, "photo_not_found", "Photo not found.")
    if photo.status == "upload_aborted":
        return photo.id, "upload_aborted"
    if photo.status == "uploaded":
        raise upload_error(409, "invalid_upload_state", "Photo upload is already completed.")

    session = repo.get_active_upload_session(photo.id)
    if session is None:
        raise upload_error(409, "upload_session_not_found", "No active upload session found.")

    try:
        if photo.upload_mode == "multipart" and session.s3_multipart_upload_id is not None:
            abort_multipart_upload(photo.s3_key, session.s3_multipart_upload_id)
    except Exception as error:
        logger.exception(
            "upload_abort_failed",
            extra={"event_id": event_id, "photo_id": photo.id, "upload_session_id": session.id},
        )
        raise upload_error(503, "s3_abort_failed", "Upload could not be aborted.") from error

    repo.mark_photo_upload_aborted(photo.id)
    repo.mark_upload_session_aborted(session.id)
    logger.info(
        "upload_aborted",
        extra={"event_id": event_id, "photo_id": photo.id, "upload_session_id": session.id},
    )
    return photo.id, "upload_aborted"


def list_event_uploads(repo: Repository, event_id: str, limit: int, cursor: str | None) -> EventPhotoListResponse:
    event = repo.get_event(event_id)
    if event is None:
        raise upload_error(404, "event_not_found", "Event not found.")
    items, next_cursor = repo.list_event_photos_paginated(event_id, limit=limit, cursor=cursor)
    return EventPhotoListResponse(
        items=[
            EventPhotoListItem(
                photo_id=item.id,
                filename=item.filename,
                content_type=item.content_type,
                size_bytes=item.size_bytes,
                s3_key=item.s3_key,
                upload_mode=item.upload_mode,  # type: ignore[arg-type]
                status=item.status,  # type: ignore[arg-type]
                upload_started_at=item.upload_started_at,
                uploaded_at=item.uploaded_at,
                created_at=item.created_at,
                upload_error_code=item.upload_error_code,
                upload_error_message=item.upload_error_message,
            )
            for item in items
        ],
        next_cursor=next_cursor,
    )


def _verify_uploaded_object(s3_key: str, expected_size: int) -> None:
    size, _content_type, _etag = head_photo_object(s3_key)
    if size is None:
        return
    if size != expected_size:
        raise upload_error(503, "upload_verification_failed", "Uploaded object size did not match the expected file size.")
