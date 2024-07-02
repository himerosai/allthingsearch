from minio import Minio
from minio.error import S3Error


def calculate_bucket_size(minio_client, bucket_name):

        
    try:
        # Initialize total size to 0
        total_size = 0
        
        # List all objects in the bucket
        objects = minio_client.list_objects(bucket_name=bucket_name, recursive=True)
        
        # Sum the size of each object
        for obj in objects:
            total_size += obj.size
        

        if total_size is not None:
            print(f"The total size of the bucket '{bucket_name}' is {total_size} bytes.")
        else:
            print("Failed to calculate the bucket size.")

        return total_size
    except S3Error as e:
        print(f"An error occurred: {e}")
        return None

