import boto3
import requests

bucket = "wedding-ai-storage-v1"
key = "test-wedding-006/IMG_20180515_211005.jpg"

s3 = boto3.client("s3", region_name="ap-south-1")

# 1️⃣ List keys exactly (with repr to catch hidden characters)
print("Listing objects with repr():")
response = s3.list_objects_v2(
    Bucket=bucket,
    Prefix="test-wedding-006/"
)

for obj in response.get("Contents", []):
    print(repr(obj["Key"]))

print("\nGenerating presigned URL...")

# 2️⃣ Generate presigned URL
url = s3.generate_presigned_url(
    "get_object",
    Params={
        "Bucket": bucket,
        "Key": key
    },
    ExpiresIn=3600
)

print("\nPresigned URL:")
print(url)

print("\nTesting with requests...")

# 3️⃣ Test via requests (no browser involved)
r = requests.get(url)

print("Status Code:", r.status_code)
print("First 300 chars of response:")
print(r.text[:300])
import webbrowser
webbrowser.open(url)

