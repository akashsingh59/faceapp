# Rekognition Wedding Search

Small AWS Rekognition prototype for indexing wedding photos and finding matching guest photos from a selfie.

## Main workflow

1. Initialize SQLite metadata tables.
2. Upload wedding photos to S3 under a wedding-specific prefix.
3. Index those S3 photos into a Rekognition collection.
4. Search that collection with a guest selfie.
5. Turn face matches into presigned S3 photo URLs.

## Kept files

- `db.py`: creates SQLite tables.
- `init_db.py`: initializes the local database.
- `index_wedding_s3.py`: indexes one wedding from S3 into Rekognition and stores face mappings in SQLite.
- `search_guest_db.py`: searches a wedding collection and prints matching photo URLs.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Make sure AWS credentials are available in your environment and that Rekognition/S3 access is configured for `ap-south-1`.

## Initialize DB

```powershell
python init_db.py
```

## Index a wedding

```powershell
python index_wedding_s3.py --wedding-id test-wedding-006 --bucket wedding-ai-storage-v1
```

This expects wedding photos to exist in S3 under:

```text
test-wedding-006/
```

## Search for a guest

```powershell
python search_guest_db.py --wedding-id test-wedding-006 --selfie selfie.jpg --bucket wedding-ai-storage-v1
```

## Notes

- Each wedding gets its own Rekognition collection: `wedding_<wedding_id>`.
- SQLite stores the mapping between Rekognition `face_id` values and the original S3 object keys.
- The scripts are designed for a prototype, not production hardening yet.
