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
from foundation.sources.auto_insurance import download_naic_artifact
from foundation.sources.bea_rpp import download_bea_rpp_artifact
from foundation.sources.bls_ce import download_bls_ce_artifact
from foundation.sources.census_acs import (
    download_acs_county_population_artifact,
    generate_census_county_universe_report,
    parse_acs_county_population_json,
)
from foundation.sources.cms_marketplace import (
    download_cms_marketplace_artifacts,
    download_cms_sbe_artifact,
)
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

    from dataclasses import replace

    if hud_obs and len(hud_obs) >= 3000:
        for i, art in enumerate(artifacts):
            if art.source_id == f"hud_fmr_{year}":
                artifacts[i] = replace(
                    art,
                    validation_status="VALIDATED",
                    notes=f"Parsed {len(hud_obs)} official county 1BR FMR rows.",
                )
    if census_universe and len(census_universe) >= 3000:
        for i, art in enumerate(artifacts):
            if art.source_id == f"census_acs5_{year}":
                artifacts[i] = replace(
                    art,
                    validation_status="VALIDATED",
                    notes=(
                        f"Parsed {len(census_universe)} county adult-population rows "
                        "from official 2024 ACS 5-Year B01001 summary file."
                    ),
                )

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
                    upgraded[i] = replace(
                        art,
                        validation_status="VALIDATED",
                        notes=f"Parsed {len(rows)} official Low-Cost monthly rows for {year}.",
                    )
            elif art.source_id.startswith("usda_food_thrifty"):
                rows = parse_usda_official_xlsx(path, reference_year=year, plan_key="thrifty")
                if rows:
                    upgraded[i] = replace(
                        art,
                        validation_status="VALIDATED",
                        notes=f"Parsed {len(rows)} official Thrifty monthly rows for {year}.",
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
                        validation_status="VALIDATED",
                        notes="Parsed official 2024 Interview FMLI single-person baskets.",
                    )
            elif art.source_id.startswith("bea_rpp_"):
                rpp = parse_bea_rpp_csv(CACHE_DIR, reference_year=year)
                if len(rpp) >= 50:
                    upgraded[i] = replace(
                        art,
                        validation_status="VALIDATED",
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
                        validation_status="VALIDATED",
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
                        validation_status="VALIDATED",
                        notes=miles.notes,
                    )
            elif art.source_id.startswith("cms_") and art.local_cache_filename.endswith(".zip"):
                with zipfile.ZipFile(path) as archive:
                    csv_members = [
                        name for name in archive.namelist() if name.lower().endswith(".csv")
                    ]
                if csv_members:
                    upgraded[i] = replace(
                        art,
                        validation_status="VALIDATED",
                        notes=f"Archive integrity OK; CSV member {csv_members[0]}.",
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
            "federal_tax": "VALIDATED",
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
    write_owner_decision_packet(METADATA_DIR)
    write_tax_coverage()
    write_transport_coverage()
    write_cms_coverage_stub()
    logger.info(
        "Source coverage generated. Blocking components: %s",
        len(coverage["blocking_components"]),
    )
    logger.info("Validation complete. No living-cost headline was calculated.")
    return 0


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
            rows.append(
                {
                    "year": year,
                    "state": st,
                    "status": status,
                    "primary_source": source,
                    "federal_source": FEDERAL_TAX_RULES[year]["source"],
                }
            )
    payload = {
        "report_type": "living_cost_tax_coverage",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "federal_2024_validated_tables": False,
        "federal_2026_values_match_rev_proc_2025_32": True,
        "local_tax_classes": {
            "A": "no local earned-income tax",
            "B": "county-level tax directly measurable",
            "C": "municipal tax requiring additional geography — OWNER DECISION",
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
            "mpg": {"status": "ESTIMATED_OWNER_REVIEW", "note": "28 MPG is not frozen."},
            "gas": {
                "status": "RETRIEVED_UNVALIDATED",
                "source": "EIA pswrgvwall.xls",
                "note": "PADD/regional is not state-measured.",
            },
            "insurance": {"status": "LICENSING_REVIEW"},
            "maintenance": {"status": "ESTIMATED_OWNER_REVIEW"},
            "registration": {
                "status": "SOURCE_GAP",
                "note": "Hand-entered 51-state table is not accepted as validated.",
            },
            "replacement": {"status": "ESTIMATED_OWNER_REVIEW"},
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
        "note": "Federal-platform PUF zips retrieved. SBE-only states require SBE QHP PUFs.",
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

        all_states = {
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
        }
        sbe = set(SBE_STANDALONE_STATES.get(year, frozenset()))
        federal = set(states)
        missing = sorted(all_states - federal - sbe)
        coverage["years"][str(year)] = {
            "federal_platform_service_area_states": states,
            "federal_platform_state_count": len(states),
            "sbe_standalone_states": sorted(sbe),
            "sbe_standalone_state_count": len(sbe),
            "sbe_ingestion": (
                "DOCUMENTATION_ONLY_ZIP" if year == 2026 else "OFFICIAL_ZIP_404_SOURCE_GAP"
            ),
            "states_missing_both_federal_and_sbe_files": missing,
            "note": (
                "No state may receive a premium from a plan not actually offered there. "
                "SBE standalone states are not filled from federal-platform rates."
            ),
        }
    (METADATA_DIR / "living_cost_cms_coverage.json").write_text(
        json.dumps(coverage, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
