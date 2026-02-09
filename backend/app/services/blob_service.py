import os
from datetime import datetime, timedelta
from typing import Optional

from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.core.exceptions import ResourceExistsError

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

            # Upload blob
            blob_client = container_client.get_blob_client(file_name)
            blob_client.upload_blob(file_data, overwrite=True, content_settings={"content_type": content_type})
            
            # Generate URL (assuming public access or SAS needed)
            # For now, we'll generate a SAS URL valid for 100 years (effectively permanent for this use case)
            # or return the direct URL if public access is enabled.
            # Let's stick to generating a SAS URL for security if container is private.
            
            sas_token = generate_blob_sas(
                account_name=blob_client.account_name,
                container_name=self.container_name,
                blob_name=file_name,
                account_key=self.client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(days=365*10) # 10 years
            )
            
            url = f"{blob_client.url}?{sas_token}"
            return url

        except Exception as e:
            logger.error("blob_upload_failed", error=str(e), file_name=file_name)
            return None
