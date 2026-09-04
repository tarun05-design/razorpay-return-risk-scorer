#!/usr/bin/env bash
# Fetches the Olist Brazilian E-Commerce Public Dataset into data/raw/.
#
# Preferred (official source, requires a free Kaggle account + API token
# at ~/.kaggle/kaggle.json):
#   pip install kaggle
#   kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
#
# This script uses a public GitHub mirror of the same dataset as a
# no-account-needed fallback for judges/reviewers running this quickly.
# Source: https://www.kaggle.com/olistbr/brazilian-ecommerce
# License: CC BY-NC-SA 4.0 (Olist, released for public/academic use).

set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p data/raw
TMP=$(mktemp -d)
echo "Downloading Olist dataset mirror..."
curl -sL -o "$TMP/olist.zip" \
  "https://codeload.github.com/Ganesh7699/Brazilian-E-Commerce-OList/zip/refs/heads/main"

unzip -q -o "$TMP/olist.zip" -d "$TMP"
mv "$TMP"/Brazilian-E-Commerce-OList-main/*.csv data/raw/
rm -f data/raw/final.csv  # derived/joined file we don't need; we build our own joins
rm -rf "$TMP"

echo "Done. $(ls data/raw/*.csv | wc -l) CSV files in data/raw/"
