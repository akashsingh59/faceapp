from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query

from app.models import (
    EventCreateRequest,
    EventDetailResponse,
    EventPhotoListResponse,
    EventResponse,
    ProcessEventResponse,
    UploadAbortResponse,
    UploadCompleteMultipartRequest,
    UploadCompleteResponse,
    UploadCompleteSingleRequest,
    UploadInitRequest,
    UploadInitResponse,
    UploadPartsRequest,
    UploadPartsResponse,
)
from app.repository import repo
from app.services.events import create_event, event_to_detail, event_to_response
from app.services.processing import process_event
from app.services.uploads import (
    UploadError,
    abort_photo_upload,
    complete_photo_upload,
    generate_part_urls,
    list_event_uploads,
    plan_uploads,
)

router = APIRouter(prefix="/events", tags=["events"])


def raise_http_error(error: UploadError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
    )


@router.post("", response_model=EventResponse)
def create_event_route(payload: EventCreateRequest) -> EventResponse:
    event = create_event(repo, payload.name)
    return event_to_response(event)


@router.get("/{event_id}", response_model=EventDetailResponse)
def get_event_route(event_id: str) -> EventDetailResponse:
    event = repo.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event_to_detail(repo, event)


@router.post("/{event_id}/uploads/init", response_model=UploadInitResponse)
def init_uploads_route(event_id: str, payload: UploadInitRequest) -> UploadInitResponse:
    try:
        return plan_uploads(repo, event_id, payload.files)
    except UploadError as error:
        raise_http_error(error)


@router.post("/{event_id}/uploads/{photo_id}/parts", response_model=UploadPartsResponse)
def upload_parts_route(event_id: str, photo_id: str, payload: UploadPartsRequest) -> UploadPartsResponse:
    try:
        return generate_part_urls(repo, event_id, photo_id, payload.part_numbers)
    except UploadError as error:
        raise_http_error(error)


@router.post("/{event_id}/uploads/{photo_id}/complete", response_model=UploadCompleteResponse)
def complete_upload_route(
    event_id: str,
    photo_id: str,
    payload: Annotated[
        UploadCompleteSingleRequest | UploadCompleteMultipartRequest,
        Body(discriminator="upload_mode"),
    ],
) -> UploadCompleteResponse:
    try:
        return complete_photo_upload(repo, event_id, photo_id, payload)
    except UploadError as error:
        raise_http_error(error)


@router.post("/{event_id}/uploads/{photo_id}/abort", response_model=UploadAbortResponse)
def abort_upload_route(event_id: str, photo_id: str) -> UploadAbortResponse:
    try:
        result_photo_id, status = abort_photo_upload(repo, event_id, photo_id)
    except UploadError as error:
        raise_http_error(error)
    return UploadAbortResponse(photo_id=result_photo_id, status=status)


@router.get("/{event_id}/photos", response_model=EventPhotoListResponse)
def list_photos_route(
    event_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> EventPhotoListResponse:
    try:
        return list_event_uploads(repo, event_id, limit=limit, cursor=cursor)
    except UploadError as error:
        raise_http_error(error)


@router.post("/{event_id}/process", response_model=ProcessEventResponse)
def process_event_route(event_id: str) -> ProcessEventResponse:
    event = repo.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    result = process_event(repo, event_id)
    return ProcessEventResponse(
        event_id=event_id,
        status="ready",
        indexed_photos=result["indexed_photos"],
        persons=result["persons"],
        photo_faces=result["photo_faces"],
    )


@router.post("/{event_id}/upload-urls")
def deprecated_upload_urls_route(event_id: str) -> None:
    raise HTTPException(
        status_code=410,
        detail={
            "code": "deprecated_endpoint",
            "message": "Use POST /events/{event_id}/uploads/init instead.",
        },
    )


@router.post("/{event_id}/upload-file")
def deprecated_upload_file_route(event_id: str) -> None:
    raise HTTPException(
        status_code=410,
        detail={
            "code": "deprecated_endpoint",
            "message": "Direct backend file uploads are disabled. Use direct-to-S3 upload init instead.",
        },
    )


@router.post("/{event_id}/photos")
def deprecated_register_photos_route(event_id: str) -> None:
    raise HTTPException(
        status_code=410,
        detail={
            "code": "deprecated_endpoint",
            "message": "Photo registration is handled by POST /events/{event_id}/uploads/init.",
        },
    )
