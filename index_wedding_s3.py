import boto3
import uuid
import sqlite3

from botocore.client import Config
import boto3

s3 = boto3.client(
    "s3",
    region_name="ap-south-1",
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"}
    )
)





rekognition = boto3.client('rekognition', region_name='ap-south-1')

bucket_name = "wedding-ai-storage-v1"

# Generate wedding ID

wedding_id ="test-wedding-006"
collection_id = f"wedding_{wedding_id}"

# Create collection

try:
    rekognition.create_collection(CollectionId=collection_id)
except rekognition.exceptions.ResourceAlreadyExistsException:
    print("Collection already exists. Continuing...")


# Save wedding in DB
conn = sqlite3.connect("wedding.db")
cursor = conn.cursor()
cursor.execute(
    "INSERT INTO weddings (wedding_id, collection_id, status) VALUES (?, ?, ?)",
    (wedding_id, collection_id, "processing")
)
conn.commit()

# List objects in wedding folder
response = s3.list_objects_v2(
    Bucket=bucket_name,
    Prefix="test-wedding-006/"
)
print("S3 Objects Found:")
for obj in response.get('Contents', []):
    print(obj['Key'])

if 'Contents' not in response:
    print("No files found in S3 for this wedding.")
    exit()

for obj in response['Contents']:
    s3_key = obj['Key']

    if s3_key.endswith("/"):
        continue

    filename_only = s3_key.split("/")[-1]

    try:
        response = rekognition.index_faces(
            CollectionId=collection_id,
            Image={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': s3_key
                }
            },
            ExternalImageId=filename_only,
            DetectionAttributes=[]
        )

        for face_record in response['FaceRecords']:
            face_id = face_record['Face']['FaceId']

            cursor.execute(
                "INSERT INTO faces (face_id, wedding_id, filename) VALUES (?, ?, ?)",
                (face_id, wedding_id, s3_key)
            )

        conn.commit()

        print(f"Indexed: {s3_key}")

    except Exception as e:
        print(f"Error indexing {s3_key}: {e}")

# Update status
cursor.execute(
    "UPDATE weddings SET status=? WHERE wedding_id=?",
    ("ready", wedding_id)
)
conn.commit()
conn.close()

print("Wedding indexed successfully.")
print("Wedding ID:", wedding_id)
