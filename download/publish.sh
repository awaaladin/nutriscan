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

# Keep the version label on the page in step with the app.
VERSION=$(grep -oP 'versionName = "\K[^"]+' android/app/build.gradle.kts)
sed -i -E "s/v[0-9]+\.[0-9]+\.[0-9]+ · Beta build/v${VERSION} · Beta build/" download/index.html

vercel --prod --yes --cwd download
