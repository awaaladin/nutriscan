"""Django file storage backed by Vercel Blob (public store).

Vercel's filesystem is ephemeral, so report photos must live in object
storage. This talks to the Blob REST API directly (the same calls the official
@vercel/blob client makes) so no extra Python dependency is needed.

Enabled in settings when BLOB_READ_WRITE_TOKEN is set; that variable is added
to the Vercel project automatically when a Blob store is connected to it.
"""
import os
import uuid
from urllib.parse import quote

import requests
from django.core.files.base import File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

API_URL = "https://vercel.com/api/blob"
API_VERSION = "12"


@deconstructible
class VercelBlobStorage(Storage):
    def __init__(self, token=None):
        self.token = token or os.environ.get("BLOB_READ_WRITE_TOKEN", "")

    @property
    def _store_id(self) -> str:
        # Token format: vercel_blob_rw_<storeId>_<secret>
        parts = self.token.split("_")
        return parts[3].lower() if len(parts) > 4 else ""

    def _headers(self, **extra):
        return {"authorization": f"Bearer {self.token}", "x-api-version": API_VERSION, **extra}

    def _save(self, name, content):
        directory, _, filename = name.rpartition("/")
        extension = os.path.splitext(filename)[1].lower()[:10]
        # Server-generated name: user-supplied filenames can be long or odd,
        # and uniqueness is guaranteed without a lookup.
        pathname = f"{directory + '/' if directory else ''}{uuid.uuid4().hex}{extension}"
        content.seek(0)
        response = requests.put(
            f"{API_URL}/",
            params={"pathname": pathname},
            data=content.read(),
            headers=self._headers(
                **{
                    "x-vercel-blob-access": "public",
                    "x-add-random-suffix": "0",
                    "x-content-type": getattr(content, "content_type", None) or "application/octet-stream",
                }
            ),
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["pathname"]

    def _open(self, name, mode="rb"):
        response = requests.get(self.url(name), timeout=30)
        response.raise_for_status()
        from io import BytesIO

        return File(BytesIO(response.content), name=name)

    def delete(self, name):
        requests.post(
            f"{API_URL}/delete",
            json={"urls": [self.url(name)]},
            headers=self._headers(),
            timeout=15,
        )

    def exists(self, name):
        return False  # every saved file gets a fresh UUID name

    def url(self, name):
        return f"https://{self._store_id}.public.blob.vercel-storage.com/{quote(name)}"

    def size(self, name):
        response = requests.head(self.url(name), timeout=15)
        response.raise_for_status()
        return int(response.headers.get("content-length", 0))
