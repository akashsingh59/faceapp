from pydantic import BaseModel, Field


class EventCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class EventResponse(BaseModel):
    id: str
    name: str
    slug: str
    collection_id: str
    status: str
    share_url: str


class UploadFileRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = None


class UploadUrlsRequest(BaseModel):
    files: list[UploadFileRequest]


class UploadUrlResponseItem(BaseModel):
    filename: str
    s3_key: str
    upload_url: str
    upload_required: bool


class UploadUrlsResponse(BaseModel):
    uploads: list[UploadUrlResponseItem]


class PhotoRegisterRequestItem(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    s3_key: str = Field(min_length=1)


class RegisterPhotosRequest(BaseModel):
    photos: list[PhotoRegisterRequestItem]


class PhotoResponse(BaseModel):
    id: str
    filename: str
    s3_key: str
    status: str
    created_at: str


class RegisterPhotosResponse(BaseModel):
    created: int
    photos: list[PhotoResponse]


class EventDetailResponse(EventResponse):
    photo_count: int
    person_count: int


class ProcessEventResponse(BaseModel):
    event_id: str
    status: str
    indexed_photos: int
    persons: int
    photo_faces: int


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
