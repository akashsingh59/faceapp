import logging
import threading
import time
from queue import Empty, Queue

from app.repository import Repository
from app.services.rekognition import (
    ensure_collection,
    find_or_create_person_for_face,
    index_photo_faces,
)

logger = logging.getLogger(__name__)

_EVENT_QUEUE: Queue[tuple[Repository, str, int]] = Queue()
_PROCESSING_WORKER: threading.Thread | None = None
_PROCESSING_WORKER_LOCK = threading.Lock()


def _processing_worker_loop() -> None:
    while True:
        try:
            repo, event_id, retries = _EVENT_QUEUE.get(timeout=1)
        except Empty:
            continue

        try:
            process_event(repo, event_id, retries=retries)
        except Exception:
            logger.exception("background_event_processing_failed", extra={"event_id": event_id})
        finally:
            _EVENT_QUEUE.task_done()


def start_processing_worker() -> None:
    global _PROCESSING_WORKER

    with _PROCESSING_WORKER_LOCK:
        if _PROCESSING_WORKER is not None and _PROCESSING_WORKER.is_alive():
            return

        _PROCESSING_WORKER = threading.Thread(
            name="faceapp-processing-worker",
            target=_processing_worker_loop,
            daemon=True,
        )
        _PROCESSING_WORKER.start()


def enqueue_event_processing(repo: Repository, event_id: str, retries: int = 3) -> dict[str, int | str]:
    event = repo.get_event(event_id)
    if event is None:
        return {"event_id": event_id, "status": "not_found", "indexed_photos": 0, "persons": 0, "photo_faces": 0}

    if event.status in {"processing", "queued"}:
        return {"event_id": event_id, "status": event.status, "indexed_photos": 0, "persons": 0, "photo_faces": 0}

    repo.update_event_status(event_id, "queued")
    start_processing_worker()
    _EVENT_QUEUE.put((repo, event_id, retries))

    return {"event_id": event_id, "status": "queued", "indexed_photos": 0, "persons": 0, "photo_faces": 0}


def process_event(repo: Repository, event_id: str, retries: int = 3) -> dict[str, int]:
    event = repo.get_event(event_id)
    if event is None:
        return {"indexed_photos": 0, "persons": 0, "photo_faces": 0}

    for attempt in range(1, retries + 1):
        try:
            repo.update_event_status(event_id, "processing")
            ensure_collection(event.collection_id)

            indexed_photos = 0
            created_photo_faces = 0
            for photo in repo.list_event_photos(event_id):
                if photo.status != "uploaded":
                    continue

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
                indexed_photos += 1

            repo.update_event_status(event_id, "ready")

            return {
                "indexed_photos": indexed_photos,
                "persons": len(repo.list_event_persons(event_id)),
                "photo_faces": created_photo_faces,
            }
        except Exception:
            logger.exception(
                "event_processing_failed",
                extra={"event_id": event_id, "attempt": attempt, "retries": retries},
            )
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 10))
                continue

            repo.update_event_status(event_id, "processing_failed")
            raise
