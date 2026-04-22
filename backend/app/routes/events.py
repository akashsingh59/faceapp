from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models import (
    EventCreateRequest,
    EventDetailResponse,
    EventResponse,
    PhotoResponse,
    ProcessEventResponse,
    RegisterPhotosRequest,
    RegisterPhotosResponse,
    UploadUrlsRequest,
    UploadUrlsResponse,
    UploadUrlResponseItem,
)
from app.repository import repo
from app.services.events import create_event, event_to_detail, event_to_response
from app.services.processing import process_event
from app.services.s3 import create_upload_url, photo_s3_key, upload_photo_bytes, using_real_s3

router = APIRouter(prefix="/events", tags=["events"])


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


@router.post("/{event_id}/upload-urls", response_model=UploadUrlsResponse)
def create_upload_urls_route(event_id: str, payload: UploadUrlsRequest) -> UploadUrlsResponse:
    event = repo.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    uploads = []
    for file in payload.files:
        s3_key = photo_s3_key(event_id, file.filename)
        uploads.append(
            UploadUrlResponseItem(
                filename=file.filename,
                s3_key=s3_key,
                upload_url=create_upload_url(s3_key, file.content_type),
                upload_required=using_real_s3(),
            )
        )
    return UploadUrlsResponse(uploads=uploads)


@router.post("/{event_id}/upload-file")
async def upload_file_route(
    event_id: str,
    s3_key: str = Form(...),
    file: UploadFile = File(...),
) -> dict[str, str]:
    event = repo.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    expected_prefix = f"events/{event_id}/originals/"
    if not s3_key.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail="Invalid S3 key for event")

    upload_photo_bytes(
        s3_key=s3_key,
        data=await file.read(),
        content_type=file.content_type,
    )
    return {"status": "uploaded", "s3_key": s3_key}


@router.post("/{event_id}/photos", response_model=RegisterPhotosResponse)
def register_photos_route(event_id: str, payload: RegisterPhotosRequest) -> RegisterPhotosResponse:
    event = repo.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    photos = [
        repo.create_or_get_photo(
            event_id=event_id,
            filename=photo.filename,
            s3_key=photo.s3_key,
        )
        for photo in payload.photos
    ]

    return RegisterPhotosResponse(
        created=len(photos),
        photos=[
            PhotoResponse(
                id=photo.id,
                filename=photo.filename,
                s3_key=photo.s3_key,
                status=photo.status,
                created_at=photo.created_at,
            )
            for photo in photos
        ],
    )


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


@router.get("/{event_id}/photos", response_model=list[PhotoResponse])
def list_photos_route(event_id: str) -> list[PhotoResponse]:
    event = repo.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return [
        PhotoResponse(
            id=photo.id,
            filename=photo.filename,
            s3_key=photo.s3_key,
            status=photo.status,
            created_at=photo.created_at,
        )
        for photo in repo.list_event_photos(event_id)
    ]
