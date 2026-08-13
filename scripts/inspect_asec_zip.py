import zipfile
from pathlib import Path
import pandas as pd

def inspect_zip(archive_path: Path):
    with zipfile.ZipFile(archive_path) as zf:
        print("Archive members:")
        for info in zf.infolist():
            print(f"  {info.filename}: size={info.file_size} bytes ({info.file_size / 1e6:.1f} MB)")
            if info.filename.lower().endswith(".csv"):
                # Read just the header
                with zf.open(info) as f:
                    header_line = f.readline().decode("utf-8", errors="ignore").strip()
                    cols = [c.strip().strip('"') for c in header_line.split(",")]
                    print(f"    Total columns: {len(cols)}")
                    print(f"    First 15 columns: {cols[:15]}")
                    matches = [c for c in cols if any(k in c.upper() for k in ["HTOTVAL", "NUMPER", "MARSUPWT", "H_SEQ", "PERIDNUM", "A_LINENO"])]
                    print(f"    Relevant matches: {matches}")

if __name__ == "__main__":
    inspect_zip(Path(".cache/census/asecpub25csv.zip"))
