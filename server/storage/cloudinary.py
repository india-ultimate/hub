"""Django storage that keeps uploaded files on Cloudinary, not the machine."""

import os
from typing import Any

import cloudinary.api
import cloudinary.exceptions
import cloudinary.uploader
import requests
from django.core.files.base import ContentFile, File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

from server.storage import kinds, shrink

# Each try at a free name is one upload; five clashes in a row won't happen.
TRIES = 5


@deconstructible
class CloudinaryStorage(Storage):
    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        # Django would call exists() here, one rate-limited Admin API call per
        # upload. _save finds a free name through the upload itself instead.
        # Cleaned, as the contact form saves the attachment's own name and
        # Cloudinary refuses ids with ? & # % and the like.
        folder, base = os.path.split(name)
        return os.path.join(folder, self.get_valid_name(base))

    def _save(self, name: str, content: File[Any]) -> str:
        # Images only: raw files have no pixel limit.
        upload = (kinds.resource_type(name) == "image" and shrink.shrunk(content)) or content
        for _ in range(TRIES):
            upload.seek(0)
            result = cloudinary.uploader.upload(
                upload,
                public_id=kinds.public_id(name),
                resource_type=kinds.resource_type(name),
                overwrite=False,  # a taken id answers "existing" instead
                unique_filename=False,
                use_filename=False,
                **kinds.format_option(name),
                **kinds.upload_options(name),
            )
            if not result.get("existing"):
                return name
            name = self.get_alternative_name(*os.path.splitext(name))
        raise cloudinary.exceptions.Error(f"No free name for {name}")

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
