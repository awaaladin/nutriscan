#!/usr/bin/env bash
# Builds the debug APK, copies it next to the page and deploys this folder to
# the `nutriscan-download` Vercel project (https://nutriscan-download.vercel.app).
#
# First time only, link this folder to the existing project:
#   cd download && vercel link --yes --project nutriscan-download --scope awas-projects-f82bcad8
set -euo pipefail
cd "$(dirname "$0")/.."

(cd android && ./gradlew :app:assembleDebug)
cp android/app/build/outputs/apk/debug/app-debug.apk download/nutriscan.apk

# The download page reads its version, size, date and SHA-256 from release.json, so write it
# from the file being published, then rebuild the pages.
VERSION=$(grep -oP 'versionName = "\K[^"]+' android/app/build.gradle.kts)
python site/release.py download/nutriscan.apk "$VERSION"
python site/build.py

vercel --prod --yes --cwd download
