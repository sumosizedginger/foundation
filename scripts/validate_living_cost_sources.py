"""Retrieve official source artifacts, write provenance, and report gaps.

This auditor does not calculate living-cost headlines, Gap, or Adequacy.
A source being SOURCE_GAP / LICENSING_REVIEW / UNAVAILABLE is a reportable
result, not a programming failure.
"""

from __future__ import annotations

import json
import logging
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from foundation.living_cost.geo_join import execute_geo_join_audit
from foundation.living_cost.manifest import RetrievedSourceArtifact, generate_source_manifest
from foundation.sources.auto_insurance import download_naic_artifact
from foundation.sources.bea_rpp import download_bea_rpp_artifact
from foundation.sources.bls_ce import download_bls_ce_artifact
from foundation.sources.census_acs import (
    download_acs_county_population_artifact,
    generate_census_county_universe_report,
    parse_acs_county_population_json,
)
from foundation.sources.cms_marketplace import download_cms_marketplace_artifacts
from foundation.sources.eia import download_eia_gas_artifact
from foundation.sources.fhwa_nhts import download_fhwa_nhts_artifact
from foundation.sources.hud_fmr import download_hud_fmr_artifact, parse_hud_fmr_xlsx
from foundation.sources.meps import download_meps_artifact
from foundation.sources.usda_food import download_usda_food_artifact

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
METADATA_DIR = ROOT / "data" / "metadata"

REQUIRED_COMPONENTS = (
    "housing",
    "population_weights",
    "food",
    "health_premium",
    "health_oop",
    "mileage",
    "mpg",
    "gas",
    "insurance",
    "maintenance",
    "registration",
    "replacement",
    "connectivity",
    "essentials",
    "recreation",
    "rpp",
    "federal_tax",
    "state_tax",
    "local_tax",
)


def _as_list(value: object) -> list[RetrievedSourceArtifact]:
    if value is None:
        return []
    if isinstance(value, RetrievedSourceArtifact):
        return [value]
    if isinstance(value, dict):
        artifacts: list[RetrievedSourceArtifact] = []
        for item in value.values():
            artifacts.extend(_as_list(item))
        return artifacts
    if isinstance(value, list):
        artifacts = []
        for item in value:
            artifacts.extend(_as_list(item))
        return artifacts
    return []


def _safe_acquire(label: str, fn) -> list[RetrievedSourceArtifact]:
    try:
        return _as_list(fn())
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        logger.error("Failed to acquire %s: %s", label, exc)
        return []


def validate_sources_for_year(year: int) -> list[RetrievedSourceArtifact]:
    artifacts: list[RetrievedSourceArtifact] = []

    hud_arts = _safe_acquire(
        f"HUD FMR {year}",
        lambda: download_hud_fmr_artifact(year, CACHE_DIR),
    )
    artifacts.extend(hud_arts)

    census_arts = _safe_acquire(
        f"Census ACS {year}",
        lambda: download_acs_county_population_artifact(year, CACHE_DIR),
    )
    artifacts.extend(census_arts)

    hud_obs = []
    census_universe: dict = {}
    if hud_arts and hud_arts[0].local_cache_filename:
        hud_path = CACHE_DIR / hud_arts[0].local_cache_filename
        if hud_path.is_file():
            try:
                hud_obs = parse_hud_fmr_xlsx(
                    hud_path,
                    year,
                    retrieved_at=hud_arts[0].retrieved_at,
                    file_sha256=hud_arts[0].sha256,
                )
            except (
                OSError,
                ValueError,
                RuntimeError,
                TypeError,
                KeyError,
                zipfile.BadZipFile,
            ) as exc:
                logger.error("Failed to parse HUD FMR %s: %s", year, exc)
    if census_arts and census_arts[0].local_cache_filename:
        acs_path = CACHE_DIR / census_arts[0].local_cache_filename
        if acs_path.is_file():
            try:
                census_universe = parse_acs_county_population_json(
                    acs_path,
                    reference_year=year,
                    retrieved_at=census_arts[0].retrieved_at,
                    file_sha256=census_arts[0].sha256,
                )
                generate_census_county_universe_report(
                    census_universe,
                    METADATA_DIR / "census_county_universe.json",
                )
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
                logger.error("Failed to parse Census ACS %s: %s", year, exc)

    if hud_obs and census_universe:
        try:
            execute_geo_join_audit(
                census_county_universe=census_universe,
                hud_observations=hud_obs,
                reference_year=year,
                census_artifact_sha256=census_arts[0].sha256 if census_arts else "",
                hud_artifact_sha256=hud_arts[0].sha256 if hud_arts else "",
                output_path=METADATA_DIR / f"living_cost_geo_join_{year}.json",
            )
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
            logger.error("Failed HUD↔ACS join for %s: %s", year, exc)

    artifacts.extend(
        _safe_acquire(
            f"CMS Marketplace {year}",
            lambda: download_cms_marketplace_artifacts(year, CACHE_DIR),
        )
    )
    artifacts.extend(
        _safe_acquire(f"NHTS {year}", lambda: download_fhwa_nhts_artifact(year, CACHE_DIR))
    )
    artifacts.extend(
        _safe_acquire(f"BLS CE {year}", lambda: download_bls_ce_artifact(year, CACHE_DIR))
    )
    artifacts.extend(_safe_acquire(f"MEPS {year}", lambda: download_meps_artifact(year, CACHE_DIR)))
    artifacts.extend(
        _safe_acquire(f"BEA RPP {year}", lambda: download_bea_rpp_artifact(year, CACHE_DIR))
    )
    artifacts.extend(
        _safe_acquire(f"USDA Food {year}", lambda: download_usda_food_artifact(year, CACHE_DIR))
    )
    artifacts.extend(
        _safe_acquire(f"EIA gasoline {year}", lambda: download_eia_gas_artifact(year, CACHE_DIR))
    )
    artifacts.extend(_safe_acquire(f"NAIC {year}", lambda: download_naic_artifact(year, CACHE_DIR)))
    return artifacts


