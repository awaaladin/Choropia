"""
Django file storage backed by Vercel Blob.

Why: Vercel serverless functions have a read-only filesystem, so Django's default FileSystemStorage
fails on every upload (listing photos, avatars, reel videos, chat attachments). Vercel Blob is
object storage that the Vercel CLI can provision with no extra account.

Enabled automatically when `BLOB_READ_WRITE_TOKEN` is set (Vercel sets it when a Blob store is
connected to the project) — see config/settings/base.py. Uses plain `requests`, no extra dependency.

Wire format (matches the official `vercel` Python SDK, api version 12):
  PUT  https://vercel.com/api/blob/?pathname=<path>   body = file bytes, Bearer <token>
       -> {"url": "...", "pathname": "<path>-<random>", ...}
  POST https://vercel.com/api/blob/delete             {"urls": [...]}
Files are public at  <BLOB_PUBLIC_BASE_URL>/<pathname>  (random suffix makes the URL unguessable).
"""
import mimetypes
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

from .storage_errors import StorageUnavailable

API_URL = "https://vercel.com/api/blob"
API_VERSION = "12"
TIMEOUT_SECONDS = 25


@deconstructible
class VercelBlobStorage(Storage):
    def __init__(self, token=None, base_url=None):
        self._token = token
        self._base_url = base_url

    # -- configuration ------------------------------------------------------------------------

    @property
    def token(self):
        token = self._token or getattr(settings, "BLOB_READ_WRITE_TOKEN", "")
        if not token:
            raise StorageUnavailable("BLOB_READ_WRITE_TOKEN is not configured.")
        return token

    @property
    def base_url(self):
        return (self._base_url or getattr(settings, "BLOB_PUBLIC_BASE_URL", "")).rstrip("/")

    def _auth(self, **extra):
        return {"Authorization": f"Bearer {self.token}", "x-api-version": API_VERSION, **extra}

    # -- Storage API --------------------------------------------------------------------------

    def get_available_name(self, name, max_length=None):
        # Blob adds a random suffix itself, so there is never a name clash to resolve.
        return name

    def _save(self, name, content):
        content.seek(0)
        data = content.read()
        content_type = getattr(content, "content_type", None) or mimetypes.guess_type(name)[0] or "application/octet-stream"
        headers = self._auth(**{
            "x-vercel-blob-access": "public",
            "x-add-random-suffix": "1",
            "x-content-type": content_type,
        })
        try:
            response = requests.put(f"{API_URL}/", params={"pathname": name}, data=data, headers=headers, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise StorageUnavailable(f"Could not reach Vercel Blob: {exc}") from exc
        if not response.ok:
            raise StorageUnavailable(f"Vercel Blob rejected the upload ({response.status_code}): {response.text[:200]}")
        return response.json()["pathname"]

    def url(self, name):
        if not self.base_url:
            raise StorageUnavailable("BLOB_PUBLIC_BASE_URL is not configured.")
        return f"{self.base_url}/{quote(name)}"

    def exists(self, name):
        return False  # random suffixes make every saved name unique

    def delete(self, name):
        try:
            response = requests.post(f"{API_URL}/delete", json={"urls": [self.url(name)]}, headers=self._auth(), timeout=TIMEOUT_SECONDS)
        except requests.RequestException:
            return  # best effort: an orphaned blob is harmless, a failed delete must not break a request
        if not response.ok:
            return

    def _open(self, name, mode="rb"):
        try:
            response = requests.get(self.url(name), timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise StorageUnavailable(f"Could not fetch {name}: {exc}") from exc
        if not response.ok:
            raise FileNotFoundError(name)
        return ContentFile(response.content, name=name)

    def size(self, name):
        try:
            response = requests.head(self.url(name), timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise StorageUnavailable(f"Could not stat {name}: {exc}") from exc
        return int(response.headers.get("content-length", 0))
