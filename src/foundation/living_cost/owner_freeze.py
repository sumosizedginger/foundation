"""Owner-freeze record and executable methodology for OD-001 through OD-013.

This module freezes methodology. It does not calculate or publish a Minimum
Sustainable Living Cost, Gap, Adequacy Ratio, state rankings, national median,
or Composite.

METHODOLOGY FROZEN is not SOURCE VALIDATED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal

OWNER_FREEZE_EFFECTIVE_DATE = "2026-08-15"
OWNER_FREEZE_STATUS = "ACCEPTED"
METHODOLOGY_STATUS_FROZEN = "FROZEN"

# Global rule 3 — social/recreation floors in target-year dollars.
MINIMUM_SOCIAL_RECREATION_ANNUAL = 1200.0
PREFERRED_SOCIAL_RECREATION_ANNUAL = 2400.0
MINIMUM_SOCIAL_RECREATION_MONTHLY = 100.0
PREFERRED_SOCIAL_RECREATION_MONTHLY = 200.0

# OD-012 — no generic resilience / emergency / miscellaneous reserve.
CANONICAL_RESILIENCE_RESERVE_ANNUAL = 0.0

# OD-004 — used-car age window relative to project cost year.
USED_CAR_AGE_YEARS_LO = 8
USED_CAR_AGE_YEARS_HI = 12
CANONICAL_MPG_COHORT_ID = "used_compact_midsize_gasoline"
CANONICAL_MPG_STATISTIC = "median_mpg"
FORBIDDEN_HARDCODED_MPG = (24, 28, 32)

# OD-005 retired prototype constants — must not be defaults.
RETIRED_REPLACEMENT_ACQUISITION = 10000.0
RETIRED_REPLACEMENT_SALVAGE = 2000.0
RETIRED_REPLACEMENT_YEARS = 5.0
RETIRED_REPLACEMENT_ANNUAL = 1600.0

# OD-009
BROADBAND_DOWN_MBPS = 100
BROADBAND_UP_MBPS = 20
CANONICAL_CONNECTIVITY_COMPONENTS = ("mobile", "broadband")

CostYear = int
TranslationMethod = Literal[
    "LATEST_AVAILABLE",
    "RULE_YEAR",
    "YTD",
    "TARGET_YEAR_OBSERVATION",
    "CPI_UPDATED",
    "NONE_ALREADY_LOCAL",
    "SOURCE_GAP",
    "FORMULA_PENDING_INPUTS",
]
MunicipalClass = Literal["A", "B", "C", "D"]
AcsWeightMode = Literal["canonical", "fixed_2024_sensitivity"]


@dataclass(frozen=True)
class TranslationRecord:
    project_cost_year: int
    source_data_year: int | None
    translation_method: str
    price_index_series: str | None
    translation_factor: float | None
    original_value: float | None
    translated_value: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def select_acs_weight_vintage(
    cost_year: int,
    available_vintages: list[int] | tuple[int, ...],
    mode: AcsWeightMode = "canonical",
) -> int:
    """OD-001: freshest appropriate ACS 5-Year for current; lock historical 2024.

    Historical 2024 costs must not be rewritten with later population vintages.
    Current/2026 uses the newest available county-level ACS 5-Year vintage.
    Comparability sensitivity holds 2024 weights fixed.
    """
    vintages = sorted({int(v) for v in available_vintages})
    if not vintages:
        raise ValueError("No ACS 5-Year county vintages available")
    if mode == "fixed_2024_sensitivity":
        if 2024 not in vintages:
            raise ValueError("Fixed-2024-weight sensitivity requires a 2024 ACS vintage")
        return 2024
    if cost_year <= 2024:
        if 2024 in vintages:
            return 2024
        usable = [v for v in vintages if v <= 2024]
        if not usable:
            raise ValueError("No ACS vintage appropriate for historical 2024 costs")
        return max(usable)
    return max(vintages)


def select_meps_oop_statistic() -> dict[str, Any]:
    """OD-002: weighted mean primary; median and P75 required sensitivities."""
    return {
        "canonical": "weighted_mean",
        "population": "adults_18_64_privately_insured_independent_adult",
        "sensitivities": ["weighted_median", "weighted_p75"],
        "newest_listed_at_freeze": "HC-251",
        "newest_listed_data_year": 2023,
        "scheduled_next": "2024 Full Year Consolidated (AHRQ schedule: August 2026)",
        "use_2024_if_listed": True,
        "do_not_claim_unlisted_file": True,
    }


def select_nhts_mileage_statistic(stats: dict[str, float | None]) -> dict[str, Any]:
    """OD-003: weighted median is the Foundation Mobility Standard."""
    return {
        "canonical_statistic": "weighted_median",
        "canonical_label": "FOUNDATION MOBILITY STANDARD",
        "canonical_value": stats.get("weighted_median"),
        "not_a_label": "MEASURED MINIMUM NECESSARY MILEAGE",
        "sensitivities": {
            "p25": stats.get("weighted_p25"),
            "mean": stats.get("weighted_mean"),
            "p75": stats.get("weighted_p75"),
        },
        "forbidden_as_canonical": ["weighted_mean", "weighted_p25"],
    }


def used_car_model_year_window(cost_year: int) -> tuple[int, int]:
    """OD-004: approximately 8–12 model years old relative to project cost year."""
    return (cost_year - USED_CAR_AGE_YEARS_HI, cost_year - USED_CAR_AGE_YEARS_LO)


def select_epa_mpg_cohort(
    candidates: list[dict[str, Any]],
    cost_year: int,
) -> dict[str, Any]:
    """OD-004: used-car compact+midsize gasoline cohort; median MPG canonical."""
    window = used_car_model_year_window(cost_year)
    by_id = {c.get("id"): c for c in candidates}
    chosen = by_id.get(CANONICAL_MPG_COHORT_ID)
    if chosen is None:
        raise ValueError(f"Canonical MPG cohort {CANONICAL_MPG_COHORT_ID} missing from candidates")
    mpg = chosen.get(CANONICAL_MPG_STATISTIC)
    if mpg in FORBIDDEN_HARDCODED_MPG and chosen.get("n") in (None, 0):
        raise ValueError("Hardcoded 24/28/32 MPG is not an empirical cohort result")
    return {
        "cohort_id": CANONICAL_MPG_COHORT_ID,
        "statistic": CANONICAL_MPG_STATISTIC,
        "model_year_window": window,
        "value": mpg,
        "n": chosen.get("n"),
        "sensitivities": {
            "compact_only": by_id.get("used_compact_gasoline"),
            "midsize_only": by_id.get("used_midsize_gasoline"),
            "median": chosen.get("median_mpg"),
            "weighted_mean": chosen.get("mean_mpg"),
        },
        "hardcoded_mpg_forbidden": True,
    }


def vehicle_replacement_reserve(
    acquisition_cost: float | None,
    residual_value: float | None,
    usable_remaining_years: float | None,
) -> dict[str, Any]:
    """OD-005: freeze the formula, not unsupported numeric constants.

    ANNUAL = (acquisition - residual) / usable remaining years
    """
    params_present = (
        acquisition_cost is not None
        and residual_value is not None
        and usable_remaining_years is not None
    )
    annual: float | None = None
    if params_present:
        if usable_remaining_years <= 0:
            raise ValueError("usable_remaining_years must be positive")
        annual = (float(acquisition_cost) - float(residual_value)) / float(usable_remaining_years)
    return {
        "formula": "(acquisition_cost - residual_value) / usable_remaining_years",
        "measured": False,
        "acquisition_cost": acquisition_cost,
        "residual_value": residual_value,
        "usable_remaining_years": usable_remaining_years,
        "annual_reserve": annual,
        "numeric_value_currently_available": params_present,
        "retired_defaults_forbidden": {
            "acquisition": RETIRED_REPLACEMENT_ACQUISITION,
            "salvage": RETIRED_REPLACEMENT_SALVAGE,
            "years": RETIRED_REPLACEMENT_YEARS,
            "annual": RETIRED_REPLACEMENT_ANNUAL,
        },
        "sensitivities": ["acquisition_price", "usable_years", "residual_value"],
    }


def select_naic_insurance_measure() -> dict[str, Any]:
    """OD-006: combined average premium is canonical."""
    return {
        "canonical": "combined_average_premium",
        "sensitivities": [
            "average_expenditure",
            "mandatory_liability_only_where_reproducible",
        ],
        "newest_report_at_freeze": "2022/2023 Auto Insurance Database Report",
        "source_data_year": 2023,
        "lagged_dollar_translation": "CPI_UPDATED",
        "price_index_series": "CPI-U motor vehicle insurance",
        "redistribution_status": "FREE_DOWNLOAD_REDISTRIBUTION_UNCONFIRMED",
    }


PRODUCTION_MAINTENANCE_STAT_KEYS = (
    "mean_incl_zero",
    "median_incl_zero",
    "p25_positive",
    "p50_positive",
    "positive_spender_mean",
)


def _combined_maintenance_payload(candidates: dict[str, Any] | None) -> dict[str, Any]:
    """Accept the production artifact, a candidates wrapper, or a combined row."""
    payload = candidates or {}
    nested = payload.get("candidates")
    if isinstance(nested, dict) and "maintenance_repairs_tires_combined" in nested:
        combined = nested["maintenance_repairs_tires_combined"]
        if isinstance(combined, dict):
            return combined
    direct = payload.get("maintenance_repairs_tires_combined")
    if isinstance(direct, dict):
        return direct
    if any(key in payload for key in PRODUCTION_MAINTENANCE_STAT_KEYS):
        return payload
    return {}


def select_maintenance_statistic(candidates: dict[str, Any] | None = None) -> dict[str, Any]:
    """OD-007: weighted mean including zeros is canonical.

    Consumes the production parser/artifact schema:
    mean_incl_zero, median_incl_zero, p25_positive, p50_positive,
    positive_spender_mean.
    """
    combined = _combined_maintenance_payload(candidates)
    evidence = "INCOMPLETE_PROVENANCE"
    if isinstance(candidates, dict) and candidates.get("status"):
        evidence = str(candidates["status"])
    if evidence == "VALIDATED":
        # Methodology freeze does not convert incomplete retrieve into VALIDATED.
        evidence = "INCOMPLETE_PROVENANCE"
    return {
        "canonical": "weighted_mean_including_zeros",
        "canonical_value": combined.get("mean_incl_zero"),
        "sensitivities": {
            "median_including_zeros": combined.get("median_incl_zero"),
            "positive_spender_p25": combined.get("p25_positive"),
            "positive_spender_p50": combined.get("p50_positive"),
            "positive_spender_mean": combined.get("positive_spender_mean"),
        },
        "schema_keys": list(PRODUCTION_MAINTENANCE_STAT_KEYS),
        "multi_year_pool_preferred_when_available": True,
        "do_not_wait_indefinitely_for_multiple_years": True,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "evidence_status": evidence if evidence else "INCOMPLETE_PROVENANCE",
        "do_not_promote_to_validated_because_methodology_is_frozen": True,
    }


def apply_recreation_floor(
    empirical_amount: float | None,
    *,
    floor_annual: float,
) -> float:
    """Apply a normative floor in target-year dollars."""
    empirical = 0.0 if empirical_amount is None else float(empirical_amount)
    return max(empirical, float(floor_annual))


def canonical_social_recreation_annual(empirical_p25: float | None) -> float:
    """OD-008 canonical: MAX(empirical P25, $1,200/year)."""
    return apply_recreation_floor(empirical_p25, floor_annual=MINIMUM_SOCIAL_RECREATION_ANNUAL)


def preferred_social_recreation_annual(empirical_p25: float | None) -> float:
    """OD-008 preferred modest-life: MAX(empirical P25, $2,400/year)."""
    return apply_recreation_floor(empirical_p25, floor_annual=PREFERRED_SOCIAL_RECREATION_ANNUAL)


def recreation_output_pair(empirical_p25: float | None) -> dict[str, float]:
    """Future candidate output must show both standards."""
    return {
        "minimum_sustainable_annual": canonical_social_recreation_annual(empirical_p25),
        "preferred_modest_life_annual": preferred_social_recreation_annual(empirical_p25),
        "minimum_sustainable_monthly": canonical_social_recreation_annual(empirical_p25) / 12.0,
        "preferred_modest_life_monthly": preferred_social_recreation_annual(empirical_p25) / 12.0,
        "empirical_p25": 0.0 if empirical_p25 is None else float(empirical_p25),
    }


def canonical_connectivity_bundle() -> dict[str, Any]:
    """OD-009: one mobile line AND one residential broadband connection."""
    return {
        "canonical_components": list(CANONICAL_CONNECTIVITY_COMPONENTS),
        "requires_mobile": True,
        "requires_broadband": True,
        "mobile_only": "sensitivity_only",
        "broadband_only": "sensitivity_only",
        "broadband_standard_mbps": {
            "downstream": BROADBAND_DOWN_MBPS,
            "upstream": BROADBAND_UP_MBPS,
        },
        "mobile_standard": (
            "one ordinary low-cost unlimited or sufficiently high-data smartphone line; "
            "not zero-data, emergency-only, Lifeline, or family-plan sharing"
        ),
        "acs_is_not_a_price_source": True,
        "mobile_price_evidence_status": "SOURCE_GAP",
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "do_not_invent_mobile_price": True,
    }


def translation_method_for_component(
    component_class: Literal[
        "structural_quantity",
        "target_year_rule",
        "high_frequency_price",
        "lagged_nominal_dollar",
        "already_local_current_price",
    ],
) -> TranslationMethod:
    """OD-010 hybrid component-specific translation."""
    mapping: dict[str, TranslationMethod] = {
        "structural_quantity": "LATEST_AVAILABLE",
        "target_year_rule": "RULE_YEAR",
        "high_frequency_price": "YTD",
        "lagged_nominal_dollar": "CPI_UPDATED",
        "already_local_current_price": "NONE_ALREADY_LOCAL",
    }
    return mapping[component_class]


def translate_lagged_nominal_dollars(
    original_value: float,
    *,
    project_cost_year: int,
    source_data_year: int,
    translation_method: str,
    price_index_series: str,
    translation_factor: float,
) -> TranslationRecord:
    """Apply CPI_UPDATED. Refuse silent LATEST_AVAILABLE nominal carry-forward."""
    if translation_method == "LATEST_AVAILABLE":
        raise ValueError(
            "lagged nominal dollars cannot use silent LATEST_AVAILABLE "
            "nominal carry-forward (OD-010)"
        )
    if translation_method != "CPI_UPDATED":
        raise ValueError(f"lagged nominal dollars must use CPI_UPDATED, got {translation_method}")
    if translation_factor <= 0:
        raise ValueError("translation_factor must be positive")
    translated = round(float(original_value) * float(translation_factor), 2)
    return TranslationRecord(
        project_cost_year=project_cost_year,
        source_data_year=source_data_year,
        translation_method="CPI_UPDATED",
        price_index_series=price_index_series,
        translation_factor=float(translation_factor),
        original_value=float(original_value),
        translated_value=translated,
    )


def classify_municipal_tax_geography(
    *,
    tax_applies_throughout_modeled_county: bool | None,
    tax_is_county_level: bool | None,
    municipality_covers_only_part_of_county: bool | None,
    geography_resolved: bool = True,
) -> MunicipalClass:
    """OD-011: A coterminous / B county-level / C partial / D unresolved."""
    if not geography_resolved:
        return "D"
    if tax_is_county_level is True:
        return "B"
    if tax_applies_throughout_modeled_county is True:
        return "A"
    if municipality_covers_only_part_of_county is True:
        return "C"
    return "D"


def local_tax_application_rule(
    classification: MunicipalClass,
    *,
    place_level_supported: bool = False,
    population_weighted_exposure_defensible: bool = False,
) -> dict[str, Any]:
    """Never apply a partial-city tax automatically to an entire county."""
    if classification in {"A", "B"}:
        return {
            "apply": True,
            "method": "direct",
            "status": "APPLY_DIRECT",
        }
    if classification == "C":
        if place_level_supported:
            return {
                "apply": True,
                "method": "place_subcounty",
                "status": "PLACE_LEVEL",
            }
        if population_weighted_exposure_defensible:
            return {
                "apply": True,
                "method": "population_weighted_exposure",
                "status": "WEIGHTED_EXPOSURE",
            }
        return {
            "apply": False,
            "method": None,
            "status": "SOURCE_GAP",
            "reason": ("partial-city tax cannot be applied automatically to entire county"),
        }
    return {
        "apply": False,
        "method": None,
        "status": "UNAVAILABLE",
        "reason": "unresolved municipal tax geography",
    }


def canonical_resilience_reserve() -> float:
    """OD-012: no additional generic resilience reserve."""
    return CANONICAL_RESILIENCE_RESERVE_ANNUAL


def connecticut_geography_method(hud_fiscal_year: int) -> str:
    """OD-013: reconstruct FY2024 legacy counties; direct-join FY2026 planning regions."""
    if hud_fiscal_year == 2024:
        return "legacy_county_reconstructed_from_cousub"
    if hud_fiscal_year >= 2026:
        return "direct_planning_region_join"
    raise ValueError(f"No frozen CT geography method for HUD FY{hud_fiscal_year}")


def food_plan_selection() -> dict[str, str]:
    return {
        "canonical": "usda_low_cost_food_plan",
        "sensitivity": "usda_thrifty_food_plan",
        "incomplete_year": "YTD",
    }


def health_premium_profile() -> dict[str, Any]:
    return {
        "age": 40,
        "household": "single",
        "smoker": False,
        "dependents": 0,
        "subsidy": False,
        "medicaid": False,
        "employer_contribution": False,
        "market": "aca_compliant_individual_major_medical",
        "metal": "Silver",
        "selection": "deterministic_lowest_qualifying_silver_in_actual_geography",
        "fake_deductible_or_rating_area_fallback": False,
    }


def housing_standard() -> dict[str, Any]:
    return {
        "unit": "independent_1_bedroom",
        "source": "HUD_FMR",
        "roommate": False,
        "room_rental": False,
        "homeownership": False,
        "cheapest_theoretical": False,
        "double_count_hud_tenant_utilities": False,
    }


def freshness_gate_checklist() -> dict[str, Any]:
    """Must re-check volatile sources before any future candidate MSLC calculation."""
    from foundation.living_cost.freshness import (
        REQUIRED_FRESHNESS_FAMILIES,
    )
    from foundation.living_cost.freshness import (
        freshness_gate_checklist as _enforceable_checklist,
    )

    payload = _enforceable_checklist()
    payload["legacy_named_families"] = list(REQUIRED_FRESHNESS_FAMILIES[:5])
    return payload


def living_cost_release_authorized() -> bool:
    """Public headline publication is not authorized."""
    from foundation.living_cost.freshness import (
        living_cost_release_authorized as _release,
    )

    return _release()


def candidate_calculation_authorized() -> bool:
    """Private unpublished candidate calculation is not authorized."""
    from foundation.living_cost.freshness import (
        candidate_calculation_authorized as _candidate,
    )

    return _candidate()


def public_states_modeled() -> int:
    return 0


# ---------------------------------------------------------------------------
# Machine-readable freeze record
# ---------------------------------------------------------------------------

FROZEN_DECISIONS: list[dict[str, Any]] = [
    {
        "id": "OD-001",
        "title": "ACS geographic population weights",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "Use the newest authoritative ACS 5-Year county/county-equivalent adult "
            "18+ vintage actually available and appropriate at calculation time. "
            "Do not permanently freeze an obsolete ACS vintage. Historical 2024 "
            "costs use 2024 ACS 5-Year weights and must not be rewritten with later "
            "population vintages. Current/2026 costs use the newest available ACS "
            "5-Year county vintage (today: 2024). Retain a fixed-2024-weight "
            "sensitivity for longitudinal comparison."
        ),
        "owner_rationale": (
            "Freshest appropriate weights answer the current question. A fixed-2024 "
            "sensitivity answers how costs changed holding geographic mix constant."
        ),
        "implementation_rule": (
            "select_acs_weight_vintage(cost_year, available, mode=canonical|fixed_2024_sensitivity)"
        ),
        "source_selection_rule": (
            "Newest ACS 5-Year county adult-population vintage that exists at run time; "
            "historical 2024 locked to 2024 ACS 5-Year."
        ),
        "required_sensitivity": ["fixed_2024_weight"],
        "known_evidence_gaps": [],
        "numeric_value_currently_available": True,
        "evidence_status": "VALIDATED",
        "current_vintage_as_of_freeze": 2024,
    },
    {
        "id": "OD-002",
        "title": "MEPS out-of-pocket healthcare",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "Canonical statistic is the weighted mean annual OOP among adults 18–64 "
            "who are privately insured in the independent-adult reference population. "
            "Required sensitivities: weighted median and weighted P75. Use the newest "
            "Full Year Consolidated MEPS file actually released when the candidate "
            "calculation runs. At freeze time that file is HC-251 / 2023."
        ),
        "owner_rationale": (
            "Medical spending is skewed and episodic. A median underfunds expected "
            "long-run healthcare. The budget should represent expected annual burden."
        ),
        "implementation_rule": "canonical=weighted_mean; sensitivities=weighted_median,weighted_p75",
        "source_selection_rule": (
            "If 2024 Full Year Consolidated is listed on the official MEPS PUF page, "
            "retrieve/hash/validate/use it. Otherwise HC-251 with true source year 2023."
        ),
        "required_sensitivity": ["weighted_median", "weighted_p75"],
        "known_evidence_gaps": [
            "2024 Full Year Consolidated not listed as of owner freeze; scheduled August 2026"
        ],
        "numeric_value_currently_available": False,
        "evidence_status": "RETRIEVED_UNVALIDATED",
        "newest_listed_puf": "HC-251",
        "source_data_year": 2023,
    },
    {
        "id": "OD-003",
        "title": "Necessary annual vehicle mileage",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "Canonical mobility requirement is the NHTS weighted median observed "
            "annual mileage for one-person, one-worker, age 18–64 licensed-driver "
            "households with valid annual vehicle mileage. Label: FOUNDATION MOBILITY "
            "STANDARD derived from observed NHTS median. Do not use the mean "
            "(~19,000) as minimum necessary. Do not use P25 as canonical."
        ),
        "owner_rationale": (
            "The mean is pulled by high-mileage households. P25 risks unusually "
            "constrained mobility. The median is the modest observed standard."
        ),
        "implementation_rule": "canonical=weighted_median; sensitivities=P25,mean,P75",
        "source_selection_rule": "Latest available NHTS microdata (structural quantity; do not inflate miles).",
        "required_sensitivity": ["weighted_p25", "weighted_mean", "weighted_p75"],
        "known_evidence_gaps": [],
        "numeric_value_currently_available": True,
        "evidence_status": "MEASURED",
        "approximate_canonical_value": 10000.0,
        "label": "FOUNDATION MOBILITY STANDARD",
    },
    {
        "id": "OD-004",
        "title": "Reference vehicle / MPG",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "Used-car cohort: gasoline non-BEV/non-PHEV compact + midsize passenger "
            "cars, model years approximately 8–12 years before the project cost year. "
            "Canonical MPG is the cohort median estimated real-world combined MPG. "
            "Do not freeze 24 / 28 / 32."
        ),
        "owner_rationale": (
            "A modest reliable used car, not a new car, luxury car, cherry-picked "
            "efficient model, or $1,500 beater."
        ),
        "implementation_rule": (
            "canonical cohort=used_compact_midsize_gasoline; statistic=median_mpg; "
            "window=cost_year-12 .. cost_year-8"
        ),
        "source_selection_rule": (
            "Newest final authoritative EPA/DOE fueleconomy.gov vehicle file when "
            "extracting those historical model-year cohorts."
        ),
        "required_sensitivity": [
            "compact_only",
            "midsize_only",
            "median",
            "weighted_mean",
        ],
        "known_evidence_gaps": [
            "Production/sales weights not always available on the vehicle file"
        ],
        "numeric_value_currently_available": True,
        "evidence_status": "MODELED_FROM_MEASURED_INPUTS",
        "hardcoded_mpg_forbidden": [24, 28, 32],
    },
    {
        "id": "OD-005",
        "title": "Vehicle replacement reserve",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "ANNUAL REPLACEMENT RESERVE = (reference used-car acquisition cost - "
            "expected residual/salvage value) / expected remaining usable years. "
            "Formula is frozen. Numeric constants are not. Retired $10,000 / $2,000 "
            "/ 5 years / $1,600 must not be defaults."
        ),
        "owner_rationale": (
            "Pretending the existing vehicle lasts forever understates sustainable "
            "transportation. The model is explicit and is not MEASURED."
        ),
        "implementation_rule": "vehicle_replacement_reserve(acquisition, residual, years)",
        "source_selection_rule": (
            "Newest reproducible authoritative/defensible used-vehicle price source; "
            "defensible vehicle-age/survival evidence; documented residual."
        ),
        "required_sensitivity": ["acquisition_price", "usable_years", "residual_value"],
        "known_evidence_gaps": [
            "Authoritative used-vehicle acquisition price not yet bound",
            "Usable remaining life evidence not yet bound",
            "Residual/salvage value not yet bound",
        ],
        "numeric_value_currently_available": False,
        "evidence_status": "FORMULA_FROZEN_INPUTS_PENDING",
        "formula_frozen": True,
    },
    {
        "id": "OD-006",
        "title": "Automobile insurance",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "Canonical insurance cost is the NAIC combined average premium where the "
            "relevant state statistic is available. Sensitivities: average expenditure "
            "and mandatory/liability-only where reproducible. Newest NAIC Auto "
            "Insurance Database as of freeze: 2022/2023 report, data through 2023. "
            "Translate later project years with OD-010 motor-vehicle-insurance CPI. "
            "Do not label 2023 NAIC dollars as 2026 dollars."
        ),
        "owner_rationale": (
            "Ordinary insurance capable of protecting a modest reliable vehicle, not "
            "merely the cheapest statutory liability-only policy."
        ),
        "implementation_rule": "canonical=combined_average_premium",
        "source_selection_rule": "Newest NAIC Auto Insurance Database Report actually available.",
        "required_sensitivity": [
            "average_expenditure",
            "mandatory_liability_only_where_reproducible",
        ],
        "known_evidence_gaps": [
            "State table extraction from the PDF is not yet a validated numeric series",
            "redistribution_status=FREE_DOWNLOAD_REDISTRIBUTION_UNCONFIRMED",
        ],
        "numeric_value_currently_available": False,
        "evidence_status": "RETRIEVED_UNVALIDATED",
        "source_data_year": 2023,
    },
    {
        "id": "OD-007",
        "title": "Maintenance / repairs / tires",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "Canonical annual reserve is the weighted mean including zero-spend "
            "periods among single-person vehicle-owning consumer units using the "
            "documented BLS CE VQB/MTBI architecture. Prefer a multi-year "
            "pooled/averaged estimate if multiple reproducible recent CE vintages "
            "later become available. Do not wait indefinitely before a first candidate."
        ),
        "owner_rationale": (
            "Maintenance is lumpy. Positive-spender-only overstates frequency. "
            "Median including zeros can underfund expected cost."
        ),
        "implementation_rule": "canonical=weighted_mean_including_zeros",
        "source_selection_rule": (
            "Official Interview VQB (VQBCODE/VQBEXPX) joined to FMLI single-person "
            "vehicle-owning CUs; official MTBI VQBEXPX→UCC map. UCC 470212 excluded."
        ),
        "required_sensitivity": [
            "median_including_zeros",
            "positive_spender_p25",
            "positive_spender_p50",
            "positive_spender_mean",
        ],
        "known_evidence_gaps": [
            "Official BLS CE re-retrieve remains HTTP 403; cache INCOMPLETE_PROVENANCE"
        ],
        "numeric_value_currently_available": True,
        "evidence_status": "INCOMPLETE_PROVENANCE",
        "do_not_convert_incomplete_provenance_to_validated": True,
        "current_2024_candidate_mean_incl_zero": 781.22,
    },
    {
        "id": "OD-008",
        "title": "Social & recreation",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "Empirical baseline is BLS CE weighted P25 among single-person positive "
            "spenders on the approved recreation/social allowlist. Canonical MSLC = "
            "MAX(empirical P25, $1,200/year). Preferred modest-life sensitivity = "
            "MAX(empirical P25, $2,400/year). Retain empirical P20/P25/P30. The "
            "$200/month case is PREFERRED MODEST-LIFE SOCIAL/RECREATION STANDARD, "
            "not a luxury case. Floors are consumption/social-participation "
            "standards, not emergency savings."
        ),
        "owner_rationale": (
            "Minimum sustainable life includes modest ordinary human/social "
            "participation. Empirical recreation must not fall below $100/month."
        ),
        "implementation_rule": (
            "canonical=max(ce_p25, 1200); preferred=max(ce_p25, 2400); transparency=P20,P25,P30"
        ),
        "source_selection_rule": "BLS CE Interview recreation/social allowlist; OD-010 if translating.",
        "required_sensitivity": [
            "preferred_modest_life_2400",
            "empirical_p20",
            "empirical_p25",
            "empirical_p30",
        ],
        "known_evidence_gaps": [
            "Official BLS CE re-retrieve remains HTTP 403; empirical P25 may be unavailable"
        ],
        "numeric_value_currently_available": True,
        "evidence_status": "INCOMPLETE_PROVENANCE",
        "minimum_annual_floor": MINIMUM_SOCIAL_RECREATION_ANNUAL,
        "preferred_annual_floor": PREFERRED_SOCIAL_RECREATION_ANNUAL,
    },
    {
        "id": "OD-009",
        "title": "Connectivity",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "Canonical minimum includes BOTH one mobile phone/data line AND one "
            "residential broadband connection. Mobile-only and broadband-only are "
            "sensitivities. Broadband target is the current ordinary FCC fixed-"
            "broadband benchmark (working standard 100/20 Mbps). Mobile is one "
            "ordinary low-cost unlimited or high-data smartphone line. ACS is not a "
            "price source. Do not invent a mobile price if no acceptable "
            "authoritative source exists."
        ),
        "owner_rationale": (
            "Normal functional modern participation, not the cheapest technically "
            "connected state and not a premium gigabit tier."
        ),
        "implementation_rule": "canonical=mobile+broadband; broadband=100/20; mobile=ordinary_unlimited",
        "source_selection_rule": (
            "Newest authoritative FCC evidence for broadband. Newest authoritative/"
            "reproducible mobile PRICE source; else SOURCE_GAP."
        ),
        "required_sensitivity": ["mobile_only", "broadband_only"],
        "known_evidence_gaps": [
            "FCC Urban Rate Survey retrieve has been HTTP 403",
            "No accepted authoritative mobile PRICE source (SOURCE_GAP)",
        ],
        "numeric_value_currently_available": False,
        "evidence_status": "SOURCE_GAP",
        "mobile_price_evidence": "SOURCE_GAP",
        "broadband_standard_mbps": {"down": 100, "up": 20},
    },
    {
        "id": "OD-010",
        "title": "Source lag / current-dollar translation",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "Hybrid component-specific system: structural quantities LATEST_AVAILABLE "
            "(do not inflate physical quantities); target-year laws RULE_YEAR; "
            "current high-frequency prices use actual target-year observations or YTD; "
            "lagged nominal dollar expenditure series CPI_UPDATED with the most "
            "component-specific authoritative price index; already-local current "
            "prices get no generic CPI on top. Every component stores project_cost_year, "
            "source_data_year, translation_method, price_index_series, translation_factor, "
            "original_value, translated_value. Never silently relabel old dollars. "
            "Lagged nominal dollars cannot use silent LATEST_AVAILABLE carry-forward."
        ),
        "owner_rationale": (
            "A single blanket LATEST_AVAILABLE rule is too coarse and silently "
            "relabels old dollars as current."
        ),
        "implementation_rule": "translation_method_for_component + translate_lagged_nominal_dollars",
        "source_selection_rule": (
            "Component-specific official CPI or better index: medical-care for MEPS; "
            "motor vehicle insurance for NAIC; motor vehicle maintenance/repair for CE "
            "maintenance; recreation CPI where defensible else CPI-U with disclosure."
        ),
        "required_sensitivity": ["unadjusted_LATEST_AVAILABLE_for_lagged_series"],
        "known_evidence_gaps": [
            "Component-specific index series not yet bound into a live translation table"
        ],
        "numeric_value_currently_available": True,
        "evidence_status": "RULE_FROZEN",
        "index_examples": {
            "meps_oop": "CPI-U medical care or better medical expenditure index",
            "naic_insurance": "CPI-U motor vehicle insurance",
            "ce_maintenance": "CPI-U motor vehicle maintenance and repair",
            "recreation": "recreation CPI where defensible, else CPI-U with disclosure",
            "essentials": "component-specific where practical, else CPI-U with disclosure",
        },
    },
    {
        "id": "OD-011",
        "title": "Municipal / local earned-income tax geography/overlay",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "Never apply a municipal tax to an entire county merely because one city "
            "inside the county levies it. Classify A coterminous municipality/"
            "county-equivalent; B true county-level tax; C municipality covering only "
            "part of modeled county; D unresolved. Apply A and B directly. For C, "
            "preferred method is place/subcounty calculation; else a transparent "
            "population-weighted municipal exposure only if legally and statistically "
            "defensible; else SOURCE_GAP/UNAVAILABLE. Do not silently ignore. Do not "
            "apply countywide. Do not construct statewide average local tax rates."
        ),
        "owner_rationale": (
            "NYC boroughs and Philadelphia are coterminous county-equivalents; a "
            "partial city inside a larger county is not."
        ),
        "implementation_rule": "classify_municipal_tax_geography + local_tax_application_rule",
        "source_selection_rule": (
            "Statutory geography first. Place/subcounty ACS population only if a "
            "reproducible join exists."
        ),
        "required_sensitivity": [
            "coterminous_overlay",
            "place_level",
            "unresolved_source_gap",
        ],
        "known_evidence_gaps": [
            "Place-level calculation is not yet generally supported",
            "Many local earned-income taxes remain SOURCE_GAP / unresolved",
        ],
        "numeric_value_currently_available": False,
        "evidence_status": "SOURCE_GAP",
    },
    {
        "id": "OD-012",
        "title": "Additional resilience reserve",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "No additional generic resilience reserve. Canonical extra reserve is $0. "
            "Do not add 5%, 10%, $1,200, $50/month, $100/month, or emergency savings. "
            "Annualize predictable irregular costs inside their actual component."
        ),
        "owner_rationale": (
            "The Bottom 30% benchmark is not a personal-finance-plan model. Generic "
            "savings double-count costs already annualized in components."
        ),
        "implementation_rule": "canonical_resilience_reserve() == 0",
        "source_selection_rule": "None. Future uncovered necessities are researched and added to the real category.",
        "required_sensitivity": [],
        "known_evidence_gaps": [],
        "numeric_value_currently_available": True,
        "evidence_status": "RULE_FROZEN",
        "canonical_extra_reserve_annual": 0.0,
    },
    {
        "id": "OD-013",
        "title": "Connecticut HUD/ACS geography treatment",
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "decision": (
            "FY2024: keep HUD cost geography = legacy county; reconstruct ACS adult "
            "population from official town/county-subdivision data using the official "
            "Census Connecticut crosswalk; aggregate into the eight legacy counties; "
            "join to HUD FY2024 legacy-county FMR. Do not invent planning-region rents. "
            "FY2026: HUD publishes planning-region FIPS; join directly to current ACS "
            "Connecticut planning-region geography. Preserve raw Census geography count, "
            "Foundation join geography count, transformation metadata, source hashes, "
            "and population reconciliation."
        ),
        "owner_rationale": (
            "HUD and Census published different Connecticut geographies in FY2024. "
            "The validated reconstruction already exists and must stay year-specific."
        ),
        "implementation_rule": (
            "2024=legacy_county_reconstructed_from_cousub; 2026=direct_planning_region_join"
        ),
        "source_selection_rule": (
            "Official Census CT county-to-county-subdivision crosswalk; ACS B01001 "
            "cousub adults; HUD FMR vintage geography as published."
        ),
        "required_sensitivity": [
            "reconcile_reconstructed_2024_legacy_county_adult_pop_to_ACS_CT_total"
        ],
        "known_evidence_gaps": [],
        "numeric_value_currently_available": True,
        "evidence_status": "VALIDATED",
        "fy2024_method": "legacy_county_reconstructed_from_cousub",
        "fy2026_method": "direct_planning_region_join",
    },
]


ADDITIONAL_FREEZES: dict[str, Any] = {
    "food": food_plan_selection(),
    "health_premium": health_premium_profile(),
    "housing": housing_standard(),
    "global_freshest_authoritative_data": True,
    "minimum_sustainable_definition": (
        "independent adult can pay rent, ordinary bills, adequate food, necessary "
        "transportation, auto insurance where a car is required, healthcare premiums "
        "and expected OOP, mobile+broadband, replace ordinary necessities, pay "
        "applicable taxes, and participate modestly in ordinary human/social life"
    ),
    "no_generic_savings_reserve": True,
}


def frozen_decision_by_id(decision_id: str) -> dict[str, Any]:
    for item in FROZEN_DECISIONS:
        if item["id"] == decision_id:
            return item
    raise KeyError(decision_id)


def all_ods_frozen() -> bool:
    ids = {item["id"] for item in FROZEN_DECISIONS}
    expected = {f"OD-{i:03d}" for i in range(1, 14)}
    if ids != expected:
        return False
    return all(
        item["status"] == OWNER_FREEZE_STATUS
        and item["methodology_status"] == METHODOLOGY_STATUS_FROZEN
        for item in FROZEN_DECISIONS
    )


def methodology_status_for_component(component: str) -> str:
    """Owner-freeze methodology status. Not an evidence/validation claim."""
    mapping = {
        "housing": METHODOLOGY_STATUS_FROZEN,
        "population_weights": METHODOLOGY_STATUS_FROZEN,
        "food": METHODOLOGY_STATUS_FROZEN,
        "health_premium": METHODOLOGY_STATUS_FROZEN,
        "health_oop": METHODOLOGY_STATUS_FROZEN,
        "mileage": METHODOLOGY_STATUS_FROZEN,
        "mpg": METHODOLOGY_STATUS_FROZEN,
        "gas": METHODOLOGY_STATUS_FROZEN,
        "insurance": METHODOLOGY_STATUS_FROZEN,
        "maintenance": METHODOLOGY_STATUS_FROZEN,
        "registration": "RULE_YEAR_PENDING_SOURCE",
        "replacement": METHODOLOGY_STATUS_FROZEN,
        "connectivity": METHODOLOGY_STATUS_FROZEN,
        "essentials": METHODOLOGY_STATUS_FROZEN,
        "recreation": METHODOLOGY_STATUS_FROZEN,
        "rpp": METHODOLOGY_STATUS_FROZEN,
        "federal_tax": METHODOLOGY_STATUS_FROZEN,
        "state_tax": METHODOLOGY_STATUS_FROZEN,
        "local_tax": METHODOLOGY_STATUS_FROZEN,
        "resilience": METHODOLOGY_STATUS_FROZEN,
    }
    return mapping.get(component, METHODOLOGY_STATUS_FROZEN)


def freeze_payload() -> dict[str, Any]:
    return {
        "report_type": "living_cost_owner_decisions_frozen",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "effective_date": OWNER_FREEZE_EFFECTIVE_DATE,
        "status": OWNER_FREEZE_STATUS,
        "methodology_status": METHODOLOGY_STATUS_FROZEN,
        "headline_calculated": False,
        "gap_calculated": False,
        "adequacy_calculated": False,
        "candidate_calculation_authorized": candidate_calculation_authorized(),
        "living_cost_release_authorized": living_cost_release_authorized(),
        "states_modeled": 0,
        "decisions_frozen": True,
        "all_ods_frozen": all_ods_frozen(),
        "methodology_frozen_is_not_source_validated": True,
        "global_rules": {
            "freshest_authoritative_data": True,
            "minimum_sustainable_not_deprivation": True,
            "social_recreation_floors": {
                "minimum_annual": MINIMUM_SOCIAL_RECREATION_ANNUAL,
                "preferred_annual": PREFERRED_SOCIAL_RECREATION_ANNUAL,
            },
            "no_generic_savings_reserve": True,
            "canonical_resilience_reserve_annual": CANONICAL_RESILIENCE_RESERVE_ANNUAL,
        },
        "additional_freezes": ADDITIONAL_FREEZES,
        "freshness_gate": freshness_gate_checklist(),
        "decisions": FROZEN_DECISIONS,
    }


def write_owner_freeze_record(metadata_dir) -> dict[str, Any]:
    """Write the frozen decision record. Does not calculate a headline."""
    from pathlib import Path

    payload = freeze_payload()
    metadata_dir = Path(metadata_dir)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / "living_cost_owner_decisions_frozen.json").write_text(
        __import__("json").dumps(payload, indent=2), encoding="utf-8"
    )
    lines = [
        "# Living-cost owner decisions FROZEN",
        "",
        f"Effective date: {OWNER_FREEZE_EFFECTIVE_DATE}",
        "",
        "Status: **ACCEPTED / FROZEN** for OD-001 through OD-013.",
        "",
        "No Minimum Sustainable Living Cost headline was calculated or published.",
        "",
        "`living_cost_release_authorized = false`. `states_modeled = 0`.",
        "",
        "**METHODOLOGY FROZEN is not SOURCE VALIDATED.** Evidence gaps remain.",
        "",
        "## Global rules",
        "",
        "1. Freshest authoritative data actually available at pipeline run time.",
        "2. Minimum sustainable ≠ extreme deprivation.",
        "3. Social/recreation floor $100/month canonical; $200/month preferred modest life.",
        "4. No generic savings / emergency / miscellaneous resilience reserve.",
        "",
        "## Recreation standards",
        "",
        (
            f"- MINIMUM SUSTAINABLE: at least ${MINIMUM_SOCIAL_RECREATION_ANNUAL:,.0f}/year "
            f"(${MINIMUM_SOCIAL_RECREATION_MONTHLY:,.0f}/month)."
        ),
        (
            f"- PREFERRED MODEST LIFE: at least ${PREFERRED_SOCIAL_RECREATION_ANNUAL:,.0f}/year "
            f"(${PREFERRED_SOCIAL_RECREATION_MONTHLY:,.0f}/month)."
        ),
        "",
        "Canonical MSLC uses the $100 floor. The $200 version is a named sensitivity.",
        "",
        "## Additional freezes",
        "",
        "- Food: USDA Low-Cost canonical; Thrifty is lower sensitivity; YTD if year incomplete.",
        "- Health premium: age 40, single, nonsmoker, no dependents, unsubsidized Silver.",
        "- Housing: independent 1-bedroom HUD FMR; no roommate; no utility double-count.",
        "",
        "## Freshness gate",
        "",
        (
            "Before any future candidate MSLC calculation, re-check MEPS Full Year "
            "Consolidated, USDA current-year months, CMS Marketplace/SBE, EIA gasoline, "
            "and current tax-law sources. Do not recalculate historical 2024 costs with "
            "2026 price observations."
        ),
        "",
    ]
    for item in FROZEN_DECISIONS:
        lines.extend(
            [
                f"## {item['id']} — {item['title']}",
                "",
                f"**Status:** {item['status']} / {item['methodology_status']}",
                f"**Effective date:** {item['effective_date']}",
                f"**Decision:** {item['decision']}",
                f"**Owner rationale:** {item['owner_rationale']}",
                f"**Implementation rule:** {item['implementation_rule']}",
                f"**Source-selection rule:** {item['source_selection_rule']}",
                f"**Required sensitivity:** {item['required_sensitivity']}",
                f"**Known evidence gaps:** {item['known_evidence_gaps']}",
                f"**Numeric value currently available:** {item['numeric_value_currently_available']}",
                f"**Evidence status:** {item['evidence_status']}",
                "",
            ]
        )
    (metadata_dir / "living_cost_owner_decisions_frozen.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return payload