def _component_status(artifacts: list[RetrievedSourceArtifact], *source_ids: str) -> str:
    for source_id in source_ids:
        for art in artifacts:
            if art.source_id == source_id:
                return art.validation_status
    return "PARSER_READY_NOT_RETRIEVED"


def write_coverage(artifacts: list[RetrievedSourceArtifact]) -> dict:
    coverage_by_year: dict[str, dict[str, str]] = {}
    for year in (2024, 2026):
        coverage_by_year[str(year)] = {
            "housing": _component_status(artifacts, f"hud_fmr_{year}"),
            "population_weights": _component_status(artifacts, f"census_acs5_{year}"),
            "food": _component_status(artifacts, f"usda_food_low_cost_{year}"),
            "health_premium": _component_status(
                artifacts, f"cms_rate_puf_{year}", f"cms_marketplace_puf_{year}"
            ),
            "health_oop": _component_status(artifacts, f"meps_table1_{year}"),
            "mileage": _component_status(artifacts, f"fhwa_nhts_{year}"),
            "mpg": "SOURCE_GAP",
            "gas": _component_status(artifacts, f"eia_gas_price_{year}"),
            "insurance": _component_status(artifacts, f"naic_auto_ins_{year}"),
            "maintenance": "SOURCE_GAP",
            "registration": "SOURCE_GAP",
            "replacement": "SOURCE_GAP",
            "connectivity": "SOURCE_GAP",
            "essentials": _component_status(artifacts, f"bls_ce_{year}"),
            "recreation": _component_status(artifacts, f"bls_ce_{year}"),
            "rpp": _component_status(artifacts, f"bea_rpp_{year}"),
            "federal_tax": "PARSER_READY_NOT_RETRIEVED",
            "state_tax": "SOURCE_GAP",
            "local_tax": "SOURCE_GAP",
        }
    blocking = []
    for year, components in coverage_by_year.items():
        for name, status in components.items():
            if status not in {"VALIDATED", "MEASURED"}:
                blocking.append(f"{year}:{name}:{status}")

    coverage = {
        "report_type": "living_cost_source_coverage",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "question": "What still prevents the living-cost model from being calculated?",
        "required_components": list(REQUIRED_COMPONENTS),
        "coverage_by_year": coverage_by_year,
        "retrieved_artifacts": [
            {
                "source_id": a.source_id,
                "validation_status": a.validation_status,
                "sha256": a.sha256 or None,
                "byte_size": a.byte_size or None,
                "retrieved_at": a.retrieved_at or None,
                "notes": a.notes or None,
            }
            for a in artifacts
        ],
        "blocking_components": blocking,
        "headline_calculated": False,
        "gap_calculated": False,
        "adequacy_calculated": False,
    }
    coverage_path = METADATA_DIR / "living_cost_source_coverage.json"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    return coverage


def main() -> int:
    logger.info("Starting living cost sources validation...")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)

    all_artifacts: list[RetrievedSourceArtifact] = []
    for year in (2024, 2026):
        logger.info("Validating sources for %s...", year)
        all_artifacts.extend(validate_sources_for_year(year))

    manifest_path = METADATA_DIR / "living_cost_source_manifest.json"
    generate_source_manifest(all_artifacts, manifest_path)
    logger.info("Source manifest generated at %s", manifest_path)

    coverage = write_coverage(all_artifacts)
    logger.info(
        "Source coverage generated. Blocking components: %s",
        len(coverage["blocking_components"]),
    )
    logger.info("Validation complete. No living-cost headline was calculated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
