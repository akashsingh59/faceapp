import boto3
import os
from PIL import Image
import io

client = boto3.client('rekognition', region_name='ap-south-1')

collection_id = "wedding-test"
folder_path = "wedding_photos"

for filename in os.listdir(folder_path):
    image_path = os.path.join(folder_path, filename)

    try:
        # Open image
        img = Image.open(image_path)

        # Resize (max width 1280px)
        img.thumbnail((1280, 1280))

        # Convert to bytes
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
            print(f"Indexed face in {filename} with FaceId {face_id}")

    except Exception as e:
        print(f"Error indexing {filename}: {e}")

print("Indexing complete.")
