import boto3

client = boto3.client('rekognition', region_name='ap-south-1')

collection_id = "wedding-test"

with open('selfie.jpg', 'rb') as f:
    selfie_bytes = f.read()

response = client.search_faces_by_image(
    CollectionId=collection_id,
    Image={'Bytes': selfie_bytes},
    FaceMatchThreshold=80,
    MaxFaces=50
)

print("Matches found:")

for match in response['FaceMatches']:
    print(f"FaceId: {match['Face']['FaceId']}, Similarity: {match['Similarity']}")
