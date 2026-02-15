import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict

from azure.storage.blob import BlobServiceClient

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

    async def upload_file(
        self,
        file_data: bytes,
        file_name: str,
        content_type: str = "audio/mpeg",
        metadata: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
    ) -> Optional[str]:
        if not self.client:
            logger.warning("blob_service_not_configured")
            return None

        if not file_data:
            logger.warning("blob_upload_empty_payload", file_name=file_name)
            return None

        container_client = self.client.get_container_client(self.container_name)
        try:
            if not container_client.exists():
                container_client.create_container()
        except Exception as e:
            logger.error("blob_container_init_failed", error=str(e))
            return None

        blob_client = container_client.get_blob_client(file_name)

        attempt = 0
        while attempt < max_retries:
            attempt += 1
            try:
                blob_client.upload_blob(file_data, overwrite=True)
                if metadata:
                    try:
                        blob_client.set_blob_metadata(metadata)
                    except Exception as e:
                        logger.warning(
                            "blob_set_metadata_failed",
                            error=str(e),
                            file_name=file_name,
                        )

                try:
                    props = blob_client.get_blob_properties()
                    size_ok = props.size == len(file_data)
                except Exception as e:
                    logger.warning(
                        "blob_properties_check_failed",
                        error=str(e),
                        file_name=file_name,
                    )
                    size_ok = True

                if not size_ok:
                    logger.error(
                        "blob_size_mismatch",
                        expected=len(file_data),
                        actual=props.size,
                        file_name=file_name,
                    )
                    return None

                logger.info(
                    "blob_upload_success",
                    file_name=file_name,
                    size=len(file_data),
                )
                return blob_client.url

            except Exception as e:
                logger.error(
                    "blob_upload_failed",
                    error=str(e),
                    file_name=file_name,
                    attempt=attempt,
                    error_type=type(e).__name__,
                )
                if attempt >= max_retries:
                    return None
                await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

        return None

    async def delete_older_than(self, days: int) -> int:
        if not self.client:
            logger.warning("blob_service_not_configured")
            return 0

        cutoff = datetime.utcnow() - timedelta(days=days)
        deleted = 0

        container_client = self.client.get_container_client(self.container_name)
        try:
            if not container_client.exists():
                return 0

            for blob in container_client.list_blobs():
                if blob.last_modified and blob.last_modified < cutoff:
                    try:
                        container_client.delete_blob(blob.name)
                        deleted += 1
                    except Exception as e:
                        logger.error(
                            "blob_delete_failed",
                            error=str(e),
                            blob_name=blob.name,
                        )

        except Exception as e:
            logger.error("blob_retention_scan_failed", error=str(e))

        logger.info("blob_retention_completed", deleted=deleted, days=days)
        return deleted
