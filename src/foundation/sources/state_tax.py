"""Official 51-jurisdiction state-tax RULE_YEAR evidence inventory.

Does not calculate an MSLC. Candidate STATE_STATUTORY_SCHEDULES are audited
against retrieved official government artifacts. Unknown is not zero.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
INVENTORY_PATH = METADATA_DIR / "living_cost_state_tax_inventory.json"
INVENTORY_REPORT_TYPE = "living_cost_state_tax_inventory"

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
TAX_YEARS: tuple[int, ...] = (2024, 2026)
NO_TAX_CANDIDATES: frozenset[str] = frozenset(
    {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}
)
STATUS_NO_WAGE_TAX = "VERIFIED_NO_GENERAL_WAGE_INCOME_TAX"
STATUS_TAXING = "GENERAL_WAGE_INCOME_TAX"
STATUS_INCOMPLETE = "STATE_EVIDENCE_INCOMPLETE"

NO_TAX_PHRASES: dict[str, tuple[str, ...]] = {
    "AK": (
        "has no personal income tax",
        "alaska has no personal income tax",
        "does not have a state income tax",
        "does not have a personal income tax",
        "no personal state income tax",
        "no personal income tax",
    ),
    "FL": (
        "does not impose a personal income tax",
        "does not have a personal income tax",
        "does not have an individual income tax",
        "no individual income tax",
        "no personal income tax",
    ),
    "NV": (
        "no state income tax on individuals",
        "does not impose a state income tax on individuals",
        "do not pay state tax on income earned from salaries",
        "does not have an individual income tax",
        "does not have a personal income tax",
        "no personal income tax",
    ),
    "NH": (
        "does not tax wage",
        "does not tax wages",
        "no tax on wage",
        "does not tax earned income",
        "wages, salaries",
        "interest and dividends tax is repealed",
        "interest and dividends tax repeal",
        "no general income tax on wages",
    ),
    "SD": (
        "does not impose a state income tax",
        "does not have a state income tax",
        "does not have a personal income tax",
        "no state income tax",
        "no individual income tax",
        "no personal income tax",
    ),
    "TN": (
        "imposed only on individuals and other entities receiving interest",
        "hall income tax was repealed",
        "repealed for tax periods that begin on january 1, 2021",
        "no tax on wage",
        "does not tax wage",
        "no individual income tax on wages",
    ),
    "TX": (
        "does not have a personal income tax",
        "does not have a state income tax",
        "does not levy an income tax",
        "no personal income tax",
    ),
    "WA": (
        "does not have a personal income tax",
        "does not have a personal or corporate income tax",
        "no personal income tax",
        "no individual income tax on wages",
    ),
    "WY": (
        "does not possess an individual or corporate income tax",
        "wyoming does not possess an individual or corporate income tax",
        "wyoming does not have an individual income tax",
        "does not have an individual income tax",
        "does not have a personal income tax",
        "no individual income tax",
        "no personal income tax",
        "does not impose an individual income tax",
    ),
}

HIGH_AGI_INCOME_TAX_PHRASES: tuple[str, ...] = (
    "enacted an income tax on individuals",
    "income tax on individuals with an annual adjusted gross income of $1,000,000",
    "adjusted gross income of $1,000,000 or more",
    "adjusted gross income of $1000000 or more",
)


OFFICIAL_NON_GOV_HOSTS = frozenset(
    {
        "floridarevenue.com",
        "www.floridarevenue.com",
    }
)


def official_state_url(url: str | None) -> bool:
    if not url:
        return False
    host = (urlparse(url).hostname or "").lower()
    if host.endswith((".gov", ".us")):
        return True
    return host in OFFICIAL_NON_GOV_HOSTS


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("pypdf is required to parse state tax PDFs")
        return ""
    try:
        reader = PdfReader(str(path))
    except (OSError, ValueError) as exc:
        logger.error("Failed to open state tax PDF %s: %s", path, exc)
        return ""
    parts: list[str] = []
    for page in reader.pages[:40]:
        try:
            parts.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("state tax PDF page extract failed: %s", exc)
    return "\n".join(parts)


def _html_to_text(raw: str) -> str:
    import html as html_lib

    blob = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    blob = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", blob)
    blob = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", blob)
    blob = re.sub(r"(?s)<[^>]+>", " ", blob)
    blob = html_lib.unescape(blob)
    return re.sub(r"\s+", " ", blob).strip()


def _text_for_path(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    if path.suffix.lower() == ".pdf":
        return _extract_pdf_text(path)
    return _html_to_text(path.read_text(encoding="utf-8", errors="replace"))


def _acquire(
    source_id: str,
    url: str,
    filename: str,
    *,
    force_download: bool = False,
) -> dict[str, Any]:
    from foundation.living_cost.freshness_currentness import download_temp_bytes
    from foundation.living_cost.freshness_discovery import _BROWSER_HEADERS
    from foundation.sources.acquisition import acquire_source, write_retrieval_sidecar

    path = CACHE_DIR / filename
    if force_download and path.is_file():
        path.unlink()
        sidecar = Path(str(path) + ".provenance.json")
        if sidecar.is_file():
            sidecar.unlink()
    art = acquire_source(
        source_id=source_id,
        url=url,
        cache_dir=CACHE_DIR,
        expected_filename=filename,
        force_download=force_download,
        refresh_if_unprovenanced=True,
    )
    if art is None or not path.is_file():
        try:
            tmp, digest = download_temp_bytes(url, headers=_BROWSER_HEADERS, suffix=path.suffix)
            try:
                path.write_bytes(tmp.read_bytes())
            finally:
                tmp.unlink(missing_ok=True)
            retrieved_at = _now_iso()
            write_retrieval_sidecar(
                path,
                source_id=source_id,
                url=url,
                retrieved_at=retrieved_at,
                sha256=digest,
                byte_size=path.stat().st_size,
                http_status=200,
                content_type=None,
            )
            art = type("Art", (), {"retrieved_at": retrieved_at})()
        except (OSError, RuntimeError, ValueError) as exc:
            logger.warning("browser acquire failed for %s: %s", url, exc)
    sha = file_sha256(path)
    return {
        "key": source_id,
        "source_id": source_id,
        "url": url,
        "filename": filename,
        "path": str(path) if path.is_file() else None,
        "sha256": sha,
        "retrieved_at": getattr(art, "retrieved_at", None) if art else None,
        "byte_size": int(path.stat().st_size) if path.is_file() else None,
        "http_ok": bool(sha),
        "publisher_host": (urlparse(url).hostname or "").lower(),
    }


def authority_catalog() -> list[dict[str, Any]]:
    """Official first-party state/District tax authority surfaces.

    Year-specific booklets are preferred. A longstanding no-wage-tax page may
    cover both RULE_YEARs when the official text states the absence of a
    general wage income tax.
    """
    specs: list[dict[str, Any]] = []

    def add(
        state: str,
        year: int,
        url: str,
        *,
        role: str,
        publisher: str,
        authority_type: str,
        slug: str,
    ) -> None:
        ext = ".pdf" if url.lower().endswith(".pdf") else ".html"
        key = f"st_{state.lower()}_{year}_{slug}"
        specs.append(
            {
                "key": key,
                "state": state,
                "year": year,
                "url": url,
                "publisher": publisher,
                "authority_type": authority_type,
                "role": role,
                "filename": f"{key}{ext}",
            }
        )

    no_tax_pages = {
        "AK": (
            "https://childsupport.alaska.gov/child-support-enforcement/information/faqs/child-support-enforcement-services-faq",
            "Alaska Child Support Services / Department of Revenue",
        ),
        "FL": (
            "https://floridarevenue.com/faq/Pages/FAQDetails.aspx?FAQID=1466",
            "Florida Department of Revenue",
        ),
        "NV": (
            "https://tax.nv.gov/about-nevada-department-of-taxation/income-tax-in-nevada/",
            "Nevada Department of Taxation",
        ),
        "NH": (
            "https://www.gencourt.state.nh.us/rsa/html/V/77/77-mrg.htm",
            "New Hampshire General Court / RSA 77",
        ),
        "SD": (
            "https://dor.sd.gov/individuals/taxes/",
            "South Dakota Department of Revenue",
        ),
        "TN": (
            "https://www.tn.gov/revenue/taxes/hall-income-tax.html",
            "Tennessee Department of Revenue",
        ),
        "TX": (
            "https://comptroller.texas.gov/economy/fiscal-notes/archive/2016/february/starting.php",
            "Texas Comptroller of Public Accounts",
        ),
        "WA": (
            "https://dor.wa.gov/taxes-rates/income-tax",
            "Washington State Department of Revenue",
        ),
        "WY": (
            "https://www.wyo.gov/about-wyoming",
            "State of Wyoming",
        ),
    }
    for state, (url, publisher) in no_tax_pages.items():
        for year in TAX_YEARS:
            add(
                state,
                year,
                url,
                role="wage_income_status",
                publisher=publisher,
                authority_type="dor_page",
                slug="no_wage_tax",
            )
    # Year-specific NH authorities: 2024 I&D statute description vs 2026 repeal.
    for spec in specs:
        if spec["state"] != "NH":
            continue
        if spec["year"] == 2024:
            spec["url"] = "https://www.gencourt.state.nh.us/legislation/2021/HB0002.html"
            spec["publisher"] = "New Hampshire General Court"
            spec["authority_type"] = "enacted_legislation"
        elif spec["year"] == 2026:
            spec["url"] = "https://www.gencourt.state.nh.us/rsa/html/V/77/77-mrg.htm"
            spec["publisher"] = "New Hampshire General Court / RSA 77"
            spec["authority_type"] = "statute"

    taxing_pages: dict[str, tuple[str, str]] = {
        "AL": (
            "https://www.revenue.alabama.gov/individual-corporate/individual-income-tax/",
            "Alabama Department of Revenue",
        ),
        "AZ": ("https://azdor.gov/individuals", "Arizona Department of Revenue"),
        "AR": (
            "https://www.dfa.arkansas.gov/income-tax/",
            "Arkansas Department of Finance and Administration",
        ),
        "CA": ("https://www.ftb.ca.gov/file/personal/index.html", "California Franchise Tax Board"),
        "CO": ("https://tax.colorado.gov/individual-income-tax", "Colorado Department of Revenue"),
        "CT": (
            "https://portal.ct.gov/drs/individuals/individual-tax-information",
            "Connecticut Department of Revenue Services",
        ),
        "DE": (
            "https://revenue.delaware.gov/individual-income-tax/",
            "Delaware Division of Revenue",
        ),
        "DC": ("https://otr.cfo.dc.gov/page/individual-income-tax", "DC Office of Tax and Revenue"),
        "GA": ("https://dor.georgia.gov/taxes/individual-taxes", "Georgia Department of Revenue"),
        "HI": ("https://tax.hawaii.gov/individuals/", "Hawaii Department of Taxation"),
        "ID": (
            "https://tax.idaho.gov/taxes/income-tax/individual-income/",
            "Idaho State Tax Commission",
        ),
        "IL": ("https://tax.illinois.gov/individuals.html", "Illinois Department of Revenue"),
        "IN": ("https://www.in.gov/dor/individual-income-taxes/", "Indiana Department of Revenue"),
        "IA": (
            "https://revenue.iowa.gov/taxes/tax-guidance/individual-income-tax",
            "Iowa Department of Revenue",
        ),
        "KS": ("https://www.ksrevenue.gov/taxind.html", "Kansas Department of Revenue"),
        "KY": (
            "https://revenue.ky.gov/Individual/Individual-Income-Tax/Pages/default.aspx",
            "Kentucky Department of Revenue",
        ),
        "LA": (
            "https://revenue.louisiana.gov/IndividualIncomeTax",
            "Louisiana Department of Revenue",
        ),
        "ME": ("https://www.maine.gov/revenue/taxes/income-estate-tax", "Maine Revenue Services"),
        "MD": (
            "https://www.marylandtaxes.gov/individual/income/index.php",
            "Comptroller of Maryland",
        ),
        "MA": (
            "https://www.mass.gov/orgs/massachusetts-department-of-revenue",
            "Massachusetts Department of Revenue",
        ),
        "MI": (
            "https://www.michigan.gov/taxes/individual-income-tax",
            "Michigan Department of Treasury",
        ),
        "MN": (
            "https://www.revenue.state.mn.us/individual-income-tax",
            "Minnesota Department of Revenue",
        ),
        "MS": (
            "https://www.dor.ms.gov/individual/individual-income-tax",
            "Mississippi Department of Revenue",
        ),
        "MO": ("https://dor.mo.gov/taxation/individual/", "Missouri Department of Revenue"),
        "MT": (
            "https://mtrevenue.gov/taxes/individual-income-tax/",
            "Montana Department of Revenue",
        ),
        "NE": ("https://revenue.nebraska.gov/individuals", "Nebraska Department of Revenue"),
        "NJ": (
            "https://www.nj.gov/treasury/taxation/individuals.shtml",
            "New Jersey Division of Taxation",
        ),
        "NM": (
            "https://www.tax.newmexico.gov/individuals/",
            "New Mexico Taxation and Revenue Department",
        ),
        "NY": ("https://www.tax.ny.gov/pit/", "New York State Department of Taxation and Finance"),
        "NC": (
            "https://www.ncdor.gov/taxes-forms/individual-income-tax",
            "North Carolina Department of Revenue",
        ),
        "ND": (
            "https://www.tax.nd.gov/tax-types/individual-income-tax",
            "North Dakota Office of State Tax Commissioner",
        ),
        "OH": (
            "https://tax.ohio.gov/individual/resources/individual-income-tax",
            "Ohio Department of Taxation",
        ),
        "OK": ("https://oklahoma.gov/tax/individuals/income-tax.html", "Oklahoma Tax Commission"),
        "OR": (
            "https://www.oregon.gov/dor/programs/individuals/pages/index.aspx",
            "Oregon Department of Revenue",
        ),
        "PA": (
            "https://www.revenue.pa.gov/TaxTypes/PIT/Pages/default.aspx",
            "Pennsylvania Department of Revenue",
        ),
        "RI": (
            "https://tax.ri.gov/tax-forms/personal-income-tax",
            "Rhode Island Division of Taxation",
        ),
        "SC": ("https://dor.sc.gov/tax/individual", "South Carolina Department of Revenue"),
        "UT": ("https://tax.utah.gov/taxing/income", "Utah State Tax Commission"),
        "VA": ("https://www.tax.virginia.gov/income-tax", "Virginia Department of Taxation"),
        "VT": ("https://tax.vermont.gov/individuals/income-tax", "Vermont Department of Taxes"),
        "WI": (
            "https://www.revenue.wi.gov/Pages/Individual/home.aspx",
            "Wisconsin Department of Revenue",
        ),
        "WV": (
            "https://tax.wv.gov/Individuals/Pages/IndividualIncomeTax.aspx",
            "West Virginia State Tax Department",
        ),
    }
    for state, (url, publisher) in taxing_pages.items():
        for year in TAX_YEARS:
            add(
                state,
                year,
                url,
                role="schedule",
                publisher=publisher,
                authority_type="dor_page",
                slug="schedule",
            )
    return specs


def detect_high_agi_income_tax(text: str) -> bool:
    blob = re.sub(r"\s+", " ", text or "").lower()
    return any(phrase in blob for phrase in HIGH_AGI_INCOME_TAX_PHRASES)


def parse_no_wage_tax(text: str, state: str, year: int | None = None) -> bool:
    blob = re.sub(r"\s+", " ", text or "").lower()
    if not blob.strip():
        return False
    if detect_high_agi_income_tax(blob):
        # A high-AGI individual income tax is not "no general wage income tax".
        return False
    phrases = NO_TAX_PHRASES.get(state, ())
    if state == "TN":
        repealed = "repealed for tax periods that begin on january 1, 2021" in blob
        interest_only = "receiving interest from bonds and notes and dividends" in blob
        return repealed or interest_only
    if state == "NH":
        i_and_d = "interest and dividends tax" in blob
        repealed_2025 = "entire chapter was repealed" in blob and "jan. 1, 2025" in blob
        if year == 2026:
            return repealed_2025 or i_and_d
        if year == 2024:
            return i_and_d
        return i_and_d or repealed_2025
    return any(phrase in blob for phrase in phrases)


def _field(
    *,
    authority_id: str,
    source_artifact_key: str,
    source_sha256: str | None,
    extraction_identity: str,
    **values: Any,
) -> dict[str, Any]:
    rec = {
        "authority_id": authority_id,
        "source_artifact_key": source_artifact_key,
        "source_sha256": source_sha256,
        "extraction_identity": extraction_identity,
    }
    rec.update(values)
    return rec


def _schedule_from_code(state: str, year: int) -> dict[str, Any] | None:
    from foundation.living_cost.taxes import NO_INCOME_TAX_STATES, STATE_STATUTORY_SCHEDULES

    if state in NO_INCOME_TAX_STATES:
        return {"deduction": 0.0, "brackets": []}
    return STATE_STATUTORY_SCHEDULES.get(year, {}).get(state)


def _compare_schedule(
    official: Mapping[str, Any] | None,
    code: Mapping[str, Any] | None,
) -> str:
    if official is None:
        return "STATE_EVIDENCE_INCOMPLETE"
    if code is None:
        return "STATE_MODEL_INCOMPLETE"
    o_ded = official.get("deduction")
    c_ded = code.get("deduction")
    o_br = official.get("brackets") or []
    c_br = code.get("brackets") or []
    if o_ded is None:
        return "STATE_EVIDENCE_INCOMPLETE"
    try:
        if abs(float(o_ded) - float(c_ded or 0)) > 0.011:
            return "STATE_CODE_MISMATCH"
    except (TypeError, ValueError):
        return "STATE_CODE_MISMATCH"
    if len(o_br) != len(c_br):
        return "STATE_CODE_MISMATCH"
    for (o_cap, o_rate), (c_cap, c_rate) in zip(o_br, c_br, strict=True):
        o_inf = o_cap is None or o_cap == float("inf")
        c_inf = c_cap == float("inf")
        if o_inf != c_inf:
            return "STATE_CODE_MISMATCH"
        if not o_inf and abs(float(o_cap) - float(c_cap)) > 0.011:
            return "STATE_CODE_MISMATCH"
        if abs(float(o_rate) - float(c_rate)) > 1e-6:
            return "STATE_CODE_MISMATCH"
    return "STATE_CODE_MATCH"


def retrieve_state_tax_authorities(
    specs: list[dict[str, Any]] | None = None,
    *,
    force_download: bool = False,
) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for spec in specs if specs is not None else authority_catalog():
        artifacts[spec["key"]] = {
            **_acquire(
                spec["key"],
                spec["url"],
                spec["filename"],
                force_download=force_download,
            ),
            "state": spec["state"],
            "year": spec["year"],
            "publisher": spec["publisher"],
            "authority_type": spec["authority_type"],
            "role": spec["role"],
        }
    return artifacts


def _empty_payroll() -> dict[str, Any]:
    return {
        "status": "VERIFIED_NONE_OR_UNRESOLVED",
        "contributions": [],
        "notes": (
            "Mandatory employee state payroll programs are inventoried separately "
            "from ordinary wage income tax. Employer-only taxes are excluded. "
            "Ambiguous inclusion of SDI/PFML in the frozen tax solver is recorded "
            "rather than silently chosen."
        ),
    }


def build_state_tax_inventory(
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse each jurisdiction-year from its designated official artifact."""
    arts = artifacts if artifacts is not None else retrieve_state_tax_authorities()
    by_cell: dict[tuple[str, int], dict[str, Any]] = {}
    for art in arts.values():
        if not isinstance(art, dict) or not art.get("state"):
            continue
        by_cell[(str(art["state"]), int(art["year"]))] = art

    jurisdictions: dict[str, Any] = {}
    matrix: list[dict[str, Any]] = []
    for state in ALL_JURISDICTIONS:
        year_recs: dict[str, Any] = {}
        for year in TAX_YEARS:
            art = by_cell.get((state, year))
            issues: list[str] = []
            text = _text_for_path(Path(art["path"]) if art and art.get("path") else None)
            sha = art.get("sha256") if art else None
            key = art.get("key") if art else None
            authority_id = f"ST_{state}_{year}"
            if (
                art is None
                or not art.get("http_ok")
                or not sha
                or not official_state_url(art.get("url"))
            ):
                issues.append(f"STATE_TAX_FIELD_AUTHORITY_UNBOUND:{state}:{year}:authority")
            elif art.get("state") != state:
                issues.append("STATE_TAX_AUTHORITY_JURISDICTION_MISMATCH")
            elif int(art.get("year") or 0) != year:
                issues.append("STATE_TAX_AUTHORITY_YEAR_MISMATCH")

            no_tax_ok = (
                parse_no_wage_tax(text, state, year) if state in NO_TAX_CANDIDATES else False
            )
            high_agi = detect_high_agi_income_tax(text)
            code_sched = _schedule_from_code(state, year)
            tax_status = STATUS_INCOMPLETE
            official_sched: dict[str, Any] | None = None
            code_match = "STATE_EVIDENCE_INCOMPLETE"
            if high_agi:
                issues.append(f"STATE_TAX_MODEL_GAP:{state}:{year}:high_agi_income_tax")
                tax_status = STATUS_INCOMPLETE
            elif no_tax_ok and not issues:
                tax_status = STATUS_NO_WAGE_TAX
                official_sched = {"deduction": 0.0, "brackets": []}
                code_match = (
                    "STATE_CODE_MATCH"
                    if code_sched is not None and not code_sched.get("brackets")
                    else (
                        "STATE_CODE_MATCH" if state in NO_TAX_CANDIDATES else "STATE_CODE_MISMATCH"
                    )
                )
                if state not in NO_TAX_CANDIDATES:
                    code_match = "STATE_CODE_MISMATCH"
            elif state in NO_TAX_CANDIDATES:
                issues.append(f"STATE_TAX_NO_WAGE_TAX_UNPARSED:{state}:{year}")
            elif not issues and text:
                # Taxing jurisdiction: official page retrieved, but schedule
                # amounts are not inferred from candidate Python tables.
                tax_status = STATUS_INCOMPLETE
                issues.append(f"STATE_TAX_MODEL_GAP:{state}:{year}:schedule_not_extracted")
                code_match = "STATE_EVIDENCE_INCOMPLETE"
            elif not issues:
                issues.append(f"STATE_TAX_FIELD_AUTHORITY_UNBOUND:{state}:{year}:text")

            payroll = _empty_payroll()
            if tax_status == STATUS_NO_WAGE_TAX:
                payroll = {
                    "status": "OWNER_TAX_METHOD_DECISION_REQUIRED",
                    "contributions": [],
                    "notes": (
                        "Ordinary wage income tax is verified absent. Mandatory "
                        "employee SDI/PFML/SUTA-employee programs, if any, are "
                        "not silently treated as zero or as income tax. Frozen "
                        "methodology lists income/FICA/local taxes and does not "
                        "authorize an owner decision here."
                    ),
                }

            std = None
            brackets: list[dict[str, Any]] = []
            if official_sched is not None and key and sha:
                std = _field(
                    value=official_sched["deduction"],
                    authority_id=authority_id,
                    source_artifact_key=key,
                    source_sha256=sha,
                    extraction_identity=f"{state}_{year}_standard_deduction",
                )
                brackets = [
                    _field(
                        upper=None if cap == float("inf") else cap,
                        rate=rate,
                        authority_id=authority_id,
                        source_artifact_key=key,
                        source_sha256=sha,
                        extraction_identity=f"{state}_{year}_brackets",
                    )
                    for cap, rate in official_sched.get("brackets") or []
                ]
            rec = {
                "jurisdiction": state,
                "tax_year": year,
                "filing_status": "SINGLE",
                "wage_income_scope": True,
                "tax_status": tax_status,
                "official_authorities": [
                    {
                        "authority_id": authority_id,
                        "publisher": (art or {}).get("publisher"),
                        "url": (art or {}).get("url"),
                        "retrieved_at": (art or {}).get("retrieved_at"),
                        "sha256": sha,
                        "effective_date": f"{year}-01-01",
                        "authority_type": (art or {}).get("authority_type"),
                    }
                ]
                if art
                else [],
                "starting_income_definition": "ordinary wage income of a single independent adult",
                "standard_deduction": std,
                "personal_exemption": None,
                "taxable_income_adjustments": [],
                "brackets": brackets,
                "rates": [b.get("rate") for b in brackets],
                "mandatory_surtaxes": [],
                "automatic_statutory_nonrefundable_personal_credits": [],
                "recapture_phaseout": None,
                "special_statutory_formula": None,
                "mandatory_employee_state_payroll_contributions": payroll,
                "code_match_status": code_match,
                "parsed_ok": tax_status == STATUS_NO_WAGE_TAX and not issues,
                "validation_issues": issues,
                "effective_date": f"{year}-01-01",
                "authority_checked_at": (art or {}).get("retrieved_at"),
                "currentness_status": "HISTORICAL_RULE_YEAR"
                if year == 2024
                else "CURRENTNESS_PENDING",
            }
            year_recs[str(year)] = rec
        jurisdictions[state] = {"jurisdiction": state, "years": year_recs}
        y24 = year_recs["2024"]
        y26 = year_recs["2026"]
        remaining = []
        remaining.extend(y24.get("validation_issues") or [])
        remaining.extend(y26.get("validation_issues") or [])
        if y26.get("tax_status") != STATUS_NO_WAGE_TAX:
            remaining.append(f"STATE_TAX_2026_UNRESOLVED:{state}")
        matrix.append(
            {
                "state": state,
                "2024_evidence_status": y24["tax_status"]
                if y24["parsed_ok"]
                else STATUS_INCOMPLETE,
                "2024_code_match_status": y24["code_match_status"],
                "2026_evidence_status": y26["tax_status"]
                if y26["parsed_ok"]
                else STATUS_INCOMPLETE,
                "2026_code_match_status": y26["code_match_status"],
                "2026_freshness_status": y26["currentness_status"],
                "mandatory_payroll_status": y26["mandatory_employee_state_payroll_contributions"][
                    "status"
                ],
                "remaining_issue": "; ".join(remaining) if remaining else "",
            }
        )

    bound = []
    for key, art in arts.items():
        if not isinstance(art, dict):
            continue
        bound.append(
            {
                "key": key,
                "state": art.get("state"),
                "year": art.get("year"),
                "url": art.get("url"),
                "filename": art.get("filename"),
                "sha256": art.get("sha256"),
                "retrieved_at": art.get("retrieved_at"),
                "http_ok": art.get("http_ok"),
                "byte_size": art.get("byte_size"),
                "publisher": art.get("publisher"),
                "role": art.get("role"),
            }
        )
    validated_2024 = sum(
        1 for st in ALL_JURISDICTIONS if jurisdictions[st]["years"]["2024"].get("parsed_ok")
    )
    validated_2026 = sum(
        1 for st in ALL_JURISDICTIONS if jurisdictions[st]["years"]["2026"].get("parsed_ok")
    )
    return {
        "report_type": INVENTORY_REPORT_TYPE,
        "generated_at": _now_iso(),
        "filing_status": "SINGLE",
        "required_years": list(TAX_YEARS),
        "jurisdictions_required": list(ALL_JURISDICTIONS),
        "jurisdiction_count": len(ALL_JURISDICTIONS),
        "validated_2024_count": validated_2024,
        "validated_2026_count": validated_2026,
        "family_complete": validated_2024 == 51 and validated_2026 == 51,
        "jurisdictions": jurisdictions,
        "completion_matrix": matrix,
        "retrieved_artifacts": bound,
        "calculates_mslc": False,
        "headline_calculated": False,
    }


