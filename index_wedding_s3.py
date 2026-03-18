import argparse
import sqlite3

import boto3
from botocore.client import Config


def build_parser():
    parser = argparse.ArgumentParser(
        description="Index one wedding's S3 photos into Rekognition."
    )
    parser.add_argument("--wedding-id", required=True, help="Unique wedding identifier.")
    parser.add_argument(
        "--bucket",
        default="wedding-ai-storage-v1",
        help="S3 bucket containing wedding folders.",
    )
    parser.add_argument(
        "--region",
        default="ap-south-1",
        help="AWS region for S3 and Rekognition.",
    )
    return parser


def main():
    args = build_parser().parse_args()

    s3 = boto3.client(
        "s3",
        region_name=args.region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )
    rekognition = boto3.client("rekognition", region_name=args.region)

    wedding_id = args.wedding_id
    bucket_name = args.bucket
    collection_id = f"wedding_{wedding_id}"
    prefix = f"{wedding_id}/"

    try:
        rekognition.create_collection(CollectionId=collection_id)
    except rekognition.exceptions.ResourceAlreadyExistsException:
        print("Collection already exists. Continuing...")

    conn = sqlite3.connect("wedding.db")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO weddings (wedding_id, collection_id, status)
        VALUES (?, ?, ?)
        ON CONFLICT(wedding_id) DO UPDATE SET
            collection_id = excluded.collection_id,
            status = excluded.status
        """,
        (wedding_id, collection_id, "processing"),
    )
    conn.commit()

    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    objects = response.get("Contents", [])

    print("S3 Objects Found:")
    for obj in objects:
        print(obj["Key"])

    if not objects:
        print("No files found in S3 for this wedding.")
        conn.close()
        raise SystemExit(1)

    for obj in objects:
        s3_key = obj["Key"]
        if s3_key.endswith("/"):
            continue

        filename_only = s3_key.split("/")[-1]

        try:
            response = rekognition.index_faces(
                CollectionId=collection_id,
                Image={"S3Object": {"Bucket": bucket_name, "Name": s3_key}},
                ExternalImageId=filename_only,
                DetectionAttributes=[],
            )

            for face_record in response["FaceRecords"]:
                face_id = face_record["Face"]["FaceId"]
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO faces (face_id, wedding_id, filename)
                    VALUES (?, ?, ?)
                    """,
                    (face_id, wedding_id, s3_key),
                )

            conn.commit()
            print(f"Indexed: {s3_key}")

        except Exception as exc:
            print(f"Error indexing {s3_key}: {exc}")

    cursor.execute(
        "UPDATE weddings SET status=? WHERE wedding_id=?",
        ("ready", wedding_id),
    )
    conn.commit()
    conn.close()

    print("Wedding indexed successfully.")
    print("Wedding ID:", wedding_id)


if __name__ == "__main__":
    main()
