from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from app.config import database_url
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, RowMapping


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return str(uuid4())


def collection_id_for(event_id: str) -> str:
    return f"event_{event_id.replace('-', '')}"


def row_time(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


@dataclass
class EventRecord:
    id: str
    name: str
    slug: str
    collection_id: str
    status: str = "created"
    created_at: str = field(default_factory=utc_now)


@dataclass
class PhotoRecord:
    id: str
    event_id: str
    s3_key: str
    filename: str
    status: str = "pending_upload"
    content_type: str | None = None
    size_bytes: int = 1
    upload_mode: str = "single_put"
    upload_started_at: str | None = None
    uploaded_at: str | None = None
    upload_error_code: str | None = None
    upload_error_message: str | None = None
    created_at: str = field(default_factory=utc_now)


@dataclass
class PhotoUploadSessionRecord:
    id: str
    photo_id: str
    event_id: str
    upload_mode: str
    status: str = "active"
    s3_multipart_upload_id: str | None = None
    part_size_bytes: int | None = None
    part_count: int | None = None
    expires_at: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class PersonRecord:
    id: str
    event_id: str
    face_id: str
    created_at: str = field(default_factory=utc_now)


@dataclass
class PhotoFaceRecord:
    id: str
    event_id: str
    photo_id: str
    person_id: str
    similarity: float
    created_at: str = field(default_factory=utc_now)


@dataclass
class ClientSearchRecord:
    id: str
    event_id: str
    matched_person_id: str | None
    similarity: float | None
    status: str
    created_at: str = field(default_factory=utc_now)


class Repository(Protocol):
    def create_event(self, name: str, slug: str) -> EventRecord: ...
    def get_event(self, event_id: str) -> EventRecord | None: ...
    def get_event_by_slug(self, slug: str) -> EventRecord | None: ...
    def update_event_status(self, event_id: str, status: str) -> EventRecord | None: ...
    def create_photo_upload(
        self,
        photo_id: str,
        event_id: str,
        filename: str,
        s3_key: str,
        content_type: str | None,
        size_bytes: int,
        upload_mode: str,
    ) -> PhotoRecord: ...
    def get_photo(self, photo_id: str) -> PhotoRecord | None: ...
    def get_photo_for_event(self, event_id: str, photo_id: str) -> PhotoRecord | None: ...
    def list_event_photos(self, event_id: str) -> list[PhotoRecord]: ...
    def list_event_photos_paginated(
        self,
        event_id: str,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[PhotoRecord], str | None]: ...
    def create_upload_session(
        self,
        photo_id: str,
        event_id: str,
        upload_mode: str,
        expires_at: str | None,
        s3_multipart_upload_id: str | None = None,
        part_size_bytes: int | None = None,
        part_count: int | None = None,
    ) -> PhotoUploadSessionRecord: ...
    def get_active_upload_session(self, photo_id: str) -> PhotoUploadSessionRecord | None: ...
    def mark_photo_uploading(self, photo_id: str) -> PhotoRecord | None: ...
    def mark_photo_uploaded(self, photo_id: str) -> PhotoRecord | None: ...
    def mark_photo_upload_failed(
        self,
        photo_id: str,
        error_code: str,
        error_message: str | None,
    ) -> PhotoRecord | None: ...
    def mark_photo_upload_aborted(self, photo_id: str) -> PhotoRecord | None: ...
    def mark_upload_session_completed(self, session_id: str) -> PhotoUploadSessionRecord | None: ...
    def mark_upload_session_failed(self, session_id: str) -> PhotoUploadSessionRecord | None: ...
    def mark_upload_session_aborted(self, session_id: str) -> PhotoUploadSessionRecord | None: ...
    def find_person_by_face_id(self, event_id: str, face_id: str) -> PersonRecord | None: ...
    def create_person(self, event_id: str, face_id: str) -> PersonRecord: ...
    def list_event_persons(self, event_id: str) -> list[PersonRecord]: ...
    def create_photo_face(
        self,
        event_id: str,
        photo_id: str,
        person_id: str,
        similarity: float,
    ) -> PhotoFaceRecord | None: ...
    def list_photo_faces_for_person(self, person_id: str) -> list[PhotoFaceRecord]: ...
    def create_client_search(
        self,
        event_id: str,
        matched_person_id: str | None,
        similarity: float | None,
        status: str,
    ) -> ClientSearchRecord: ...
    def get_client_search(self, search_id: str) -> ClientSearchRecord | None: ...


class MemoryRepository:
    def __init__(self) -> None:
        self.events: dict[str, EventRecord] = {}
        self.events_by_slug: dict[str, str] = {}
        self.photos: dict[str, PhotoRecord] = {}
        self.photo_by_event_key: dict[tuple[str, str], str] = {}
        self.upload_sessions: dict[str, PhotoUploadSessionRecord] = {}
        self.active_session_by_photo: dict[str, str] = {}
        self.persons: dict[str, PersonRecord] = {}
        self.person_by_event_face: dict[tuple[str, str], str] = {}
        self.photo_faces: dict[str, PhotoFaceRecord] = {}
        self.photo_face_by_photo_person: set[tuple[str, str]] = set()
        self.client_searches: dict[str, ClientSearchRecord] = {}

    def create_event(self, name: str, slug: str) -> EventRecord:
        event_id = new_id()
        event = EventRecord(
            id=event_id,
            name=name,
            slug=slug,
            collection_id=collection_id_for(event_id),
        )
        self.events[event.id] = event
        self.events_by_slug[event.slug] = event.id
        return event

    def get_event(self, event_id: str) -> EventRecord | None:
        return self.events.get(event_id)

    def get_event_by_slug(self, slug: str) -> EventRecord | None:
        event_id = self.events_by_slug.get(slug)
        if event_id is None:
            return None
        return self.events.get(event_id)

    def update_event_status(self, event_id: str, status: str) -> EventRecord | None:
        event = self.events.get(event_id)
        if event is None:
            return None
        event.status = status
        return event

    def create_photo_upload(
        self,
        photo_id: str,
        event_id: str,
        filename: str,
        s3_key: str,
        content_type: str | None,
        size_bytes: int,
        upload_mode: str,
    ) -> PhotoRecord:
        photo = PhotoRecord(
            id=photo_id,
            event_id=event_id,
            s3_key=s3_key,
            filename=filename,
            status="pending_upload",
            content_type=content_type,
            size_bytes=size_bytes,
            upload_mode=upload_mode,
        )
        self.photos[photo.id] = photo
        self.photo_by_event_key[(event_id, s3_key)] = photo.id
        return photo

    def get_photo(self, photo_id: str) -> PhotoRecord | None:
        return self.photos.get(photo_id)

    def get_photo_for_event(self, event_id: str, photo_id: str) -> PhotoRecord | None:
        photo = self.photos.get(photo_id)
        if photo is None or photo.event_id != event_id:
            return None
        return photo

    def list_event_photos(self, event_id: str) -> list[PhotoRecord]:
        photos = [photo for photo in self.photos.values() if photo.event_id == event_id]
        return sorted(photos, key=lambda photo: (photo.created_at, photo.id))

    def list_event_photos_paginated(
        self,
        event_id: str,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[PhotoRecord], str | None]:
        photos = sorted(
            [photo for photo in self.photos.values() if photo.event_id == event_id],
            key=lambda photo: (photo.created_at, photo.id),
            reverse=True,
        )
        if cursor:
            photos = [photo for photo in photos if f"{photo.created_at}|{photo.id}" < cursor]
        items = photos[: limit + 1]
        next_cursor = None
        if len(items) > limit:
            last = items[limit - 1]
            next_cursor = f"{last.created_at}|{last.id}"
            items = items[:limit]
        return items, next_cursor

    def create_upload_session(
        self,
        photo_id: str,
        event_id: str,
        upload_mode: str,
        expires_at: str | None,
        s3_multipart_upload_id: str | None = None,
        part_size_bytes: int | None = None,
        part_count: int | None = None,
    ) -> PhotoUploadSessionRecord:
        session = PhotoUploadSessionRecord(
            id=new_id(),
            photo_id=photo_id,
            event_id=event_id,
            upload_mode=upload_mode,
            s3_multipart_upload_id=s3_multipart_upload_id,
            part_size_bytes=part_size_bytes,
            part_count=part_count,
            expires_at=expires_at,
        )
        self.upload_sessions[session.id] = session
        self.active_session_by_photo[photo_id] = session.id
        return session

    def get_active_upload_session(self, photo_id: str) -> PhotoUploadSessionRecord | None:
        session_id = self.active_session_by_photo.get(photo_id)
        if session_id is None:
            return None
        session = self.upload_sessions.get(session_id)
        if session is None or session.status != "active":
            return None
        return session

    def mark_photo_uploading(self, photo_id: str) -> PhotoRecord | None:
        photo = self.photos.get(photo_id)
        if photo is None:
            return None
        if photo.upload_started_at is None:
            photo.upload_started_at = utc_now()
        photo.status = "uploading"
        return photo

    def mark_photo_uploaded(self, photo_id: str) -> PhotoRecord | None:
        photo = self.photos.get(photo_id)
        if photo is None:
            return None
        if photo.upload_started_at is None:
            photo.upload_started_at = utc_now()
        photo.status = "uploaded"
        photo.uploaded_at = utc_now()
        photo.upload_error_code = None
        photo.upload_error_message = None
        return photo

    def mark_photo_upload_failed(
        self,
        photo_id: str,
        error_code: str,
        error_message: str | None,
    ) -> PhotoRecord | None:
        photo = self.photos.get(photo_id)
        if photo is None:
            return None
        if photo.upload_started_at is None:
            photo.upload_started_at = utc_now()
        photo.status = "upload_failed"
        photo.upload_error_code = error_code
        photo.upload_error_message = error_message
        return photo

    def mark_photo_upload_aborted(self, photo_id: str) -> PhotoRecord | None:
        photo = self.photos.get(photo_id)
        if photo is None:
            return None
        photo.status = "upload_aborted"
        return photo

    def mark_upload_session_completed(self, session_id: str) -> PhotoUploadSessionRecord | None:
        session = self.upload_sessions.get(session_id)
        if session is None:
            return None
        session.status = "completed"
        session.updated_at = utc_now()
        self.active_session_by_photo.pop(session.photo_id, None)
        return session

    def mark_upload_session_failed(self, session_id: str) -> PhotoUploadSessionRecord | None:
        session = self.upload_sessions.get(session_id)
        if session is None:
            return None
        session.status = "failed"
        session.updated_at = utc_now()
        self.active_session_by_photo.pop(session.photo_id, None)
        return session

    def mark_upload_session_aborted(self, session_id: str) -> PhotoUploadSessionRecord | None:
        session = self.upload_sessions.get(session_id)
        if session is None:
            return None
        session.status = "aborted"
        session.updated_at = utc_now()
        self.active_session_by_photo.pop(session.photo_id, None)
        return session

    def find_person_by_face_id(self, event_id: str, face_id: str) -> PersonRecord | None:
        person_id = self.person_by_event_face.get((event_id, face_id))
        if person_id is None:
            return None
        return self.persons[person_id]

    def create_person(self, event_id: str, face_id: str) -> PersonRecord:
        existing = self.find_person_by_face_id(event_id, face_id)
        if existing is not None:
            return existing
        person = PersonRecord(id=new_id(), event_id=event_id, face_id=face_id)
        self.persons[person.id] = person
        self.person_by_event_face[(event_id, face_id)] = person.id
        return person

    def list_event_persons(self, event_id: str) -> list[PersonRecord]:
        return [person for person in self.persons.values() if person.event_id == event_id]

    def create_photo_face(
        self,
        event_id: str,
        photo_id: str,
        person_id: str,
        similarity: float,
    ) -> PhotoFaceRecord | None:
        key = (photo_id, person_id)
        if key in self.photo_face_by_photo_person:
            return None
        photo_face = PhotoFaceRecord(
            id=new_id(),
            event_id=event_id,
            photo_id=photo_id,
            person_id=person_id,
            similarity=similarity,
        )
        self.photo_faces[photo_face.id] = photo_face
        self.photo_face_by_photo_person.add(key)
        return photo_face

    def list_photo_faces_for_person(self, person_id: str) -> list[PhotoFaceRecord]:
        rows = [row for row in self.photo_faces.values() if row.person_id == person_id]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    def create_client_search(
        self,
        event_id: str,
        matched_person_id: str | None,
        similarity: float | None,
        status: str,
    ) -> ClientSearchRecord:
        search = ClientSearchRecord(
            id=new_id(),
            event_id=event_id,
            matched_person_id=matched_person_id,
            similarity=similarity,
            status=status,
        )
        self.client_searches[search.id] = search
        return search

    def get_client_search(self, search_id: str) -> ClientSearchRecord | None:
        return self.client_searches.get(search_id)


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )

    def create_event(self, name: str, slug: str) -> EventRecord:
        event_id = new_id()
        row = self._one(
            """
            INSERT INTO events (id, name, slug, collection_id, status)
            VALUES (:id, :name, :slug, :collection_id, 'created')
            RETURNING id, name, slug, collection_id, status, created_at
            """,
            {
                "id": event_id,
                "name": name,
                "slug": slug,
                "collection_id": collection_id_for(event_id),
            },
        )
        return event_from_row(row)

    def get_event(self, event_id: str) -> EventRecord | None:
        row = self._maybe_one(
            """
            SELECT id, name, slug, collection_id, status, created_at
            FROM events
            WHERE id = :id
            """,
            {"id": event_id},
        )
        return event_from_row(row) if row else None

    def get_event_by_slug(self, slug: str) -> EventRecord | None:
        row = self._maybe_one(
            """
            SELECT id, name, slug, collection_id, status, created_at
            FROM events
            WHERE slug = :slug
            """,
            {"slug": slug},
        )
        return event_from_row(row) if row else None

    def update_event_status(self, event_id: str, status: str) -> EventRecord | None:
        row = self._maybe_one(
            """
            UPDATE events
            SET status = :status
            WHERE id = :id
            RETURNING id, name, slug, collection_id, status, created_at
            """,
            {"id": event_id, "status": status},
        )
        return event_from_row(row) if row else None

    def create_photo_upload(
        self,
        photo_id: str,
        event_id: str,
        filename: str,
        s3_key: str,
        content_type: str | None,
        size_bytes: int,
        upload_mode: str,
    ) -> PhotoRecord:
        row = self._one(
            """
            INSERT INTO photos (
                id,
                event_id,
                s3_key,
                filename,
                status,
                content_type,
                size_bytes,
                upload_mode
            )
            VALUES (
                :id,
                :event_id,
                :s3_key,
                :filename,
                'pending_upload',
                :content_type,
                :size_bytes,
                :upload_mode
            )
            RETURNING id, event_id, s3_key, filename, status, content_type,
                size_bytes, upload_mode, upload_started_at, uploaded_at,
                upload_error_code, upload_error_message, created_at
            """,
            {
                "id": photo_id,
                "event_id": event_id,
                "s3_key": s3_key,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": size_bytes,
                "upload_mode": upload_mode,
            },
        )
        return photo_from_row(row)

    def get_photo(self, photo_id: str) -> PhotoRecord | None:
        row = self._maybe_one(
            """
            SELECT id, event_id, s3_key, filename, status, content_type,
                size_bytes, upload_mode, upload_started_at, uploaded_at,
                upload_error_code, upload_error_message, created_at
            FROM photos
            WHERE id = :id
            """,
            {"id": photo_id},
        )
        return photo_from_row(row) if row else None

    def get_photo_for_event(self, event_id: str, photo_id: str) -> PhotoRecord | None:
        row = self._maybe_one(
            """
            SELECT id, event_id, s3_key, filename, status, content_type,
                size_bytes, upload_mode, upload_started_at, uploaded_at,
                upload_error_code, upload_error_message, created_at
            FROM photos
            WHERE id = :id AND event_id = :event_id
            """,
            {"id": photo_id, "event_id": event_id},
        )
        return photo_from_row(row) if row else None

    def list_event_photos(self, event_id: str) -> list[PhotoRecord]:
        rows = self._all(
            """
            SELECT id, event_id, s3_key, filename, status, content_type,
                size_bytes, upload_mode, upload_started_at, uploaded_at,
                upload_error_code, upload_error_message, created_at
            FROM photos
            WHERE event_id = :event_id
            ORDER BY created_at
            """,
            {"event_id": event_id},
        )
        return [photo_from_row(row) for row in rows]

    def list_event_photos_paginated(
        self,
        event_id: str,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[PhotoRecord], str | None]:
        params: dict[str, object] = {"event_id": event_id, "limit": limit + 1}
        cursor_sql = ""
        if cursor:
            created_at, photo_id = decode_cursor(cursor)
            params["cursor_created_at"] = created_at
            params["cursor_id"] = photo_id
            cursor_sql = """
                AND (
                    created_at < :cursor_created_at
                    OR (created_at = :cursor_created_at AND id < CAST(:cursor_id AS uuid))
                )
            """
        rows = self._all(
            f"""
            SELECT id, event_id, s3_key, filename, status, content_type,
                size_bytes, upload_mode, upload_started_at, uploaded_at,
                upload_error_code, upload_error_message, created_at
            FROM photos
            WHERE event_id = :event_id
            {cursor_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """,
            params,
        )
        items = [photo_from_row(row) for row in rows]
        next_cursor = None
        if len(items) > limit:
            last = items[limit - 1]
            next_cursor = encode_cursor(last.created_at, last.id)
            items = items[:limit]
        return items, next_cursor

    def create_upload_session(
        self,
        photo_id: str,
        event_id: str,
        upload_mode: str,
        expires_at: str | None,
        s3_multipart_upload_id: str | None = None,
        part_size_bytes: int | None = None,
        part_count: int | None = None,
    ) -> PhotoUploadSessionRecord:
        row = self._one(
            """
            INSERT INTO photo_upload_sessions (
                id,
                photo_id,
                event_id,
                upload_mode,
                s3_multipart_upload_id,
                part_size_bytes,
                part_count,
                status,
                expires_at
            )
            VALUES (
                :id,
                :photo_id,
                :event_id,
                :upload_mode,
                :s3_multipart_upload_id,
                :part_size_bytes,
                :part_count,
                'active',
                :expires_at
            )
            RETURNING id, photo_id, event_id, upload_mode, s3_multipart_upload_id,
                part_size_bytes, part_count, status, expires_at, created_at, updated_at
            """,
            {
                "id": new_id(),
                "photo_id": photo_id,
                "event_id": event_id,
                "upload_mode": upload_mode,
                "s3_multipart_upload_id": s3_multipart_upload_id,
                "part_size_bytes": part_size_bytes,
                "part_count": part_count,
                "expires_at": expires_at,
            },
        )
        return photo_upload_session_from_row(row)

    def get_active_upload_session(self, photo_id: str) -> PhotoUploadSessionRecord | None:
        row = self._maybe_one(
            """
            SELECT id, photo_id, event_id, upload_mode, s3_multipart_upload_id,
                part_size_bytes, part_count, status, expires_at, created_at, updated_at
            FROM photo_upload_sessions
            WHERE photo_id = :photo_id AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"photo_id": photo_id},
        )
        return photo_upload_session_from_row(row) if row else None

    def mark_photo_uploading(self, photo_id: str) -> PhotoRecord | None:
        row = self._maybe_one(
            """
            UPDATE photos
            SET
                status = 'uploading',
                upload_started_at = COALESCE(upload_started_at, now())
            WHERE id = :id
            RETURNING id, event_id, s3_key, filename, status, content_type,
                size_bytes, upload_mode, upload_started_at, uploaded_at,
                upload_error_code, upload_error_message, created_at
            """,
            {"id": photo_id},
        )
        return photo_from_row(row) if row else None

    def mark_photo_uploaded(self, photo_id: str) -> PhotoRecord | None:
        row = self._maybe_one(
            """
            UPDATE photos
            SET
                status = 'uploaded',
                upload_started_at = COALESCE(upload_started_at, now()),
                uploaded_at = now(),
                upload_error_code = NULL,
                upload_error_message = NULL
            WHERE id = :id
            RETURNING id, event_id, s3_key, filename, status, content_type,
                size_bytes, upload_mode, upload_started_at, uploaded_at,
                upload_error_code, upload_error_message, created_at
            """,
            {"id": photo_id},
        )
        return photo_from_row(row) if row else None

    def mark_photo_upload_failed(
        self,
        photo_id: str,
        error_code: str,
        error_message: str | None,
    ) -> PhotoRecord | None:
        row = self._maybe_one(
            """
            UPDATE photos
            SET
                status = 'upload_failed',
                upload_started_at = COALESCE(upload_started_at, now()),
                upload_error_code = :error_code,
                upload_error_message = :error_message
            WHERE id = :id
            RETURNING id, event_id, s3_key, filename, status, content_type,
                size_bytes, upload_mode, upload_started_at, uploaded_at,
                upload_error_code, upload_error_message, created_at
            """,
            {"id": photo_id, "error_code": error_code, "error_message": error_message},
        )
        return photo_from_row(row) if row else None

    def mark_photo_upload_aborted(self, photo_id: str) -> PhotoRecord | None:
        row = self._maybe_one(
            """
            UPDATE photos
            SET status = 'upload_aborted'
            WHERE id = :id
            RETURNING id, event_id, s3_key, filename, status, content_type,
                size_bytes, upload_mode, upload_started_at, uploaded_at,
                upload_error_code, upload_error_message, created_at
            """,
            {"id": photo_id},
        )
        return photo_from_row(row) if row else None

    def mark_upload_session_completed(self, session_id: str) -> PhotoUploadSessionRecord | None:
        return self._mark_upload_session(session_id, "completed")

    def mark_upload_session_failed(self, session_id: str) -> PhotoUploadSessionRecord | None:
        return self._mark_upload_session(session_id, "failed")

    def mark_upload_session_aborted(self, session_id: str) -> PhotoUploadSessionRecord | None:
        return self._mark_upload_session(session_id, "aborted")

    def find_person_by_face_id(self, event_id: str, face_id: str) -> PersonRecord | None:
        row = self._maybe_one(
            """
            SELECT id, event_id, face_id, created_at
            FROM persons
            WHERE event_id = :event_id AND face_id = :face_id
            """,
            {"event_id": event_id, "face_id": face_id},
        )
        return person_from_row(row) if row else None

    def create_person(self, event_id: str, face_id: str) -> PersonRecord:
        row = self._one(
            """
            INSERT INTO persons (id, event_id, face_id)
            VALUES (:id, :event_id, :face_id)
            ON CONFLICT (event_id, face_id)
            DO UPDATE SET face_id = EXCLUDED.face_id
            RETURNING id, event_id, face_id, created_at
            """,
            {"id": new_id(), "event_id": event_id, "face_id": face_id},
        )
        return person_from_row(row)

    def list_event_persons(self, event_id: str) -> list[PersonRecord]:
        rows = self._all(
            """
            SELECT id, event_id, face_id, created_at
            FROM persons
            WHERE event_id = :event_id
            ORDER BY created_at
            """,
            {"event_id": event_id},
        )
        return [person_from_row(row) for row in rows]

    def create_photo_face(
        self,
        event_id: str,
        photo_id: str,
        person_id: str,
        similarity: float,
    ) -> PhotoFaceRecord | None:
        row = self._maybe_one(
            """
            INSERT INTO photo_faces (id, event_id, photo_id, person_id, similarity)
            VALUES (:id, :event_id, :photo_id, :person_id, :similarity)
            ON CONFLICT (photo_id, person_id) DO NOTHING
            RETURNING id, event_id, photo_id, person_id, similarity, created_at
            """,
            {
                "id": new_id(),
                "event_id": event_id,
                "photo_id": photo_id,
                "person_id": person_id,
                "similarity": similarity,
            },
        )
        return photo_face_from_row(row) if row else None

    def list_photo_faces_for_person(self, person_id: str) -> list[PhotoFaceRecord]:
        rows = self._all(
            """
            SELECT id, event_id, photo_id, person_id, similarity, created_at
            FROM photo_faces
            WHERE person_id = :person_id
            ORDER BY created_at DESC
            """,
            {"person_id": person_id},
        )
        return [photo_face_from_row(row) for row in rows]

    def create_client_search(
        self,
        event_id: str,
        matched_person_id: str | None,
        similarity: float | None,
        status: str,
    ) -> ClientSearchRecord:
        row = self._one(
            """
            INSERT INTO client_searches
                (id, event_id, matched_person_id, similarity, status)
            VALUES
                (:id, :event_id, :matched_person_id, :similarity, :status)
            RETURNING id, event_id, matched_person_id, similarity, status, created_at
            """,
            {
                "id": new_id(),
                "event_id": event_id,
                "matched_person_id": matched_person_id,
                "similarity": similarity,
                "status": status,
            },
        )
        return client_search_from_row(row)

    def get_client_search(self, search_id: str) -> ClientSearchRecord | None:
        row = self._maybe_one(
            """
            SELECT id, event_id, matched_person_id, similarity, status, created_at
            FROM client_searches
            WHERE id = :id
            """,
            {"id": search_id},
        )
        return client_search_from_row(row) if row else None

    def _mark_upload_session(self, session_id: str, status: str) -> PhotoUploadSessionRecord | None:
        row = self._maybe_one(
            """
            UPDATE photo_upload_sessions
            SET status = :status, updated_at = now()
            WHERE id = :id
            RETURNING id, photo_id, event_id, upload_mode, s3_multipart_upload_id,
                part_size_bytes, part_count, status, expires_at, created_at, updated_at
            """,
            {"id": session_id, "status": status},
        )
        return photo_upload_session_from_row(row) if row else None

    def _execute(self, sql: str, params: dict[str, object]) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(sql), params)

    def _maybe_one(self, sql: str, params: dict[str, object]) -> RowMapping | None:
        with self.engine.begin() as conn:
            return conn.execute(text(sql), params).mappings().first()

    def _one(self, sql: str, params: dict[str, object]) -> RowMapping:
        row = self._maybe_one(sql, params)
        if row is None:
            raise RuntimeError("Database statement did not return a row")
        return row

    def _all(self, sql: str, params: dict[str, object]) -> list[RowMapping]:
        with self.engine.begin() as conn:
            return list(conn.execute(text(sql), params).mappings().all())


def encode_cursor(created_at: str, photo_id: str) -> str:
    return f"{created_at}|{photo_id}"


def decode_cursor(cursor: str) -> tuple[str, str]:
    created_at, _, photo_id = cursor.partition("|")
    if not created_at or not photo_id:
        raise ValueError("Invalid cursor")
    return created_at, photo_id


def event_from_row(row: RowMapping) -> EventRecord:
    return EventRecord(
        id=str(row["id"]),
        name=str(row["name"]),
        slug=str(row["slug"]),
        collection_id=str(row["collection_id"]),
        status=str(row["status"]),
        created_at=row_time(row["created_at"]),
    )


def photo_from_row(row: RowMapping) -> PhotoRecord:
    return PhotoRecord(
        id=str(row["id"]),
        event_id=str(row["event_id"]),
        s3_key=str(row["s3_key"]),
        filename=str(row["filename"]),
        status=str(row["status"]),
        content_type=str(row["content_type"]) if row["content_type"] is not None else None,
        size_bytes=int(row["size_bytes"]),
        upload_mode=str(row["upload_mode"]),
        upload_started_at=row_time(row["upload_started_at"]) if row["upload_started_at"] is not None else None,
        uploaded_at=row_time(row["uploaded_at"]) if row["uploaded_at"] is not None else None,
        upload_error_code=str(row["upload_error_code"]) if row["upload_error_code"] is not None else None,
        upload_error_message=str(row["upload_error_message"]) if row["upload_error_message"] is not None else None,
        created_at=row_time(row["created_at"]),
    )


def photo_upload_session_from_row(row: RowMapping) -> PhotoUploadSessionRecord:
    return PhotoUploadSessionRecord(
        id=str(row["id"]),
        photo_id=str(row["photo_id"]),
        event_id=str(row["event_id"]),
        upload_mode=str(row["upload_mode"]),
        s3_multipart_upload_id=str(row["s3_multipart_upload_id"]) if row["s3_multipart_upload_id"] is not None else None,
        part_size_bytes=int(row["part_size_bytes"]) if row["part_size_bytes"] is not None else None,
        part_count=int(row["part_count"]) if row["part_count"] is not None else None,
        status=str(row["status"]),
        expires_at=row_time(row["expires_at"]) if row["expires_at"] is not None else None,
        created_at=row_time(row["created_at"]),
        updated_at=row_time(row["updated_at"]),
    )


def person_from_row(row: RowMapping) -> PersonRecord:
    return PersonRecord(
        id=str(row["id"]),
        event_id=str(row["event_id"]),
        face_id=str(row["face_id"]),
        created_at=row_time(row["created_at"]),
    )


def photo_face_from_row(row: RowMapping) -> PhotoFaceRecord:
    return PhotoFaceRecord(
        id=str(row["id"]),
        event_id=str(row["event_id"]),
        photo_id=str(row["photo_id"]),
        person_id=str(row["person_id"]),
        similarity=float(row["similarity"]),
        created_at=row_time(row["created_at"]),
    )


def client_search_from_row(row: RowMapping) -> ClientSearchRecord:
    similarity = row["similarity"]
    return ClientSearchRecord(
        id=str(row["id"]),
        event_id=str(row["event_id"]),
        matched_person_id=str(row["matched_person_id"]) if row["matched_person_id"] else None,
        similarity=float(similarity) if similarity is not None else None,
        status=str(row["status"]),
        created_at=row_time(row["created_at"]),
    )


def build_repository() -> Repository:
    url = database_url()
    if url:
        return PostgresRepository(url)
    return MemoryRepository()


repo = build_repository()
