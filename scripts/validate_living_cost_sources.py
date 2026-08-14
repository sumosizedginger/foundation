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
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from foundation.living_cost.geo_join import execute_geo_join_audit
from foundation.living_cost.manifest import RetrievedSourceArtifact, generate_source_manifest
from foundation.living_cost.owner_packet import write_owner_decision_packet
from foundation.sources.acquisition import read_retrieval_sidecar, validation_status_after_parse
from foundation.sources.auto_insurance import download_naic_artifact
from foundation.sources.bea_rpp import download_bea_rpp_artifact
from foundation.sources.bls_ce import (
    download_bls_ce_artifact,
    parse_bls_ce_maintenance_candidates,
)
from foundation.sources.census_acs import (
    download_acs_county_population_artifact,
    generate_census_county_universe_report,
    parse_acs_county_population_json,
)
from foundation.sources.census_ct import (
    CT_PLANNING_REGION_FIPS,
    apply_legacy_ct_weights_to_universe,
    download_ct_crosswalk_artifact,
    parse_acs_ct_cousub_adults,
    parse_ct_crosswalk,
    reconstruct_legacy_county_adult_pop,
)
from foundation.sources.cms_marketplace import (
    download_cms_marketplace_artifacts,
    download_cms_sbe_artifact,
)
from foundation.sources.eia import download_eia_gas_artifact
from foundation.sources.epa_mpg import download_epa_mpg_artifact, parse_epa_mpg_candidates
from foundation.sources.fcc_urs import download_fcc_urs_artifact, parse_fcc_urs_broadband
from foundation.sources.fhwa_nhts import download_fhwa_nhts_artifact
from foundation.sources.hud_fmr import download_hud_fmr_artifact, parse_hud_fmr_xlsx
from foundation.sources.meps import check_meps_2024_full_year_listing, download_meps_artifact
from foundation.sources.usda_food import download_usda_food_artifact, month_coverage

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


