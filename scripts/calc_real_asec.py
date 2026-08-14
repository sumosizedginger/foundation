import zipfile
from pathlib import Path

import pandas as pd

from foundation.bottom30 import calculate_bottom30
from foundation.independent_check import weighted_percentile_reference
from foundation.percentiles import weighted_percentiles


def calculate_real_asec(archive_path: Path):
    with zipfile.ZipFile(archive_path) as zf:
        with zf.open("hhpub25.csv") as f:
            hh = pd.read_csv(f, usecols=["H_SEQ", "HTOTVAL", "H_NUMPER"], low_memory=False)
        with zf.open("pppub25.csv") as f:
            pp = pd.read_csv(f, usecols=["PH_SEQ", "MARSUPWT", "A_LINENO"], low_memory=False)

        merged = pp.merge(hh, left_on="PH_SEQ", right_on="H_SEQ", how="inner")
        # Ensure H_SEQ exists in merged
        if "H_SEQ" not in merged.columns and "PH_SEQ" in merged.columns:
            merged["H_SEQ"] = merged["PH_SEQ"]

        result = calculate_bottom30(merged, survey_year=2025, income_year=2024)
        print("=== CANONICAL BOTTOM-30 RESULT (Survey 2025 / Income 2024) ===")
        print(f"Cutoff: ${result.cutoff:,.2f}")
        print(f"Valid records: {result.valid_records:,}")
        print(f"Excluded records: {result.excluded_records:,}")
        print(f"Total weighted population: {result.total_relative_weight / 100:,.0f} persons")

        # Independent cross-check:
        prep_values = merged["HTOTVAL"] / merged["H_NUMPER"]
        prep_weights = merged["MARSUPWT"]
        valid_mask = (merged["H_NUMPER"] > 0) & (merged["MARSUPWT"] > 0) & prep_values.notna()
        ref_cutoff = weighted_percentile_reference(
            prep_values[valid_mask], prep_weights[valid_mask], 0.30
        )
        print(f"Independent reference cutoff: ${ref_cutoff:,.2f}")
        assert result.cutoff == ref_cutoff, f"Mismatch: {result.cutoff} vs {ref_cutoff}"
        print("Independent cross-check PASSED!")

        # Multi-quantile distribution:
        quantiles = weighted_percentiles(
            prep_values[valid_mask],
            prep_weights[valid_mask],
            [0.10, 0.20, 0.30, 0.40, 0.50, 0.75, 0.90],
        )
        print("\n=== PER-PERSON HOUSEHOLD INCOME QUANTILES ===")
        for p, val in quantiles.items():
            print(f"  P{int(p * 100):02d}: ${val:,.2f}")


if __name__ == "__main__":
    calculate_real_asec(Path(".cache/census/asecpub25csv.zip"))
