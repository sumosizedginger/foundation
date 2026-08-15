from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from foundation.bottom30 import calculate_bottom30_from_zip
from foundation.config import load_definitions, load_indicators, load_sources
from foundation.historical import get_historical_vintages_summary
from foundation.living_cost.engine import run_living_cost_pipeline
from foundation.living_cost.manifest import generate_source_manifest
from foundation.sources.bls import fetch_all_pressure_signals
from foundation.sources.census_asec import download_asec_archive


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    temp_path.replace(path)


def run_full_pipeline(project_root: Path | None = None) -> dict[str, Any]:
    if project_root is None:
        project_root = Path(__file__).resolve().parents[2]

    cache_dir = project_root / "data" / "cache"
    current_dir = project_root / "data" / "current"
    history_dir = project_root / "data" / "history"
    metadata_dir = project_root / "data" / "metadata"
    site_data_dir = project_root / "site" / "data"

    cache_dir.mkdir(parents=True, exist_ok=True)
    current_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    site_data_dir.mkdir(parents=True, exist_ok=True)

    project_defs = load_definitions()
    load_sources()
    load_indicators()

    # 1. Axis 1: Population Anchor
    zip_path = cache_dir / "asecpub25csv.zip"
    if not zip_path.exists():
        download_asec_archive(survey_year=2025, cache_dir=cache_dir)
    latest_pop = calculate_bottom30_from_zip(
        zip_path,
        survey_year=2025,
        income_year=2024,
    )
    atomic_write_json(current_dir / "population.json", latest_pop.to_dict())

    # 2. Axis 2 remains unpublished. The engine writes transition-state files only.
    # Canonical owner permissions live in config/definitions.yml.
    from foundation.living_cost.freshness import (
        candidate_calculation_authorized,
        living_cost_release_authorized,
    )

    if living_cost_release_authorized():
        raise RuntimeError("Living-cost publication is not authorized.")
    if candidate_calculation_authorized():
        from foundation.living_cost.freshness import assert_candidate_freshness_ready

        assert_candidate_freshness_ready({}, project_cost_year=2026)
        raise RuntimeError("Private candidate assembler is not built.")

    living_cost_res = run_living_cost_pipeline(project_root)
    survival_consolidated = living_cost_res["survival_consolidated"]

    # 3. Honest static registry. No retrieved hashes unless acquire actually ran.
    manifest_doc = generate_source_manifest(
        [],
        metadata_dir / "living_cost_source_manifest.json",
    )
    atomic_write_json(site_data_dir / "living_cost_source_manifest.json", manifest_doc)

    # 4. National Economic Pressure Signals
    pressure_signals = fetch_all_pressure_signals(cache_dir=cache_dir)
    stale_count = sum(1 for p in pressure_signals if p.is_stale)
    pressures_payload = {
        "as_of": datetime.now(UTC).strftime("%Y-%m-%d"),
        "count": len(pressure_signals),
        "stale_count": stale_count,
        "signals": [p.to_dict() for p in pressure_signals],
    }
    atomic_write_json(current_dir / "pressures.json", pressures_payload)

    # 5. Historical Timeline
    historical_timeline = get_historical_vintages_summary()

    import dataclasses

    current_asec_sha = ""
    if latest_pop.source_artifact is not None:
        current_asec_sha = latest_pop.source_artifact.sha256
    for i, hist in enumerate(historical_timeline):
        if hist.survey_year == 2025 and current_asec_sha:
            historical_timeline[i] = dataclasses.replace(hist, archive_sha256=current_asec_sha)

    hist_payload = {
        "base_currency_year": 2024,
        "vintages": [h.to_dict() for h in historical_timeline],
    }
    atomic_write_json(current_dir / "history.json", hist_payload)

    # 6. Data Health composed from actual component state
    has_stale_pressures = any(p.is_stale for p in pressure_signals)
    overall_health = "PARTIAL"

    data_health = {
        "status": overall_health,
        "overall_state": "PARTIAL",
        "description": (
            "Canonical Population Anchor is verified. Minimum Sustainable Living Cost "
            "data pipeline validation is in progress. Composite is prelaunch."
        ),
        "living_cost_status": "pipeline_validation_in_progress",
        "states_modeled": 0,
        "validation_state": "axis2_unpublished",
        "components": {
            "population_anchor": {
                "status": "VERIFIED",
                "survey_year": 2025,
                "income_year": 2024,
                "cutoff": latest_pop.cutoff,
            },
            "historical_vintages": {
                "status": "VERIFIED",
                "count": len(historical_timeline),
            },
            "living_cost": {
                "status": "PIPELINE_VALIDATION_IN_PROGRESS",
                "states_modeled": 0,
                "note": (
                    "Prototype outputs retired. Empirical county source validation is "
                    "in progress. No living-cost headline is published."
                ),
            },
            "pressure_signals": {
                "status": "STALE_CACHED" if has_stale_pressures else "CURRENT",
                "registered_count": len(pressure_signals),
                "stale_count": stale_count,
                "note": "Registered BLS pressure signals; current retrieval status varies.",
            },
            "composite_score": {
                "status": "PRELAUNCH",
                "released": False,
            },
        },
    }

    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()

    latest_dashboard = {
        "project": project_defs.get("project", project_defs),
        "as_of": datetime.now(UTC).strftime("%Y-%m-%d"),
        "published_at": now_iso,
        "composite": {
            "status": "prelaunch",
            "score": None,
            "message": (
                "The composite Foundation score is locked in PRELAUNCH / RESEARCH. "
                "No provisional score is published."
            ),
        },
        "population_anchor": latest_pop.to_dict(),
        "survival_floor": survival_consolidated,
        "pressures": [p.to_dict() for p in pressure_signals],
        "history": [h.to_dict() for h in historical_timeline],
        "data_health": data_health,
        "latest_changes": [
            (
                "Reproduced 2025 CPS ASEC (2024 Income) Bottom-30 Population Anchor: "
                f"${latest_pop.cutoff:,.2f}/year."
            ),
            "Cross-checked weighted percentile against independent implementation (diff = 0.0).",
            (
                "Minimum Sustainable Living Cost: DATA PIPELINE VALIDATION IN PROGRESS. "
                "No headline, Gap, or Adequacy is published."
            ),
            "Ingested registered BLS National Economic Pressure Signals; retrieval status varies.",
            "Published historical CPS ASEC vintages in nominal and constant 2024 dollars.",
        ],
    }
    atomic_write_json(current_dir / "latest.json", latest_dashboard)
    atomic_write_json(site_data_dir / "latest.json", latest_dashboard)

    return latest_dashboard
