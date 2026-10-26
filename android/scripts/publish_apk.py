"""
Publish a signed Android build to the website.

    set BLOB_READ_WRITE_TOKEN=...      (vercel env pull a scratch file and copy just this value)
    python android/scripts/publish_apk.py <path-to-apk> <version-name> <version-code>

Uploads two files to the Vercel Blob store under FIXED names (the `vercel blob put` CLI always adds
a random suffix, so this talks to the Blob API directly):

    downloads/choropia.apk    served at  https://choropia.vercel.app/downloads/choropia.apk
    downloads/latest.json     read by    GET /api/v1/app/android/   (version, size, SHA-256)

No redeploy is needed: the website redirects to these fixed names. Cached for 60 seconds.
"""
import hashlib
import json
import os
import sys
import tempfile

import requests

API = "https://vercel.com/api/blob"


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    apk_path, version, version_code = sys.argv[1], sys.argv[2], int(sys.argv[3])
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        sys.exit("Set BLOB_READ_WRITE_TOKEN first.")

    data = open(apk_path, "rb").read()
    info = {
        "version": version,
        "version_code": version_code,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    base_headers = {"Authorization": f"Bearer {token}", "x-api-version": "12"}

    def put(pathname, body, content_type):
        headers = {
            **base_headers,
            "x-vercel-blob-access": "public",
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1",
            "x-cache-control-max-age": "60",
            "x-content-type": content_type,
        }
        response = requests.put(API + "/", params={"pathname": pathname}, data=body, headers=headers, timeout=300)
        response.raise_for_status()
        print("uploaded", response.json()["url"])

    put("downloads/choropia.apk", data, "application/vnd.android.package-archive")
    put("downloads/latest.json", json.dumps(info).encode(), "application/json")
    print("published:", info)


if __name__ == "__main__":
    main()
