from google.cloud import storage

class Bucket:

    def __init__(self, bucket_name):
        self.storage_client = storage.Client()
        self.bucket_name = bucket_name

    def upload_blob(self, source_file_name, destination_blob_name):
        """Uploads a file to the bucket."""
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        print(f"File {source_file_name} uploaded to {destination_blob_name}.")
        return blob

    # Example:
    # upload_blob("my-globally-unique-bucket-name", "local_file.txt", "cloud_file.txt")
    def download_blob(self, source_blob_name, destination_file_name):
        """Downloads a blob from the bucket."""
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(source_blob_name)
        blob.download_to_filename(destination_file_name)
        print(f"Blob {source_blob_name} downloaded to {destination_file_name}.")

    # Example:
    # download_blob("my-globally-unique-bucket-name", "cloud_file.txt", "downloaded_local_file.txt")

    def list_blobs(self):
        """Lists all the blobs in the bucket."""
        bucket = self.storage_client.bucket(self.bucket_name)
        blobs = self.storage_client.list_blobs(bucket)
        for blob in blobs:
            print(blob.name)



    def __check_exists(self):
        """Checks if the blob already exists"""
