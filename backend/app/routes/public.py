from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app.models import PublicEventResponse, SearchPhotoResponse, SearchResponse
from app.repository import repo
from app.services.rekognition import search_person_by_selfie
from app.services.s3 import get_photo_object

router = APIRouter(prefix="/public", tags=["public"])


def photo_image_url(request: Request, photo_id: str) -> str:
    return str(request.url_for("get_public_photo_image_route", photo_id=photo_id))


def result_photo_response(request: Request, photo) -> SearchPhotoResponse:
    return SearchPhotoResponse(
        id=photo.id,
        filename=photo.filename,
        url=photo_image_url(request, photo.id),
    )


@router.get("/events/{slug}", response_model=PublicEventResponse)
def get_public_event_route(slug: str) -> PublicEventResponse:
    event = repo.get_event_by_slug(slug)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return PublicEventResponse(
        id=event.id,
        name=event.name,
        slug=event.slug,
        status=event.status,
    )


@router.post("/events/{slug}/search", response_model=SearchResponse)
async def search_event_route(
    request: Request,
    slug: str,
    selfie: UploadFile = File(...),
) -> SearchResponse:
    event = repo.get_event_by_slug(slug)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status != "ready":
        raise HTTPException(status_code=409, detail="Event is not ready for search")

    selfie_bytes = await selfie.read()
    person, similarity = search_person_by_selfie(
        repo,
        event.id,
        event.collection_id,
        selfie.filename or "selfie.jpg",
        selfie_bytes,
    )
    if person is None:
        search = repo.create_client_search(
            event_id=event.id,
            matched_person_id=None,
            similarity=None,
            status="no_match",
        )
        return SearchResponse(id=search.id, status="no_match", similarity=None, photos=[])

    photo_faces = repo.list_photo_faces_for_person(person.id)
    photos = []
    for photo_face in photo_faces:
        photo = repo.get_photo(photo_face.photo_id)
        if photo is None:
            continue
        photos.append(result_photo_response(request, photo))

    search = repo.create_client_search(
        event_id=event.id,
        matched_person_id=person.id,
        similarity=similarity,
        status="completed",
    )
    return SearchResponse(
        id=search.id,
        status="completed",
        similarity=similarity,
        photos=photos,
    )


@router.get("/searches/{search_id}", response_model=SearchResponse)
def get_search_route(request: Request, search_id: str) -> SearchResponse:
    search = repo.get_client_search(search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="Search not found")

    if search.matched_person_id is None:
        return SearchResponse(
            id=search.id,
            status=search.status,
            similarity=search.similarity,
            photos=[],
        )

    photo_faces = repo.list_photo_faces_for_person(search.matched_person_id)
    photos = []
    for photo_face in photo_faces:
        photo = repo.get_photo(photo_face.photo_id)
        if photo is None:
            continue
        photos.append(result_photo_response(request, photo))

    return SearchResponse(
        id=search.id,
        status=search.status,
        similarity=search.similarity,
        photos=photos,
    )


@router.get("/photos/{photo_id}/image", name="get_public_photo_image_route")
def get_public_photo_image_route(photo_id: str) -> Response:
    photo = repo.get_photo(photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Photo not found")

    try:
        data, content_type = get_photo_object(photo.s3_key)
    except Exception as error:
        raise HTTPException(status_code=404, detail=f"Photo image not available: {error}") from error

    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )
