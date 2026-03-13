import boto3
import os
import uuid
import sqlite3
from PIL import Image
import io

client = boto3.client('rekognition', region_name='ap-south-1')

# Generate wedding ID
wedding_id = str(uuid.uuid4())
collection_id = f"wedding_{wedding_id}"

# Create collection
client.create_collection(CollectionId=collection_id)

# Save wedding in DB
conn = sqlite3.connect("wedding.db")
cursor = conn.cursor()
cursor.execute(
    "INSERT INTO weddings (wedding_id, collection_id, status) VALUES (?, ?, ?)",
    (wedding_id, collection_id, "processing")
)
conn.commit()

folder_path = "wedding_photos"

for filename in os.listdir(folder_path):
    image_path = os.path.join(folder_path, filename)

    try:
        img = Image.open(image_path)
        img.thumbnail((1280, 1280))

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        image_bytes = buffer.getvalue()

        response = client.index_faces(
            CollectionId=collection_id,
            Image={'Bytes': image_bytes},
            ExternalImageId=filename,
            DetectionAttributes=[]
        )

        for face_record in response['FaceRecords']:
            face_id = face_record['Face']['FaceId']

            cursor.execute(
                "INSERT INTO faces (face_id, wedding_id, filename) VALUES (?, ?, ?)",
                (face_id, wedding_id, filename)
            )

        conn.commit()

    except Exception as e:
        print(f"Error indexing {filename}: {e}")

# Update status
cursor.execute(
    "UPDATE weddings SET status=? WHERE wedding_id=?",
    ("ready", wedding_id)
)
conn.commit()

conn.close()

print("Wedding indexed successfully.")
print("Wedding ID:", wedding_id)