def _ct_universe_for_2024_join(
    census_universe: dict,
) -> dict:
    """Use reconstructed legacy-county adult weights for FY2024 HUD geography only."""
    ct_path_xlsx = CACHE_DIR / "ct_cou_to_cousub_crosswalk.xlsx"
    ct_path_txt = CACHE_DIR / "ct_cou_to_cousub_crosswalk.txt"
    ct_path = ct_path_xlsx if ct_path_xlsx.exists() else ct_path_txt
    acs_dat = CACHE_DIR / "acsdt5y2024-b01001.dat"
    if not acs_dat.exists():
        for candidate in CACHE_DIR.glob("acsdt5y2024-b01001*"):
            acs_dat = candidate
            break
    if not ct_path.exists() or not acs_dat.exists():
        return census_universe
    reconstruction = reconstruct_legacy_county_adult_pop(
        parse_ct_crosswalk(ct_path),
        parse_acs_ct_cousub_adults(acs_dat),
    )
    if not reconstruction.get("reproduced"):
        return census_universe
    return apply_legacy_ct_weights_to_universe(census_universe, reconstruction)


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

    from dataclasses import replace

    if hud_obs and len(hud_obs) >= 3000:
        for i, art in enumerate(artifacts):
            if art.source_id == f"hud_fmr_{year}":
                artifacts[i] = replace(
                    art,
                    validation_status=validation_status_after_parse(art, parsed_ok=True),
                    notes=f"Parsed {len(hud_obs)} official county 1BR FMR rows.",
                )
    if census_universe and len(census_universe) >= 3000:
        for i, art in enumerate(artifacts):
            if art.source_id == f"census_acs5_{year}":
                artifacts[i] = replace(
                    art,
                    validation_status=validation_status_after_parse(art, parsed_ok=True),
                    notes=(
                        f"Parsed {len(census_universe)} county adult-population rows "
                        "from official 2024 ACS 5-Year B01001 summary file."
                    ),
                )

    if hud_obs and census_universe:
        try:
            join_universe = census_universe
            if year == 2024:
                join_universe = _ct_universe_for_2024_join(census_universe)
            census_sha = census_arts[0].sha256 if census_arts else ""
            hud_sha = hud_arts[0].sha256 if hud_arts else ""
            census_retrieved = census_arts[0].retrieved_at if census_arts else ""
            hud_retrieved = hud_arts[0].retrieved_at if hud_arts else ""
            if not census_sha and census_arts and census_arts[0].local_cache_filename:
                side = read_retrieval_sidecar(CACHE_DIR / census_arts[0].local_cache_filename)
                if side:
                    census_sha = str(side.get("sha256") or "")
                    census_retrieved = census_retrieved or str(side.get("retrieved_at") or "")
            if not hud_sha and hud_arts and hud_arts[0].local_cache_filename:
                side = read_retrieval_sidecar(CACHE_DIR / hud_arts[0].local_cache_filename)
                if side:
                    hud_sha = str(side.get("sha256") or "")
                    hud_retrieved = hud_retrieved or str(side.get("retrieved_at") or "")
            execute_geo_join_audit(
                census_county_universe=join_universe,
                hud_observations=hud_obs,
                reference_year=year,
                census_artifact_sha256=census_sha,
                hud_artifact_sha256=hud_sha,
                raw_census_county_universe=census_universe,
                census_source_id=census_arts[0].source_id if census_arts else f"census_acs5_{year}",
                hud_source_id=hud_arts[0].source_id if hud_arts else f"hud_fmr_{year}",
                census_reference_period="2024 ACS 5-Year B01001",
                hud_reference_period=str(year),
                census_retrieved_at=census_retrieved,
                hud_retrieved_at=hud_retrieved,
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
        _safe_acquire(f"CMS SBE {year}", lambda: download_cms_sbe_artifact(year, CACHE_DIR))
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
    artifacts.extend(
        _safe_acquire(f"EPA MPG {year}", lambda: download_epa_mpg_artifact(year, CACHE_DIR))
    )
    artifacts.extend(
        _safe_acquire(f"FCC URS {year}", lambda: download_fcc_urs_artifact(year, CACHE_DIR))
    )
    if year == 2024:
        artifacts.extend(
            _safe_acquire("Census CT crosswalk", lambda: download_ct_crosswalk_artifact(CACHE_DIR))
        )

    artifacts = _upgrade_parsed_artifacts(year, artifacts)
    return artifacts


def _upgrade_parsed_artifacts(
    year: int, artifacts: list[RetrievedSourceArtifact]
) -> list[RetrievedSourceArtifact]:
    """Promote retrieved archives to VALIDATED only after a real schema parse succeeds."""
    from dataclasses import replace

    from foundation.sources.bea_rpp import parse_bea_rpp_csv
    from foundation.sources.bls_ce import parse_bls_ce_microdata
    from foundation.sources.eia import parse_eia_gas_prices_csv
    from foundation.sources.fhwa_nhts import parse_fhwa_nhts_mileage
    from foundation.sources.usda_food import parse_usda_official_xlsx

    upgraded = list(artifacts)
    for i, art in enumerate(upgraded):
        if art.validation_status in {"SOURCE_GAP", "LICENSING_REVIEW", "UNAVAILABLE"}:
            continue
        if not art.local_cache_filename:
            continue
        path = CACHE_DIR / art.local_cache_filename
        if not path.is_file():
            continue
        try:
            if art.source_id.startswith("usda_food_low_cost"):
                rows = parse_usda_official_xlsx(path, reference_year=year, plan_key="low_cost")
                if rows:
                    months = month_coverage([str(r.get("month") or "") for r in rows])
                    upgraded[i] = replace(
                        art,
                        validation_status=validation_status_after_parse(art, parsed_ok=True),
                        notes=(
                            f"Parsed {len(rows)} official Low-Cost monthly rows for {year}. "
                            f"months_included={months['months_included']} "
                            f"month_count={months['month_count']} "
                            f"first_month={months['first_month']} last_month={months['last_month']}."
                        ),
                    )
            elif art.source_id.startswith("usda_food_thrifty"):
                rows = parse_usda_official_xlsx(path, reference_year=year, plan_key="thrifty")
                if rows:
                    months = month_coverage([str(r.get("month") or "") for r in rows])
                    upgraded[i] = replace(
                        art,
                        validation_status=validation_status_after_parse(art, parsed_ok=True),
                        notes=(
                            f"Parsed {len(rows)} official Thrifty monthly rows for {year}. "
                            f"months_included={months['months_included']} "
                            f"month_count={months['month_count']} "
                            f"first_month={months['first_month']} last_month={months['last_month']}."
                        ),
                    )
            elif art.source_id.startswith("usda_food_"):
                rows = parse_usda_official_xlsx(path, reference_year=year, plan_key="alaska")
                if rows:
                    months = month_coverage([str(r.get("month") or "") for r in rows])
                    upgraded[i] = replace(
                        art,
                        validation_status=validation_status_after_parse(art, parsed_ok=True),
                        notes=(
                            f"Parsed {len(rows)} official monthly rows for {year} "
                            f"{art.source_id}. months_included={months['months_included']} "
                            f"month_count={months['month_count']} "
                            f"first_month={months['first_month']} last_month={months['last_month']}."
                        ),
                    )
            elif art.source_id.startswith("bls_ce_"):
                obs = parse_bls_ce_microdata(
                    CACHE_DIR,
                    reference_year=year,
                    retrieved_at=art.retrieved_at,
                    file_sha256=art.sha256,
                )
                if obs and any(o.value_annual is not None for o in obs):
                    upgraded[i] = replace(
                        art,
                        validation_status=validation_status_after_parse(art, parsed_ok=True),
                        notes="Parsed official 2024 Interview FMLI single-person baskets.",
                    )
            elif art.source_id.startswith("bea_rpp_"):
                rpp = parse_bea_rpp_csv(CACHE_DIR, reference_year=year)
                if len(rpp) >= 50:
                    upgraded[i] = replace(
                        art,
                        validation_status=validation_status_after_parse(art, parsed_ok=True),
                        notes=f"Parsed {len(rpp)} official 2024 All-items state RPP values.",
                    )
            elif art.source_id.startswith("eia_gas_price_"):
                gas = parse_eia_gas_prices_csv(
                    CACHE_DIR,
                    reference_year=year,
                    retrieved_at=art.retrieved_at,
                    file_sha256=art.sha256,
                )
                if gas:
                    upgraded[i] = replace(
                        art,
                        validation_status=validation_status_after_parse(art, parsed_ok=True),
                        notes=(
                            f"Parsed {len(gas)} EIA regular retail series for {year}. "
                            "Regional/PADD series are not labeled state-measured."
                        ),
                    )
            elif art.source_id.startswith("fhwa_nhts_"):
                miles = parse_fhwa_nhts_mileage(
                    CACHE_DIR,
                    reference_year=year,
                    retrieved_at=art.retrieved_at,
                    file_sha256=art.sha256,
                )
                if miles.value_annual is not None:
                    upgraded[i] = replace(
                        art,
                        validation_status=validation_status_after_parse(art, parsed_ok=True),
                        notes=miles.notes,
                    )
            elif art.source_id.startswith("epa_mpg_"):
                cands = parse_epa_mpg_candidates(
                    CACHE_DIR,
                    reference_year=year,
                    retrieved_at=art.retrieved_at,
                    file_sha256=art.sha256,
                )
                if cands:
                    upgraded[i] = replace(
                        art,
                        validation_status=validation_status_after_parse(
                            art, parsed_ok=True, parsed_status="RETRIEVED_UNVALIDATED"
                        )
                        if not art.retrieved_at
                        else "RETRIEVED_UNVALIDATED",
                        notes=(
                            f"EPA MPG candidates parsed ({len(cands)} cohorts). "
                            "OD-004 not frozen. 24/28/32 are not the empirical model."
                        ),
                    )
            elif art.source_id.startswith("fcc_urs_"):
                obs = parse_fcc_urs_broadband(
                    CACHE_DIR,
                    reference_year=year,
                    retrieved_at=art.retrieved_at,
                    file_sha256=art.sha256,
                )
                if obs:
                    upgraded[i] = replace(
                        art,
                        validation_status="RETRIEVED_UNVALIDATED",
                        notes=obs[0].notes,
                    )
            elif art.source_id.startswith("naic_auto_ins_"):
                upgraded[i] = replace(
                    art,
                    validation_status="RETRIEVED_UNVALIDATED"
                    if art.sha256
                    else art.validation_status,
                )
            elif art.source_id.startswith("cms_sbe_puf_"):
                continue
            elif art.source_id.startswith("cms_sbe_"):
                with zipfile.ZipFile(path) as archive:
                    csv_members = [
                        name for name in archive.namelist() if name.lower().endswith(".csv")
                    ]
                if not csv_members:
                    upgraded[i] = replace(
                        art,
                        validation_status="SOURCE_GAP",
                        notes="SBE state archive has no CSV members (documentation-only).",
                    )
                else:
                    upgraded[i] = replace(
                        art,
                        validation_status="RETRIEVED_UNVALIDATED",
                        notes=f"SBE state archive integrity OK; {len(csv_members)} CSV members.",
                    )
            elif art.source_id.startswith("cms_") and art.local_cache_filename.endswith(".zip"):
                with zipfile.ZipFile(path) as archive:
                    csv_members = [
                        name for name in archive.namelist() if name.lower().endswith(".csv")
                    ]
                if csv_members:
                    upgraded[i] = replace(
                        art,
                        validation_status="RETRIEVED_UNVALIDATED",
                        notes=(
                            f"Archive integrity OK; CSV member {csv_members[0]}. "
                            "Component not VALIDATED until SBE states are joined."
                        ),
                    )
                else:
                    upgraded[i] = replace(
                        art,
                        validation_status="SOURCE_GAP",
                        notes="Archive has no CSV members (documentation-only).",
                    )
        except (
            OSError,
            ValueError,
            RuntimeError,
            TypeError,
            KeyError,
            zipfile.BadZipFile,
        ) as exc:
            logger.error("Parse upgrade failed for %s: %s", art.source_id, exc)
    return upgraded


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
            "food": "MODELED_FROM_MEASURED_INPUTS"
            if _component_status(artifacts, f"usda_food_low_cost_{year}")
            in {"VALIDATED", "MODELED_FROM_MEASURED_INPUTS", "RETRIEVED_UNVALIDATED"}
            else _component_status(artifacts, f"usda_food_low_cost_{year}"),
            "health_premium": "MODELED_FROM_MEASURED_INPUTS",
            "health_oop": _component_status(artifacts, f"meps_table1_{year}"),
            "mileage": _component_status(artifacts, f"fhwa_nhts_{year}"),
            "mpg": (
                "RETRIEVED_UNVALIDATED"
                if _component_status(artifacts, f"epa_mpg_{year}")
                in {"VALIDATED", "RETRIEVED_UNVALIDATED", "INCOMPLETE_PROVENANCE"}
                else "ESTIMATED_OWNER_REVIEW"
            ),
            "gas": _component_status(artifacts, f"eia_gas_price_{year}"),
            "insurance": _component_status(artifacts, f"naic_auto_ins_{year}"),
            "maintenance": "INCOMPLETE_PROVENANCE",
            "registration": "SOURCE_GAP",
            "replacement": "ESTIMATED_OWNER_REVIEW",
            "connectivity": (
                "RETRIEVED_UNVALIDATED"
                if _component_status(artifacts, f"fcc_urs_broadband_{year}")
                in {
                    "VALIDATED",
                    "RETRIEVED_UNVALIDATED",
                    "MODELED_FROM_MEASURED_INPUTS",
                    "INCOMPLETE_PROVENANCE",
                }
                else "SOURCE_GAP"
            ),
            "essentials": "MODELED_FROM_MEASURED_INPUTS"
            if _component_status(artifacts, f"bls_ce_{year}") == "VALIDATED"
            else _component_status(artifacts, f"bls_ce_{year}"),
            "recreation": "MODELED_FROM_MEASURED_INPUTS"
            if _component_status(artifacts, f"bls_ce_{year}") == "VALIDATED"
            else _component_status(artifacts, f"bls_ce_{year}"),
            "rpp": _component_status(artifacts, f"bea_rpp_{year}"),
            "federal_tax": "INVENTORY_NOT_VALIDATED",
            "state_tax": "SOURCE_GAP",
            "local_tax": "SOURCE_GAP",
        }
    blocking = []
    for year, components in coverage_by_year.items():
        for name, status in components.items():
            if status not in {
                "VALIDATED",
                "MEASURED",
                "MODELED_FROM_MEASURED_INPUTS",
            }:
                blocking.append(f"{year}:{name}:{status}")

    coverage = {
        "report_type": "living_cost_source_coverage",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "question": "What still prevents the living-cost model from being calculated?",
        "required_components": list(REQUIRED_COMPONENTS),
        "coverage_by_year": coverage_by_year,
        "source_lag": {
            "housing": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2026},
                "translation_method": "NONE",
            },
            "population_weights": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2024},
                "translation_method": "LATEST_AVAILABLE",
            },
            "food": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2026},
                "translation_method": {"2024": "NONE", "2026": "YTD"},
            },
            "health_premium": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2026},
                "translation_method": "NONE",
            },
            "health_oop": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2023, "2026": 2023},
                "translation_method": "CPI_UPDATED",
                "price_index_series": "CPI-U medical care recommended for lagged MEPS OOP dollars (not applied; OD-010 unfrozen)",
            },
            "mileage": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2022, "2026": 2022},
                "translation_method": "LATEST_AVAILABLE",
            },
            "gas": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2026},
                "translation_method": "NONE",
            },
            "essentials": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2024},
                "translation_method": {"2024": "NONE", "2026": "CPI_UPDATED"},
                "price_index_series": {
                    "2024": None,
                    "2026": "CPI-U recommended for lagged nominal CE dollar series (not applied; OD-010 unfrozen)",
                },
            },
            "recreation": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2024},
                "translation_method": {"2024": "NONE", "2026": "CPI_UPDATED"},
                "price_index_series": {
                    "2024": None,
                    "2026": "CPI-U recommended for lagged nominal CE dollar series (not applied; OD-010 unfrozen)",
                },
            },
            "rpp": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2024},
                "translation_method": "LATEST_AVAILABLE",
            },
            "federal_tax": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2026},
                "translation_method": "RULE_YEAR",
            },
            "mpg": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2024},
                "translation_method": "LATEST_AVAILABLE",
            },
            "insurance": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2023, "2026": 2023},
                "translation_method": "CPI_UPDATED",
                "price_index_series": "CPI-U motor vehicle insurance recommended for 2023 NAIC dollars (not applied; OD-006/OD-010 unfrozen)",
            },
            "maintenance": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2024},
                "translation_method": {"2024": "NONE", "2026": "CPI_UPDATED"},
                "price_index_series": {
                    "2024": None,
                    "2026": "CPI-U motor vehicle maintenance and repair recommended (not applied; OD-007/OD-010 unfrozen)",
                },
            },
            "registration": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": None, "2026": None},
                "translation_method": "SOURCE_GAP",
            },
            "replacement": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": None, "2026": None},
                "translation_method": "ESTIMATED_OWNER_REVIEW",
            },
            "connectivity": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2026},
                "translation_method": {"2024": "YTD", "2026": "YTD"},
                "price_index_series": None,
            },
            "state_tax": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": 2024, "2026": 2026},
                "translation_method": "RULE_YEAR",
            },
            "local_tax": {
                "project_cost_year": {"2024": 2024, "2026": 2026},
                "source_data_year": {"2024": None, "2026": None},
                "translation_method": "SOURCE_GAP",
            },
        },
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
        "status_dimensions": {
            "note": (
                "evidence_status is source retrieve/parse honesty. "
                "methodology_status is whether an owner decision is still required. "
                "They are not synonyms. An official parse with incomplete retrieval "
                "is INCOMPLETE_PROVENANCE, not a guessed estimate."
            ),
            "by_year": {
                year: {
                    "housing": {
                        "evidence_status": coverage_by_year[year]["housing"],
                        "methodology_status": "READY",
                    },
                    "population_weights": {
                        "evidence_status": coverage_by_year[year]["population_weights"],
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "food": {
                        "evidence_status": coverage_by_year[year]["food"],
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "health_premium": {
                        "evidence_status": coverage_by_year[year]["health_premium"],
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "health_oop": {
                        "evidence_status": coverage_by_year[year]["health_oop"],
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "mileage": {
                        "evidence_status": coverage_by_year[year]["mileage"],
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "mpg": {
                        "evidence_status": coverage_by_year[year]["mpg"],
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "gas": {
                        "evidence_status": coverage_by_year[year]["gas"],
                        "methodology_status": "READY",
                    },
                    "insurance": {
                        "evidence_status": coverage_by_year[year]["insurance"],
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "maintenance": {
                        "evidence_status": "INCOMPLETE_PROVENANCE",
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "registration": {
                        "evidence_status": "SOURCE_GAP",
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "replacement": {
                        "evidence_status": "ESTIMATED_OWNER_REVIEW",
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "connectivity": {
                        "evidence_status": coverage_by_year[year]["connectivity"],
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "essentials": {
                        "evidence_status": coverage_by_year[year]["essentials"],
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "recreation": {
                        "evidence_status": coverage_by_year[year]["recreation"],
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "rpp": {
                        "evidence_status": coverage_by_year[year]["rpp"],
                        "methodology_status": "READY",
                    },
                    "federal_tax": {
                        "evidence_status": "INVENTORY_NOT_VALIDATED",
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "state_tax": {
                        "evidence_status": "SOURCE_GAP",
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                    "local_tax": {
                        "evidence_status": "SOURCE_GAP",
                        "methodology_status": "OWNER_REVIEW_PENDING",
                    },
                }
                for year in coverage_by_year
            },
        },
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
    write_owner_decision_packet(METADATA_DIR)
    write_tax_coverage()
    write_transport_coverage()
    write_cms_coverage_stub()
    write_cms_platform_and_sbe_reports()
    write_correction_side_reports()
    logger.info(
        "Source coverage generated. Blocking components: %s",
        len(coverage["blocking_components"]),
    )
    logger.info("Validation complete. No living-cost headline was calculated.")
    return 0


def write_correction_side_reports() -> None:
    """MEPS refresh, CT reconstruction, CE maintenance candidates. No headline."""
    meps_refresh = check_meps_2024_full_year_listing()
    (METADATA_DIR / "living_cost_meps_2024_refresh.json").write_text(
        json.dumps(
            {
                "report_type": "meps_2024_full_year_refresh",
                "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                **meps_refresh,
                "continue_using": None
                if meps_refresh.get("released")
                else "HC-251 true source year = 2023",
                "headline_calculated": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    ct_path_xlsx = CACHE_DIR / "ct_cou_to_cousub_crosswalk.xlsx"
    ct_path_txt = CACHE_DIR / "ct_cou_to_cousub_crosswalk.txt"
    ct_path = ct_path_xlsx if ct_path_xlsx.exists() else ct_path_txt
    acs_dat = CACHE_DIR / "acsdt5y2024-b01001.dat"
    if not acs_dat.exists():
        # official cache name may vary
        for candidate in CACHE_DIR.glob("acsdt5y2024-b01001*"):
            acs_dat = candidate
            break
    crosswalk_rows = parse_ct_crosswalk(ct_path) if ct_path.exists() else []
    cousub_adults = parse_acs_ct_cousub_adults(acs_dat) if acs_dat.exists() else {}
    ct_report = reconstruct_legacy_county_adult_pop(crosswalk_rows, cousub_adults)
    ct_report.update(
        {
            "report_type": "connecticut_legacy_county_reconstruction",
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "planning_region_fips_locked": list(CT_PLANNING_REGION_FIPS),
            "architecture": "keep_hud_geography_legacy_county",
            "headline_calculated": False,
        }
    )
    (METADATA_DIR / "living_cost_ct_reconstruction.json").write_text(
        json.dumps(ct_report, indent=2), encoding="utf-8"
    )

    maint = parse_bls_ce_maintenance_candidates(CACHE_DIR, reference_year=2024)
    (METADATA_DIR / "living_cost_maintenance_candidates.json").write_text(
        json.dumps(
            {
                "report_type": "living_cost_maintenance_candidates",
                "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
                **maint,
                "headline_calculated": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def write_tax_coverage() -> None:
    from foundation.living_cost.taxes import (
        FEDERAL_TAX_RULES,
        NO_INCOME_TAX_STATES,
        STATE_STATUTORY_SCHEDULES,
    )

    states = [
        "AL",
        "AK",
        "AZ",
        "AR",
        "CA",
        "CO",
        "CT",
        "DE",
        "DC",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NV",
        "NH",
        "NJ",
        "NM",
        "NY",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "TX",
        "UT",
        "VT",
        "VA",
        "WA",
        "WV",
        "WI",
        "WY",
    ]
    rows = []
    for year in (2024, 2026):
        for st in states:
            if st in NO_INCOME_TAX_STATES:
                status = "NO_STATE_EARNED_INCOME_TAX"
                source = "No general state earned-income tax"
            elif st in STATE_STATUTORY_SCHEDULES.get(year, {}):
                status = "INVENTORY_NOT_VALIDATED"
                source = str(STATE_STATUTORY_SCHEDULES[year][st].get("source") or "")
            else:
                status = "SOURCE_GAP"
                source = ""
            schedule = STATE_STATUTORY_SCHEDULES.get(year, {}).get(st, {})
            rows.append(
                {
                    "year": year,
                    "state": st,
                    "status": status,
                    "primary_source": source,
                    "brackets": schedule.get("brackets"),
                    "rates": [b[1] for b in schedule.get("brackets", [])]
                    if schedule.get("brackets")
                    else None,
                    "deductions": schedule.get("deduction"),
                    "exemptions": schedule.get("exemption"),
                    "ordinary_credits": schedule.get("credits"),
                    "unusual_mechanics": schedule.get("notes"),
                    "implementation_status": status,
                    "federal_source": FEDERAL_TAX_RULES[year]["source"],
                }
            )
    payload = {
        "report_type": "living_cost_tax_coverage",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "federal_2024_validated_tables": False,
        "federal_validation_gate": (
            "Boundary tests exist in tests/test_living_cost.py but IRS source PDFs "
            "are not retrieved/parsed, so federal_tax is not VALIDATED."
        ),
        "federal_2026_values_match_rev_proc_2025_32": True,
        "local_tax_classes": {
            "A": "geography is coterminous / tax applies throughout modeled county-equivalent; direct overlay may be appropriate",
            "B": "tax is county-level; direct overlay may be appropriate",
            "C": "municipality occupies only part of county — do not apply city tax countywide; use place/subcounty, population-weight, or mark unresolved",
            "D": "unresolved",
        },
        "rows": rows,
        "headline_calculated": False,
    }
    (METADATA_DIR / "living_cost_tax_coverage.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def write_transport_coverage() -> None:
    payload = {
        "report_type": "living_cost_transport_coverage",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "components": {
            "mileage": {
                "status": "MEASURED_TRAVEL_BEHAVIOR",
                "source": "2022 NHTS V2.1 vehv2pub ANNMILES / hhv2pub WTHHFIN",
                "note": "Observed, not minimum necessary. Owner decision OD-003.",
            },
            "mpg": {
                "status": "RETRIEVED_UNVALIDATED",
                "note": "EPA fueleconomy.gov vehicle-level candidates built. OD-004 cohort not frozen. 24/28/32 are not the empirical model.",
            },
            "gas": {
                "status": "VALIDATED",
                "source": "EIA pswrgvwall.xls",
                "note": "PADD/regional is not state-measured.",
            },
            "insurance": {
                "status": "RETRIEVED_UNVALIDATED",
                "note": "Official free NAIC 2022/2023 Auto Insurance Database Report retrieved. redistribution_status=FREE_DOWNLOAD_REDISTRIBUTION_UNCONFIRMED. OD-006 measure not frozen.",
            },
            "maintenance": {
                "evidence_status": "INCOMPLETE_PROVENANCE",
                "methodology_status": "OWNER_REVIEW_PENDING",
                "status": "INCOMPLETE_PROVENANCE",
                "note": (
                    "Official 2024 Interview VQB/UCC candidates among single-person "
                    "vehicle-owning CE units. Cached official artifact parses; official "
                    "re-retrieve remains HTTP 403. Not a guessed estimate. Not VALIDATED. "
                    "TIRECQ / historical UCC 470211 absence is not measured zero. "
                    "UCC 470212 is excluded as fuel residual. OD-007 not frozen."
                ),
            },
            "registration": {
                "status": "SOURCE_GAP",
                "evidence_status": "SOURCE_GAP",
                "methodology_status": "OWNER_REVIEW_PENDING",
                "note": "Hand-entered 51-state table is not accepted as validated.",
            },
            "replacement": {
                "status": "ESTIMATED_OWNER_REVIEW",
                "evidence_status": "ESTIMATED_OWNER_REVIEW",
                "methodology_status": "OWNER_REVIEW_PENDING",
            },
        },
        "headline_calculated": False,
    }
    (METADATA_DIR / "living_cost_transport_coverage.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def write_cms_coverage_stub() -> None:
    import io

    coverage: dict[str, Any] = {
        "report_type": "living_cost_cms_coverage",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "years": {},
        "headline_calculated": False,
        "note": (
            "Federal-platform PUF zips retrieved. Official per-state SBE QHP PUF zips "
            "are retrieved from cms.gov/files/zip (not a national SBE zip). "
            "The 2026 sbe-puf-files-2026.zip dictionary archive is documentation-only "
            "and is not treated as missing plan data."
        ),
    }
    for year in (2024, 2026):
        sa = CACHE_DIR / f"cms_{year}_service_area_puf.zip"
        states: list[str] = []
        if sa.exists():
            with zipfile.ZipFile(sa) as zf:
                csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if csvs:
                    with zf.open(csvs[0]) as fh:
                        reader = __import__("csv").DictReader(
                            io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                        )
                        found = set()
                        for row in reader:
                            st = str(row.get("StateCode") or row.get("State") or "").strip()
                            if len(st) == 2:
                                found.add(st.upper())
                        states = sorted(found)
        from foundation.sources.cms_marketplace import SBE_STANDALONE_STATES
        from foundation.sources.cms_platform import ALL_JURISDICTIONS, SBE_FP_STATES

        all_states = set(ALL_JURISDICTIONS)
        sbe = set(SBE_STANDALONE_STATES.get(year, frozenset()))
        federal = set(states)
        # Oregon / SBE-FP individual market is federal even if an SBE ZIP exists.
        missing = sorted(all_states - federal - sbe)
        rating_areas: set[str] = set()
        counties: set[str] = set()
        rate_zip = CACHE_DIR / f"cms_{year}_rate_puf.zip"
        if rate_zip.exists():
            with zipfile.ZipFile(rate_zip) as zf:
                csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if csvs:
                    with zf.open(csvs[0]) as fh:
                        reader = __import__("csv").DictReader(
                            io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                        )
                        for row in reader:
                            st = str(row.get("StateCode") or "").strip().upper()
                            area = str(row.get("RatingAreaId") or "").strip()
                            if st and area:
                                rating_areas.add(f"{st}:{area}")
        sa = CACHE_DIR / f"cms_{year}_service_area_puf.zip"
        if sa.exists():
            with zipfile.ZipFile(sa) as zf:
                csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
                if csvs:
                    with zf.open(csvs[0]) as fh:
                        reader = __import__("csv").DictReader(
                            io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                        )
                        for row in reader:
                            county = str(row.get("County") or "").strip()
                            if county:
                                counties.add(county)
        join_obs_count = 0
        try:
            from foundation.sources.cms_marketplace import parse_cms_marketplace_multi_puf

            join_obs = parse_cms_marketplace_multi_puf(year, CACHE_DIR)
            join_obs_count = len(join_obs)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, zipfile.BadZipFile) as exc:
            logger.error("CMS join failed for %s: %s", year, exc)
        coverage["years"][str(year)] = {
            "federal_platform_service_area_states": states,
            "federal_platform_state_count": len(states),
            "sbe_standalone_states": sorted(sbe),
            "sbe_standalone_state_count": len(sbe),
            "sbe_fp_states": sorted(SBE_FP_STATES.get(year, frozenset())),
            "sbe_ingestion": "PER_STATE_OFFICIAL_ZIPS",
            "states_missing_both_federal_and_sbe_files": missing,
            "rating_areas_represented": len(rating_areas),
            "counties_represented": len(counties),
            "joined_lowest_silver_rating_areas": join_obs_count,
            "oregon_individual_market_source": "federal_exchange_puf",
            "note": (
                "No state may receive a premium from a plan not actually offered there. "
                "SBE standalone states are not filled from federal-platform rates. "
                "SBE-FP states including Oregon use federal Exchange PUFs for "
                "individual-market plan/rate data. SBE ZIP existence is not "
                "platform classification. Standalone SBE lowest-Silver joins "
                "are implemented; health_premium is MODELED_FROM_MEASURED_INPUTS. "
                "No healthcare headline is published."
            ),
        }
        from foundation.sources.cms_marketplace import SBE_STATE_ZIP_SLUGS

        slugs = SBE_STATE_ZIP_SLUGS.get(year, {})
        retrieved_sbe = []
        parsed_sbe = []
        missing_sbe = []
        for st, slug in slugs.items():
            path = CACHE_DIR / f"cms_sbe_{year}_{st.lower()}_{slug}"
            if not path.is_file():
                missing_sbe.append(st)
                continue
            retrieved_sbe.append(st)
            try:
                with zipfile.ZipFile(path) as archive:
                    csvs = [n for n in archive.namelist() if n.lower().endswith(".csv")]
                if csvs:
                    parsed_sbe.append(st)
            except zipfile.BadZipFile:
                pass
        coverage["years"][str(year)]["sbe_states_expected"] = sorted(sbe)
        coverage["years"][str(year)]["sbe_states_retrieved"] = retrieved_sbe
        coverage["years"][str(year)]["sbe_states_parsed"] = parsed_sbe
        coverage["years"][str(year)]["sbe_states_missing"] = missing_sbe
        coverage["years"][str(year)]["sbe_expected_count"] = len(sbe)
        coverage["years"][str(year)]["sbe_retrieved_count"] = len(retrieved_sbe)
        coverage["years"][str(year)]["sbe_parsed_count"] = len(parsed_sbe)
        sbe_join_path = METADATA_DIR / "living_cost_cms_sbe_lowest_silver.json"
        if sbe_join_path.exists():
            sbe_join_doc = json.loads(sbe_join_path.read_text(encoding="utf-8"))
            year_join = sbe_join_doc.get("years", {}).get(str(year), {})
            coverage["years"][str(year)]["sbe_lowest_silver_states_joined"] = year_join.get(
                "states_joined", []
            )
            coverage["years"][str(year)]["sbe_lowest_silver_output_count"] = year_join.get(
                "lowest_silver_output_count", 0
            )
            coverage["years"][str(year)]["all_standalone_sbe_joined"] = year_join.get(
                "all_standalone_joined", False
            )
    (METADATA_DIR / "living_cost_cms_coverage.json").write_text(
        json.dumps(coverage, indent=2), encoding="utf-8"
    )


def write_cms_platform_and_sbe_reports() -> None:
    from foundation.sources.cms_marketplace import (
        SBE_STATE_ZIP_SLUGS,
        parse_standalone_sbe_lowest_silver,
    )
    from foundation.sources.cms_platform import (
        assert_platform_map_invariants,
        build_platform_map,
    )

    maps: dict[str, Any] = {
        "report_type": "cms_individual_market_platform_map",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "headline_calculated": False,
        "years": {},
    }
    sbe_join: dict[str, Any] = {
        "report_type": "cms_sbe_lowest_silver_join",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "headline_calculated": False,
        "years": {},
    }
    for year in (2024, 2026):
        slugs = SBE_STATE_ZIP_SLUGS.get(year, {})
        archive_states = set()
        for st, slug in slugs.items():
            path = CACHE_DIR / f"cms_sbe_{year}_{st.lower()}_{slug}"
            if path.is_file():
                archive_states.add(st)
        payload = build_platform_map(year, archive_states)
        assert_platform_map_invariants(year, payload)
        maps["years"][str(year)] = payload
        join = parse_standalone_sbe_lowest_silver(year, CACHE_DIR)
        serializable = dict(join)
        serializable.pop("observations", None)
        sbe_join["years"][str(year)] = serializable
        maps["years"][str(year)]["sbe_lowest_silver_states_joined"] = join["states_joined"]
        maps["years"][str(year)]["sbe_lowest_silver_output_count"] = join[
            "lowest_silver_output_count"
        ]
        maps["years"][str(year)]["all_standalone_sbe_joined"] = join["all_standalone_joined"]
    (METADATA_DIR / "cms_individual_market_platform_map.json").write_text(
        json.dumps(maps, indent=2), encoding="utf-8"
    )
    (METADATA_DIR / "living_cost_cms_sbe_lowest_silver.json").write_text(
        json.dumps(sbe_join, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
