#!/usr/bin/env python3
"""
Downloads and extracts the Olist Brazilian E-Commerce dataset into data/raw/.
Works natively across Windows, Linux, and macOS.
"""
import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"

MIRROR_URL = "https://codeload.github.com/Ganesh7699/Brazilian-E-Commerce-OList/zip/refs/heads/main"

def main():
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Olist dataset from mirror: {MIRROR_URL} ...")
    
    req = urllib.request.Request(
        MIRROR_URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
    
    print(f"Downloaded {len(content) / (1024 * 1024):.2f} MB. Extracting CSV files to {DATA_RAW} ...")
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        for member in z.infolist():
            if member.filename.endswith(".csv"):
                filename = Path(member.filename).name
                if filename == "final.csv":
                    continue  # Skip derived joined file
                target_path = DATA_RAW / filename
                with z.open(member) as source, open(target_path, "wb") as target:
                    shutil.copyfileobj(source, target)
                print(f"  Extracted: {filename}")

    csv_count = len(list(DATA_RAW.glob("*.csv")))
    print(f"\nDone! {csv_count} CSV files ready in {DATA_RAW}.")

if __name__ == "__main__":
    main()
