"""Living Cost canonical source registry and retrieved-artifact manifest.

Static registry records publisher identity and official landing/artifact URLs.
Retrieved hashes, sizes, and timestamps are written only after a real retrieval.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StaticSourceDef:
    source_id: str
    publisher: str
    dataset: str
    reference_year: int
    release: str
    url: str
    licensing_notes: str
    landing_page: str = ""
    parser_identifier: str = ""
    source_vintage_note: str = ""


@dataclass(frozen=True)
class RetrievedSourceArtifact:
    source_id: str
    retrieved_at: str
    sha256: str
    byte_size: int
    local_cache_filename: str
    validation_status: str
    resolved_url: str = ""
    notes: str = ""


HUD_FMR_LANDING = "https://www.huduser.gov/portal/datasets/fmr.html"
CMS_PUF_LANDING = "https://www.cms.gov/marketplace/resources/data/public-use-files"
ACS_LANDING = (
    "https://www2.census.gov/programs-surveys/acs/summary_file/2024/"
    "table-based-SF/data/5YRData/acsdt5y2024-b01001.dat"
)
MEPS_HC243_LANDING = (
    "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files_detail.jsp?cboPufNumber=HC-243"
)
USDA_FOOD_LANDING = "https://www.fns.usda.gov/cnpp/usda-food-plans-cost-food-monthly-reports"
EIA_GAS_LANDING = "https://www.eia.gov/petroleum/gasdiesel/"
NHTS_LANDING = "https://nhts.ornl.gov/downloads"
BLS_CE_LANDING = "https://www.bls.gov/cex/pumd_data.htm"
BEA_RPP_LANDING = (
    "https://www.bea.gov/data/prices-inflation/regional-price-parities-state-and-metro-area"
)
NAIC_LANDING = "https://content.naic.org/research-actuarial-services/auto-insurance-database-report"


STATIC_SOURCES: list[StaticSourceDef] = [
    StaticSourceDef(
        source_id="hud_fmr_2024",
        publisher="U.S. Department of Housing and Urban Development (HUD)",
        dataset="Fair Market Rents (FMR) 1-Bedroom 40th Percentile County Dataset",
        reference_year=2024,
        release="HUD FY 2024 Fair Market Rents (Revised, effective March 11, 2024)",
        url="https://www.huduser.gov/portal/datasets/fmr/fmr2024/FMR2024_final_revised.xlsx",
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page=HUD_FMR_LANDING,
        parser_identifier="foundation.sources.hud_fmr.parse_hud_fmr_xlsx",
        source_vintage_note="Official county workbook FMR2024_final_revised.xlsx",
    ),
    StaticSourceDef(
        source_id="hud_fmr_2026",
        publisher="U.S. Department of Housing and Urban Development (HUD)",
        dataset="Fair Market Rents (FMR) 1-Bedroom 40th Percentile County Dataset",
        reference_year=2026,
        release="HUD FY 2026 Fair Market Rents (Revised, effective May 21, 2026)",
        url="https://www.huduser.gov/portal/datasets/fmr/fmr2026/FY26_FMRs_revised.xlsx",
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page=HUD_FMR_LANDING,
        parser_identifier="foundation.sources.hud_fmr.parse_hud_fmr_xlsx",
        source_vintage_note="Official county workbook FY26_FMRs_revised.xlsx",
    ),
    StaticSourceDef(
        source_id="census_acs5_2024",
        publisher="U.S. Census Bureau",
        dataset="American Community Survey 5-Year Estimates Table B01001 (Adult Population Age 18+)",
        reference_year=2024,
        release="2024 ACS 5-Year Data Release (B01001 summary file)",
        url=ACS_LANDING,
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page="https://www.census.gov/programs-surveys/acs",
        parser_identifier="foundation.sources.census_acs.parse_acs_summary_dat",
        source_vintage_note=(
            "Frozen weight vintage is 2024 ACS 5-Year B01001. Used for both 2024 and 2026 cost years."
        ),
    ),
    StaticSourceDef(
        source_id="census_acs5_2026",
        publisher="U.S. Census Bureau",
        dataset="American Community Survey 5-Year Estimates Table B01001 (Adult Population Age 18+)",
        reference_year=2026,
        release="2024 ACS 5-Year Data Release (shared weight vintage)",
        url=ACS_LANDING,
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page="https://www.census.gov/programs-surveys/acs",
        parser_identifier="foundation.sources.census_acs.parse_acs_summary_dat",
        source_vintage_note=(
            "2026 cost year uses the same 2024 ACS 5-Year weight vintage as 2024. "
            "Not a 2026 Census file."
        ),
    ),
    StaticSourceDef(
        source_id="cms_rate_puf_2024",
        publisher="Centers for Medicare & Medicaid Services (CMS)",
        dataset="Marketplace Exchange PUFs (Rate, Plan Attributes, Service Area, Benefits)",
        reference_year=2024,
        release="CMS 2024 Exchange PUF (updated August 6, 2024)",
        url="https://download.cms.gov/marketplace-puf/2024/rate-puf.zip",
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page=CMS_PUF_LANDING,
        parser_identifier="foundation.sources.cms_marketplace.parse_cms_marketplace_multi_puf",
        source_vintage_note="FFE + SBE-FP only. Standalone SBE states require SBE QHP PUFs.",
    ),
    StaticSourceDef(
        source_id="cms_rate_puf_2026",
        publisher="Centers for Medicare & Medicaid Services (CMS)",
        dataset="Marketplace Exchange PUFs (Rate, Plan Attributes, Service Area, Benefits)",
        reference_year=2026,
        release="CMS 2026 Exchange PUF (updated August 4, 2026)",
        url="https://download.cms.gov/marketplace-puf/2026/rate-puf.zip",
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page=CMS_PUF_LANDING,
        parser_identifier="foundation.sources.cms_marketplace.parse_cms_marketplace_multi_puf",
        source_vintage_note="FFE + SBE-FP only. Standalone SBE states require SBE QHP PUFs.",
    ),
    StaticSourceDef(
        source_id="meps_table1_2024",
        publisher="Agency for Healthcare Research and Quality (AHRQ)",
        dataset="MEPS Household Component HC-251 2023 Full Year Consolidated Data File",
        reference_year=2024,
        release="MEPS HC-251 (2023 data year; newest official Full Year Consolidated at execution)",
        url="https://meps.ahrq.gov/mepsweb/data_files/pufs/h251/h251dat.zip",
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page=MEPS_HC243_LANDING,
        parser_identifier="foundation.sources.meps.parse_meps_oop_csv",
        source_vintage_note="2023 MEPS data year used as OOP source vintage for 2024 cost year. Not a 2024 MEPS file.",
    ),
    StaticSourceDef(
        source_id="usda_food_low_cost_2024",
        publisher="U.S. Department of Agriculture (USDA)",
        dataset="USDA Food Plans: Monthly Cost of Food Reports (Low-Cost Plan)",
        reference_year=2024,
        release="USDA/CNPP monthly Cost of Food reports",
        url="https://www.fna.usda.gov/sites/default/files/resource-files/usda-lowcostplan-sept2007-present.xlsx",
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page="https://www.fna.usda.gov/research/cnpp/usda-food-plans/cost-food-monthly-reports",
        parser_identifier="foundation.sources.usda_food.parse_usda_official_xlsx",
        source_vintage_note="Official CNPP Low-Cost archive usda-lowcostplan-sept2007-present.xlsx.",
    ),
    StaticSourceDef(
        source_id="eia_gas_price_2024",
        publisher="U.S. Energy Information Administration (EIA)",
        dataset="Weekly Retail Gasoline and Diesel Prices",
        reference_year=2024,
        release="EIA gasoline and diesel landing page / Open Data",
        url=EIA_GAS_LANDING,
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page=EIA_GAS_LANDING,
        parser_identifier="foundation.sources.eia.parse_eia_gas_prices_csv",
    ),
    StaticSourceDef(
        source_id="naic_auto_ins_2024",
        publisher="National Association of Insurance Commissioners (NAIC)",
        dataset="2022/2023 Auto Insurance Database Report",
        reference_year=2024,
        release="NAIC 2022/2023 Auto Insurance Database Report (Adopted December 2025; free download)",
        url="https://content.naic.org/sites/default/files/publication-aut-pb-auto-insurance-database.pdf",
        licensing_notes="Free official download. redistribution_status=FREE_DOWNLOAD_REDISTRIBUTION_UNCONFIRMED.",
        landing_page="https://content.naic.org/publications",
        parser_identifier="foundation.sources.auto_insurance.parse_naic_auto_insurance_csv",
        source_vintage_note="data_year=2023; publication_year=2025; OD-006 measure not frozen.",
    ),
    StaticSourceDef(
        source_id="fhwa_nhts_2024",
        publisher="Federal Highway Administration (FHWA) / ORNL",
        dataset="2022 NextGen National Household Travel Survey V2.1 public-use files",
        reference_year=2024,
        release="2022 NHTS V2.1",
        url=NHTS_LANDING,
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page=NHTS_LANDING,
        parser_identifier="foundation.sources.fhwa_nhts.parse_fhwa_nhts_mileage",
        source_vintage_note="Exact V2.1 CSV zip URL must be resolved from the downloads page.",
    ),
    StaticSourceDef(
        source_id="bls_ce_2024",
        publisher="U.S. Bureau of Labor Statistics (BLS)",
        dataset="Consumer Expenditure Survey Interview PUMD (CSV)",
        reference_year=2024,
        release="BLS CE Interview 2024 PUMD",
        url="https://www.bls.gov/cex/pumd/data/csv/intrvw24.zip",
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page=BLS_CE_LANDING,
        parser_identifier="foundation.sources.bls_ce.parse_bls_ce_microdata",
        source_vintage_note="2024 Interview year. Path is /csv/, not legacy /comma/.",
    ),
    StaticSourceDef(
        source_id="bea_rpp_2024",
        publisher="U.S. Bureau of Economic Analysis (BEA)",
        dataset="Regional Price Parities by State and Metro Area",
        reference_year=2024,
        release="BEA RPP current release February 19, 2026 (2024 data year)",
        url=BEA_RPP_LANDING,
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page=BEA_RPP_LANDING,
        parser_identifier="foundation.sources.bea_rpp.parse_bea_rpp_csv",
        source_vintage_note="Use official BEA API/download. Do not assume year-2.",
    ),
    StaticSourceDef(
        source_id="irs_rev_proc_2023_34",
        publisher="Internal Revenue Service (IRS)",
        dataset="Internal Revenue Bulletin: Rev. Proc. 2023-34 (2024 Tax Inflation Adjustments)",
        reference_year=2024,
        release="IRS Rev. Proc. 2023-34",
        url="https://www.irs.gov/pub/irs-drop/rp-23-34.pdf",
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page="https://www.irs.gov/irb",
        parser_identifier="foundation.living_cost.taxes",
    ),
    StaticSourceDef(
        source_id="irs_rev_proc_2025_32",
        publisher="Internal Revenue Service (IRS)",
        dataset="Internal Revenue Bulletin: Rev. Proc. 2025-32 (2026 Tax Inflation Adjustments)",
        reference_year=2026,
        release="IRS Rev. Proc. 2025-32",
        url="https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
        licensing_notes="U.S. Government Work (Public Domain)",
        landing_page="https://www.irs.gov/irb",
        parser_identifier="foundation.living_cost.taxes",
    ),
]


def generate_source_manifest(
    retrieved_artifacts: list[RetrievedSourceArtifact], output_path: Path | None = None
) -> dict[str, Any]:
    """Generate and write the canonical living cost source manifest."""
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()

    sources_out = []
    artifacts_by_id = {a.source_id: a for a in retrieved_artifacts}

    for static_def in STATIC_SOURCES:
        base_dict: dict[str, Any] = {
            "source_id": static_def.source_id,
            "publisher": static_def.publisher,
            "dataset": static_def.dataset,
            "reference_year": static_def.reference_year,
            "release": static_def.release,
            "url": static_def.url,
            "landing_page": static_def.landing_page,
            "licensing_notes": static_def.licensing_notes,
            "parser_identifier": static_def.parser_identifier,
            "source_vintage_note": static_def.source_vintage_note,
            "parser_version": "0.2.0-draft",
        }

        artifact = artifacts_by_id.get(static_def.source_id)
        if artifact:
            base_dict["retrieved_at"] = artifact.retrieved_at or None
            base_dict["sha256"] = artifact.sha256 or None
            base_dict["byte_size"] = artifact.byte_size or None
            base_dict["local_cache_filename"] = artifact.local_cache_filename or None
            base_dict["validation_status"] = artifact.validation_status
            base_dict["resolved_url"] = artifact.resolved_url or None
            base_dict["retrieval_notes"] = artifact.notes or None
        else:
            base_dict["retrieved_at"] = None
            base_dict["sha256"] = None
            base_dict["byte_size"] = None
            base_dict["local_cache_filename"] = None
            base_dict["validation_status"] = "PARSER_READY_NOT_RETRIEVED"
            base_dict["resolved_url"] = None
            base_dict["retrieval_notes"] = None

        sources_out.append(base_dict)

    known_ids = {item["source_id"] for item in sources_out}
    for artifact in retrieved_artifacts:
        if artifact.source_id in known_ids:
            continue
        sources_out.append(
            {
                "source_id": artifact.source_id,
                "retrieved_at": artifact.retrieved_at or None,
                "sha256": artifact.sha256 or None,
                "byte_size": artifact.byte_size or None,
                "local_cache_filename": artifact.local_cache_filename or None,
                "validation_status": artifact.validation_status,
                "resolved_url": artifact.resolved_url or None,
                "retrieval_notes": artifact.notes or None,
            }
        )

    manifest_doc = {
        "manifest_type": "living_cost_source_manifest",
        "methodology_version": "0.2.0-draft",
        "generated_at": now_iso,
        "source_count": len(sources_out),
        "sources": sources_out,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest_doc, fh, indent=2)

    return manifest_doc
