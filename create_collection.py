import boto3
import uuid

client = boto3.client('rekognition', region_name='ap-south-1')

wedding_id = str(uuid.uuid4())
collection_id = f"wedding_{wedding_id}"

response = client.create_collection(CollectionId=collection_id)

print("Created collection:", collection_id)
