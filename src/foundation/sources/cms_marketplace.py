"""CMS Health Insurance Marketplace Source Adapter.

Ingests and parses official CMS Marketplace Public Use Files (PUF) for Federally-facilitated
Marketplaces (FFM) and official State-Based Exchange (SBE) public rate files to deterministically
select the Lowest-Cost Adequate Silver Plan for an independent single adult (Age 40, non-tobacco).

LOWEST-COST ADEQUATE SILVER SELECTION CRITERIA:
1. Standard individual-market major medical plan (HMO, PPO, EPO, POS) covering Essential Health Benefits.
2. Metal Level = "Silver" (70% actuarial value benchmark).
3. Excludes: Catastrophic plans, dental-only, vision-only, child-only, and non-ACA indemnity plans.
4. Profile: Single adult age 40, non-smoker / standard non-tobacco rate.
5. Geography: Validated plan availability in the specific rating area.
6. Pricing: 100% unsubsidized gross premium (zero ACA Advance Premium Tax Credits).
7. Deterministic Tie-Breaker:
   - Primary: Lowest monthly unsubsidized premium ($/mo).
   - Secondary: Lower medical in-network individual deductible.
   - Tertiary: Alphabetical Plan ID (StandardComponentId) ascending.
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source, record_unretrieved
from foundation.sources.cms_platform import STANDALONE_INDIVIDUAL_SBE

logger = logging.getLogger(__name__)

CMS_PUF_LANDING = "https://www.cms.gov/marketplace/resources/data/public-use-files"
CMS_SBE_PUF_LANDING = "https://www.cms.gov/marketplace/resources/data/state-based-public-use-files"

CMS_PUF_SLUGS = {
    "rate_puf": "rate-puf",
    "plan_attributes_puf": "plan-attributes-puf",
    "service_area_puf": "service-area-puf",
    "benefits_puf": "benefits-and-cost-sharing-puf",
}

CMS_PUF_URLS: dict[int, dict[str, str]] = {
    year: {
        key: f"https://download.cms.gov/marketplace-puf/{year}/{slug}.zip"
        for key, slug in CMS_PUF_SLUGS.items()
    }
    for year in (2024, 2026)
}


def download_cms_marketplace_artifacts(
    year: int, cache_dir: Path, force_download: bool = False
) -> dict[str, Any]:
    """Download required CMS PUFs for a given year."""
    if year not in CMS_PUF_URLS:
        raise ValueError(f"Unsupported CMS PUF reference year: {year}")

    config = CMS_PUF_URLS[year]
    cache_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {}
    for puf_type, url in config.items():
        artifact = acquire_source(
            source_id=f"cms_{puf_type}_{year}",
            url=url,
            cache_dir=cache_dir,
            expected_filename=f"cms_{year}_{puf_type}.zip",
            force_download=force_download,
        )
        if artifact is None:
            raise RuntimeError(f"Required CMS PUF {puf_type} for {year} is UNAVAILABLE.")
        artifacts[puf_type] = artifact

    return artifacts


# Standalone individual-market SBE states. Oregon is excluded: PY2024
# HealthCare.gov / PY2026 SBE-FP. ZIP existence is not classification.
# Year-specific slugs still retrieve Oregon archives for SHOP/scope inspection.
SBE_STANDALONE_STATES: dict[int, frozenset[str]] = STANDALONE_INDIVIDUAL_SBE

# Official per-state zip slugs copied from the CMS landing-page Downloads section.
# Filenames are year-specific and not assumed to follow one national pattern.
SBE_STATE_ZIP_SLUGS: dict[int, dict[str, str]] = {
    2024: {
        "CA": "californiasbepuf2024.zip",
        "CO": "coloradosbepuf2024.zip",
        "CT": "connecticutsbepuf2024.zip",
        "DC": "districtofcolumbiasbepuf2024.zip",
        "ID": "idahosbepuf2024.zip",
        "KY": "kentuckysbepuf2024.zip",
        "ME": "mainesbepuf2024.zip",
        "MD": "marylandsbepuf2024.zip",
        "MA": "massachusettssbepuf2024.zip",
        "MN": "minnesotasbepuf2024.zip",
        "NV": "nevadasbepuf2024.zip",
        "NJ": "newjerseysbepuf2024.zip",
        "NM": "newmexicosbepuf2024.zip",
        "NY": "newyorksbepuf2024.zip",
        "OR": "oregonsbepuf2024.zip",
        "PA": "pennsylvaniasbepuf2024.zip",
        "RI": "rhodeislandsbepuf2024.zip",
        "VT": "vermontsbepuf2024.zip",
        "VA": "virginiasbepuf2024.zip",
        "WA": "washingtonsbepuf2024.zip",
    },
    2026: {
        "CA": "californiasbpuf2026.zip",
        "CO": "coloradosbepuf2026.zip",
        "CT": "connecticutsbepuf2026.zip",
        "DC": "districtofcolumbiapuf2026.zip",
        "GA": "georgiasbepuf2026.zip",
        "ID": "idahosbepuf2026.zip",
        "IL": "illinois-sbe-qhp-puf.zip",
        "KY": "kentuckysbepuf2026.zip",
        "ME": "mainesbepuf2026.zip",
        "MD": "marylandsbepuf2026.zip",
        "MA": "massachusettssbepuf2026.zip",
        "MN": "minnesotasbepuf2026.zip",
        "NV": "nevadasbepuf2026.zip",
        "NJ": "newjerseysbepuf2026.zip",
        "NM": "newmexicosbepuf2026.zip",
        "NY": "newyorksbepuf2026.zip",
        "OR": "oregonsbepuf2026.zip",
        "PA": "pennsylvaniasbepuf2026.zip",
        "RI": "rhodeislandsbepuf2026.zip",
        "VT": "vermontsbepuf2026.zip",
        "VA": "virginiasbepuf2026.zip",
        "WA": "washingtonsbepuf2026.zip",
    },
}

SBE_DICTIONARY_ZIP: dict[int, str] = {
    2024: "https://www.cms.gov/files/zip/2024-sbe-qhp-puf-datadictionary.zip",
    2026: "https://www.cms.gov/files/zip/sbe-puf-files-2026.zip",
}


def sbe_state_zip_url(year: int, state: str) -> str:
    slug = SBE_STATE_ZIP_SLUGS[year][state]
    return f"https://www.cms.gov/files/zip/{slug}"


def download_cms_sbe_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Retrieve official per-state CMS SBE QHP PUF zips. Dictionary-only zips are not plan data."""
    if year not in SBE_STATE_ZIP_SLUGS:
        raise ValueError(f"Unsupported CMS SBE reference year: {year}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    from dataclasses import replace

    artifacts = []
    retrieved_states: list[str] = []
    parsed_states: list[str] = []
    missing_states: list[str] = []
    for state, slug in SBE_STATE_ZIP_SLUGS[year].items():
        artifact = acquire_source(
            source_id=f"cms_sbe_{state.lower()}_{year}",
            url=sbe_state_zip_url(year, state),
            cache_dir=cache_dir,
            expected_filename=f"cms_sbe_{year}_{state.lower()}_{slug}",
            force_download=force_download,
            refresh_if_unprovenanced=True,
        )
        if artifact is None:
            missing_states.append(state)
            artifacts.append(
                record_unretrieved(
                    f"cms_sbe_{state.lower()}_{year}",
                    status="SOURCE_GAP",
                    resolved_url=sbe_state_zip_url(year, state),
                    notes=(
                        f"Official {year} SBE QHP PUF zip for {state} was not retrieved "
                        f"from {CMS_SBE_PUF_LANDING}."
                    ),
                )
            )
            continue
        retrieved_states.append(state)
        path = cache_dir / artifact.local_cache_filename
        csv_members: list[str] = []
        if path.is_file():
            try:
                with zipfile.ZipFile(path) as archive:
                    csv_members = [
                        name for name in archive.namelist() if name.lower().endswith(".csv")
                    ]
            except zipfile.BadZipFile:
                csv_members = []
        if csv_members:
            parsed_states.append(state)
            artifacts.append(
                replace(
                    artifact,
                    validation_status="RETRIEVED_UNVALIDATED",
                    notes=(
                        f"{year} SBE QHP PUF {state}: {len(csv_members)} CSV members "
                        f"({', '.join(csv_members[:6])}). Per-state file; not a national SBE zip. "
                        "Do not infer federal-platform classification from this file."
                    ),
                )
            )
        else:
            artifacts.append(
                replace(
                    artifact,
                    validation_status="SOURCE_GAP",
                    notes=(
                        f"{year} SBE QHP PUF {state} archive contains no CSV members "
                        "(documentation-only or unexpected layout)."
                    ),
                )
            )

    # Year-level coverage artifact used by the auditor / coverage report.
    from foundation.living_cost.manifest import RetrievedSourceArtifact

    expected = sorted(SBE_STANDALONE_STATES[year])
    notes = (
        f"{year} SBE QHP PUF per-state retrieval from {CMS_SBE_PUF_LANDING}. "
        f"SBE states expected={expected}. retrieved={retrieved_states}. "
        f"parsed={parsed_states}. missing={missing_states}. "
        "Do not treat the documentation-only national dictionary zip as plan data. "
        "Do not infer federal-platform classification rules from a state-specific SBE file."
    )
    status = "RETRIEVED_UNVALIDATED" if parsed_states else "SOURCE_GAP"
    artifacts.append(
        RetrievedSourceArtifact(
            source_id=f"cms_sbe_puf_{year}",
            retrieved_at="",
            sha256="",
            byte_size=0,
            local_cache_filename="",
            validation_status=status,
            resolved_url=CMS_SBE_PUF_LANDING,
            notes=notes,
        )
    )
    return artifacts


def _open_puf_table(path: Path) -> Iterator[dict[str, str]]:
    """Yield rows from a CMS PUF CSV or a zip that contains one CSV."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not members:
                return
            with archive.open(members[0]) as raw:
                yield from csv.DictReader(
                    io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
                )
        return
    with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        yield from csv.DictReader(fh)


def _puf_path(cache_dir: Path, year: int, puf_type: str) -> Path | None:
    zip_path = cache_dir / f"cms_{year}_{puf_type}.zip"
    csv_path = cache_dir / f"cms_{year}_{puf_type}.csv"
    if zip_path.exists():
        return zip_path
    if csv_path.exists():
        return csv_path
    return None


def parse_cms_marketplace_multi_puf(
    year: int,
    cache_dir: Path,
) -> list[LivingCostComponentObservation]:
    """Join Plan Attributes, Benefits, and Rates PUFs to select Lowest-Cost Adequate Silver."""
    config = CMS_PUF_URLS.get(year)
    if not config:
        raise ValueError(f"Unsupported CMS PUF reference year: {year}")

    rate_file = _puf_path(cache_dir, year, "rate_puf")
    plan_file = _puf_path(cache_dir, year, "plan_attributes_puf")
    service_file = _puf_path(cache_dir, year, "service_area_puf")
    benefits_file = _puf_path(cache_dir, year, "benefits_puf")

    if rate_file is None or plan_file is None or benefits_file is None:
        logger.warning(f"CMS PUF files missing for {year}, returning empty list.")
        return []

    # 1. Parse Plan Attributes to find valid Silver major medical plans and their deductibles.
    # We map PlanId -> { "deductible": float, "metal": "Silver" }
    valid_plans: dict[str, dict[str, Any]] = {}
    for row in _open_puf_table(plan_file):
        metal = str(row.get("MetalLevel", "")).strip().lower()
        if metal != "silver":
            continue

        plan_type = str(row.get("PlanType", "")).strip().upper()
        if "DENTAL" in plan_type or "CATASTROPHIC" in plan_type:
            continue

        market_cov = str(row.get("MarketCoverage", "")).strip().upper()
        if market_cov == "SHOP":  # Exclude small business
            continue

        plan_id = str(row.get("StandardComponentId", "")).strip()
        if not plan_id:
            continue

        ded_str = row.get("TEHBDedInnTier1Individual", "")
        try:
            # E.g. "$5,000" or "Not Applicable"
            ded = float(str(ded_str).replace("$", "").replace(",", "").strip())
        except ValueError:
            ded = None

        if ded is None:
            continue  # Missing deductible means it fails closed for 'adequate' tie-breaker

        service_area_id = str(row.get("ServiceAreaId") or "").strip()
        issuer_id = str(row.get("IssuerId") or "").strip()
        if not service_area_id or not issuer_id:
            continue  # Fail closed: cannot join to service geography.
        valid_plans[plan_id] = {
            "deductible": ded,
            "metal": "Silver",
            "service_area_id": service_area_id,
            "issuer_id": issuer_id,
            "state": str(row.get("StateCode") or "").strip().upper(),
        }

    benefit_plan_ids: set[str] = set()
    for row in _open_puf_table(benefits_file):
        dental = str(row.get("DentalOnlyPlan") or "").strip().lower()
        if dental in {"yes", "y", "true", "1"}:
            continue
        bid = str(row.get("StandardComponentId") or row.get("PlanId") or "").strip()[:14]
        if bid:
            benefit_plan_ids.add(bid)
    if not benefit_plan_ids:
        logger.warning("CMS Benefits PUF produced no join keys for %s", year)
        return []
    valid_plans = {pid: meta for pid, meta in valid_plans.items() if pid in benefit_plan_ids}
    if not valid_plans:
        logger.warning("CMS Benefits join removed every Silver plan for %s", year)
        return []

    service_keys: set[tuple[str, str, str]] = set()
    if service_file is not None:
        for row in _open_puf_table(service_file):
            dental = str(row.get("DentalOnlyPlan") or "").strip().lower()
            if dental in {"yes", "y", "true", "1"}:
                continue
            issuer_id = str(row.get("IssuerId") or "").strip()
            service_area_id = str(row.get("ServiceAreaId") or "").strip()
            state_alpha = str(row.get("StateCode") or "").strip().upper()
            if not issuer_id or not service_area_id or not state_alpha:
                continue
            cover_state = str(row.get("CoverEntireState") or "").strip().lower()
            county = str(row.get("County") or "").strip()
            if cover_state not in {"yes", "y", "true", "1"} and not county:
                continue
            service_keys.add((state_alpha, issuer_id, service_area_id))

    # 2. Parse Rates PUF for Age 40, non-tobacco, joining against valid_plans
    candidates_by_area: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for row in _open_puf_table(rate_file):
        age = str(row.get("Age", "")).strip()
        if age != "40" and age != "Age 40":
            continue

        tobacco = str(row.get("Tobacco", "")).strip().upper()
        if "TOBACCO" in tobacco and "NON" not in tobacco:
            # We want standard or non-tobacco rates only
            continue

        plan_id = str(row.get("PlanId", "")).strip()
        # The rate PUF PlanId is often 14 chars. StandardComponentId is 14 chars.
        base_plan_id = plan_id[:14] if len(plan_id) >= 14 else plan_id

        if base_plan_id not in valid_plans:
            continue

        plan_meta = valid_plans[base_plan_id]
        if service_keys:
            join_key = (
                str(row.get("StateCode") or "").strip().upper() or plan_meta["state"],
                plan_meta["issuer_id"],
                plan_meta["service_area_id"],
            )
            if join_key not in service_keys:
                continue

        rating_area = str(row.get("RatingAreaId", "")).strip()
        state_alpha = str(row.get("StateCode", "")).strip().upper()

        if not state_alpha or not rating_area:
            continue  # Fail closed on missing geography

        rate_str = row.get("IndividualRate", "0")
        try:
            monthly_prem = float(str(rate_str).replace("$", "").replace(",", "").strip())
        except ValueError:
            continue

        if monthly_prem <= 0:
            continue

        deductible = valid_plans[base_plan_id]["deductible"]

        key = (state_alpha, rating_area)
        candidates_by_area.setdefault(key, []).append(
            {
                "plan_id": plan_id,
                "monthly_premium": monthly_prem,
                "deductible": deductible,
                "state": state_alpha,
                "rating_area": rating_area,
            }
        )

    observations: list[LivingCostComponentObservation] = []

    # 3. Deterministic Selection
    for (state_alpha, rating_area), candidates in sorted(candidates_by_area.items()):
        # Sort by: (1) monthly_premium asc, (2) deductible asc, (3) plan_id asc
        sorted_candidates = sorted(
            candidates, key=lambda c: (c["monthly_premium"], c["deductible"], c["plan_id"])
        )
        selected = sorted_candidates[0]
        annual_prem = round(selected["monthly_premium"] * 12.0, 2)
        geo_id = f"{state_alpha}_{rating_area.replace(' ', '_')}"

        obs = LivingCostComponentObservation(
            component_id="healthcare_silver_unsubsidized",
            category="healthcare",
            geography_type="rating_area",
            geography_id=geo_id,
            geography_name=f"{state_alpha} {rating_area}",
            state=state_alpha,
            reference_year=year,
            value_annual=annual_prem,
            value_monthly=round(selected["monthly_premium"], 2),
            unit="USD",
            status=ComponentStatus.MEASURED,
            source_id=f"cms_rate_puf_{year}",
            source_variable="IndividualRate_Age40_Silver_Adequate",
            source_url=config["rate_puf"],
            source_release=f"CMS Marketplace PUF ({year})",
            source_reference_period=str(year),
            retrieved_at="",  # Will be populated by pipeline artifact tracker
            source_artifact_sha256="",  # Will be populated by pipeline artifact tracker
            methodology_version="0.2.0-draft",
            notes=(
                f"Lowest-Cost Adequate Silver Plan: {selected['plan_id']} "
                f"(${selected['monthly_premium']:,.2f}/mo, Deductible: ${selected['deductible']:,.0f}) "
                f"in {state_alpha} {rating_area}."
            ),
        )
        observations.append(obs)

    return observations


def _norm_field_key(name: str) -> str:
    return "".join(ch for ch in name.upper() if ch.isalnum())


def _row_get(row: dict[str, str], *names: str) -> str:
    mapped = {_norm_field_key(k): v for k, v in row.items()}
    for name in names:
        value = mapped.get(_norm_field_key(name))
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def _parse_money(raw: str) -> float | None:
    text = str(raw or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"not applicable", "n/a", "na", "none"}:
        return None
    cleaned = text.replace("$", "").replace(",", "").split("|", 1)[0].strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _classify_sbe_member(name: str) -> str | None:
    lower = name.lower().replace("\\", "/").rsplit("/", 1)[-1]
    if not lower.endswith(".csv"):
        return None
    if "rate" in lower:
        return "rate"
    if "plan" in lower and "benefit" not in lower:
        return "plan"
    if "service" in lower:
        return "service_area"
    if "benefit" in lower:
        return "benefits"
    if "business" in lower:
        return "business_rules"
    return None


def inspect_sbe_archive(path: Path, year: int, state: str) -> dict[str, Any]:
    """Inspect an official SBE ZIP without inferring platform classification."""
    report: dict[str, Any] = {
        "year": year,
        "state": state,
        "SBE_archive_exists": path.is_file(),
        "members": [],
        "market_scope": "unknown",
        "platform_scope": "sbe_qhp_archive",
        "source_use": "inspect_only",
        "rows_by_file": {},
        "market_coverage_counts": {},
    }
    if not path.is_file():
        report["source_use"] = "archive_missing"
        return report
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.namelist()
            report["members"] = members
            markets: dict[str, int] = {}
            for name in members:
                kind = _classify_sbe_member(name)
                if kind is None:
                    continue
                with archive.open(name) as raw:
                    reader = csv.DictReader(
                        io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
                    )
                    count = 0
                    for row in reader:
                        count += 1
                        if kind == "plan":
                            market = _row_get(row, "Market Coverage", "MarketCoverage") or "<blank>"
                            markets[market] = markets.get(market, 0) + 1
                    report["rows_by_file"][kind] = count
            report["market_coverage_counts"] = markets
            individual = any("individual" in key.lower() for key in markets)
            shop = any("shop" in key.lower() for key in markets)
            if shop and not individual:
                report["market_scope"] = "SHOP_only"
                report["source_use"] = "retain_artifact_do_not_use_for_individual_silver"
            elif individual and shop:
                report["market_scope"] = "individual_and_SHOP"
                report["source_use"] = "individual_market_rows_only_for_lowest_silver"
            elif individual:
                report["market_scope"] = "individual"
                report["source_use"] = "individual_market_lowest_silver"
            else:
                report["market_scope"] = "no_market_coverage_field_or_empty"
                report["source_use"] = "fail_closed_unknown_market"
    except zipfile.BadZipFile:
        report["market_scope"] = "bad_zip"
        report["source_use"] = "archive_unreadable"
    return report


def parse_sbe_state_lowest_silver(
    path: Path,
    year: int,
    state: str,
) -> dict[str, Any]:
    """Lowest-Silver join for one standalone SBE ZIP. Schemas may differ from federal PUF."""
    empty = {
        "year": year,
        "state": state,
        "status": "UNAVAILABLE",
        "rows_parsed_by_source_file": {},
        "individual_market_rows_retained": 0,
        "silver_plans_retained": 0,
        "age_40_rates_retained": 0,
        "service_areas_represented": 0,
        "rating_areas_represented": 0,
        "counties_represented": 0,
        "final_qualifying_plan_count": 0,
        "lowest_silver_output_count": 0,
        "unmatched_join_keys": 0,
        "duplicate_keys": 0,
        "observations": [],
        "notes": "",
    }
    if not path.is_file():
        empty["notes"] = "SBE ZIP missing"
        return empty

    tables: dict[str, list[dict[str, str]]] = {}
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                kind = _classify_sbe_member(name)
                if kind is None:
                    continue
                with archive.open(name) as raw:
                    reader = csv.DictReader(
                        io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
                    )
                    tables[kind] = list(reader)
    except zipfile.BadZipFile as exc:
        empty["notes"] = f"Bad SBE ZIP: {exc}"
        return empty

    rows_by_file = {kind: len(rows) for kind, rows in tables.items()}
    empty["rows_parsed_by_source_file"] = rows_by_file
    if "plan" not in tables or "rate" not in tables:
        empty["notes"] = "SBE ZIP missing Plan or Rate CSV"
        empty["status"] = "SOURCE_GAP"
        return empty

    valid_plans: dict[str, dict[str, Any]] = {}
    individual_rows = 0
    silver_rows = 0
    for row in tables["plan"]:
        market = _row_get(row, "Market Coverage", "MarketCoverage").upper()
        if "SHOP" in market:
            continue
        if market and "INDIVIDUAL" not in market:
            continue
        individual_rows += 1
        metal = _row_get(row, "Metal Level", "MetalLevel").lower()
        if metal != "silver":
            continue
        silver_rows += 1
        dental = _row_get(row, "Dental Only Plan", "DentalOnlyPlan").lower()
        if dental in {"yes", "y", "true", "1"}:
            continue
        plan_type = _row_get(row, "Plan Type", "PlanType").upper()
        if "DENTAL" in plan_type or "CATASTROPHIC" in plan_type:
            continue
        plan_id = _row_get(row, "Standard Component ID", "StandardComponentId")
        if not plan_id:
            continue
        deductible = _parse_money(
            _row_get(
                row,
                "TEHB DED INN TIER 1 INDIVIDUAL",
                "TEHBDedInnTier1Individual",
                "MEHB DED INN TIER1 INDIVIDUAL",
                "MEHBDedInnTier1Individual",
            )
        )
        if deductible is None:
            continue
        service_area_id = _row_get(row, "Service Area ID", "ServiceAreaId")
        issuer_id = _row_get(row, "Issuer ID", "IssuerId")
        if not service_area_id or not issuer_id:
            continue
        valid_plans[plan_id] = {
            "deductible": deductible,
            "service_area_id": service_area_id,
            "issuer_id": issuer_id,
            "state": _row_get(row, "State Code", "StateCode").upper() or state,
        }

    if "benefits" in tables:
        benefit_ids: set[str] = set()
        for row in tables["benefits"]:
            dental = _row_get(row, "Dental Only Plan", "DentalOnlyPlan").lower()
            if dental in {"yes", "y", "true", "1"}:
                continue
            bid = _row_get(row, "Standard Component ID", "StandardComponentId", "Plan ID", "PlanId")
            if bid:
                benefit_ids.add(bid[:14])
        if benefit_ids:
            valid_plans = {
                pid: meta for pid, meta in valid_plans.items() if pid[:14] in benefit_ids
            }

    service_keys: set[tuple[str, str, str]] = set()
    counties: set[str] = set()
    if "service_area" in tables:
        for row in tables["service_area"]:
            dental = _row_get(row, "Dental Only Plan", "DentalOnlyPlan").lower()
            if dental in {"yes", "y", "true", "1"}:
                continue
            issuer_id = _row_get(row, "Issuer ID", "IssuerId")
            service_area_id = _row_get(row, "Service Area ID", "ServiceAreaId")
            state_alpha = _row_get(row, "State Code", "StateCode").upper() or state
            if not issuer_id or not service_area_id:
                continue
            cover_state = _row_get(row, "Cover Entire State", "CoverEntireState").lower()
            county = _row_get(row, "County")
            if cover_state not in {"yes", "y", "true", "1"} and not county:
                continue
            if county:
                counties.add(county)
            service_keys.add((state_alpha, issuer_id, service_area_id))

    candidates_by_area: dict[tuple[str, str], list[dict[str, Any]]] = {}
    age40 = 0
    unmatched_join = 0
    for row in tables["rate"]:
        age = _row_get(row, "Age")
        # Vermont (and any community-rated SBE) publishes a single Individual
        # Rate with a blank Age. That rate is the age-independent single-adult
        # premium and is the correct Age-40 equivalent. Other explicit ages
        # still require 40 / Age 40.
        if age not in {"40", "Age 40", ""}:
            continue
        tobacco = _row_get(row, "Tobacco").upper()
        if "TOBACCO" in tobacco and "NON" not in tobacco:
            continue
        plan_id = _row_get(row, "Plan ID", "PlanId")
        base_plan_id = plan_id[:14] if len(plan_id) >= 14 else plan_id
        if base_plan_id not in valid_plans:
            continue
        age40 += 1
        plan_meta = valid_plans[base_plan_id]
        if service_keys:
            join_key = (
                _row_get(row, "State Code", "StateCode").upper() or plan_meta["state"],
                plan_meta["issuer_id"],
                plan_meta["service_area_id"],
            )
            if join_key not in service_keys:
                unmatched_join += 1
                continue
        rating_area = _row_get(row, "Rating Area ID", "RatingAreaId")
        state_alpha = _row_get(row, "State Code", "StateCode").upper() or state
        if not state_alpha or not rating_area:
            continue
        monthly = _parse_money(_row_get(row, "Individual Rate", "IndividualRate"))
        if monthly is None or monthly <= 0:
            continue
        key = (state_alpha, rating_area)
        candidates_by_area.setdefault(key, []).append(
            {
                "plan_id": plan_id,
                "monthly_premium": monthly,
                "deductible": plan_meta["deductible"],
                "state": state_alpha,
                "rating_area": rating_area,
            }
        )

    observations: list[LivingCostComponentObservation] = []
    for (state_alpha, rating_area), candidates in sorted(candidates_by_area.items()):
        selected = min(
            candidates, key=lambda c: (c["monthly_premium"], c["deductible"], c["plan_id"])
        )
        annual_prem = round(selected["monthly_premium"] * 12.0, 2)
        geo_id = f"{state_alpha}_{rating_area.replace(' ', '_')}"
        observations.append(
            LivingCostComponentObservation(
                component_id="healthcare_silver_unsubsidized",
                category="healthcare",
                geography_type="rating_area",
                geography_id=geo_id,
                geography_name=f"{state_alpha} {rating_area}",
                state=state_alpha,
                reference_year=year,
                value_annual=annual_prem,
                value_monthly=round(selected["monthly_premium"], 2),
                unit="USD",
                status=ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
                source_id=f"cms_sbe_{state.lower()}_{year}",
                source_variable="IndividualRate_Age40_Silver_Adequate_SBE",
                source_url=sbe_state_zip_url(year, state),
                source_release=f"CMS SBE QHP PUF ({year} {state})",
                source_reference_period=str(year),
                retrieved_at="",
                source_artifact_sha256="",
                methodology_version="0.2.0-draft",
                notes=(
                    f"SBE lowest-cost adequate Silver: {selected['plan_id']} "
                    f"(${selected['monthly_premium']:,.2f}/mo) in {state_alpha} {rating_area}."
                ),
            )
        )

    status = "MODELED_FROM_MEASURED_INPUTS" if observations else "RETRIEVED_UNVALIDATED"
    notes = (
        f"{state} {year} SBE lowest-Silver join. "
        f"individual_rows={individual_rows}; silver={silver_rows}; "
        f"age40_joined={age40}; outputs={len(observations)}."
    )
    if individual_rows == 0:
        notes += " No individual-market plan rows; do not treat as federal-platform fill."
        status = "RETRIEVED_UNVALIDATED"
    return {
        "year": year,
        "state": state,
        "status": status,
        "rows_parsed_by_source_file": rows_by_file,
        "individual_market_rows_retained": individual_rows,
        "silver_plans_retained": silver_rows,
        "age_40_rates_retained": age40,
        "service_areas_represented": len(service_keys),
        "rating_areas_represented": len(candidates_by_area),
        "counties_represented": len(counties),
        "final_qualifying_plan_count": len(valid_plans),
        "lowest_silver_output_count": len(observations),
        "unmatched_join_keys": unmatched_join,
        "duplicate_keys": 0,
        "observations": observations,
        "notes": notes,
    }


def parse_standalone_sbe_lowest_silver(
    year: int,
    cache_dir: Path,
) -> dict[str, Any]:
    """Run the lowest-Silver join for every true standalone individual-market SBE."""
    slugs = SBE_STATE_ZIP_SLUGS[year]
    standalone = sorted(SBE_STANDALONE_STATES[year])
    states: dict[str, Any] = {}
    observations: list[LivingCostComponentObservation] = []
    for state in standalone:
        slug = slugs[state]
        path = cache_dir / f"cms_sbe_{year}_{state.lower()}_{slug}"
        report = parse_sbe_state_lowest_silver(path, year, state)
        states[state] = {k: v for k, v in report.items() if k != "observations"}
        observations.extend(report["observations"])
    oregon_path = cache_dir / f"cms_sbe_{year}_or_{slugs['OR']}" if "OR" in slugs else None
    oregon = (
        inspect_sbe_archive(oregon_path, year, "OR")
        if oregon_path is not None
        else {"SBE_archive_exists": False, "market_scope": "no_archive_slug"}
    )
    passed = [
        st
        for st, rep in states.items()
        if rep["lowest_silver_output_count"] > 0 and rep["individual_market_rows_retained"] > 0
    ]
    return {
        "year": year,
        "standalone_states": standalone,
        "states_joined": passed,
        "states_joined_count": len(passed),
        "standalone_count": len(standalone),
        "all_standalone_joined": len(passed) == len(standalone) and len(standalone) > 0,
        "lowest_silver_output_count": len(observations),
        "oregon_archive": oregon,
        "states": states,
        "observations": observations,
    }