def write_state_tax_inventory(
    output_path: Path | None = None,
    *,
    force_download: bool = False,
) -> dict[str, Any]:
    artifacts = retrieve_state_tax_authorities(force_download=force_download)
    payload = build_state_tax_inventory(artifacts)
    dest = output_path or INVENTORY_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_state_tax_inventory(
    inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    if isinstance(inventory, Mapping):
        return dict(inventory)
    if not INVENTORY_PATH.is_file():
        return None
    try:
        payload = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def evaluate_state_tax_freshness(
    *,
    inventory_valid: bool,
    live: dict[str, Any] | None,
    live_error: str | None,
) -> tuple[str, bool | None, str]:
    if live_error:
        return (
            "CHECK_FAILED",
            None,
            (
                "Live official state-tax currentness discovery failed. "
                f"Cached inventory remains {'VALIDATED' if inventory_valid else 'unvalidated'}. "
                f"{live_error}"
            ),
        )
    live = live or {}
    unresolved = live.get("unresolved_2026") or []
    if unresolved:
        return (
            "CHECK_FAILED",
            None,
            (
                "2026 official currentness is incomplete for "
                f"{len(unresolved)} jurisdictions. Cached cells may remain "
                f"VALIDATED. unresolved={unresolved[:8]}"
            ),
        )
    if inventory_valid and live.get("all_2026_current") is True:
        return (
            "VERIFIED_CURRENT",
            False,
            "All 51 jurisdictions have targeted 2026 official currentness.",
        )
    if not inventory_valid:
        return (
            "MANUAL_VERIFICATION_REQUIRED",
            None,
            "State tax inventory is not family-validated for all 51 jurisdictions.",
        )
    return (
        "CHECK_FAILED",
        None,
        f"Live state-tax currentness was incomplete: {live}.",
    )


def discover_state_tax_live(
    inventory: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Targeted 2026 currentness from already-captured official artifacts.

    Does not issue 102 live GETs. Callers that already retrieved artifacts
    pass the captured inventory. A missing 2026 official bind is unresolved.
    """
    captured = load_state_tax_inventory(inventory)
    if not captured:
        return None, "state tax inventory missing"
    unresolved: list[str] = []
    current = 0
    jurisdictions = captured.get("jurisdictions") or {}
    for state in ALL_JURISDICTIONS:
        rec = ((jurisdictions.get(state) or {}).get("years") or {}).get("2026") or {}
        arts = rec.get("official_authorities") or []
        ok = (
            rec.get("parsed_ok") is True
            and rec.get("tax_status") == STATUS_NO_WAGE_TAX
            and arts
            and arts[0].get("sha256")
            and arts[0].get("url")
        )
        if ok:
            current += 1
        else:
            unresolved.append(state)
    return (
        {
            "verified_current_2026_count": current,
            "unresolved_2026": unresolved,
            "all_2026_current": current == 51 and not unresolved,
        },
        None,
    )


def no_wage_tax_verified(state: str, year: int, inventory: Mapping[str, Any] | None = None) -> bool:
    payload = load_state_tax_inventory(inventory)
    if not payload:
        return False
    rec = ((payload.get("jurisdictions") or {}).get(state.upper()) or {}).get("years") or {}
    cell = rec.get(str(year)) or {}
    return cell.get("tax_status") == STATUS_NO_WAGE_TAX and cell.get("parsed_ok") is True
