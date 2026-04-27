from typing import Literal

from pydantic import BaseModel, Field


UploadMode = Literal["single_put", "multipart"]
PhotoUploadStatus = Literal[
    "pending_upload",
    "uploading",
    "uploaded",
    "upload_failed",
    "upload_aborted",
]


class EventCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class EventResponse(BaseModel):
    id: str
    name: str
    slug: str
    collection_id: str
    status: str
    share_url: str


class EventDetailResponse(EventResponse):
    photo_count: int
    person_count: int


class ProcessEventResponse(BaseModel):
    event_id: str
    status: str
    indexed_photos: int
    persons: int
    photo_faces: int


class UploadInitFileRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    content_type: str | None = Field(default=None, max_length=255)


class UploadInitRequest(BaseModel):
    files: list[UploadInitFileRequest] = Field(min_length=1)


class MultipartUploadPartResponse(BaseModel):
    part_number: int
    upload_url: str


class MultipartUploadPlanDetails(BaseModel):
    upload_id: str
    part_size_bytes: int
    part_count: int
    parts: list[MultipartUploadPartResponse]


class SinglePutUploadPlanResponse(BaseModel):
    photo_id: str
    filename: str
    content_type: str | None
    size_bytes: int
    s3_key: str
    status: PhotoUploadStatus
    upload_mode: Literal["single_put"]
    upload_session_id: str
    expires_in_seconds: int
    upload_url: str


class MultipartUploadPlanResponse(BaseModel):
    photo_id: str
    filename: str
    content_type: str | None
    size_bytes: int
    s3_key: str
    status: PhotoUploadStatus
    upload_mode: Literal["multipart"]
    upload_session_id: str
    expires_in_seconds: int
    multipart: MultipartUploadPlanDetails


class UploadInitResponse(BaseModel):
    uploads: list[SinglePutUploadPlanResponse | MultipartUploadPlanResponse]


class UploadPartsRequest(BaseModel):
    part_numbers: list[int] = Field(min_length=1)


class UploadPartsResponse(BaseModel):
    photo_id: str
    upload_session_id: str
    upload_id: str
    parts: list[MultipartUploadPartResponse]


class UploadCompleteMultipartPartRequest(BaseModel):
    part_number: int = Field(ge=1)
    etag: str = Field(min_length=1)


class UploadCompleteSingleRequest(BaseModel):
    upload_mode: Literal["single_put"]


class UploadCompleteMultipartRequest(BaseModel):
    upload_mode: Literal["multipart"]
    upload_id: str = Field(min_length=1)
    parts: list[UploadCompleteMultipartPartRequest] = Field(min_length=1)


class UploadCompleteResponse(BaseModel):
    photo_id: str
    status: Literal["uploaded"]


class UploadAbortResponse(BaseModel):
    photo_id: str
    status: Literal["upload_aborted"]


class EventPhotoListItem(BaseModel):
    photo_id: str
    filename: str
    content_type: str | None
    size_bytes: int
    s3_key: str
    upload_mode: UploadMode
    status: PhotoUploadStatus
    upload_started_at: str | None
    uploaded_at: str | None
    created_at: str
    upload_error_code: str | None
    upload_error_message: str | None


class EventPhotoListResponse(BaseModel):
    items: list[EventPhotoListItem]
    next_cursor: str | None


class PublicEventResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: str


class SearchPhotoResponse(BaseModel):
    id: str
    filename: str
    url: str


class SearchResponse(BaseModel):
    id: str
    status: str
    similarity: float | None
    photos: list[SearchPhotoResponse]
