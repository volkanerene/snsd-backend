"""
S3 Client Utility for File Operations
Provides comprehensive S3 file management including upload, download, delete, and folder operations.
"""

import os
import boto3
from typing import Optional, List, BinaryIO, Dict, Any
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class S3Client:
    """AWS S3 Client for file operations"""

    def __init__(self, bucket_name: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize S3 client

        Args:
            bucket_name: S3 bucket name (defaults to env variable S3_BUCKET_NAME)
            region: AWS region (defaults to env variable AWS_REGION)
        """
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

        if not self.bucket_name:
            raise ValueError("S3_BUCKET_NAME environment variable is required")

        self.s3_client = boto3.client("s3", region_name=self.region)
        self.s3_resource = boto3.resource("s3", region_name=self.region)
        self.bucket = self.s3_resource.Bucket(self.bucket_name)

    def upload_file(
        self,
        file_obj: BinaryIO,
        object_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        acl: str = "private"
    ) -> Dict[str, Any]:
        """
        Upload a file to S3

        Args:
            file_obj: File object to upload
            object_key: S3 object key (path/filename)
            content_type: MIME type of the file
            metadata: Custom metadata for the file
            acl: Access control list (private, public-read, etc.)

        Returns:
            Dictionary with upload details including URL and etag
        """
        try:
            extra_args = {"ACL": acl}

            if content_type:
                extra_args["ContentType"] = content_type

            if metadata:
                extra_args["Metadata"] = metadata

            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_key,
                ExtraArgs=extra_args
            )

            logger.info(f"File uploaded successfully to {object_key}")

            return {
                "success": True,
                "bucket": self.bucket_name,
                "key": object_key,
                "url": f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{object_key}",
                "region": self.region
            }

        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            raise Exception(f"Failed to upload file: {str(e)}")

    def upload_file_from_path(
        self,
        file_path: str,
        object_key: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload a file from local path to S3

        Args:
            file_path: Local file path
            object_key: S3 object key (defaults to filename)
            content_type: MIME type of the file
            metadata: Custom metadata for the file

        Returns:
            Dictionary with upload details
        """
        if not object_key:
            object_key = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            return self.upload_file(f, object_key, content_type, metadata)

    def download_file(self, object_key: str, destination_path: str) -> bool:
        """
        Download a file from S3 to local path

        Args:
            object_key: S3 object key
            destination_path: Local destination path

        Returns:
            True if successful
        """
        try:
            self.s3_client.download_file(
                self.bucket_name,
                object_key,
                destination_path
            )
            logger.info(f"File downloaded successfully from {object_key}")
            return True

        except ClientError as e:
            logger.error(f"Error downloading file from S3: {e}")
            raise Exception(f"Failed to download file: {str(e)}")

    def get_file_content(self, object_key: str) -> bytes:
        """
        Get file content as bytes

        Args:
            object_key: S3 object key

        Returns:
            File content as bytes
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            return response["Body"].read()

        except ClientError as e:
            logger.error(f"Error getting file content from S3: {e}")
            raise Exception(f"Failed to get file content: {str(e)}")

    def delete_file(self, object_key: str) -> bool:
        """
        Delete a file from S3

        Args:
            object_key: S3 object key

        Returns:
            True if successful
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            logger.info(f"File deleted successfully: {object_key}")
            return True

        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            raise Exception(f"Failed to delete file: {str(e)}")

    def delete_files(self, object_keys: List[str]) -> Dict[str, Any]:
        """
        Delete multiple files from S3

        Args:
            object_keys: List of S3 object keys

        Returns:
            Dictionary with deletion results
        """
        try:
            objects = [{"Key": key} for key in object_keys]

            response = self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": objects}
            )

            deleted = response.get("Deleted", [])
            errors = response.get("Errors", [])

            logger.info(f"Deleted {len(deleted)} files, {len(errors)} errors")

            return {
                "success": True,
                "deleted": deleted,
                "errors": errors
            }

        except ClientError as e:
            logger.error(f"Error deleting files from S3: {e}")
            raise Exception(f"Failed to delete files: {str(e)}")

    def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000,
        delimiter: str = ""
    ) -> List[Dict[str, Any]]:
        """
        List files in S3 bucket

        Args:
            prefix: Prefix to filter files (folder path)
            max_keys: Maximum number of keys to return
            delimiter: Delimiter for grouping (use "/" for folders)

        Returns:
            List of file information dictionaries
        """
        try:
            params = {
                "Bucket": self.bucket_name,
                "MaxKeys": max_keys
            }

            if prefix:
                params["Prefix"] = prefix

            if delimiter:
                params["Delimiter"] = delimiter

            response = self.s3_client.list_objects_v2(**params)

            files = []
            for obj in response.get("Contents", []):
                files.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "etag": obj["ETag"].strip('"')
                })

            # Include folders if delimiter is used
            folders = []
            for prefix_obj in response.get("CommonPrefixes", []):
                folders.append({
                    "key": prefix_obj["Prefix"],
                    "type": "folder"
                })

            return files + folders

        except ClientError as e:
            logger.error(f"Error listing files from S3: {e}")
            raise Exception(f"Failed to list files: {str(e)}")

    def file_exists(self, object_key: str) -> bool:
        """
        Check if a file exists in S3

        Args:
            object_key: S3 object key

        Returns:
            True if file exists
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def get_file_metadata(self, object_key: str) -> Dict[str, Any]:
        """
        Get file metadata

        Args:
            object_key: S3 object key

        Returns:
            Dictionary with file metadata
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=object_key
            )

            return {
                "key": object_key,
                "size": response["ContentLength"],
                "content_type": response.get("ContentType"),
                "last_modified": response["LastModified"].isoformat(),
                "etag": response["ETag"].strip('"'),
                "metadata": response.get("Metadata", {})
            }

        except ClientError as e:
            logger.error(f"Error getting file metadata from S3: {e}")
            raise Exception(f"Failed to get file metadata: {str(e)}")

    def copy_file(
        self,
        source_key: str,
        destination_key: str,
        source_bucket: Optional[str] = None
    ) -> bool:
        """
        Copy a file within S3

        Args:
            source_key: Source S3 object key
            destination_key: Destination S3 object key
            source_bucket: Source bucket (defaults to same bucket)

        Returns:
            True if successful
        """
        try:
            source_bucket = source_bucket or self.bucket_name

            copy_source = {
                "Bucket": source_bucket,
                "Key": source_key
            }

            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=destination_key
            )

            logger.info(f"File copied from {source_key} to {destination_key}")
            return True

        except ClientError as e:
            logger.error(f"Error copying file in S3: {e}")
            raise Exception(f"Failed to copy file: {str(e)}")

    def move_file(
        self,
        source_key: str,
        destination_key: str
    ) -> bool:
        """
        Move a file within S3 (copy and delete)

        Args:
            source_key: Source S3 object key
            destination_key: Destination S3 object key

        Returns:
            True if successful
        """
        self.copy_file(source_key, destination_key)
        self.delete_file(source_key)
        logger.info(f"File moved from {source_key} to {destination_key}")
        return True

    def create_folder(self, folder_path: str) -> bool:
        """
        Create a folder in S3 (by creating an empty object with trailing /)

        Args:
            folder_path: Folder path (should end with /)

        Returns:
            True if successful
        """
        try:
            if not folder_path.endswith("/"):
                folder_path += "/"

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=folder_path,
                Body=b""
            )

            logger.info(f"Folder created: {folder_path}")
            return True

        except ClientError as e:
            logger.error(f"Error creating folder in S3: {e}")
            raise Exception(f"Failed to create folder: {str(e)}")

    def delete_folder(self, folder_path: str) -> Dict[str, Any]:
        """
        Delete a folder and all its contents from S3

        Args:
            folder_path: Folder path (should end with /)

        Returns:
            Dictionary with deletion results
        """
        try:
            if not folder_path.endswith("/"):
                folder_path += "/"

            # List all objects in the folder
            objects = self.list_files(prefix=folder_path, max_keys=1000)

            if not objects:
                logger.info(f"No objects found in folder: {folder_path}")
                return {"success": True, "deleted": [], "errors": []}

            # Delete all objects
            object_keys = [obj["key"] for obj in objects if obj.get("type") != "folder"]

            if object_keys:
                result = self.delete_files(object_keys)
                logger.info(f"Folder deleted: {folder_path}")
                return result

            return {"success": True, "deleted": [], "errors": []}

        except ClientError as e:
            logger.error(f"Error deleting folder from S3: {e}")
            raise Exception(f"Failed to delete folder: {str(e)}")

    def generate_presigned_url(
        self,
        object_key: str,
        expiration: int = 3600,
        http_method: str = "GET"
    ) -> str:
        """
        Generate a presigned URL for file access

        Args:
            object_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            http_method: HTTP method (GET, PUT, DELETE)

        Returns:
            Presigned URL
        """
        try:
            client_method_map = {
                "GET": "get_object",
                "PUT": "put_object",
                "DELETE": "delete_object"
            }

            client_method = client_method_map.get(http_method.upper(), "get_object")

            url = self.s3_client.generate_presigned_url(
                client_method,
                Params={
                    "Bucket": self.bucket_name,
                    "Key": object_key
                },
                ExpiresIn=expiration
            )

            logger.info(f"Presigned URL generated for {object_key}")
            return url

        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise Exception(f"Failed to generate presigned URL: {str(e)}")

    def generate_presigned_post(
        self,
        object_key: str,
        expiration: int = 3600,
        max_file_size: int = 10 * 1024 * 1024,  # 10 MB
        allowed_content_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate presigned POST data for direct browser upload

        Args:
            object_key: S3 object key
            expiration: URL expiration time in seconds
            max_file_size: Maximum file size in bytes
            allowed_content_types: List of allowed content types

        Returns:
            Dictionary with URL and fields for POST request
        """
        try:
            conditions = [
                {"bucket": self.bucket_name},
                ["starts-with", "$key", object_key],
                ["content-length-range", 0, max_file_size]
            ]

            if allowed_content_types:
                conditions.append(["starts-with", "$Content-Type", ""])

            response = self.s3_client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=object_key,
                ExpiresIn=expiration,
                Conditions=conditions
            )

            logger.info(f"Presigned POST generated for {object_key}")
            return response

        except ClientError as e:
            logger.error(f"Error generating presigned POST: {e}")
            raise Exception(f"Failed to generate presigned POST: {str(e)}")


# Singleton instance
_s3_client: Optional[S3Client] = None


def get_s3_client() -> S3Client:
    """Get or create S3 client singleton instance"""
    global _s3_client
    if _s3_client is None:
        _s3_client = S3Client()
    return _s3_client
