import os
from dataclasses import dataclass
from pathlib import Path

from app.repository import PersonRecord, Repository
from app.services.s3 import s3_bucket


@dataclass
class IndexedFace:
    face_id: str
    similarity: float


def using_real_rekognition() -> bool:
    return os.getenv("AWS_REKOGNITION_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def face_id_from_photo_filename(filename: str) -> str:
    stem = Path(filename).stem.lower()
    person_hint = stem.split("_")[0].split("-")[0]
    return f"face_{person_hint or stem}"


def face_id_from_selfie(filename: str) -> str:
    return face_id_from_photo_filename(filename)


def rekognition_client():
    import boto3

    return boto3.client("rekognition")


def ensure_collection(collection_id: str) -> None:
    if not using_real_rekognition():
        return

    from botocore.exceptions import ClientError

    try:
        rekognition_client().create_collection(CollectionId=collection_id)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code != "ResourceAlreadyExistsException":
            raise


def index_photo_faces(collection_id: str, s3_key: str, filename: str) -> list[IndexedFace]:
    if not using_real_rekognition():
        return [IndexedFace(face_id=face_id_from_photo_filename(filename), similarity=99.0)]

    response = rekognition_client().index_faces(
        CollectionId=collection_id,
        Image={"S3Object": {"Bucket": s3_bucket(), "Name": s3_key}},
        MaxFaces=50,
        QualityFilter="AUTO",
    )

    faces: list[IndexedFace] = []
    for record in response.get("FaceRecords", []):
        face = record.get("Face", {})
        face_id = face.get("FaceId")
        if face_id:
            faces.append(IndexedFace(face_id=face_id, similarity=100.0))
    return faces


def find_existing_person_for_indexed_face(
    repo: Repository,
    event_id: str,
    collection_id: str,
    face_id: str,
) -> tuple[PersonRecord | None, float | None]:
    direct = repo.find_person_by_face_id(event_id, face_id)
    if direct is not None:
        return direct, 100.0

    if not using_real_rekognition():
        return None, None

    response = rekognition_client().search_faces(
        CollectionId=collection_id,
        FaceId=face_id,
        FaceMatchThreshold=90,
        MaxFaces=10,
    )
    for match in response.get("FaceMatches", []):
        match_face_id = match.get("Face", {}).get("FaceId")
        if not match_face_id or match_face_id == face_id:
            continue

        person = repo.find_person_by_face_id(event_id, match_face_id)
        if person is not None:
            return person, float(match.get("Similarity", 0))

    return None, None


def find_or_create_person_for_face(
    repo: Repository,
    event_id: str,
    collection_id: str,
    face_id: str,
) -> tuple[PersonRecord, bool, float]:
    existing, similarity = find_existing_person_for_indexed_face(
        repo=repo,
        event_id=event_id,
        collection_id=collection_id,
        face_id=face_id,
    )
    if existing is not None:
        return existing, False, similarity or 100.0

    return repo.create_person(event_id=event_id, face_id=face_id), True, 100.0


def search_person_by_selfie(
    repo: Repository,
    event_id: str,
    collection_id: str,
    selfie_filename: str,
    selfie_bytes: bytes | None = None,
) -> tuple[PersonRecord | None, float | None]:
    if not using_real_rekognition():
        face_id = face_id_from_selfie(selfie_filename)
        person = repo.find_person_by_face_id(event_id, face_id)
        if person is None:
            return None, None
        return person, 98.5

    if selfie_bytes is None:
        return None, None

    response = rekognition_client().search_faces_by_image(
        CollectionId=collection_id,
        Image={"Bytes": selfie_bytes},
        FaceMatchThreshold=90,
        MaxFaces=10,
    )
    for match in response.get("FaceMatches", []):
        face_id = match.get("Face", {}).get("FaceId")
        if not face_id:
            continue

        person = repo.find_person_by_face_id(event_id, face_id)
        if person is not None:
            return person, float(match.get("Similarity", 0))

        person, resolved_similarity = find_existing_person_for_indexed_face(
            repo=repo,
            event_id=event_id,
            collection_id=collection_id,
            face_id=face_id,
        )
        if person is not None:
            return person, resolved_similarity or float(match.get("Similarity", 0))

    return None, None
