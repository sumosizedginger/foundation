import zipfile
from pathlib import Path

import pandas as pd


def inspect_asec_merge(archive_path: Path):
    with zipfile.ZipFile(archive_path) as zf:
        print("Reading hhpub25.csv...")
        with zf.open("hhpub25.csv") as f:
            hh = pd.read_csv(f, usecols=["H_SEQ", "HTOTVAL", "H_NUMPER"], low_memory=False)
        print(f"Household records: {len(hh)}")
        print(hh.head())
        print(hh.describe())

        print("\nReading pppub25.csv...")
        with zf.open("pppub25.csv") as f:
            pp = pd.read_csv(
                f, usecols=["PH_SEQ", "A_LINENO", "MARSUPWT", "A_AGE"], low_memory=False
            )
        print(f"Person records: {len(pp)}")
        print(pp.head())
        print(pp.describe())

        # Merge household onto person records: each person gets their household's HTOTVAL and H_NUMPER
        merged = pp.merge(hh, left_on="PH_SEQ", right_on="H_SEQ", how="inner")
        print(f"\nMerged person records: {len(merged)}")
        print(merged.head())

        print("\nMARSUPWT summary:")
        print(merged["MARSUPWT"].describe())
        print(f"Sum of MARSUPWT: {merged['MARSUPWT'].sum():,.2f}")


if __name__ == "__main__":
    inspect_asec_merge(Path(".cache/census/asecpub25csv.zip"))
