"""Enforceable freshness gate for a future PRIVATE candidate MSLC calculation.

This module does not calculate or publish a Minimum Sustainable Living Cost.
It only refuses a future candidate when authorization or freshness is unmet.

candidate_calculation_authorized:
    owner permission to calculate PRIVATE / UNPUBLISHED candidate outputs.

living_cost_release_authorized:
    owner permission to publish headline MSLC / rankings / Gap / Adequacy /
    Composite. Never implied by candidate authorization.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
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
    "bea_rpp",
    "federal_tax_law",
    "state_tax_law",
    "local_tax_law",
    "vehicle_registration",
    "vehicle_replacement",
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


def candidate_calculation_authorized() -> bool:
    """Private unpublished candidate calculation is not authorized."""
    return False


def living_cost_release_authorized() -> bool:
    """Public headline publication is not authorized."""
    return False


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
        "candidate_calculation_authorized": candidate_calculation_authorized(),
        "living_cost_release_authorized": living_cost_release_authorized(),
        "private_candidate_never_implies_publication": True,
    }


def assert_candidate_freshness_ready(
    checks: Iterable[FreshnessCheck] | dict[str, FreshnessCheck],
    *,
    project_cost_year: int,
    required_families: Iterable[str] = REQUIRED_FRESHNESS_FAMILIES,
    translation_index_bound: bool = False,
    silent_source_year_relabel: bool = False,
    candidate_calculation_authorized: bool = False,
    living_cost_release_authorized: bool = False,
) -> None:
    """Refuse a future PRIVATE candidate when freshness or candidate auth is incomplete.

    Does not compute MSLC, Gap, Adequacy, rankings, or a national median.
    Does not require living_cost_release_authorized (publication is a later gate).
    """
    del living_cost_release_authorized  # publication is a separate owner permission
    if not candidate_calculation_authorized:
        raise FreshnessGateError(
            "candidate_calculation_authorized is false; private candidate refused"
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
        if check.retrieval_validation_status == "VALIDATED":
            vintage = (check.latest_authoritative_vintage_found or "").strip()
            artifact = (check.selected_artifact or "").strip()
            if not vintage or not artifact or _is_placeholder_label(vintage, artifact):
                raise FreshnessGateError(
                    f"{family}: VALIDATED freshness record lacks a concrete vintage/artifact"
                )


def assert_public_release_authorized(*, living_cost_release_authorized: bool = False) -> None:
    """Public headline publication requires the separate release authorization."""
    if not living_cost_release_authorized:
        raise FreshnessGateError(
            "living_cost_release_authorized is false; public headline publication refused"
        )


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


_PLACEHOLDER_LABELS = {
    "latest retrieved bea rpp",
    "bea rpp artifact",
    "latest retrieved",
    "current artifact",
    "validated artifact",
}


def _is_placeholder_label(vintage: str, artifact: str) -> bool:
    labels = {vintage.strip().lower(), artifact.strip().lower()}
    return bool(labels & _PLACEHOLDER_LABELS)


def current_family_truth() -> dict[str, FreshnessCheck]:
    """Honest current-state freshness records. Do not fake readiness."""
    checked = _now_iso()
    specs: list[tuple[str, str, str | None, str | None, str]] = [
        (
            "acs_population_weights",
            "VALIDATED",
            "2024 ACS 5-Year B01001",
            "census_acs5_2024 / acsdt5y2024-b01001.dat",
            "Newest county-level ACS 5-Year vintage at check time is 2024; used for current and historical 2024. Fixed-2024 sensitivity retained.",
        ),
        (
            "hud_fmr",
            "VALIDATED",
            "FY2024 / FY2026",
            "FMR2024_final_revised.xlsx / FY26_FMRs_revised.xlsx",
            "Official HUD FY2024 and FY2026 county workbooks are the newest applicable FMR vintages.",
        ),
        (
            "usda_food",
            "MODELED_FROM_MEASURED_INPUTS",
            "target-year monthly reports / YTD",
            "usda food-plan monthly reports",
            "Canonical USDA Low-Cost; Thrifty sensitivity. Incomplete years use YTD.",
        ),
        (
            "cms_marketplace_sbe",
            "MODELED_FROM_MEASURED_INPUTS",
            "PY2024 / PY2026 Exchange PUF + SBE",
            "cms rate/plan/service-area PUF zips",
            "Federal PUF plus year-specific SBE archives. Not a published healthcare headline.",
        ),
        (
            "meps_full_year_consolidated",
            "RETRIEVED_UNVALIDATED",
            "HC-251 / 2023",
            "h251dat.zip",
            (
                "MEPS HEALTH OOP DERIVATION: RETRIEVED_UNVALIDATED. "
                "HC-251 downloaded is not sufficient. Still required: newest officially "
                "released Full Year Consolidated PUF; validate fixed-width/codebook parse; "
                "enforce age 18-64 privately insured filter; apply survey weights; derive "
                "weighted-mean canonical OOP; retain median/P75; hash/provenance; bind "
                "OD-010 medical price translation for lagged years."
            ),
        ),
        (
            "nhts_mileage",
            "VALIDATED",
            "2022 NHTS V2.1",
            "nhts_2022_csv.zip",
            "Structural quantity. Foundation Mobility Standard is weighted median. Do not inflate miles.",
        ),
        (
            "epa_vehicle",
            "RETRIEVED_UNVALIDATED",
            "EPA/DOE fueleconomy.gov vehicles.csv.zip",
            "epa_fueleconomy_vehicles.csv.zip",
            (
                "OD-004 methodology is FROZEN; EPA MPG evidence is RETRIEVED_UNVALIDATED. "
                "Before candidate readiness validate gasoline non-BEV/non-PHEV compact+"
                "midsize 8-12 model-year window median combined MPG from official rows; "
                "record artifact, vintage, model-year range, row count, filters, median, "
                "sensitivities, hash/provenance. Frozen methodology is not VALIDATED evidence."
            ),
        ),
        (
            "eia_gasoline",
            "VALIDATED",
            "EIA weekly retail gasoline",
            "pswrgvwall.xls",
            "High-frequency price. Use target-year observations / YTD.",
        ),
        (
            "naic_auto_insurance",
            "RETRIEVED_UNVALIDATED",
            "2022/2023 Auto Insurance Database Report / data through 2023",
            "publication-aut-pb-auto-insurance-database.pdf",
            "Official PDF retrieved. State-table extraction is not a validated numeric series.",
        ),
        (
            "bls_ce",
            "INCOMPLETE_PROVENANCE",
            "2024 Interview PUMD cache",
            "intrvw24.zip",
            "Official re-retrieve remains HTTP 403. Cached parse is not VALIDATED.",
        ),
        (
            "fcc_broadband",
            "SOURCE_GAP",
            None,
            None,
            "FCC Urban Rate Survey retrieve historically HTTP 403 / incomplete.",
        ),
        (
            "mobile_price",
            "SOURCE_GAP",
            None,
            None,
            "No accepted authoritative mobile PRICE source. Do not invent a price.",
        ),
        (
            "bea_rpp",
            "VALIDATED",
            "BEA SARPP All-items 2024 / current release February 19, 2026",
            "SARPP.zip",
            (
                "Official BEA RPP landing page still lists Current Release "
                "February 19, 2026 and Next release December 10, 2026. "
                "Newest official All-items state RPP data year is 2024. "
                "Selected artifact is apps.bea.gov/regional/zip/SARPP.zip "
                "(sha256 38713c6224c4c26ae020ffecd4549b82dca84f43d34f93dfdb43f4070cf011da; "
                "retrieved_at 2026-08-14T20:18:54Z). 2026 cost year reuses 2024 "
                "as LATEST_AVAILABLE and does not relabel the source year. "
                "This record — not a prior VALIDATED parse alone — establishes "
                "the vintage is still the newest appropriate authoritative release."
            ),
        ),
        (
            "federal_tax_law",
            "INVENTORY_NOT_VALIDATED",
            "2024 and 2026 statutory tables in code",
            None,
            "RULE_YEAR tables exist for 2024 and 2026 only. Inventory not validated against primary IRS/SSA artifacts.",
        ),
        (
            "state_tax_law",
            "SOURCE_GAP",
            "2024 and 2026 schedules in code",
            None,
            "State schedule inventory incomplete / unvalidated as applicable.",
        ),
        (
            "local_tax_law",
            "SOURCE_GAP",
            "MD county / NYC / Philadelphia verified; Harris County TX verified no local EIT",
            None,
            "Most county FIPS remain UNRESOLVED_SOURCE_GAP. Place-level class-C overlay not generally implemented.",
        ),
        (
            "vehicle_registration",
            "SOURCE_GAP",
            None,
            None,
            "No accepted 51-state official registration-fee inventory.",
        ),
        (
            "vehicle_replacement",
            "FORMULA_FROZEN_INPUTS_PENDING",
            None,
            None,
            (
                "OD-005 formula frozen: (acquisition - residual) / usable remaining years. "
                "Acquisition price, residual/salvage value, and usable remaining years "
                "are not bound. Do not invent numeric values."
            ),
        ),
        (
            "od010_price_index",
            "INVENTORY_NOT_VALIDATED",
            None,
            None,
            "Component-specific CPI/index series for lagged nominal dollars are not bound into a live translation table.",
        ),
    ]
    return {
        source_id: FreshnessCheck(
            source_id=source_id,
            latest_checked_at=checked,
            latest_authoritative_vintage_found=vintage,
            selected_vintage=vintage,
            selected_artifact=artifact,
            newer_data_exists=False,
            retrieval_validation_status=status,
            reason_if_not_refreshed=reason,
        )
        for source_id, status, vintage, artifact, reason in specs
    }


def evaluate_freshness_readiness(
    checks: dict[str, FreshnessCheck],
) -> dict[str, Any]:
    blocking: list[str] = []
    for family in REQUIRED_FRESHNESS_FAMILIES:
        check = checks.get(family)
        if check is None:
            blocking.append(f"{family}:CHECK_NOT_PERFORMED")
            continue
        if not check.latest_checked_at:
            blocking.append(f"{family}:MISSING_CHECKED_AT")
        if check.newer_data_exists:
            blocking.append(f"{family}:NEWER_DATA_NOT_PROCESSED")
        if check.retrieval_validation_status in BLOCKING_EVIDENCE:
            blocking.append(f"{family}:{check.retrieval_validation_status}")
        if check.retrieval_validation_status == "VALIDATED":
            vintage = (check.latest_authoritative_vintage_found or "").strip()
            artifact = (check.selected_artifact or "").strip()
            if not vintage or not artifact or _is_placeholder_label(vintage, artifact):
                blocking.append(f"{family}:VALIDATED_WITHOUT_CONCRETE_VINTAGE")
    authorized = candidate_calculation_authorized()
    return {
        "ready_for_private_candidate": authorized and not blocking,
        "candidate_calculation_authorized": authorized,
        "living_cost_release_authorized": living_cost_release_authorized(),
        "translation_index_bound": False,
        "blocker_count": len(blocking),
        "blockers": blocking,
        "headline_calculated": False,
    }


def write_candidate_freshness_report(metadata_dir: Path) -> dict[str, Any]:
    """Write a truthful fail-closed freshness artifact. Does not calculate MSLC."""
    checks = current_family_truth()
    readiness = evaluate_freshness_readiness(checks)
    payload = {
        "report_type": "living_cost_candidate_freshness",
        "generated_at": _now_iso(),
        "schema_version": "1.0",
        "calculates_mslc": False,
        "required_families": list(REQUIRED_FRESHNESS_FAMILIES),
        "checks": {key: check.to_dict() for key, check in checks.items()},
        **readiness,
        "notes": {
            "health_oop": (
                "MEPS HEALTH OOP DERIVATION: RETRIEVED_UNVALIDATED. "
                "Do not claim healthcare OOP ready merely because HC-251 was downloaded."
            ),
            "mpg": (
                "EPA MPG evidence is RETRIEVED_UNVALIDATED. "
                "OD-004 methodology FROZEN is not VALIDATED evidence."
            ),
            "vehicle_replacement": (
                "Formula frozen. Acquisition, residual, and usable years pending."
            ),
        },
    }
    metadata_dir.mkdir(parents=True, exist_ok=True)
    dest = metadata_dir / "living_cost_candidate_freshness.json"
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


BLOCKER_NOTES: dict[str, str] = {
    "health_oop": (
        "MEPS HEALTH OOP DERIVATION: RETRIEVED_UNVALIDATED. "
        "Tasks still required: use newest officially released Full Year Consolidated PUF; "
        "validate fixed-width/codebook parsing; enforce approved age/private-insurance "
        "filter; apply correct survey weights; derive weighted-mean canonical OOP; "
        "retain median/P75 sensitivity; produce source hash/provenance; bind OD-010 "
        "medical price translation for lagged years. Do not claim healthcare OOP ready "
        "merely because HC-251 was downloaded."
    ),
    "mpg": (
        "EPA MPG: RETRIEVED_UNVALIDATED. OD-004 methodology is FROZEN; evidence is not "
        "VALIDATED. Before candidate readiness validate gasoline non-BEV/non-PHEV "
        "compact+midsize 8-12 model-year window median combined MPG from official EPA/"
        "DOE rows. Record artifact, vintage, cohort model-year range, row count, filter "
        "criteria, median MPG, sensitivities, hash/provenance."
    ),
}


def stamp_source_coverage_from_current_truth(coverage_path: Path) -> dict[str, Any]:
    """Regenerate control metadata on the existing honest coverage file.

    Does not change evidence statuses to look better.
    """
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    coverage["generated_at"] = datetime.now(UTC).replace(microsecond=0).isoformat()
    coverage["candidate_calculation_authorized"] = False
    coverage["living_cost_release_authorized"] = False
    coverage["states_modeled"] = 0
    coverage["headline_calculated"] = False
    coverage["gap_calculated"] = False
    coverage["adequacy_calculated"] = False
    coverage["blocker_notes"] = dict(BLOCKER_NOTES)
    required_blockers = {
        "health_oop": "RETRIEVED_UNVALIDATED",
        "mpg": "RETRIEVED_UNVALIDATED",
        "maintenance": "INCOMPLETE_PROVENANCE",
        "essentials": "INCOMPLETE_PROVENANCE",
        "recreation": "INCOMPLETE_PROVENANCE",
        "insurance": "RETRIEVED_UNVALIDATED",
        "registration": "SOURCE_GAP",
        "replacement": "FORMULA_FROZEN_INPUTS_PENDING",
        "connectivity": "SOURCE_GAP",
        "federal_tax": "INVENTORY_NOT_VALIDATED",
        "state_tax": "SOURCE_GAP",
        "local_tax": "SOURCE_GAP",
    }
    for year, comps in coverage.get("coverage_by_year", {}).items():
        for name, expected in required_blockers.items():
            actual = comps.get(name)
            if actual != expected:
                raise ValueError(
                    f"coverage {year}.{name} is {actual!r}, expected {expected!r}; "
                    "do not alter evidence statuses to look better"
                )
    coverage_path.write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    return coverage
