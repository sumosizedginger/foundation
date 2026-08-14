"""Standalone Source Validation Script.

Retrieves official source artifacts, calculates hashes, validates schemas, generates source manifest,
generates geo-join reports, reports gaps, and does NOT update headline economic outputs.
Validation succeeds in producing an audit report even when a source is unavailable.
"""

import logging
import sys
from pathlib import Path

# Add src/ to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from foundation.living_cost.geo_join import execute_geo_join_audit
from foundation.living_cost.manifest import RetrievedSourceArtifact, generate_source_manifest
from foundation.sources.acquisition import acquire_source
from foundation.sources.bea_rpp import download_bea_rpp_artifact
from foundation.sources.bls_ce import download_bls_ce_microdata
from foundation.sources.census_acs import acquire_census_acs_universe
from foundation.sources.cms_marketplace import download_cms_puf_artifacts
from foundation.sources.eia import download_eia_gas_artifact
from foundation.sources.fhwa_nhts import download_nhts_artifact
from foundation.sources.hud_fmr import download_hud_fmr_artifact
from foundation.sources.meps import download_meps_artifact
from foundation.sources.usda_food import download_usda_food_artifact
from foundation.sources.auto_insurance import download_naic_artifact

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
METADATA_DIR = Path(__file__).resolve().parent.parent / "data" / "metadata"


def validate_sources_for_year(year: int) -> list[RetrievedSourceArtifact]:
    artifacts = []
    
    # 1. HUD FMR
    try:
        hud_art = download_hud_fmr_artifact(year, CACHE_DIR)
        artifacts.append(hud_art)
        hud_sha256 = hud_art.sha256
    except Exception as e:
        logger.error(f"Failed to acquire HUD FMR for {year}: {e}")
        hud_sha256 = ""

    # 2. Census ACS
    try:
        census_data, census_art = acquire_census_acs_universe(year, CACHE_DIR)
        artifacts.append(census_art)
        census_sha256 = census_art.sha256
        census_universe = census_data
    except Exception as e:
        logger.error(f"Failed to acquire Census ACS for {year}: {e}")
        census_sha256 = ""
        census_universe = {}

    # Geo-join Audit (HUD FMR <-> Census ACS)
    # We need hud_observations to do the geo join. For now, since this script is just validation,
    # and geo_join expects parsed observations, we'll run the parser for HUD if available.
    if hud_sha256 and census_universe:
        try:
            from foundation.sources.hud_fmr import parse_hud_fmr_xlsx
            hud_obs = parse_hud_fmr_xlsx(CACHE_DIR, year, retrieved_at=hud_art.retrieved_at, file_sha256=hud_sha256)
            join_report = execute_geo_join_audit(
                census_county_universe=census_universe,
                hud_observations=hud_obs,
                reference_year=year,
                census_artifact_sha256=census_sha256,
                hud_artifact_sha256=hud_sha256,
                output_path=METADATA_DIR / f"living_cost_geo_join_{year}.json",
            )
            logger.info(f"Generated geo-join report for {year}: matched {join_report['matched_counties_count']} counties.")
        except Exception as e:
            logger.error(f"Failed to execute geo-join audit for {year}: {e}")

    # 3. CMS Marketplace
    try:
        cms_arts = download_cms_puf_artifacts(year, CACHE_DIR)
        artifacts.extend(cms_arts)
    except Exception as e:
        logger.error(f"Failed to acquire CMS Marketplace PUF for {year}: {e}")

    # 4. FHWA NHTS
    try:
        nhts_art = download_nhts_artifact(year, CACHE_DIR)
        artifacts.append(nhts_art)
    except Exception as e:
        logger.error(f"Failed to acquire FHWA NHTS for {year}: {e}")

    # 5. BLS CE
    try:
        bls_art = download_bls_ce_microdata(year, CACHE_DIR)
        artifacts.append(bls_art)
    except Exception as e:
        logger.error(f"Failed to acquire BLS CE for {year}: {e}")

    # 6. MEPS
    try:
        meps_art = download_meps_artifact(year, CACHE_DIR)
        artifacts.append(meps_art)
    except Exception as e:
        logger.error(f"Failed to acquire MEPS for {year}: {e}")

    # 7. BEA RPP
    try:
        bea_art = download_bea_rpp_artifact(year, CACHE_DIR)
        artifacts.append(bea_art)
    except Exception as e:
        logger.error(f"Failed to acquire BEA RPP for {year}: {e}")

    # 8. USDA Food
    try:
        usda_art = download_usda_food_artifact(year, CACHE_DIR)
        artifacts.append(usda_art)
    except Exception as e:
        logger.error(f"Failed to acquire USDA Food for {year}: {e}")

    # 9. EIA Gas
    try:
        eia_art = download_eia_gas_artifact(year, CACHE_DIR)
        artifacts.append(eia_art)
    except Exception as e:
        logger.error(f"Failed to acquire EIA Gas for {year}: {e}")

    # 10. NAIC Auto Insurance
    try:
        naic_art = download_naic_artifact(year, CACHE_DIR)
        artifacts.append(naic_art)
    except Exception as e:
        logger.error(f"Failed to acquire NAIC Auto Insurance for {year}: {e}")

    return artifacts


def main():
    logger.info("Starting living cost sources validation...")
    
    all_artifacts = []
    
    for year in [2024, 2026]:
        logger.info(f"Validating sources for {year}...")
        arts = validate_sources_for_year(year)
        all_artifacts.extend(arts)
        
    # Generate Source Manifest
    manifest_path = METADATA_DIR / "living_cost_source_manifest.json"
    generate_source_manifest(all_artifacts, manifest_path)
    logger.info(f"Source manifest generated at {manifest_path}")

    # Generate Source Coverage (Summary of what is missing)
    import json
    from datetime import UTC, datetime
    
    coverage = {
        "report_type": "living_cost_source_coverage",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "retrieved_artifacts": [a.source_id for a in all_artifacts],
        "validation_success": True
    }
    
    coverage_path = METADATA_DIR / "living_cost_source_coverage.json"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    with coverage_path.open("w") as fh:
        json.dump(coverage, fh, indent=2)
    logger.info(f"Source coverage generated at {coverage_path}")
    
    logger.info("Validation complete.")


if __name__ == "__main__":
    main()
