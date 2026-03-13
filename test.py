import boto3

client = boto3.client('rekognition', region_name='ap-south-1')

with open('image1.jpg', 'rb') as source_file:
    source_bytes = source_file.read()

with open('image2.jpg', 'rb') as target_file:
    target_bytes = target_file.read()

response = client.compare_faces(
    SourceImage={'Bytes': source_bytes},
    TargetImage={'Bytes': target_bytes},
    SimilarityThreshold=80
)

if response['FaceMatches']:
    similarity = response['FaceMatches'][0]['Similarity']
    print(f"Match found with similarity: {similarity}%")
else:
    print("No match found")
