from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class SourceArtifact:
    source_id: str
    url: str
    retrieved_at: str
    sha256: str
    bytes: int
    content_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationReport:
    archive_filename: str
    sha256: str
    survey_year: int
    income_year: int
    household_records: int
    person_records: int
    matched_person_records: int
    unmatched_person_records: int
    unmatched_household_records: int
    duplicate_household_keys: int
    raw_marsupwt_total: float
    scaled_represented_population: float
    weight_scale: int
    quantiles: dict[str, float]
    canonical_p30: float
    independent_reference_p30: float
    implementation_diff: float
    parser_version: str
    methodology_version: str
    calculated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Bottom30Result:
    survey_year: int
    income_year: int
    percentile: float
    cutoff: float
    monthly_cutoff: float
    valid_records: int
    excluded_records: int
    total_relative_weight: float
    represented_population: float
    weight_scale: int
    quantiles: dict[str, float]
    methodology_version: str
    calculated_at: str
    source_artifact: SourceArtifact | None = None
    validation_report: ValidationReport | None = None

    @classmethod
    def create(
        cls,
        *,
        survey_year: int,
        income_year: int,
        percentile: float,
        cutoff: float,
        valid_records: int,
        excluded_records: int,
        total_relative_weight: float,
        represented_population: float,
        weight_scale: int = 100,
        quantiles: dict[str, float] | None = None,
        methodology_version: str,
        source_artifact: SourceArtifact | None = None,
        validation_report: ValidationReport | None = None,
    ) -> Bottom30Result:
        return cls(
            survey_year=survey_year,
            income_year=income_year,
            percentile=percentile,
            cutoff=cutoff,
            monthly_cutoff=round(cutoff / 12.0, 2),
            valid_records=valid_records,
            excluded_records=excluded_records,
            total_relative_weight=total_relative_weight,
            represented_population=represented_population,
            weight_scale=weight_scale,
            quantiles=quantiles or {},
            methodology_version=methodology_version,
            calculated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            source_artifact=source_artifact,
            validation_report=validation_report,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = "measured"
        data["role"] = "population_anchor"
        data["definition"] = (
            "household money income / people in household; person-weighted 30th percentile"
        )
        return data


@dataclass(frozen=True)
class SurvivalComponent:
    category: str
    category_label: str
    annual_cost: float
    monthly_cost: float
    source_name: str
    source_agency: str
    source_url: str
    method: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HouseholdSurvivalFloor:
    household_size: int
    composition_label: str
    population_anchor_annual: float
    population_anchor_monthly: float
    survival_floor_annual: float
    survival_floor_monthly: float
    survival_gap_annual: float
    survival_gap_monthly: float
    adequacy_ratio: float
    adequacy_percent: int
    is_adequate: bool
    components: dict[str, float]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkComparison:
    name: str
    author: str
    url: str
    geography: str
    reference_year: int
    retrieved_at: str
    estimated_single_adult_annual: float
    methodological_divergence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SurvivalFloorResult:
    status: str
    status_label: str
    reference_year: int
    single_adult_floor_annual: float
    single_adult_floor_monthly: float
    population_anchor_annual: float
    survival_gap_annual: float
    adequacy_ratio: float
    adequacy_percent: int
    components: list[SurvivalComponent]
    household_matrix: list[HouseholdSurvivalFloor]
    methodology_version: str
    calculated_at: str
    benchmark_comparisons: dict[str, BenchmarkComparison]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "status_label": self.status_label,
            "reference_year": self.reference_year,
            "single_adult_floor_annual": self.single_adult_floor_annual,
            "single_adult_floor_monthly": self.single_adult_floor_monthly,
            "population_anchor_annual": self.population_anchor_annual,
            "survival_gap_annual": self.survival_gap_annual,
            "adequacy_ratio": self.adequacy_ratio,
            "adequacy_percent": self.adequacy_percent,
            "components": [c.to_dict() for c in self.components],
            "household_matrix": [h.to_dict() for h in self.household_matrix],
            "methodology_version": self.methodology_version,
            "calculated_at": self.calculated_at,
            "benchmark_comparisons": {
                k: v.to_dict() for k, v in self.benchmark_comparisons.items()
            },
        }


@dataclass(frozen=True)
class EconomicPressureObservation:
    series_id: str
    label: str
    category: str  # "labor" or "prices"
    observation_period: str  # e.g. "2025-12"
    year: int
    period_name: str
    value: float
    display_value: str
    unit: str
    metric_type: str  # "rate", "level", "price_inflation"
    mom_change_pct: float | None  # 1-month % change
    ann_3m_change_pct: float | None  # 3-month annualized % change
    yoy_change_pct: float | None  # 12-month % change
    direction_desired: str  # "lower_is_better" or "higher_is_better"
    publisher: str
    source_url: str
    seasonal_adjustment: str
    retrieved_at: str
    freshness_status: str  # "current", "stale", "cached"
    is_stale: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
