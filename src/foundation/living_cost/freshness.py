"""Enforceable freshness gate for a future candidate MSLC calculation.

This module does not calculate or publish a Minimum Sustainable Living Cost.
It only refuses a future candidate when freshness requirements are unmet.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

REQUIRED_FRESHNESS_FAMILIES: tuple[str, ...] = (
    "acs_population_weights",
    "hud_fmr",
    "usda_food",
    "cms_marketplace_sbe",
    "meps_full_year_consolidated",
    "nhts_mileage",
    "epa_vehicle",
    "eia_gasoline",
    "naic_auto_insurance",
    "bls_ce",
    "fcc_broadband",
    "mobile_price",
    "federal_tax_law",
    "state_tax_law",
    "local_tax_law",
    "vehicle_registration",
    "od010_price_index",
)

BLOCKING_EVIDENCE = {
    "SOURCE_GAP",
    "UNAVAILABLE",
    "INCOMPLETE_PROVENANCE",
    "FORMULA_FROZEN_INPUTS_PENDING",
    "INVENTORY_NOT_VALIDATED",
    "RETRIEVED_UNVALIDATED",
}


class FreshnessGateError(RuntimeError):
    """Future candidate calculation is not allowed."""


@dataclass(frozen=True)
class FreshnessCheck:
    source_id: str
    latest_checked_at: str
    latest_authoritative_vintage_found: str | None
    selected_vintage: str | None
    selected_artifact: str | None
    newer_data_exists: bool
    retrieval_validation_status: str
    reason_if_not_refreshed: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def freshness_gate_checklist() -> dict[str, Any]:
    return {
        "required_before_candidate_calculation": list(REQUIRED_FRESHNESS_FAMILIES),
        "if_newer_authoritative_data_exist": [
            "retrieve",
            "hash",
            "validate",
            "use",
        ],
        "do_not_recalculate_historical_2024_with_2026_prices": True,
        "headline_authorized_by_this_gate": False,
        "calculates_mslc": False,
    }


def assert_candidate_freshness_ready(
    checks: Iterable[FreshnessCheck] | dict[str, FreshnessCheck],
    *,
    project_cost_year: int,
    required_families: Iterable[str] = REQUIRED_FRESHNESS_FAMILIES,
    translation_index_bound: bool = False,
    silent_source_year_relabel: bool = False,
    living_cost_release_authorized: bool = False,
) -> None:
    """Refuse a future candidate calculation when freshness is incomplete.

    Does not compute MSLC, Gap, Adequacy, rankings, or a national median.
    """
    if not living_cost_release_authorized:
        raise FreshnessGateError(
            "living_cost_release_authorized is false; candidate calculation refused"
        )
    by_id: dict[str, FreshnessCheck]
    if isinstance(checks, dict):
        by_id = dict(checks)
    else:
        by_id = {item.source_id: item for item in checks}

    missing = [family for family in required_families if family not in by_id]
    if missing:
        raise FreshnessGateError(
            f"required freshness check was not performed: {', '.join(missing)}"
        )

    if silent_source_year_relabel:
        raise FreshnessGateError("source year is being silently relabeled")

    if not translation_index_bound:
        raise FreshnessGateError("required OD-010 translation index is not bound")

    for family in required_families:
        check = by_id[family]
        if not check.latest_checked_at:
            raise FreshnessGateError(f"{family}: freshness check has no latest_checked_at")
        if check.newer_data_exists:
            raise FreshnessGateError(
                f"{family}: newer authoritative source is known but not processed"
            )
        if check.retrieval_validation_status in BLOCKING_EVIDENCE:
            raise FreshnessGateError(
                f"{family}: required source remains {check.retrieval_validation_status}"
            )
        if check.selected_vintage and str(project_cost_year) not in str(check.selected_vintage):
            # Historical 2024 may select a 2024 vintage while current year is 2026.
            # Relabel detection is the silent_source_year_relabel flag plus
            # newer_data_exists. Do not treat a documented older structural
            # vintage as automatic failure.
            pass
