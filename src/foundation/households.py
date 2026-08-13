from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class HouseholdTransformReport:
    input_records: int
    valid_records: int
    excluded_records: int
    invalid_income: int
    invalid_household_size: int
    invalid_weight: int


REQUIRED_ASEC_COLUMNS = ("HTOTVAL", "H_NUMPER", "MARSUPWT", "H_SEQ")


def prepare_person_records(
    frame: pd.DataFrame,
    *,
    income_col: str = "HTOTVAL",
    people_col: str = "H_NUMPER",
    weight_col: str = "MARSUPWT",
    household_id_col: str = "H_SEQ",
) -> tuple[pd.DataFrame, HouseholdTransformReport]:
    """Prepare person records for the canonical Bottom-30 calculation.

    Negative income is retained if numeric. Non-positive household counts and
    non-positive person weights are excluded and reported.
    """
    required = [income_col, people_col, weight_col, household_id_col]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    data = frame[required].copy()

    for col in (income_col, people_col, weight_col):
        data[col] = pd.to_numeric(data[col], errors="coerce")

    invalid_income_mask = ~np.isfinite(data[income_col].astype(float))
    invalid_people_mask = ~np.isfinite(data[people_col].astype(float)) | (data[people_col] <= 0)
    invalid_weight_mask = ~np.isfinite(data[weight_col].astype(float)) | (data[weight_col] <= 0)

    valid_mask = ~(invalid_income_mask | invalid_people_mask | invalid_weight_mask)
    valid = data.loc[valid_mask].copy()

    valid["household_income_per_person"] = valid[income_col] / valid[people_col]
    valid["person_weight"] = valid[weight_col].astype(float)

    report = HouseholdTransformReport(
        input_records=len(data),
        valid_records=len(valid),
        excluded_records=int((~valid_mask).sum()),
        invalid_income=int(invalid_income_mask.sum()),
        invalid_household_size=int(invalid_people_mask.sum()),
        invalid_weight=int(invalid_weight_mask.sum()),
    )
    return valid, report
