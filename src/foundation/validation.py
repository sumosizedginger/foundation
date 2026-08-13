from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


class ValidationError(RuntimeError):
    """Raised when a publication-critical validation fails."""


@dataclass(frozen=True)
class ValidationMessage:
    level: str
    code: str
    message: str


def require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise ValidationError(f"Required columns missing: {missing}")


def validate_bottom30_prepared(frame: pd.DataFrame) -> list[ValidationMessage]:
    require_columns(frame, ["household_income_per_person", "person_weight"])

    if frame.empty:
        raise ValidationError("No valid records remain after preparation")

    if (frame["person_weight"] <= 0).any():
        raise ValidationError("Prepared data contains non-positive person weights")

    if frame["household_income_per_person"].isna().any():
        raise ValidationError("Prepared data contains missing per-person income")

    messages: list[ValidationMessage] = []

    if (frame["household_income_per_person"] < 0).any():
        messages.append(
            ValidationMessage(
                "info",
                "negative-income-retained",
                "Negative household money income exists and is retained per methodology.",
            )
        )

    return messages
