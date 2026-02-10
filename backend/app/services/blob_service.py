import os
from datetime import datetime, timedelta
from typing import Optional

from azure.storage.blob import BlobServiceClient, BlobSasPermissions

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("services.blob_service")

class BlobService:
    def __init__(self):
        self.connection_string = settings.azure_storage_connection_string
        self.container_name = settings.azure_storage_container_name
        self.client: Optional[BlobServiceClient] = None
        
        if self.connection_string:
            try:
                self.client = BlobServiceClient.from_connection_string(self.connection_string)
            except Exception as e:
                logger.error("blob_service_init_failed", error=str(e))

    async def upload_file(self, file_data: bytes, file_name: str, content_type: str = "audio/mpeg") -> Optional[str]:
        """
        Uploads a file to Azure Blob Storage and returns the URL.
        """
        if not self.client:
            logger.warning("blob_service_not_configured")
            return None

        try:
            # Ensure container exists
            container_client = self.client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container()

            blob_client = container_client.get_blob_client(file_name)
            blob_client.upload_blob(file_data, overwrite=True)
            return blob_client.url

        except Exception as e:
            logger.error("blob_upload_failed", error=str(e), file_name=file_name)
            return None
