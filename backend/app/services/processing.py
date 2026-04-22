from app.repository import Repository
from app.services.rekognition import (
    ensure_collection,
    find_or_create_person_for_face,
    index_photo_faces,
)


def process_event(repo: Repository, event_id: str) -> dict[str, int]:
    event = repo.get_event(event_id)
    if event is None:
        return {"indexed_photos": 0, "persons": 0, "photo_faces": 0}

    repo.update_event_status(event_id, "processing")
    ensure_collection(event.collection_id)

    indexed_photos = 0
    created_photo_faces = 0
    for photo in repo.list_event_photos(event_id):
        indexed_faces = index_photo_faces(
            collection_id=event.collection_id,
            s3_key=photo.s3_key,
            filename=photo.filename,
        )
        for indexed_face in indexed_faces:
            person, _was_created, similarity = find_or_create_person_for_face(
                repo=repo,
                event_id=event_id,
                collection_id=event.collection_id,
                face_id=indexed_face.face_id,
            )
            photo_face = repo.create_photo_face(
                event_id=event_id,
                photo_id=photo.id,
                person_id=person.id,
                similarity=similarity,
            )
            if photo_face is not None:
                created_photo_faces += 1
        repo.mark_photo_indexed(photo.id)
        indexed_photos += 1

    repo.update_event_status(event_id, "ready")

    return {
        "indexed_photos": indexed_photos,
        "persons": len(repo.list_event_persons(event_id)),
        "photo_faces": created_photo_faces,
    }
