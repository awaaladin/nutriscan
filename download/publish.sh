#!/usr/bin/env bash
# Publishes the APK that GitHub Actions built (.github/workflows/build-apk.yml) to the download page,
# then deploys this folder to the `nutriscan-download` Vercel project (https://nutriscan-download.vercel.app).
# Nothing is compiled on this machine.
#
#   bash download/publish.sh            # the latest successful build of main
#   bash download/publish.sh <run-id>   # a specific run
#
# First time only, link this folder to the existing project:
#   cd download && vercel link --yes --project nutriscan-download --scope awas-projects-f82bcad8
set -euo pipefail
cd "$(dirname "$0")/.."

RUN_ID="${1:-$(gh run list --workflow build-apk.yml --branch main --status success --limit 1 --json databaseId -q '.[0].databaseId')}"
if [ -z "$RUN_ID" ]; then
  echo "No successful build-apk.yml run on main yet." >&2
  exit 1
fi
rm -rf apk-output
gh run download "$RUN_ID" -n app-debug -D apk-output
cp apk-output/*.apk download/nutriscan.apk

# The download page reads its version, size, date and SHA-256 from release.json, so write it
# from the file being published, then rebuild the pages.
VERSION=$(grep -oP 'versionName = "\K[^"]+' android/app/build.gradle.kts)
python site/release.py download/nutriscan.apk "$VERSION"
python site/build.py

vercel --prod --yes --cwd download
