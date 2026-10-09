"""Django storage that keeps uploaded files on Cloudinary, not the machine."""

from typing import Any

import cloudinary.api
import cloudinary.exceptions
import cloudinary.uploader
import requests
from django.core.files.base import ContentFile, File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

from server.storage import kinds


@deconstructible
class CloudinaryStorage(Storage):
    def _save(self, name: str, content: File[Any]) -> str:
        content.seek(0)
        cloudinary.uploader.upload(
            content,
            public_id=kinds.public_id(name),
            resource_type=kinds.resource_type(name),
            overwrite=False,
            unique_filename=False,
            use_filename=False,
            **kinds.upload_options(name),
        )
        return name

    def _open(self, name: str, mode: str = "rb") -> File[bytes]:
        # CKEditor's uploader reads images back to make thumbnails.
        response = requests.get(self.url(name), timeout=30)
        response.raise_for_status()
        return ContentFile(response.content, name=name)

    def delete(self, name: str) -> None:
        if name:  # "not found" is fine: the file is gone either way
            cloudinary.uploader.destroy(
                kinds.public_id(name), resource_type=kinds.resource_type(name), invalidate=True
            )

    def _resource(self, name: str) -> dict[str, Any]:
        return cloudinary.api.resource(
            kinds.public_id(name), resource_type=kinds.resource_type(name)
        )

    def exists(self, name: str) -> bool:
        try:
            self._resource(name)
        except cloudinary.exceptions.NotFound:
            return False
        return True

    def size(self, name: str) -> int:
        return int(self._resource(name)["bytes"])

    def url(self, name: str | None) -> str:
        return kinds.url(name) if name else ""
