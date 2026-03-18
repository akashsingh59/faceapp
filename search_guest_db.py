import argparse
import sqlite3

import boto3


def build_parser():
    parser = argparse.ArgumentParser(
        description="Search a wedding collection by guest selfie."
    )
    parser.add_argument("--wedding-id", required=True, help="Wedding to search.")
    parser.add_argument(
        "--selfie",
        default="selfie.jpg",
        help="Path to the guest selfie image.",
    )
    parser.add_argument(
        "--bucket",
        default="wedding-ai-storage-v1",
        help="S3 bucket containing wedding photos.",
    )
    parser.add_argument(
        "--region",
        default="ap-south-1",
        help="AWS region for S3 and Rekognition.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=70,
        help="Face match threshold for Rekognition.",
    )
    parser.add_argument(
        "--max-faces",
        type=int,
        default=50,
        help="Maximum number of matches returned by Rekognition.",
    )
    return parser


def main():
    args = build_parser().parse_args()

    conn = sqlite3.connect("wedding.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT collection_id FROM weddings WHERE wedding_id=?",
        (args.wedding_id,),
    )
    result = cursor.fetchone()

    if not result:
        print("Wedding not found.")
        conn.close()
        raise SystemExit(1)

    collection_id = result[0]
    rekognition = boto3.client("rekognition", region_name=args.region)
    s3 = boto3.client("s3", region_name=args.region)

    with open(args.selfie, "rb") as file_obj:
        selfie_bytes = file_obj.read()

    response = rekognition.search_faces_by_image(
        CollectionId=collection_id,
        Image={"Bytes": selfie_bytes},
        FaceMatchThreshold=args.threshold,
        MaxFaces=args.max_faces,
    )

    matched_filenames = set()
    for match in response.get("FaceMatches", []):
        face_id = match["Face"]["FaceId"]
        cursor.execute("SELECT filename FROM faces WHERE face_id=?", (face_id,))
        row = cursor.fetchone()
        if row:
            matched_filenames.add(row[0])

    conn.close()

    if not matched_filenames:
        print("No matching photos found.")
        return

    print("\nMatched photo URLs:\n")
    for filename in sorted(matched_filenames):
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": args.bucket, "Key": filename},
            ExpiresIn=3600,
        )
        print(url)


if __name__ == "__main__":
    main()

