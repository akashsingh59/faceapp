import boto3
import os
import time
from botocore.exceptions import ClientError, ConnectionClosedError

client = boto3.client('rekognition', region_name='ap-south-1')

with open('selfie.jpg', 'rb') as f:
    selfie_bytes = f.read()

folder_path = 'wedding_photos'

for filename in os.listdir(folder_path):
    image_path = os.path.join(folder_path, filename)

    try:
        with open(image_path, 'rb') as img:
            image_bytes = img.read()

        response = client.compare_faces(
            SourceImage={'Bytes': selfie_bytes},
            TargetImage={'Bytes': image_bytes},
            SimilarityThreshold=80
        )

        if response['FaceMatches']:
            similarity = response['FaceMatches'][0]['Similarity']
            print(f"Match found in {filename} with similarity {similarity:.2f}%")

        time.sleep(0.5)  # small delay to avoid rapid-fire calls

    except Exception as e:
        print(f"Error processing {filename}: {e}")
        continue

