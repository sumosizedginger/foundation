"""Year-specific CMS individual-market platform / data-source map.

SBE ZIP existence is not a platform classification. SBE-FP states use the
federal Exchange PUFs for individual-market plan/rate data.
"""

from __future__ import annotations

from typing import Any

ALL_JURISDICTIONS: tuple[str, ...] = (
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
)

# Standalone individual-market State-Based Marketplaces / SBEs.
# Oregon is NOT included: PY2024 HealthCare.gov; PY2026 SBE-FP.
# Evidence: CMS Open Enrollment reporting (2024 HealthCare.gov for OR);
# CMS PY2026 21 SBE + 3 SBE-FP (AR, OR, OK).
STANDALONE_INDIVIDUAL_SBE: dict[int, frozenset[str]] = {
    2024: frozenset(
        {
            "CA",
            "CO",
            "CT",
            "DC",
            "ID",
            "KY",
            "ME",
            "MD",
            "MA",
            "MN",
            "NV",
            "NJ",
            "NM",
            "NY",
            "PA",
            "RI",
            "VT",
            "VA",
            "WA",
        }
    ),
    2026: frozenset(
        {
            "CA",
            "CO",
            "CT",
            "DC",
            "GA",
            "ID",
            "IL",
            "KY",
            "ME",
            "MD",
            "MA",
            "MN",
            "NV",
            "NJ",
            "NM",
            "NY",
            "PA",
            "RI",
            "VT",
            "VA",
            "WA",
        }
    ),
}

# Governance classification. Individual-market data source remains federal PUF.
SBE_FP_STATES: dict[int, frozenset[str]] = {
    2024: frozenset({"AR", "OK", "OR"}),
    2026: frozenset({"AR", "OK", "OR"}),
}

INDIVIDUAL_SOURCE_FEDERAL = "federal_exchange_puf"
INDIVIDUAL_SOURCE_SBE = "sbe_qhp_puf"
PLATFORM_STANDALONE_SBE = "standalone_sbm"
PLATFORM_SBE_FP = "sbe_fp"
PLATFORM_FFM = "healthcare_gov_ffm"


def individual_market_source(year: int, state: str) -> str:
    st = state.upper()
    if st in STANDALONE_INDIVIDUAL_SBE[year]:
        return INDIVIDUAL_SOURCE_SBE
    return INDIVIDUAL_SOURCE_FEDERAL


def marketplace_platform_classification(year: int, state: str) -> str:
    st = state.upper()
    if st in STANDALONE_INDIVIDUAL_SBE[year]:
        return PLATFORM_STANDALONE_SBE
    if st in SBE_FP_STATES[year]:
        return PLATFORM_SBE_FP
    return PLATFORM_FFM


def build_platform_map(year: int, sbe_archive_states: set[str] | None = None) -> dict[str, Any]:
    """Machine-readable 50-state+DC individual-market platform/source map."""
    if year not in STANDALONE_INDIVIDUAL_SBE:
        raise ValueError(f"Unsupported CMS platform year: {year}")
    archives = {s.upper() for s in (sbe_archive_states or set())}
    jurisdictions: dict[str, dict[str, Any]] = {}
    for state in ALL_JURISDICTIONS:
        platform = marketplace_platform_classification(year, state)
        source = individual_market_source(year, state)
        archive_exists = state in archives
        shop_source = "sbe_qhp_puf" if archive_exists else "not_in_sbe_archive"
        if platform == PLATFORM_SBE_FP and archive_exists:
            source_use = (
                "individual_market_from_federal_exchange_puf; "
                "sbe_archive_retained_for_shop_or_non_individual_scope"
            )
        elif source == INDIVIDUAL_SOURCE_SBE:
            source_use = "individual_market_lowest_silver_from_sbe_qhp_puf"
        else:
            source_use = "individual_market_lowest_silver_from_federal_exchange_puf"
        jurisdictions[state] = {
            "marketplace_platform_classification": platform,
            "individual_market_source": source,
            "SHOP_source": shop_source,
            "SBE_archive_exists": archive_exists,
            "source_use": source_use,
        }
    standalone = sorted(STANDALONE_INDIVIDUAL_SBE[year])
    sbe_fp = sorted(SBE_FP_STATES[year])
    federal = sorted(
        s
        for s in ALL_JURISDICTIONS
        if individual_market_source(year, s) == INDIVIDUAL_SOURCE_FEDERAL
    )
    return {
        "report_type": "cms_individual_market_platform_map",
        "year": year,
        "jurisdiction_count": len(ALL_JURISDICTIONS),
        "standalone_individual_sbe_states": standalone,
        "standalone_individual_sbe_count": len(standalone),
        "sbe_fp_states": sbe_fp,
        "sbe_fp_count": len(sbe_fp),
        "federal_platform_individual_market_states": federal,
        "federal_platform_individual_market_count": len(federal),
        "note": (
            "SBE QHP ZIP existence is not platform classification. "
            "SBE-FPs use the federal platform and are in the federal Exchange PUFs. "
            "Oregon individual-market source is federal for 2024 and 2026."
        ),
        "jurisdictions": jurisdictions,
    }


def assert_platform_map_invariants(year: int, payload: dict[str, Any] | None = None) -> None:
    """Fail if any jurisdiction is double-counted or missing."""
    payload = payload or build_platform_map(year)
    juris = payload["jurisdictions"]
    if set(juris) != set(ALL_JURISDICTIONS):
        raise ValueError("Platform map does not cover exactly 50 states + DC")
    standalone = set(payload["standalone_individual_sbe_states"])
    federal = set(payload["federal_platform_individual_market_states"])
    overlap = standalone & federal
    if overlap:
        raise ValueError(f"Jurisdictions classified as both standalone SBE and federal: {overlap}")
    if standalone | federal != set(ALL_JURISDICTIONS):
        raise ValueError("Standalone SBE + federal platform do not partition 50 states + DC")
    if "OR" in standalone:
        raise ValueError("Oregon must not be a standalone individual-market SBE")
    if payload["jurisdiction_count"] != 51:
        raise ValueError("Expected 51 jurisdictions")
    if year == 2024 and payload["standalone_individual_sbe_count"] != 19:
        raise ValueError("2024 standalone individual SBE count must be 19")
    if year == 2024 and payload["federal_platform_individual_market_count"] != 32:
        raise ValueError("2024 federal-platform individual-market count must be 32")
    if year == 2026 and payload["standalone_individual_sbe_count"] != 21:
        raise ValueError("2026 standalone individual SBE count must be 21")
    if year == 2026 and payload["federal_platform_individual_market_count"] != 30:
        raise ValueError("2026 federal-platform individual-market count must be 30")
    for state in SBE_FP_STATES[year]:
        if juris[state]["individual_market_source"] != INDIVIDUAL_SOURCE_FEDERAL:
            raise ValueError(f"{state} SBE-FP must use federal Exchange PUFs")
