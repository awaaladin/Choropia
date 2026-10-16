"""
Serves the Android app from object storage, so shipping a new version never needs a redeploy.

  GET /downloads/choropia.apk    302 -> the APK in the Blob store (the URL the website's button uses)
  GET /api/v1/app/android/       version / size / SHA-256 of the current APK, for the download page

To publish a new build, upload two files to the Blob store (fixed names, overwrite allowed):
  downloads/choropia.apk    the signed release APK
  downloads/latest.json     {"version": "1.2.0", "version_code": 3, "size_bytes": ..., "sha256": "..."}
"""
import requests
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseRedirect, JsonResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

APK_PATH = "downloads/choropia.apk"
INFO_PATH = "downloads/latest.json"
INFO_CACHE_KEY = "android-app-info"
INFO_CACHE_SECONDS = 300
MIN_ANDROID = "8.0"


def _blob_base():
    return getattr(settings, "BLOB_PUBLIC_BASE_URL", "").rstrip("/")


def apk_redirect(request):
    base = _blob_base()
    if not base:
        return JsonResponse({"detail": "The Android app isn't available yet."}, status=404)
    # ?download=1 makes the Blob CDN send Content-Disposition: attachment, so browsers save the file.
    response = HttpResponseRedirect(f"{base}/{APK_PATH}?download=1")
    response["Cache-Control"] = "no-store"  # always point at the newest build
    return response


class AndroidAppInfoView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        info = cache.get(INFO_CACHE_KEY)
        if info is None:
            info = self._fetch_info()
            if info is None:
                return Response({"detail": "The Android app isn't available yet."}, status=404)
            cache.set(INFO_CACHE_KEY, info, INFO_CACHE_SECONDS)
        return Response(info)

    @staticmethod
    def _fetch_info():
        base = _blob_base()
        if not base:
            return None
        try:
            response = requests.get(f"{base}/{INFO_PATH}", timeout=5)
            if not response.ok:
                return None
            raw = response.json()
        except (requests.RequestException, ValueError):
            return None
        return {
            "version": raw.get("version", ""),
            "version_code": raw.get("version_code"),
            "size_bytes": raw.get("size_bytes"),
            "sha256": raw.get("sha256", ""),
            "min_android": MIN_ANDROID,
            "download_url": "/downloads/choropia.apk",
        }
