"""Official 51-jurisdiction state-tax RULE_YEAR evidence inventory.

Does not calculate an MSLC. Candidate STATE_STATUTORY_SCHEDULES are audited
against retrieved official government artifacts. Unknown is not zero.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
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
    except Exception as exc:  # noqa: BLE001
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
    header = path.read_bytes()[:8]
    if path.suffix.lower() == ".pdf" or header.startswith(b"%PDF"):
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
    sidecar = Path(str(path) + ".provenance.json")
    if sidecar.is_file() and not force_download:
        try:
            prev = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prev = {}
        if isinstance(prev, dict) and prev.get("url") and prev.get("url") != url:
            force_download = True
    if force_download and path.is_file():
        path.unlink()
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
        ext = ".pdf" if spec["url"].lower().endswith(".pdf") else ".html"
        spec["filename"] = f"{spec['key']}{ext}"
    # Year-specific WA authorities: 2024 I-2111 prohibition vs 2026 ESSB 6346
    # (tax imposed beginning January 1, 2028 — not a 2026 RULE_YEAR tax).
    for spec in specs:
        if spec["state"] != "WA":
            continue
        if spec["year"] == 2024:
            spec["url"] = (
                "https://lawfilesext.leg.wa.gov/biennium/2023-24/Pdf/Initiatives/"
                "Initiatives/Initiative%202111.sl.pdf"
            )
            spec["publisher"] = "Washington State Legislature / Initiative 2111"
            spec["authority_type"] = "enacted_legislation"
        elif spec["year"] == 2026:
            spec["url"] = (
                "https://lawfilesext.leg.wa.gov/biennium/2025-26/Pdf/Bills/"
                "Session%20Laws/Senate/6346-S.sl.pdf"
            )
            spec["publisher"] = "Washington State Legislature / ESSB 6346 Chapter 238"
            spec["authority_type"] = "enacted_legislation"
        spec["filename"] = f"{spec['key']}.pdf"
    add(
        "WA",
        2024,
        (
            "https://lawfilesext.leg.wa.gov/biennium/2023-24/Pdf/Bill%20Reports/"
            "House/I2111%20HIB%20FIN%2024.pdf"
        ),
        role="preexisting_status",
        publisher=(
            "Washington State Legislature / House Finance Committee report on Initiative 2111"
        ),
        authority_type="legislative_analysis",
        slug="preexisting_no_wage_tax",
    )

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
    year_specific_taxing: dict[tuple[str, int], tuple[str, str, str]] = {
        ("PA", 2024): (
            "https://www.pa.gov/agencies/revenue/resources/tax-rates/personal-income-tax-rates",
            "Pennsylvania Department of Revenue / Personal Income Tax Rates (2004–Present table)",
            "rate_table",
        ),
        ("PA", 2026): (
            "https://www.pa.gov/agencies/revenue/resources/tax-types-and-information/personal-income-tax",
            "Pennsylvania Department of Revenue / Personal Income Tax",
            "dor_page",
        ),
        ("IL", 2024): (
            (
                "https://tax.illinois.gov/content/dam/soi/en/web/tax/forms/incometax/documents/"
                "2024/individual/il-1040-instr.pdf"
            ),
            "Illinois Department of Revenue / 2024 IL-1040 instructions",
            "form_instructions",
        ),
        ("IL", 2026): (
            "https://tax.illinois.gov/research/taxrates/income.html",
            "Illinois Department of Revenue / Income Tax Rates",
            "rate_table",
        ),
        ("NC", 2024): (
            (
                "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/"
                "Chapter_105/GS_105-153.7.html"
            ),
            "North Carolina General Assembly / G.S. 105-153.7",
            "statute",
        ),
        ("NC", 2026): (
            (
                "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/"
                "Chapter_105/GS_105-153.7.html"
            ),
            "North Carolina General Assembly / G.S. 105-153.7",
            "statute",
        ),
        ("AZ", 2024): (
            "https://www.azleg.gov/ars/43/01011.htm",
            "Arizona Legislature / A.R.S. § 43-1011",
            "statute",
        ),
        ("AZ", 2026): (
            "https://www.azleg.gov/ars/43/01011.htm",
            "Arizona Legislature / A.R.S. § 43-1011",
            "statute",
        ),
        ("IN", 2024): (
            "https://forms.in.gov/Download.aspx?id=16379",
            "Indiana Department of Revenue / 2024 IT-40 instruction booklet",
            "form_instructions",
        ),
        ("IN", 2026): (
            "https://forms.in.gov/Download.aspx?id=2750",
            "Indiana Department of Revenue / Schedule EZ (individual AGI tax-rate windows)",
            "form_instructions",
        ),
        ("KY", 2024): (
            "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=56339",
            "Kentucky General Assembly / KRS 141.020",
            "statute",
        ),
        ("KY", 2026): (
            "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=56339",
            "Kentucky General Assembly / KRS 141.020",
            "statute",
        ),
        ("MI", 2024): (
            "https://www.michigan.gov/taxes/individual-income-tax",
            "Michigan Department of Treasury",
            "dor_page",
        ),
        ("MI", 2026): (
            "https://www.michigan.gov/taxes/individual-income-tax",
            "Michigan Department of Treasury",
            "dor_page",
        ),
        ("UT", 2024): (
            "https://tax.utah.gov/taxing/income",
            "Utah State Tax Commission",
            "dor_page",
        ),
        ("UT", 2026): (
            "https://tax.utah.gov/taxing/income",
            "Utah State Tax Commission",
            "dor_page",
        ),
        ("IA", 2024): (
            "https://revenue.iowa.gov/taxes/tax-guidance/individual-income-tax",
            "Iowa Department of Revenue",
            "dor_page",
        ),
        ("IA", 2026): (
            "https://revenue.iowa.gov/taxes/tax-guidance/individual-income-tax",
            "Iowa Department of Revenue",
            "dor_page",
        ),
        ("GA", 2024): (
            "https://dor.georgia.gov/taxes/individual-taxes",
            "Georgia Department of Revenue",
            "dor_page",
        ),
        ("GA", 2026): (
            "https://dor.georgia.gov/taxes/individual-taxes",
            "Georgia Department of Revenue",
            "dor_page",
        ),
        ("CO", 2024): (
            "https://tax.colorado.gov/individual-income-tax",
            "Colorado Department of Revenue",
            "dor_page",
        ),
        ("CO", 2026): (
            "https://tax.colorado.gov/individual-income-tax",
            "Colorado Department of Revenue",
            "dor_page",
        ),
        ("ID", 2024): (
            "https://tax.idaho.gov/taxes/income-tax/individual-income/",
            "Idaho State Tax Commission",
            "dor_page",
        ),
        ("ID", 2026): (
            "https://tax.idaho.gov/taxes/income-tax/individual-income/",
            "Idaho State Tax Commission",
            "dor_page",
        ),
        ("MS", 2024): (
            "https://www.dor.ms.gov/individual/individual-income-tax",
            "Mississippi Department of Revenue",
            "dor_page",
        ),
        ("MS", 2026): (
            "https://www.dor.ms.gov/individual/individual-income-tax",
            "Mississippi Department of Revenue",
            "dor_page",
        ),
        ("OH", 2024): (
            "https://tax.ohio.gov/individual/resources/individual-income-tax",
            "Ohio Department of Taxation",
            "dor_page",
        ),
        ("OH", 2026): (
            "https://tax.ohio.gov/individual/resources/individual-income-tax",
            "Ohio Department of Taxation",
            "dor_page",
        ),
    }
    for spec in specs:
        key = (str(spec.get("state")), int(spec.get("year") or 0))
        override = year_specific_taxing.get(key)
        if override is None or spec.get("role") != "schedule":
            continue
        url, publisher, authority_type = override
        spec["url"] = url
        spec["publisher"] = publisher
        spec["authority_type"] = authority_type
        ext = ".pdf" if url.lower().endswith(".pdf") else ".html"
        spec["filename"] = f"{spec['key']}{ext}"
    add(
        "NC",
        2024,
        "https://www.ncdor.gov/taxes-forms/individual-income-tax/tax-rate-schedules",
        role="rate_table",
        publisher="North Carolina Department of Revenue / Tax Rate Schedules",
        authority_type="dor_page",
        slug="rate_table",
    )
    add(
        "NC",
        2024,
        "https://www.ncdor.gov/2024-d-400-schedule-web-fill-version/open",
        role="standard_deduction",
        publisher="North Carolina Department of Revenue / 2024 D-400 Schedule A",
        authority_type="form_instructions",
        slug="standard_deduction",
    )
    add(
        "NC",
        2026,
        "https://www.ncdor.gov/income-tax-withholding-tables-and-instructions-employers/open",
        role="standard_deduction",
        publisher="North Carolina Department of Revenue / 2026 withholding tables",
        authority_type="withholding_schedule",
        slug="standard_deduction",
    )
    add(
        "AZ",
        2024,
        "https://azdor.gov/sites/default/files/document/FORMS_INDIVIDUAL_2024_140Booklet.pdf",
        role="form_instructions",
        publisher="Arizona Department of Revenue / 2024 Form 140 booklet",
        authority_type="form_instructions",
        slug="form_140_booklet",
    )
    add(
        "MI",
        2024,
        (
            "https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/IIT/"
            "TY2024/MI-1040-Instructions.pdf"
        ),
        role="form_instructions",
        publisher="Michigan Department of Treasury / 2024 MI-1040 instructions",
        authority_type="form_instructions",
        slug="mi1040_instructions",
    )
    return specs


def detect_high_agi_income_tax(text: str) -> bool:
    blob = re.sub(r"\s+", " ", text or "").lower()
    return any(phrase in blob for phrase in HIGH_AGI_INCOME_TAX_PHRASES)


def _normalize_statute_text(text: str) -> str:
    """Collapse whitespace and PDF wrap-line numbers inserted between words."""
    blob = re.sub(r"\s+", " ", text or "")
    blob = re.sub(r"([A-Za-z,.$])\s+\d{1,3}\s+(\d)", r"\1 \2", blob)
    blob = re.sub(r"([A-Za-z])\s+\d{1,3}\s+([A-Za-z])", r"\1 \2", blob)
    return blob.lower()


def parse_future_income_tax(text: str) -> dict[str, Any]:
    """Parse enacted-but-possibly-future individual income tax applicability.

    A DOR announcement that a tax 'exists' is not RULE_YEAR applicability.
    Unknown effective year is fail-closed (not zero).
    """
    blob = _normalize_statute_text(text)
    exists = detect_high_agi_income_tax(blob) or (
        "a tax is imposed on the receipt of washington taxable income" in blob
    )
    first_year: int | None = None
    m = re.search(
        r"beginning\s+january\s+1,\s+(\d{4}),\s+a tax is imposed",
        blob,
    )
    if m:
        first_year = int(m.group(1))
        exists = True
    else:
        m = re.search(r"imposed\s+beginning\s+january\s+1,\s+(\d{4})", blob)
        if m:
            first_year = int(m.group(1))
            exists = True
    threshold = None
    if "$1,000,000" in blob or "1,000,000 or more" in blob or "one million dollar" in blob:
        threshold = 1_000_000.0
    unknown = bool(exists and first_year is None)
    return {
        "tax_exists": exists,
        "effective_start": f"{first_year}-01-01" if first_year else None,
        "first_tax_year": first_year,
        "threshold": threshold,
        "unknown_effective_year": unknown,
    }


def tax_applies_to_rule_year(info: Mapping[str, Any] | None, year: int) -> bool | None:
    """True if the parsed tax applies to ``year``; None if existence is unknown-dated."""
    if not info or not info.get("tax_exists"):
        return False
    if info.get("unknown_effective_year") or info.get("first_tax_year") is None:
        return None
    try:
        return int(year) >= int(info["first_tax_year"])
    except (TypeError, ValueError):
        return None


_MONTH_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _iso_date(month_name: str, day: str | int, year: str | int) -> str | None:
    month = _MONTH_NUM.get(str(month_name).strip().lower())
    if not month:
        return None
    try:
        return f"{int(year):04d}-{month:02d}-{int(day):02d}"
    except (TypeError, ValueError):
        return None


def parse_authority_effective_date(text: str) -> str | None:
    """Parse a session-law / rule effective date. Never invent RULE_YEAR-01-01."""
    if not (text or "").strip():
        return None
    header = re.search(
        r"EFFECTIVE DATE:\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
        text,
        re.IGNORECASE,
    )
    if header:
        parsed = _iso_date(header.group(1), header.group(2), header.group(3))
        if parsed:
            return parsed
    enacted = re.search(
        r"Effective:\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
        text,
    )
    if enacted:
        parsed = _iso_date(enacted.group(1), enacted.group(2), enacted.group(3))
        if parsed:
            return parsed
    blob = _normalize_statute_text(text)
    for pattern in (
        r"this act takes effect ([a-z]+ \d{1,2}, \d{4})",
        r"the (?:bill|initiative) takes effect ([a-z]+ \d{1,2}, \d{4})",
        r"effective date[: ]+([a-z]+ \d{1,2}, \d{4})",
        r"takes effect ([a-z]+ \d{1,2}, \d{4})",
    ):
        m = re.search(pattern, blob)
        if not m:
            continue
        parts = m.group(1).split()
        if len(parts) == 3:
            parsed = _iso_date(parts[0], parts[1].rstrip(","), parts[2])
            if parsed:
                return parsed
    return None


def parse_preexisting_no_wage_tax(text: str) -> bool:
    """Official 2024 contemporaneous proof that WA already had no wage PIT."""
    blob = _normalize_statute_text(text)
    phrases = (
        "longstanding tradition of not having an income tax based on personal income",
        "long-standing tradition of not having an income tax",
        "long-standing tradition of opposition to an income tax",
        "longstanding tradition of opposition to an income tax",
        "does not capture any of the state's existing revenue sources",
        "does not capture any of the states existing revenue sources",
        "codify in law the state's longstanding tradition of not having an income tax",
        "codify the state's long-standing tradition of opposition to an income tax",
        "washington currently does not impose a personal income tax",
        "washington does not currently impose a tax on personal income",
        "the state does not currently impose a personal income tax",
        "no existing tax would be repealed",
        "fiscal impact is zero",
        "no impact on state revenues",
    )
    return any(phrase in blob for phrase in phrases)


def extract_year_identity(text: str, year: int) -> dict[str, Any]:
    blob = text or ""
    found = bool(re.search(rf"\b{int(year)}\b", blob))
    return {"found": found, "year": int(year)}


def parse_no_wage_tax(text: str, state: str, year: int | None = None) -> bool:
    blob = _normalize_statute_text(text)
    if not blob.strip():
        return False
    future = parse_future_income_tax(blob)
    applies: bool | None = False
    if year is not None:
        applies = tax_applies_to_rule_year(future, year)
    elif future.get("tax_exists"):
        # No RULE_YEAR supplied: existence of an undated or future tax is not
        # proof of current-year zero, and is not proof it applies now.
        applies = tax_applies_to_rule_year(future, 2026)
    if applies is True:
        return False
    if applies is None and future.get("tax_exists"):
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
    if state == "WA":
        prohibition = (
            "neither the state nor any county, city, or other local jurisdiction" in blob
            and "personal income" in blob
        ) or "personal income tax prohibition" in blob
        if prohibition:
            return True
        if future.get("tax_exists") and applies is False:
            return True
        return any(phrase in blob for phrase in phrases)
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


def _authority_record(art: Mapping[str, Any], *, text: str, authority_id: str) -> dict[str, Any]:
    return {
        "authority_id": authority_id,
        "publisher": art.get("publisher"),
        "url": art.get("url"),
        "retrieved_at": art.get("retrieved_at"),
        "sha256": art.get("sha256"),
        "authority_effective_date": parse_authority_effective_date(text),
        "effective_date": parse_authority_effective_date(text),
        "authority_type": art.get("authority_type"),
        "role": art.get("role"),
        "source_artifact_key": art.get("key"),
    }


def _wa_2024_evidence_chain(
    cell_arts: list[dict[str, Any]],
    texts: list[str],
) -> dict[str, Any]:
    preexisting_ok = False
    preexisting_art = None
    i2111_art = None
    i2111_text = ""
    i2111_effective = None
    for art, text in zip(cell_arts, texts, strict=False):
        role = str(art.get("role") or "")
        if role == "preexisting_status" or "HIB FIN" in str(art.get("url") or ""):
            preexisting_art = art
            preexisting_ok = parse_preexisting_no_wage_tax(text)
        if role == "wage_income_status" or "Initiative%202111" in str(art.get("url") or ""):
            i2111_art = art
            i2111_text = text
            i2111_effective = parse_authority_effective_date(text)
    return {
        "pre_existing_status": {
            "status": ("no general wage-income tax before 2024-06-06" if preexisting_ok else None),
            "authority_id": "ST_WA_2024_PREEXISTING" if preexisting_art else None,
            "source_artifact_key": (preexisting_art or {}).get("key"),
            "source_sha256": (preexisting_art or {}).get("sha256"),
            "parsed_ok": preexisting_ok,
            "url": (preexisting_art or {}).get("url"),
        },
        "initiative_2111": {
            "effective_date": i2111_effective,
            "role": "prospective prohibition",
            "authority_id": "ST_WA_2024",
            "source_artifact_key": (i2111_art or {}).get("key"),
            "source_sha256": (i2111_art or {}).get("sha256"),
            "prohibition_parsed": parse_no_wage_tax(i2111_text, "WA", 2024),
        },
        "rule_year_2024_result": (
            "no general wage-income tax for full tax year"
            if preexisting_ok and i2111_effective == "2024-06-06"
            else None
        ),
    }


def build_state_tax_inventory(
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse each jurisdiction-year from its designated official artifact."""
    from foundation.sources.state_tax_schedules import (
        extract_official_schedule,
        merge_extracted_schedules,
        official_to_compare,
    )

    arts = artifacts if artifacts is not None else retrieve_state_tax_authorities()
    by_cell: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for art in arts.values():
        if not isinstance(art, dict) or not art.get("state"):
            continue
        by_cell.setdefault((str(art["state"]), int(art["year"])), []).append(art)

    jurisdictions: dict[str, Any] = {}
    matrix: list[dict[str, Any]] = []
    for state in ALL_JURISDICTIONS:
        year_recs: dict[str, Any] = {}
        for year in TAX_YEARS:
            cell_arts = by_cell.get((state, year), [])
            issues: list[str] = []
            texts: list[str] = []
            for art in cell_arts:
                texts.append(_text_for_path(Path(art["path"]) if art.get("path") else None))
            combined = "\n".join(texts)
            primary = None
            for art in cell_arts:
                if art.get("role") in {"wage_income_status", "schedule"}:
                    primary = art
                    break
            if primary is None and cell_arts:
                primary = cell_arts[0]
            authority_id = f"ST_{state}_{year}"
            bound_ok = False
            for art in cell_arts:
                if (
                    art.get("http_ok")
                    and art.get("sha256")
                    and official_state_url(art.get("url"))
                    and art.get("state") == state
                    and int(art.get("year") or 0) == year
                ):
                    bound_ok = True
                elif art.get("state") != state:
                    issues.append("STATE_TAX_AUTHORITY_JURISDICTION_MISMATCH")
                elif int(art.get("year") or 0) != year:
                    issues.append("STATE_TAX_AUTHORITY_YEAR_MISMATCH")
            if not bound_ok:
                issues.append(f"STATE_TAX_FIELD_AUTHORITY_UNBOUND:{state}:{year}:authority")

            no_tax_ok = (
                parse_no_wage_tax(combined, state, year) if state in NO_TAX_CANDIDATES else False
            )
            future = parse_future_income_tax(combined)
            applies = tax_applies_to_rule_year(future, year)
            authority_effective = parse_authority_effective_date(combined)
            code_sched = _schedule_from_code(state, year)
            tax_status = STATUS_INCOMPLETE
            official_sched: dict[str, Any] | None = None
            code_match = "STATE_EVIDENCE_INCOMPLETE"
            evidence_chain: dict[str, Any] | None = None
            wa_preexisting_ok = False
            if state == "WA" and year == 2024:
                evidence_chain = _wa_2024_evidence_chain(cell_arts, texts)
                wa_preexisting_ok = bool(
                    (evidence_chain.get("pre_existing_status") or {}).get("parsed_ok")
                )
                if no_tax_ok and not wa_preexisting_ok:
                    issues.append("STATE_TAX_WA_PREEXISTING_UNBOUND:WA:2024")
            if applies is None and future.get("tax_exists"):
                issues.append(
                    f"STATE_TAX_MODEL_GAP:{state}:{year}:high_agi_income_tax_unknown_effective_year"
                )
                tax_status = STATUS_INCOMPLETE
            elif applies is True:
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
            elif bound_ok and combined.strip():
                parts: list[tuple[dict[str, Any], dict[str, Any]]] = []
                for art, text in zip(cell_arts, texts, strict=False):
                    piece = extract_official_schedule(state, year, text)
                    if piece:
                        parts.append((piece, art))
                extracted = merge_extracted_schedules(parts)
                if extracted and extracted.get("complete"):
                    tax_status = STATUS_TAXING
                    official_sched = extracted
                    code_match = _compare_schedule(official_to_compare(extracted), code_sched)
                else:
                    tax_status = STATUS_INCOMPLETE
                    issues.append(f"STATE_TAX_MODEL_GAP:{state}:{year}:schedule_not_extracted")
                    code_match = "STATE_EVIDENCE_INCOMPLETE"
                    if extracted and not extracted.get("complete"):
                        official_sched = extracted
                        code_match = "STATE_MODEL_INCOMPLETE"
            elif not issues:
                issues.append(f"STATE_TAX_FIELD_AUTHORITY_UNBOUND:{state}:{year}:text")

            payroll = _empty_payroll()
            if tax_status in {STATUS_NO_WAGE_TAX, STATUS_TAXING}:
                payroll = {
                    "status": "OWNER_TAX_METHOD_DECISION_REQUIRED",
                    "contributions": [],
                    "notes": (
                        "Ordinary wage income tax evidence is inventoried separately "
                        "from mandatory employee SDI/PFML/SUTA-employee programs. "
                        "Those programs are not silently treated as zero or as PIT."
                    ),
                }

            std = None
            exemption_field = None
            brackets: list[dict[str, Any]] = []
            field_sources = (official_sched or {}).get("field_sources") or {}
            fallback_art = primary if isinstance(primary, dict) else {}

            def _field_art(
                name: str, sources: Mapping[str, Any], fallback: dict[str, Any]
            ) -> dict[str, Any]:
                art = sources.get(name) or fallback
                return art if isinstance(art, dict) else {}

            if official_sched is not None and official_sched.get("brackets") is not None:
                ded_art = _field_art("deduction", field_sources, fallback_art)
                ex_art = _field_art("personal_exemption", field_sources, fallback_art)
                br_art = _field_art("brackets", field_sources, fallback_art)
                if official_sched.get("deduction") is not None and ded_art.get("sha256"):
                    std = _field(
                        value=official_sched["deduction"],
                        authority_id=authority_id,
                        source_artifact_key=ded_art.get("key"),
                        source_sha256=ded_art.get("sha256"),
                        extraction_identity=f"{state}_{year}_standard_deduction",
                        tax_year=year,
                    )
                if official_sched.get("personal_exemption") is not None and ex_art.get("sha256"):
                    exemption_field = _field(
                        value=official_sched["personal_exemption"],
                        authority_id=authority_id,
                        source_artifact_key=ex_art.get("key"),
                        source_sha256=ex_art.get("sha256"),
                        extraction_identity=f"{state}_{year}_personal_exemption",
                        tax_year=year,
                    )
                if br_art.get("sha256"):
                    brackets = [
                        _field(
                            upper=None if cap == float("inf") else cap,
                            rate=rate,
                            authority_id=authority_id,
                            source_artifact_key=br_art.get("key"),
                            source_sha256=br_art.get("sha256"),
                            extraction_identity=f"{state}_{year}_brackets",
                            tax_year=year,
                        )
                        for cap, rate in official_sched.get("brackets") or []
                    ]
            parsed_ok = (
                tax_status in {STATUS_NO_WAGE_TAX, STATUS_TAXING}
                and not issues
                and (tax_status != STATUS_TAXING or bool((official_sched or {}).get("complete")))
            )
            authorities = [
                _authority_record(
                    art, text=text, authority_id=f"ST_{state}_{year}_{art.get('role')}"
                )
                for art, text in zip(cell_arts, texts, strict=False)
            ]
            rec = {
                "jurisdiction": state,
                "tax_year": year,
                "filing_status": "SINGLE",
                "wage_income_scope": True,
                "tax_status": tax_status,
                "official_authorities": authorities,
                "starting_income_definition": (official_sched or {}).get(
                    "starting_income_base",
                    "ordinary wage income of a single independent adult",
                ),
                "standard_deduction": std,
                "personal_exemption": exemption_field,
                "taxable_income_adjustments": [],
                "brackets": brackets,
                "rates": [b.get("rate") for b in brackets],
                "mandatory_surtaxes": [],
                "automatic_statutory_nonrefundable_personal_credits": [],
                "recapture_phaseout": None,
                "special_statutory_formula": None,
                "mandatory_employee_state_payroll_contributions": payroll,
                "code_match_status": code_match,
                "parsed_ok": parsed_ok,
                "validation_issues": issues,
                "authority_effective_date": authority_effective,
                "effective_date": authority_effective,
                "rule_applies_to_tax_year": True if parsed_ok else None,
                "first_applicable_tax_year": (
                    future.get("first_tax_year")
                    if future.get("tax_exists")
                    else year
                    if parsed_ok
                    else None
                ),
                "authority_checked_at": (primary or {}).get("retrieved_at"),
                "currentness_status": "HISTORICAL_RULE_YEAR"
                if year == 2024
                else "CURRENTNESS_PENDING",
                "future_legislation": {
                    "tax_enacted": bool(future.get("tax_exists")),
                    "tax_applies_to_year": applies,
                    "authority_effective_date": authority_effective,
                    "tax_imposition_start": future.get("effective_start"),
                    "effective_start": future.get("effective_start"),
                    "first_tax_year": future.get("first_tax_year"),
                    "threshold": future.get("threshold"),
                    "unknown_effective_year": bool(future.get("unknown_effective_year")),
                },
                "evidence_chain": evidence_chain,
            }
            year_recs[str(year)] = rec
        jurisdictions[state] = {"jurisdiction": state, "years": year_recs}
        y24 = year_recs["2024"]
        y26 = year_recs["2026"]
        remaining = []
        remaining.extend(y24.get("validation_issues") or [])
        remaining.extend(y26.get("validation_issues") or [])
        if not y26.get("parsed_ok"):
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
        "live_verified_current_2026_count": 0,
        "no_general_wage_tax_count": sum(
            1
            for st in ALL_JURISDICTIONS
            if jurisdictions[st]["years"]["2024"].get("tax_status") == STATUS_NO_WAGE_TAX
            and jurisdictions[st]["years"]["2024"].get("parsed_ok")
            and jurisdictions[st]["years"]["2026"].get("tax_status") == STATUS_NO_WAGE_TAX
            and jurisdictions[st]["years"]["2026"].get("parsed_ok")
        ),
        "taxing_pairs_completed": sum(
            1
            for st in ALL_JURISDICTIONS
            if jurisdictions[st]["years"]["2024"].get("tax_status") == STATUS_TAXING
            and jurisdictions[st]["years"]["2024"].get("parsed_ok")
            and jurisdictions[st]["years"]["2026"].get("tax_status") == STATUS_TAXING
            and jurisdictions[st]["years"]["2026"].get("parsed_ok")
        ),
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


