import boto3
import sqlite3

# ---- CONFIG ----
wedding_id = "test-wedding-006"  # change if needed
bucket_name = "wedding-ai-storage-v1"
# ----------------

# Connect to DB
conn = sqlite3.connect("wedding.db")
cursor = conn.cursor()

# Get collection_id
cursor.execute(
    "SELECT collection_id FROM weddings WHERE wedding_id=?",
    (wedding_id,)
)
result = cursor.fetchone()

if not result:
    print("Wedding not found.")
    conn.close()
    exit()

collection_id = result[0]

rekognition = boto3.client('rekognition', region_name='ap-south-1')
s3 = boto3.client('s3', region_name='ap-south-1')

# Load selfie
with open('selfie.jpg', 'rb') as f:
    selfie_bytes = f.read()

response = rekognition.search_faces_by_image(
    CollectionId=collection_id,
    Image={'Bytes': selfie_bytes},
    FaceMatchThreshold=70,
    MaxFaces=50
)
print(response)

matched_filenames = set()

for match in response['FaceMatches']:
    face_id = match['Face']['FaceId']

    cursor.execute(
        "SELECT filename FROM faces WHERE face_id=?",
        (face_id,)
    )

    row = cursor.fetchone()
    if row:
        matched_filenames.add(row[0])

conn.close()

matched_urls = []

for filename in matched_filenames:
    url = s3.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': bucket_name,
            'Key': filename
        },
        ExpiresIn=3600
    )
    url = url.replace(
    f"{bucket_name}.s3.amazonaws.com",
    f"{bucket_name}.s3.ap-south-1.amazonaws.com"
    )
    matched_urls.append(url)

print("\nMatched photo URLs:\n")

for url in matched_urls:
    print(url)

import webbrowser
webbrowser.open(url)

