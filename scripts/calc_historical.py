import zipfile
from pathlib import Path

import pandas as pd
import requests

from foundation.bottom30 import calculate_bottom30


def process_historical_asec(survey_year: int, income_year: int):
    yy = str(survey_year)[-2:]
    url = f"https://www2.census.gov/programs-surveys/cps/datasets/{survey_year}/march/asecpub{yy}csv.zip"
    cache_file = Path(f".cache/census/asecpub{yy}csv.zip")
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    if not cache_file.exists():
        print(f"Downloading {survey_year} ASEC from {url}...")
        r = requests.get(url, stream=True, headers={"User-Agent": "TheFoundation/0.1"})
        r.raise_for_status()
        with open(cache_file, "wb") as f:
            f.writelines(r.iter_content(chunk_size=1024 * 1024))

    print(f"Opening {cache_file}...")
    with zipfile.ZipFile(cache_file) as zf:
        hh_file = f"hhpub{yy}.csv"
        pp_file = f"pppub{yy}.csv"
        with zf.open(hh_file) as f:
            hh = pd.read_csv(f, usecols=["H_SEQ", "HTOTVAL", "H_NUMPER"], low_memory=False)
        with zf.open(pp_file) as f:
            pp = pd.read_csv(f, usecols=["PH_SEQ", "MARSUPWT", "A_LINENO"], low_memory=False)

        merged = pp.merge(hh, left_on="PH_SEQ", right_on="H_SEQ", how="inner")
        if "H_SEQ" not in merged.columns and "PH_SEQ" in merged.columns:
            merged["H_SEQ"] = merged["PH_SEQ"]

        result = calculate_bottom30(merged, survey_year=survey_year, income_year=income_year)
        print(
            f"Survey {survey_year} (Income {income_year}): Cutoff = ${result.cutoff:,.2f}, Population = {result.total_relative_weight / 100:,.0f}"
        )
        return result


if __name__ == "__main__":
    for sy, iy in [(2024, 2023), (2023, 2022)]:
        try:
            process_historical_asec(sy, iy)
        except (requests.RequestException, OSError, ValueError, zipfile.BadZipFile) as e:
            print(f"Error for {sy}: {e}")