def inventory_file_sha256(path: Path | None = None) -> str | None:
    """SHA-256 of inventory file bytes with newlines normalized to LF.

    Git working copies may use CRLF on Windows. Binding identity must be
    the same on Linux CI and a Windows checkout of the same commit.
    """
    dest = path or INVENTORY_PATH
    if not dest.is_file():
        return None
    data = dest.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def bind_state_tax_freshness_to_inventory(
    *,
    freshness_inventory_sha: str | None,
    freshness_inventory_generated_at: str | None,
    selected_artifact_ids: Sequence[str] | None = None,
    inventory_path: Path | None = None,
    inventory_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed when freshness describes a different inventory generation.

    Counts copied from an older run are not proof of synchronization.
    """
    dest = inventory_path or INVENTORY_PATH
    issues: list[str] = []
    file_sha = inventory_file_sha256(dest)
    payload: Mapping[str, Any]
    if inventory_payload is not None:
        payload = inventory_payload
    elif dest.is_file():
        try:
            loaded = json.loads(dest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = None
        payload = loaded if isinstance(loaded, dict) else {}
    else:
        payload = {}
        issues.append("STATE_TAX_FRESHNESS_INVENTORY_MISSING")
    if not freshness_inventory_sha:
        issues.append("STATE_TAX_FRESHNESS_INVENTORY_SHA_MISSING")
    elif file_sha is None:
        issues.append("STATE_TAX_FRESHNESS_INVENTORY_MISSING")
    elif freshness_inventory_sha != file_sha:
        issues.append("STATE_TAX_FRESHNESS_INVENTORY_SHA_MISMATCH")
    generated_at = payload.get("generated_at")
    if not freshness_inventory_generated_at:
        issues.append("STATE_TAX_FRESHNESS_INVENTORY_GENERATED_AT_MISSING")
    elif generated_at and freshness_inventory_generated_at != generated_at:
        issues.append("STATE_TAX_FRESHNESS_INVENTORY_GENERATED_AT_MISMATCH")
    inv_names: set[str] = set()
    for item in payload.get("retrieved_artifacts") or []:
        if not isinstance(item, dict):
            continue
        for key in ("filename", "key", "artifact_id"):
            value = item.get(key)
            if value:
                inv_names.add(str(value))
    for artifact_id in selected_artifact_ids or []:
        if not artifact_id:
            continue
        if str(artifact_id) not in inv_names:
            issues.append(f"STATE_TAX_FRESHNESS_STALE_ARTIFACT:{artifact_id}")
    return {
        "ok": not issues,
        "issues": issues,
        "inventory_sha256": file_sha,
        "inventory_generated_at": generated_at,
        "freshness_inventory_sha": freshness_inventory_sha,
        "freshness_inventory_generated_at": freshness_inventory_generated_at,
    }


def state_tax_freshness_payload_binding(
    freshness: Mapping[str, Any],
    *,
    inventory_path: Path | None = None,
    inventory_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind a written freshness report to the inventory file it claims to describe."""
    check = (freshness.get("checks") or {}).get("state_tax_law") or {}
    extra = check.get("extra") or {}
    ids: list[str] = []
    for item in check.get("selected_artifacts") or []:
        if not isinstance(item, dict):
            continue
        artifact_id = item.get("artifact_id") or item.get("filename")
        if artifact_id:
            ids.append(str(artifact_id))
    return bind_state_tax_freshness_to_inventory(
        freshness_inventory_sha=extra.get("inventory_sha256"),
        freshness_inventory_generated_at=extra.get("inventory_generated_at"),
        selected_artifact_ids=ids,
        inventory_path=inventory_path,
        inventory_payload=inventory_payload,
    )


def evaluate_state_tax_freshness(
    *,
    inventory_valid: bool,
    live: dict[str, Any] | None,
    live_error: str | None,
    inventory_binding: Mapping[str, Any] | None = None,
) -> tuple[str, bool | None, str]:
    if inventory_binding is not None and inventory_binding.get("ok") is not True:
        issues = list(inventory_binding.get("issues") or [])
        return (
            "CHECK_FAILED",
            None,
            (
                "State-tax freshness is not bound to the current inventory. "
                "Cross-run stale freshness cannot claim synchronization. "
                f"issues={issues[:8]}"
            ),
        )
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
    if live.get("live_check_performed") is not True:
        return (
            "CHECK_FAILED",
            None,
            (
                "No targeted first-party 2026 currentness check was performed. "
                "Cached artifact validity is not currentness. "
                f"evidence_valid_2026_count={live.get('evidence_valid_2026_count')} "
                "live_verified_current_2026_count=0."
            ),
        )
    if live.get("newer_data_exists") is True or live.get("newer_available_2026"):
        return (
            "NEWER_AVAILABLE",
            True,
            (
                "A current official source shows a 2026-applicable change. "
                f"newer={live.get('newer_available_2026')}"
            ),
        )
    live_failed = live.get("live_failed_2026") or []
    if live_failed:
        return (
            "CHECK_FAILED",
            None,
            (
                "Targeted live official checks failed. Cached evidence is not demoted. "
                f"live_failed={live_failed[:8]}"
            ),
        )
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
    *,
    fetch_fn: Any | None = None,
    perform_live: bool = True,
    run_cache: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Targeted 2026 currentness. Cached SHA/URL is not VERIFIED_CURRENT.

    Issues one first-party GET per distinct currentness URL during this run,
    and only for cells that are already evidence-valid (parsed_ok). Unparsed
    taxing cells stay CURRENTNESS_PENDING rather than drawing 102 GETs.
    """
    from foundation.sources.state_tax_currentness import (
        STATUS_CHECK_FAILED,
        STATUS_NEWER_AVAILABLE,
        STATUS_VERIFIED_CURRENT,
        assess_2026_currentness,
        collect_live_authority_text,
        currentness_surfaces,
        currentness_urls_for_cell,
        default_fetch_currentness,
    )

    captured = load_state_tax_inventory(inventory)
    if not captured:
        return None, "state tax inventory missing"
    jurisdictions = captured.get("jurisdictions") or {}
    evidence_valid = 0
    live_verified = 0
    live_failed: list[str] = []
    newer: list[str] = []
    unresolved: list[str] = []
    pending: list[str] = []
    cache: dict[str, Any] = run_cache if run_cache is not None else {}
    fetcher = fetch_fn or default_fetch_currentness
    surfaces = currentness_surfaces()
    live_check_performed = bool(perform_live)

    for state in ALL_JURISDICTIONS:
        rec = ((jurisdictions.get(state) or {}).get("years") or {}).get("2026") or {}
        valid = rec.get("parsed_ok") is True
        if valid:
            evidence_valid += 1
        if not perform_live:
            unresolved.append(state)
            pending.append(state)
            continue
        if not valid:
            unresolved.append(state)
            pending.append(state)
            continue
        urls = currentness_urls_for_cell(state, rec, surfaces)
        if not urls:
            live_failed.append(state)
            unresolved.append(state)
            continue
        live = collect_live_authority_text(urls, cache=cache, fetch_fn=fetcher)
        assessed = assess_2026_currentness(
            state=state,
            cell=rec,
            live=live,
            live_check_performed=True,
        )
        status = assessed.get("currentness_status")
        rec["currentness_status"] = status
        rec["currentness"] = assessed
        if status == STATUS_VERIFIED_CURRENT:
            live_verified += 1
        elif status == STATUS_NEWER_AVAILABLE:
            newer.append(state)
            unresolved.append(state)
        elif status == STATUS_CHECK_FAILED:
            live_failed.append(state)
            unresolved.append(state)
        else:
            pending.append(state)
            unresolved.append(state)

    result = {
        "evidence_valid_2026_count": evidence_valid,
        "live_verified_current_2026_count": live_verified if perform_live else 0,
        "verified_current_2026_count": live_verified if perform_live else 0,
        "live_failed_2026": live_failed,
        "live_not_checked_2026": pending,
        "newer_available_2026": newer,
        "unresolved_2026": unresolved,
        "all_2026_current": perform_live and live_verified == 51 and not unresolved,
        "live_check_performed": live_check_performed,
        "newer_data_exists": True if newer else (False if live_verified == 51 else None),
    }
    return result, None


def no_wage_tax_verified(state: str, year: int, inventory: Mapping[str, Any] | None = None) -> bool:
    payload = load_state_tax_inventory(inventory)
    if not payload:
        return False
    rec = ((payload.get("jurisdictions") or {}).get(state.upper()) or {}).get("years") or {}
    cell = rec.get(str(year)) or {}
    return cell.get("tax_status") == STATUS_NO_WAGE_TAX and cell.get("parsed_ok") is True
