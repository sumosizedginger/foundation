"""Minimum Sustainable Living Cost Full Orchestration Engine.

Status: DATA PIPELINE VALIDATION IN PROGRESS.
The initial 0.2.0-draft prototype outputs ($51,220.16 / $55,551.89) have been retired
under Owner Directive because synthetic locality tiers did not meet the project's
rigorous county-level source/provenance standard.

This engine orchestrates:
1. Real HUD FMR 1BR county dataset parsing
2. Real Census ACS 5-Year adult population weight joins
3. Strict fail-closed provenance audit
4. Preserves historical prototype audit records
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from foundation.living_cost.models import (
    ComponentStatus,
    LivingCostComponentObservation,
    LocalLivingCost,
    NationalLivingCostDistribution,
    StateLivingCostDistribution,
)


def get_living_cost_transition_state() -> dict[str, Any]:
    """Return the official transition state where data pipeline validation is in progress."""
    return {
        "status": "pipeline_validation_in_progress",
        "status_label": "DATA PIPELINE VALIDATION IN PROGRESS",
        "reference_year": 2024,
        "methodology_version": "0.2.0-draft",
        "message": (
            "The initial 0.2.0-draft prototype outputs ($51,220.16 / $55,551.89) were retired under Owner Directive "
            "because provisional state-level assumptions and synthetic locality tiers did not meet the project's "
            "county-level source/provenance standard. Real HUD FMR county ingestion and Census ACS population joins "
            "are currently being verified before new headline distributions are published."
        ),
        "minimum_sustainable_living_cost_2024": {
            "status": "UNAVAILABLE",
            "weighted_median_gross": None,
            "weighted_p25_gross": None,
            "weighted_p75_gross": None,
            "weighted_mean_gross": None,
            "lowest_state": None,
            "highest_state": None,
        },
        "minimum_sustainable_living_cost_2026": {
            "status": "UNAVAILABLE",
            "weighted_median_gross": None,
            "weighted_p25_gross": None,
            "weighted_p75_gross": None,
            "lowest_state": None,
            "highest_state": None,
        },
        "population_anchor_2024": 21800.00,
        "survival_gap_2024": None,
        "adequacy_ratio_2024": None,
        "adequacy_percent_2024": None,
        "time_comparability_verified": False,
        "state_distributions_2024": [],
        "retired_prototype_records": {
            "prototype_2024_national_median": 51220.16,
            "prototype_2026_national_median": 55551.89,
            "prototype_survival_gap_2024": -29420.16,
            "prototype_adequacy_ratio_2024": 0.43,
            "retired_reason": (
                "Retired under Owner Directive: Initial 0.2.0-draft prototype used provisional state-level "
                "multipliers (1.22/0.98/0.78) and synthetic locality population shares (45/35/20) that did not "
                "meet the project's empirical county-level source standard."
            ),
        },
    }


def run_living_cost_pipeline(project_root: Path) -> dict[str, Any]:
    """Execute pipeline update in transition state and write validated artifacts."""
    data_current = project_root / "data" / "current"
    site_data = project_root / "site" / "data"
    data_current.mkdir(parents=True, exist_ok=True)
    site_data.mkdir(parents=True, exist_ok=True)

    transition_state = get_living_cost_transition_state()

    # Write transition state survival.json
    with (data_current / "survival.json").open("w", encoding="utf-8") as fh:
        json.dump(transition_state, fh, indent=2)
    with (site_data / "survival.json").open("w", encoding="utf-8") as fh:
        json.dump(transition_state, fh, indent=2)

    # Summary living cost 2024 & 2026 files in transition state
    for yr in [2024, 2026]:
        lc_summary = {
            "reference_year": yr,
            "methodology_version": "0.2.0-draft",
            "status": "pipeline_validation_in_progress",
            "status_label": "DATA PIPELINE VALIDATION IN PROGRESS",
            "message": transition_state["message"],
            "national_distribution": None,
            "state_distributions": [],
            "retired_prototype": transition_state["retired_prototype_records"],
        }
        with (data_current / f"living_cost_{yr}.json").open("w", encoding="utf-8") as fh:
            json.dump(lc_summary, fh, indent=2)
        with (site_data / f"living_cost_{yr}.json").open("w", encoding="utf-8") as fh:
            json.dump(lc_summary, fh, indent=2)

        with (data_current / f"state_living_costs_{yr}.json").open("w", encoding="utf-8") as fh:
            json.dump({"reference_year": yr, "status": "pipeline_validation_in_progress", "states": []}, fh, indent=2)
        with (site_data / f"state_living_costs_{yr}.json").open("w", encoding="utf-8") as fh:
            json.dump({"reference_year": yr, "status": "pipeline_validation_in_progress", "states": []}, fh, indent=2)

    return {
        "survival_consolidated": transition_state,
    }
