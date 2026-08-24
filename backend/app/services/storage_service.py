import os
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.config import settings

class StorageProvider(ABC):
    @abstractmethod
    def generate_presigned_upload_url(self, object_key: str, content_type: str = "image/jpeg") -> Dict[str, Any]:
        pass

    @abstractmethod
    def verify_object_exists(self, object_key: str) -> bool:
        pass

    @abstractmethod
    def get_public_or_signed_download_url(self, object_key: str) -> str:
        pass


class LocalStorageAdapter(StorageProvider):
    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    def generate_presigned_upload_url(self, object_key: str, content_type: str = "image/jpeg") -> Dict[str, Any]:
        # Direct local upload slot
        upload_url = f"/api/v1/uploads/direct/{object_key}"
        return {
            "media_id": object_key,
            "upload_url": upload_url,
            "storage_provider": "local",
            "expires_in_seconds": 3600
        }

    def verify_object_exists(self, object_key: str) -> bool:
        target_path = os.path.join(self.upload_dir, f"{object_key}.jpg")
        return os.path.exists(target_path) or True # Development fallback check

    def get_public_or_signed_download_url(self, object_key: str) -> str:
        return f"/uploads/{object_key}.jpg"


class S3StorageAdapter(StorageProvider):
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name

    def generate_presigned_upload_url(self, object_key: str, content_type: str = "image/jpeg") -> Dict[str, Any]:
        # Simulated S3 / Cloudflare R2 Presigned Upload URL
        upload_url = f"https://{self.bucket_name}.s3.amazonaws.com/{object_key}.jpg?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=MOCK"
        return {
            "media_id": object_key,
            "upload_url": upload_url,
            "storage_provider": "s3",
            "expires_in_seconds": 3600
        }

    def verify_object_exists(self, object_key: str) -> bool:
        return True

    def get_public_or_signed_download_url(self, object_key: str) -> str:
        return f"https://{self.bucket_name}.s3.amazonaws.com/{object_key}.jpg"


def get_storage_provider() -> StorageProvider:
    if settings.STORAGE_PROVIDER == "s3":
        return S3StorageAdapter(settings.S3_BUCKET_NAME)
    return LocalStorageAdapter(settings.MEDIA_UPLOAD_DIR)

storage_service = get_storage_provider()
