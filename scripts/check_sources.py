import zipfile
import requests
import io

def inspect_zip_members(year):
    yy = str(year)[-2:]
    url = f"https://www2.census.gov/programs-surveys/cps/datasets/{year}/march/asecpub{yy}csv.zip"
    print(f"Fetching {year} from {url}...")
    # Stream first few MB to check or full zip if necessary
    # Or fetch range request to inspect zip directory at end of file
    headers = {"User-Agent": "TheFoundation/0.1"}
    r = requests.get(url, stream=True, headers=headers)
    r.raise_for_status()
    print("Content length:", r.headers.get("content-length"))

if __name__ == "__main__":
    inspect_zip_members(2025)
