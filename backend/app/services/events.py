from app.models import EventDetailResponse, EventResponse
from app.repository import EventRecord, Repository
from app.services.slugs import make_slug


def build_share_url(slug: str) -> str:
    return f"/s/{slug}"


def event_to_response(event: EventRecord) -> EventResponse:
    return EventResponse(
        id=event.id,
        name=event.name,
        slug=event.slug,
        collection_id=event.collection_id,
        status=event.status,
        share_url=build_share_url(event.slug),
    )


def event_to_detail(repo: Repository, event: EventRecord) -> EventDetailResponse:
    photos = repo.list_event_photos(event.id)
    persons = repo.list_event_persons(event.id)
    return EventDetailResponse(
        **event_to_response(event).model_dump(),
        photo_count=len(photos),
        person_count=len(persons),
    )


def create_event(repo: Repository, name: str) -> EventRecord:
    return repo.create_event(name=name, slug=make_slug(name))
