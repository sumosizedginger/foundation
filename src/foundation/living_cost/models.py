from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class LivingCostComponentObservation:
    component_id: str
    category: str
    geography_type: str  # "county", "fmr_area", "state", "national"
    geography_id: str  # FIPS code or identifier
    geography_name: str
    state: str
    reference_year: int
    value_annual: float
    value_monthly: float
    unit: str
    status: str
    source_id: str
    source_variable: str
    source_url: str
    source_release: str
    source_reference_period: str
    retrieved_at: str
    source_artifact_sha256: str
    methodology_version: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LocalLivingCost:
    geography_id: str
    geography_name: str
    state: str
    reference_year: int
    profile_id: str
    adult_population: int
    components: dict[str, float]
    net_needs_annual: float
    net_needs_monthly: float
    gross_required_income: float
    gross_required_monthly: float
    taxes: dict[str, float]
    status: str
    validation_state: str
    methodology_version: str
    calculated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StateLivingCostDistribution:
    state: str
    state_name: str
    reference_year: int
    profile_id: str
    represented_adult_population: int
    locality_count: int
    weighted_p25_gross: float
    weighted_median_gross: float
    weighted_p75_gross: float
    weighted_mean_gross: float
    min_locality_gross: float
    max_locality_gross: float
    weighted_median_net_needs: float
    methodology_version: str
    calculated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NationalLivingCostDistribution:
    geography: str
    reference_year: int
    profile_id: str
    represented_adult_population: int
    locality_count: int
    weighted_p25_gross: float
    weighted_median_gross: float
    weighted_p75_gross: float
    weighted_mean_gross: float
    lowest_state_median: dict[str, Any]
    highest_state_median: dict[str, Any]
    status: str
    methodology_version: str
    calculated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
