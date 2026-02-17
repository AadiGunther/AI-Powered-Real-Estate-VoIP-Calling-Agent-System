import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
from urllib.parse import urlparse

from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

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

    def _parse_account_credentials(self) -> Optional[Dict[str, str]]:
        if not self.connection_string:
            logger.warning("blob_sas_missing_connection_string")
            return None
        parts: Dict[str, str] = {}
        for segment in self.connection_string.split(";"):
            if "=" in segment:
                key, value = segment.split("=", 1)
                parts[key] = value
        account_name = parts.get("AccountName")
        account_key = parts.get("AccountKey")
        if not account_name or not account_key:
            logger.error("blob_sas_missing_account_credentials")
            return None
        return {"account_name": account_name, "account_key": account_key}

    def generate_sas_for_blob(
        self,
        container_name: str,
        blob_name: str,
        expiry_minutes: int = 15,
    ) -> Optional[str]:
        if not self.client:
            logger.warning("blob_sas_client_not_configured")
            return None

        creds = self._parse_account_credentials()
        if not creds:
            return None

        try:
            sas_token = generate_blob_sas(
                account_name=creds["account_name"],
                container_name=container_name,
                blob_name=blob_name,
                account_key=creds["account_key"],
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(minutes=expiry_minutes),
            )
            blob_client = self.client.get_blob_client(container=container_name, blob=blob_name)
            return f"{blob_client.url}?{sas_token}"
        except Exception as e:
            logger.error(
                "blob_sas_generation_failed",
                error=str(e),
                container_name=container_name,
                blob_name=blob_name,
            )
            return None

    def generate_sas_from_blob_url(self, blob_url: str, expiry_minutes: int = 15) -> Optional[str]:
        if not blob_url:
            logger.warning("blob_sas_missing_blob_url")
            return None
        parsed = urlparse(blob_url)
        path = parsed.path.lstrip("/")
        if not path or "/" not in path:
            logger.error("blob_sas_invalid_blob_url", blob_url=blob_url)
            return None
        container_name, blob_name = path.split("/", 1)
        return self.generate_sas_for_blob(container_name, blob_name, expiry_minutes=expiry_minutes)

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
