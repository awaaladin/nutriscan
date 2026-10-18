"""Writes download/release.json for the APK sitting in download/. Run by publish.sh.

    python site/release.py <path-to-apk> <version>
The download page reads this file, so the version, size and SHA-256 fingerprint it shows are
always those of the file actually being served."""
import datetime
import hashlib
import json
import os
import sys

apk, version = sys.argv[1], sys.argv[2]
data = open(apk, "rb").read()
out = {
    "version": version,
    "size_mb": round(len(data) / (1024 * 1024), 1),
    "date": datetime.date.today().strftime("%d %B %Y").lstrip("0"),
    "sha256": hashlib.sha256(data).hexdigest(),
}
path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "download", "release.json")
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print(out)
