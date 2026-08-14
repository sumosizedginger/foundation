from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ComponentStatus(str, Enum):
    VALIDATED = "VALIDATED"
    RETRIEVED_UNVALIDATED = "RETRIEVED_UNVALIDATED"
    PARSER_READY_NOT_RETRIEVED = "PARSER_READY_NOT_RETRIEVED"
    MEASURED = "MEASURED"
    MODELED_FROM_MEASURED_INPUTS = "MODELED_FROM_MEASURED_INPUTS"
    ESTIMATED = "ESTIMATED"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"
    UNAVAILABLE = "UNAVAILABLE"
    SOURCE_GAP = "SOURCE_GAP"
    LICENSING_REVIEW = "LICENSING_REVIEW"


@dataclass(frozen=True)
class LivingCostComponentObservation:
    component_id: str
    category: str
    geography_type: str  # "county", "fmr_area", "state", "national"
    geography_id: str  # 5-digit FIPS or standard identifier
    geography_name: str
    state: str
    reference_year: int
    value_annual: float | None
    value_monthly: float | None
    unit: str
    status: ComponentStatus
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
        data = asdict(self)
        data["status"] = (
            self.status.value if isinstance(self.status, ComponentStatus) else str(self.status)
        )
        return data


@dataclass(frozen=True)
class LocalLivingCost:
    geography_id: str  # 5-digit County FIPS code
    geography_name: str
    state: str
    reference_year: int
    profile_id: str
    adult_population: int
    components: dict[str, float | None]
    net_needs_annual: float | None
    net_needs_monthly: float | None
    gross_required_income: float | None
    gross_required_monthly: float | None
    taxes: dict[str, float | None]
    status: ComponentStatus
    validation_state: str
    methodology_version: str
    calculated_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = (
            self.status.value if isinstance(self.status, ComponentStatus) else str(self.status)
        )
        return data


@dataclass(frozen=True)
class StateLivingCostDistribution:
    state: str
    state_name: str
    reference_year: int
    profile_id: str
    represented_adult_population: int
    locality_count: int
    status: ComponentStatus
    weighted_p25_gross: float | None
    weighted_median_gross: float | None
    weighted_p75_gross: float | None
    weighted_mean_gross: float | None
    min_locality_gross: float | None
    max_locality_gross: float | None
    weighted_median_net_needs: float | None
    methodology_version: str
    calculated_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = (
            self.status.value if isinstance(self.status, ComponentStatus) else str(self.status)
        )
        return data


@dataclass(frozen=True)
class NationalLivingCostDistribution:
    geography: str
    reference_year: int
    profile_id: str
    represented_adult_population: int
    locality_count: int
    weighted_p25_gross: float | None
    weighted_median_gross: float | None
    weighted_p75_gross: float | None
    weighted_mean_gross: float | None
    lowest_state_median: dict[str, Any] | None
    highest_state_median: dict[str, Any] | None
    status: ComponentStatus
    methodology_version: str
    calculated_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = (
            self.status.value if isinstance(self.status, ComponentStatus) else str(self.status)
        )
        return data
