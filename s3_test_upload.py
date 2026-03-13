import boto3

s3 = boto3.client('s3', region_name='ap-south-1')

bucket_name = "wedding-ai-storage-v1"
file_path = "wedding_photos/image1.jpg"
s3_key = "test/image1.jpg"

s3.upload_file(file_path, bucket_name, s3_key)

print("Upload successful.")
