"""
API-wide exception handling.

DRF's default handler only understands API exceptions; anything else becomes Django's blank
"Server Error (500)" HTML page, which a mobile or web client can't show to a person. The one
failure class worth special-casing is **file storage being unavailable** (e.g. a read-only serverless
filesystem before object storage is configured, or the bucket rejecting a write): that is a
deployment/outage condition, not a bug in the request, so it answers 503 with a clear JSON message.
"""
import errno
import logging

import requests
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.views import set_rollback

from .storage_errors import StorageUnavailable

try:  # boto3 is a dependency, but never let an import problem take the whole API down
    from botocore.exceptions import BotoCoreError, ClientError

    _BOTO_ERRORS = (BotoCoreError, ClientError)
except ImportError:  # pragma: no cover
    _BOTO_ERRORS = ()

logger = logging.getLogger(__name__)

# errno values that mean "the disk/bucket will not take this write" (read-only FS, permission, full).
_STORAGE_ERRNOS = {errno.EROFS, errno.EACCES, errno.ENOSPC}

STORAGE_UNAVAILABLE_MESSAGE = "File uploads are temporarily unavailable. Please try again later."


def is_storage_failure(exc: BaseException) -> bool:
    if isinstance(exc, (*_BOTO_ERRORS, StorageUnavailable)):
        return True
    # requests' exceptions subclass OSError too — those are network errors, not storage.
    if isinstance(exc, OSError) and not isinstance(exc, requests.RequestException):
        return exc.errno in _STORAGE_ERRNOS
    return False


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    if is_storage_failure(exc):
        logger.error("File storage failure while handling %s", context.get("view"), exc_info=exc)
        set_rollback()  # undo any rows written earlier in the same request
        return Response({"detail": STORAGE_UNAVAILABLE_MESSAGE}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return None  # anything else: let Django produce its normal 500 (and log it)
