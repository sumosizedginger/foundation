"""Retrieve and parse official IRS federal tax authorities.

Validates statutory RULES for a single independent adult. Does not calculate
gross-required income or an MSLC. Each inventory field is parsed from its
designated year-specific artifact.
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
INVENTORY_PATH = METADATA_DIR / "living_cost_federal_tax_inventory.json"
INVENTORY_REPORT_TYPE = "living_cost_federal_tax_inventory"

IRS_PUBLICATIONS_LISTING_URL = "https://www.irs.gov/publications"
IRS_RP_2023_34_URL = "https://www.irs.gov/pub/irs-drop/rp-23-34.pdf"
IRS_RP_2025_32_URL = "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf"
IRS_IRB_2023_48_URL = "https://www.irs.gov/pub/irs-irbs/irb23-48.pdf"
IRS_2026_NEWS_URL = (
    "https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026"
    "-including-amendments-from-the-one-big-beautiful-bill"
)
IRS_TOPICS_IN_THE_NEWS_URL = "https://www.irs.gov/newsroom/topics-in-the-news"
CURRENT_2026_INFLATION_AUTHORITY = "Rev. Proc. 2025-32"
IRS_TOPIC_751_URL = "https://www.irs.gov/taxtopics/tc751"
IRS_TOPIC_560_URL = "https://www.irs.gov/taxtopics/tc560"
IRS_PUB15_2024_URL = "https://www.irs.gov/pub/irs-prior/p15--2024.pdf"
IRS_PUB15_2026_PRIOR_URL = "https://www.irs.gov/pub/irs-prior/p15--2026.pdf"
IRS_PUB15_CURRENT_PDF_URL = "https://www.irs.gov/pub/irs-pdf/p15.pdf"
SSA_2024_PDF_URL = "https://www.ssa.gov/news/press/factsheets/colafacts2024.pdf"
SSA_2026_PDF_URL = "https://www.ssa.gov/news/press/factsheets/colafacts2026.pdf"
SSA_2026_HTML_URL = "https://www.ssa.gov/news/en/cola/factsheets/2026.html"
SSA_CBB_URL = "https://www.ssa.gov/oact/cola/cbb.html"
SSA_TAX_RATES_URL = "https://www.ssa.gov/oact/progdata/taxRates.html"

ALLOWED_AUTHORITY_HOSTS = frozenset({"www.irs.gov", "irs.gov", "www.ssa.gov", "ssa.gov"})

INCOME_TAX_ARTIFACT_BY_YEAR = {2024: "irs_rp_2023_34", 2026: "irs_rp_2025_32"}
PAYROLL_ARTIFACT_BY_YEAR = {2024: "irs_pub15_2024", 2026: "irs_pub15_2026"}
INCOME_TAX_AUTHORITY_ID = {2024: "IRS_RP_2023_34", 2026: "IRS_RP_2025_32"}
PAYROLL_AUTHORITY_ID = {2024: "IRS_PUB_15_2024", 2026: "IRS_PUB_15_2026"}

# Comparison constants only. Never used to manufacture inventory evidence.
ADDITIONAL_MEDICARE_RATE = 0.009
ADDITIONAL_MEDICARE_THRESHOLD_SINGLE = 200000.0
OASDI_EMPLOYEE_RATE = 0.062
MEDICARE_HI_EMPLOYEE_RATE = 0.0145


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


def official_authority_url(url: str | None) -> bool:
    if not url:
        return False
    host = (urlparse(url).hostname or "").lower()
    return host in ALLOWED_AUTHORITY_HOSTS


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("pypdf is required to parse IRS/SSA PDFs")
        return ""
    try:
        reader = PdfReader(str(path))
    except (OSError, ValueError) as exc:
        logger.error("Failed to open tax PDF %s: %s", path, exc)
        return ""
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("tax PDF page extract failed: %s", exc)
    return "\n".join(parts)


def _acquire(source_id: str, url: str, filename: str) -> dict[str, Any]:
    from foundation.sources.acquisition import acquire_source

    path = CACHE_DIR / filename
    art = acquire_source(
        source_id=source_id,
        url=url,
        cache_dir=CACHE_DIR,
        expected_filename=filename,
        force_download=False,
        refresh_if_unprovenanced=True,
    )
    if (art is None or not path.is_file()) and "ssa.gov" in url:
        art = _acquire_browser(source_id, url, filename)
    sha = file_sha256(path)
    return {
        "source_id": source_id,
        "url": url,
        "filename": filename,
        "path": str(path) if path.is_file() else None,
        "sha256": sha,
        "retrieved_at": getattr(art, "retrieved_at", None) if art else None,
        "byte_size": int(path.stat().st_size) if path.is_file() else None,
        "http_ok": bool(sha),
    }


def _acquire_browser(source_id: str, url: str, filename: str):
    """SSA often 403s generic clients; retry with the project browser UA."""
    from foundation.living_cost.freshness_currentness import download_temp_bytes
    from foundation.living_cost.freshness_discovery import _BROWSER_HEADERS
    from foundation.living_cost.manifest import RetrievedSourceArtifact
    from foundation.sources.acquisition import write_retrieval_sidecar

    dest = CACHE_DIR / filename
    try:
        tmp, digest = download_temp_bytes(url, headers=_BROWSER_HEADERS, suffix=dest.suffix)
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning("browser acquire failed for %s: %s", url, exc)
        return None
    except Exception as exc:  # noqa: BLE001 — requests types vary by transport
        logger.warning("browser acquire failed for %s: %s", url, exc)
        return None
    try:
        dest.write_bytes(tmp.read_bytes())
    finally:
        tmp.unlink(missing_ok=True)
    retrieved_at = _now_iso()
    write_retrieval_sidecar(
        dest,
        source_id=source_id,
        url=url,
        retrieved_at=retrieved_at,
        sha256=digest,
        byte_size=dest.stat().st_size,
        http_status=200,
        content_type=None,
    )
    return RetrievedSourceArtifact(
        source_id=source_id,
        retrieved_at=retrieved_at,
        sha256=digest,
        byte_size=dest.stat().st_size,
        local_cache_filename=filename,
        validation_status="VALIDATED",
        resolved_url=url,
        notes="retrieved with browser UA after default client 403",
    )


def parse_standard_deduction_single(text: str, year: int) -> float | None:
    """Parse unmarried/single standard deduction from the IRS Rev. Proc. section."""
    pattern = (
        rf"For taxable years beginning in {year}, the standard deduction\s+amounts.*?"
        r"Unmarried Individuals \(other than Surviving Spouses and Heads of\s+"
        r"Households\)[^\n]*\s*\$([0-9,]+)"
    )
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return float(match.group(1).replace(",", ""))
    alt = re.search(
        rf"Standard Deduction\.?\s+(?:For taxable years beginning in {year}|"
        rf"for any taxable year beginning in {year}).*?"
        r"Unmarried Individuals \(other than Surviving Spouses and Heads of\s+"
        r"Households\)[^\n]*\s*\$([0-9,]+)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if alt:
        return float(alt.group(1).replace(",", ""))
    return None


def parse_single_brackets(text: str, year: int) -> list[tuple[float, float]] | None:
    """Parse TABLE 3 Section 1(j)(2)(C) unmarried ordinary brackets."""
    del year
    marker = "TABLE 3 - Section 1(j)(2)(C)"
    idx = text.find(marker)
    if idx < 0:
        idx = text.upper().find("TABLE 3 - SECTION 1(J)(2)(C)")
    if idx < 0:
        return None
    window = text[idx : idx + 4000]
    start = re.search(r"If Taxable Income Is:", window, re.IGNORECASE)
    if not start:
        return None
    body = window[start.end() :]
    nxt = re.search(r"If Taxable Income Is:", body, re.IGNORECASE)
    if nxt:
        body = body[: nxt.start()]
    not_overs = [
        float(x.replace(",", "")) for x in re.findall(r"not over \$([0-9,]+)", body, re.IGNORECASE)
    ]
    rates = (0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37)
    if len(not_overs) < 6:
        return None
    brackets = [(not_overs[i], rates[i]) for i in range(6)]
    brackets.append((float("inf"), 0.37))
    return brackets


def parse_oasdi_wage_base(text: str, year: int) -> float | None:
    year_window = _year_payroll_window(text, year)
    patterns = (
        r"social security wage base\s+limit is \$([0-9,]+)",
        rf"wage base \(\$([0-9,]+) for {year}\)",
        rf"for earnings in {year}[^\n]{{0,80}}\$([0-9,]+)",
        r"Social Security \(OASDI only\)[^\n]{0,40}\$([0-9,]+)",
        rf"maximum taxable earnings[^\n]{{0,80}}{year}[^\n]{{0,40}}\$([0-9,]+)",
        rf"contribution and benefit base[^\n]{{0,80}}{year}[^\n]{{0,40}}\$([0-9,]+)",
        r"social security wage base(?:\s+limit)?\s+is \$([0-9,]+)",
    )
    for blob in (year_window, text):
        for pat in patterns:
            match = re.search(pat, blob, re.IGNORECASE)
            if not match:
                continue
            try:
                value = float(match.group(1).replace(",", ""))
            except ValueError:
                continue
            if 100_000 <= value <= 300_000:
                return value
    match = re.search(rf"\b{year}\b\s+\$?([0-9]{{3}},[0-9]{{3}})", year_window or text)
    if match:
        value = float(match.group(1).replace(",", ""))
        if 100_000 <= value <= 300_000:
            return value
    return None


def parse_employee_oasdi_rate(text: str) -> float | None:
    if re.search(r"social security tax on taxable wages is 6\.2\s*%", text, re.IGNORECASE):
        return 0.062
    if re.search(r"6\.2\s*percent", text, re.IGNORECASE):
        return 0.062
    if re.search(r"Social Security is 6\.2\s*%", text, re.IGNORECASE):
        return 0.062
    match = re.search(r"OASDI[^%]{0,40}(6\.2)\s*%", text, re.IGNORECASE)
    if match:
        return 0.062
    return None


def parse_employee_medicare_rate(text: str) -> float | None:
    if re.search(r"Medicare tax rate is 1\.45\s*%", text, re.IGNORECASE):
        return 0.0145
    if re.search(r"tax rate for Medicare is 1\.45\s*%", text, re.IGNORECASE):
        return 0.0145
    if re.search(r"1\.45\s*percent", text, re.IGNORECASE):
        return 0.0145
    match = re.search(r"Medicare[^%]{0,40}(1\.45)\s*%", text, re.IGNORECASE)
    if match:
        return 0.0145
    return None


def parse_medicare_no_limit(text: str) -> bool:
    return bool(
        re.search(r"no wage\s+base\s+limit for Medicare", text, re.IGNORECASE)
        or re.search(r"There is no wage\s+base\s+limit for Medicare", text, re.IGNORECASE)
    )


def parse_additional_medicare(text: str) -> dict[str, Any] | None:
    """Parse Additional Medicare withholding from official text. No constant fill-in."""
    if not (
        re.search(r"additional medicare", text, re.IGNORECASE)
        or re.search(r"additional 0\.9\s*percent", text, re.IGNORECASE)
        or re.search(r"0\.9\s*percent in Medicare", text, re.IGNORECASE)
    ):
        return None
    rate = None
    if (
        re.search(
            r"(?:withhold a\s+)?0\.9\s*%\s+Additional Medicare",
            text,
            re.IGNORECASE,
        )
        or re.search(r"additional 0\.9\s*%", text, re.IGNORECASE)
        or re.search(r"additional 0\.9\s*percent", text, re.IGNORECASE)
        or re.search(r"0\.9\s*percent in Medicare", text, re.IGNORECASE)
    ):
        rate = 0.009
    thresh = None
    match = re.search(
        r"excess of \$([0-9,]+)\s+in a calendar year",
        text,
        re.IGNORECASE,
    )
    if match:
        thresh = float(match.group(1).replace(",", ""))
    if thresh is None:
        match = re.search(
            r"more than \$([0-9,]+)\s*\(\$([0-9,]+) for married",
            text,
            re.IGNORECASE,
        )
        if match:
            thresh = float(match.group(1).replace(",", ""))
    if thresh is None:
        match = re.search(
            r"Additional Medicare.{0,120}(?:excess of|more than)\s+\$([0-9,]+)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            thresh = float(match.group(1).replace(",", ""))
    if rate is None or thresh is None:
        return None
    return {
        "applicable": True,
        "threshold": thresh,
        "rate": rate,
    }


def parse_pub15_identity(text: str) -> dict[str, Any]:
    """Identify Publication 15 revision year from official PDF text."""
    year = None
    match = re.search(r"Publication 15\s*\((\d{4})\)", text, re.IGNORECASE)
    if match:
        year = int(match.group(1))
    if year is None:
        match = re.search(r"Employer's Tax Guide[^\n]{0,40}(\d{4})", text, re.IGNORECASE)
        if match:
            year = int(match.group(1))
    if year is None:
        match = re.search(r"p15/(\d{4})", text, re.IGNORECASE)
        if match:
            year = int(match.group(1))
    if year is None:
        match = re.search(r"Social security and Medicare tax for (\d{4})", text, re.IGNORECASE)
        if match:
            year = int(match.group(1))
    return {
        "title": "Publication 15 (Circular E), Employer's Tax Guide" if year else None,
        "publication_year": year,
    }


def parse_pub15_listing(html: str) -> dict[str, Any]:
    """Parse the official IRS publications listing for Publication 15."""
    match = re.search(
        r"Publication 15\s*\((\d{4})\).*?(?:href=)?[\"']?([^\"'\s>]*p15(?:--\d{4})?\.pdf)",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    year = None
    href = None
    if match:
        year = int(match.group(1))
        href = match.group(2)
    if year is None:
        simple = re.search(r"Publication 15\s*\((\d{4})\)", html, re.IGNORECASE)
        if simple:
            year = int(simple.group(1))
    if href and href.startswith("/"):
        href = "https://www.irs.gov" + href
    if href is None and year:
        href = IRS_PUB15_CURRENT_PDF_URL
    return {
        "revision_year": year,
        "listed_pdf_url": href,
        "current_pdf_url": IRS_PUB15_CURRENT_PDF_URL,
        "year_specific_prior_url": (
            f"https://www.irs.gov/pub/irs-prior/p15--{year}.pdf" if year else None
        ),
    }


def discover_pub15_2026_url(listing_html: str | None = None) -> dict[str, Any]:
    """Discover the official 2026 Publication 15 URL from the IRS listing."""
    html = listing_html
    retrieved_at = None
    listing_error = None
    if html is None:
        try:
            from foundation.living_cost.freshness_discovery import fetch_text

            html, retrieved_at = fetch_text(IRS_PUBLICATIONS_LISTING_URL)
        except (OSError, RuntimeError, ValueError) as exc:
            listing_error = str(exc)
            html = ""
    parsed = parse_pub15_listing(html) if html else {}
    year = parsed.get("revision_year")
    chosen = None
    chosen_kind = None
    if year == 2026:
        # Prefer the year-specific prior URL when the listing year is 2026.
        chosen = parsed.get("year_specific_prior_url") or IRS_PUB15_2026_PRIOR_URL
        chosen_kind = "year_specific_prior"
    return {
        "listing_url": IRS_PUBLICATIONS_LISTING_URL,
        "listing_retrieved_at": retrieved_at,
        "listing_error": listing_error,
        "revision_year": year,
        "resolved_url": chosen,
        "url_kind": chosen_kind,
        "current_pdf_url": IRS_PUB15_CURRENT_PDF_URL,
        "fallback_current_if_prior_missing": year == 2026,
    }


def _year_payroll_window(text: str, year: int) -> str:
    marker = rf"Social security and Medicare tax for {year}"
    match = re.search(marker, text, re.IGNORECASE)
    if not match:
        return text
    return text[match.start() : match.start() + 2500]


def _text_for(art: dict[str, Any] | None) -> str:
    if not art:
        return ""
    path = Path(art["path"]) if art.get("path") else None
    if path is None or not path.is_file():
        return ""
    if path.suffix.lower() == ".pdf":
        return _extract_pdf_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


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


def retrieve_federal_tax_authorities() -> dict[str, Any]:
    """Download official IRS/SSA artifacts into cache. Does not invent values."""
    discovery = discover_pub15_2026_url()
    pub15_2026_url = discovery.get("resolved_url") or IRS_PUB15_2026_PRIOR_URL
    artifacts: dict[str, Any] = {
        "irs_rp_2023_34": _acquire("irs_rp_2023_34", IRS_RP_2023_34_URL, "irs_rp-23-34.pdf"),
        "irs_irb_2023_48": _acquire("irs_irb_2023_48", IRS_IRB_2023_48_URL, "irs_irb23-48.pdf"),
        "irs_rp_2025_32": _acquire("irs_rp_2025_32", IRS_RP_2025_32_URL, "irs_rp-25-32.pdf"),
        "irs_pub15_2024": _acquire("irs_pub15_2024", IRS_PUB15_2024_URL, "irs_p15_2024.pdf"),
        "irs_pub15_2026": _acquire("irs_pub15_2026", pub15_2026_url, "irs_p15_2026.pdf"),
        "irs_2026_news": _acquire("irs_2026_news", IRS_2026_NEWS_URL, "irs_2026_inflation.html"),
        "irs_topic_751": _acquire("irs_topic_751", IRS_TOPIC_751_URL, "irs_tc751.html"),
        "irs_topic_560": _acquire("irs_topic_560", IRS_TOPIC_560_URL, "irs_tc560.html"),
        "ssa_2024_factsheet": _acquire("ssa_cola_2024", SSA_2024_PDF_URL, "ssa_colafacts2024.pdf"),
        "ssa_2026_factsheet_pdf": _acquire(
            "ssa_cola_2026_pdf", SSA_2026_PDF_URL, "ssa_colafacts2026.pdf"
        ),
        "ssa_cbb": _acquire("ssa_cbb", SSA_CBB_URL, "ssa_cbb.html"),
        "ssa_tax_rates": _acquire("ssa_tax_rates", SSA_TAX_RATES_URL, "ssa_taxRates.html"),
        "ssa_2026_html": _acquire("ssa_cola_2026_html", SSA_2026_HTML_URL, "ssa_cola_2026.html"),
    }
    pub15_2026 = artifacts["irs_pub15_2026"]
    if not pub15_2026.get("http_ok") and discovery.get("fallback_current_if_prior_missing"):
        artifacts["irs_pub15_2026"] = _acquire(
            "irs_pub15_2026", IRS_PUB15_CURRENT_PDF_URL, "irs_p15_2026.pdf"
        )
        artifacts["irs_pub15_2026"]["url_kind"] = "current_listing_p15_pdf"
    else:
        artifacts["irs_pub15_2026"]["url_kind"] = discovery.get("url_kind")
    artifacts["irs_pub15_2026"]["listing_revision_year"] = discovery.get("revision_year")
    artifacts["irs_pub15_2026"]["listing_url"] = IRS_PUBLICATIONS_LISTING_URL
    artifacts["_pub15_discovery"] = discovery
    return artifacts


def _income_fields(year: int, art: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    text = _text_for(art)
    key = INCOME_TAX_ARTIFACT_BY_YEAR[year]
    authority = INCOME_TAX_AUTHORITY_ID[year]
    sha = art.get("sha256") if art else None
    std = parse_standard_deduction_single(text, year)
    brackets = parse_single_brackets(text, year)
    if std is None:
        issues.append("STANDARD_DEDUCTION_UNPARSED")
    if not brackets:
        issues.append("BRACKETS_UNPARSED")
    std_rec = _field(
        value=std,
        authority_id=authority,
        source_artifact_key=key,
        source_sha256=sha,
        extraction_identity=f"rp_{year}_standard_deduction_unmarried",
    )
    br_recs = [
        _field(
            upper=None if cap == float("inf") else cap,
            rate=rate,
            authority_id=authority,
            source_artifact_key=key,
            source_sha256=sha,
            extraction_identity=f"rp_{year}_table3_section_1j2c",
        )
        for cap, rate in (brackets or [])
    ]
    return {"standard_deduction": std_rec, "income_tax_brackets": br_recs}, issues


def _payroll_fields(year: int, art: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    text = _text_for(art)
    key = PAYROLL_ARTIFACT_BY_YEAR[year]
    authority = PAYROLL_AUTHORITY_ID[year]
    sha = art.get("sha256") if art else None
    identity = parse_pub15_identity(text) if text else {}
    if art and art.get("http_ok") and identity.get("publication_year") not in {None, year}:
        issues.append(f"PUB15_YEAR_MISMATCH:{identity.get('publication_year')}")
    oasdi_rate = parse_employee_oasdi_rate(text)
    oasdi_cap = parse_oasdi_wage_base(text, year)
    hi_rate = parse_employee_medicare_rate(text)
    no_limit = parse_medicare_no_limit(text)
    addl = parse_additional_medicare(text)
    if oasdi_rate is None:
        issues.append("OASDI_RATE_UNPARSED")
    if oasdi_cap is None:
        issues.append("OASDI_WAGE_BASE_UNPARSED")
    if hi_rate is None:
        issues.append("MEDICARE_RATE_UNPARSED")
    if not no_limit:
        issues.append("MEDICARE_NO_LIMIT_UNPARSED")
    if addl is None:
        issues.append("ADDITIONAL_MEDICARE_UNPARSED")
    oasdi = _field(
        employee_rate=oasdi_rate,
        taxable_maximum=oasdi_cap,
        authority_id=authority,
        source_artifact_key=key,
        source_sha256=sha,
        extraction_identity=f"pub15_{year}_oasdi",
    )
    medicare = _field(
        employee_rate=hi_rate,
        taxable_maximum=None,
        no_limit=bool(no_limit),
        authority_id=authority,
        source_artifact_key=key,
        source_sha256=sha,
        extraction_identity=f"pub15_{year}_medicare_hi",
    )
    if addl is None:
        addl_rec = _field(
            applicable=False,
            threshold=None,
            rate=None,
            authority_id=authority,
            source_artifact_key=key,
            source_sha256=sha,
            extraction_identity=f"pub15_{year}_additional_medicare",
        )
    else:
        addl_rec = _field(
            applicable=True,
            threshold=addl["threshold"],
            rate=addl["rate"],
            authority_id=authority,
            source_artifact_key=key,
            source_sha256=sha,
            extraction_identity=f"pub15_{year}_additional_medicare",
        )
    return {
        "oasdi": oasdi,
        "medicare_hi": medicare,
        "additional_medicare_tax": addl_rec,
        "pub15_identity": identity,
    }, issues


def build_federal_tax_inventory(artifacts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse each field from its designated official artifact. No text-soup merge."""
    arts = artifacts if artifacts is not None else retrieve_federal_tax_authorities()
    discovery = (
        arts.get("_pub15_discovery") if isinstance(arts.get("_pub15_discovery"), dict) else {}
    )
    years: dict[str, Any] = {}
    for year, income_key, payroll_key in (
        (2024, "irs_rp_2023_34", "irs_pub15_2024"),
        (2026, "irs_rp_2025_32", "irs_pub15_2026"),
    ):
        income, income_issues = _income_fields(year, arts.get(income_key))
        payroll, payroll_issues = _payroll_fields(year, arts.get(payroll_key))
        issues = income_issues + payroll_issues
        years[str(year)] = {
            "tax_year": year,
            "filing_status": "SINGLE",
            "standard_deduction": income["standard_deduction"],
            "income_tax_brackets": income["income_tax_brackets"],
            "oasdi": payroll["oasdi"],
            "medicare_hi": payroll["medicare_hi"],
            "additional_medicare_tax": payroll["additional_medicare_tax"],
            "pub15_identity": payroll.get("pub15_identity"),
            "issues": issues,
            "parsed_ok": not issues,
        }
    bound_artifacts = []
    for key, art in arts.items():
        if key.startswith("_") or not isinstance(art, dict):
            continue
        bound_artifacts.append(
            {
                "key": key,
                "url": art.get("url"),
                "filename": art.get("filename"),
                "sha256": art.get("sha256"),
                "retrieved_at": art.get("retrieved_at"),
                "http_ok": art.get("http_ok"),
                "byte_size": art.get("byte_size"),
                "document_identity": art.get("listing_revision_year")
                if key == "irs_pub15_2026"
                else None,
            }
        )
    return {
        "report_type": INVENTORY_REPORT_TYPE,
        "generated_at": _now_iso(),
        "filing_status": "SINGLE",
        "years": years,
        "retrieved_artifacts": bound_artifacts,
        "pub15_2026_discovery": {
            "listing_url": IRS_PUBLICATIONS_LISTING_URL,
            "revision_year": discovery.get("revision_year"),
            "resolved_url": (arts.get("irs_pub15_2026") or {}).get("url"),
            "listing_error": discovery.get("listing_error"),
        },
        "calculates_mslc": False,
        "headline_calculated": False,
    }


def write_federal_tax_inventory(output_path: Path | None = None) -> dict[str, Any]:
    payload = build_federal_tax_inventory()
    dest = output_path or INVENTORY_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _normalize_rev_proc_id(token: str) -> str:
    token = token.strip().replace(" ", "")
    match = re.fullmatch(r"(?:20)?(\d{2})-(\d+)", token)
    if not match:
        return token
    return f"20{match.group(1)}-{int(match.group(2))}"


def parse_current_2026_inflation_authority(html: str | None) -> dict[str, Any]:
    """Identify the applicable 2026 inflation-adjustment Rev. Proc. from a current IRS surface.

    The historical October 2025 announcement is not used here.
    """
    empty = {
        "current_2026_inflation_authority": None,
        "current_authority_status": "NOT_FOUND",
        "cited_authorities": [],
        "section_found": False,
        "successor_rev_proc": None,
    }
    if not html or not str(html).strip():
        return empty
    section_match = re.search(
        r"<h2[^>]*>\s*Inflation adjustments for tax year 2026\s*</h2>(.*?)(?:<h2\b|$)",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if section_match:
        section = section_match.group(1)
        section_found = True
    else:
        text_match = re.search(
            r"Inflation adjustments for tax year 2026(.{0,4000})",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if not text_match:
            return empty
        section = text_match.group(1)
        section_found = True
    cited: list[str] = []
    for item in re.findall(
        r"Rev(?:enue)?\.?\s*Proc(?:edure)?\.?\s*(\d{4}-\d+)",
        section,
        re.IGNORECASE,
    ):
        cited.append(_normalize_rev_proc_id(item))
    for item in re.findall(r"RP-(\d{4}-\d+)", section, re.IGNORECASE):
        cited.append(_normalize_rev_proc_id(item))
    for yy, num in re.findall(r"rp-(\d{2})-(\d+)\.pdf", section, re.IGNORECASE):
        cited.append(_normalize_rev_proc_id(f"{yy}-{num}"))
    unique: list[str] = []
    for item in cited:
        if item not in unique:
            unique.append(item)
    if not unique:
        return {
            "current_2026_inflation_authority": None,
            "current_authority_status": "AMBIGUOUS",
            "cited_authorities": [],
            "section_found": section_found,
            "successor_rev_proc": None,
        }
    others = [item for item in unique if item != "2025-32"]
    if others:
        successor = others[0]
        for item in others:
            if item.startswith("2026-"):
                successor = item
                break
        return {
            "current_2026_inflation_authority": f"Rev. Proc. {successor}",
            "current_authority_status": "IDENTIFIED",
            "cited_authorities": unique,
            "section_found": True,
            "successor_rev_proc": f"Rev. Proc. {successor}",
        }
    return {
        "current_2026_inflation_authority": CURRENT_2026_INFLATION_AUTHORITY,
        "current_authority_status": "IDENTIFIED",
        "cited_authorities": unique,
        "section_found": True,
        "successor_rev_proc": None,
    }


def captured_2026_payroll(inventory: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Read 2026 payroll fields from one captured inventory payload. No duplicated literals."""
    if not isinstance(inventory, Mapping):
        return None
    years = inventory.get("years")
    if not isinstance(years, Mapping):
        return None
    rec = years.get("2026")
    if not isinstance(rec, Mapping):
        return None
    oasdi = rec.get("oasdi") if isinstance(rec.get("oasdi"), Mapping) else {}
    medicare = rec.get("medicare_hi") if isinstance(rec.get("medicare_hi"), Mapping) else {}
    addl = (
        rec.get("additional_medicare_tax")
        if isinstance(rec.get("additional_medicare_tax"), Mapping)
        else {}
    )
    captured = {
        "oasdi_employee_rate": oasdi.get("employee_rate"),
        "oasdi_taxable_maximum": oasdi.get("taxable_maximum"),
        "medicare_hi_employee_rate": medicare.get("employee_rate"),
        "medicare_no_limit": medicare.get("no_limit"),
        "additional_medicare_threshold": addl.get("threshold"),
        "additional_medicare_rate": addl.get("rate"),
    }
    if any(value is None for value in captured.values()):
        return None
    return captured


def compare_live_pub15_to_inventory(
    live_text: str | None,
    inventory: Mapping[str, Any] | None,
) -> bool | None:
    """Compare live Publication 15 payroll fields to one captured 2026 inventory record.

    Returns True on agreement, False on disagreement, None if either side is incomplete.
    """
    expected = captured_2026_payroll(inventory)
    if expected is None or not live_text:
        return None
    live_rate = parse_employee_oasdi_rate(live_text)
    live_cap = parse_oasdi_wage_base(live_text, 2026)
    live_hi = parse_employee_medicare_rate(live_text)
    live_no_limit = parse_medicare_no_limit(live_text)
    live_addl = parse_additional_medicare(live_text)
    if (
        live_rate is None
        or live_cap is None
        or live_hi is None
        or not live_no_limit
        or live_addl is None
        or live_addl.get("threshold") is None
        or live_addl.get("rate") is None
    ):
        return None
    return (
        live_rate == expected["oasdi_employee_rate"]
        and live_cap == expected["oasdi_taxable_maximum"]
        and live_hi == expected["medicare_hi_employee_rate"]
        and bool(live_no_limit) == bool(expected["medicare_no_limit"])
        and live_addl["threshold"] == expected["additional_medicare_threshold"]
        and live_addl["rate"] == expected["additional_medicare_rate"]
    )


def load_captured_federal_tax_inventory(
    inventory: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Load one inventory payload. Callers must reuse this object for compare."""
    if isinstance(inventory, Mapping):
        return dict(inventory)
    if not INVENTORY_PATH.is_file():
        return None
    try:
        payload = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def assemble_federal_tax_live_currentness(
    *,
    listing_html: str | None,
    current_authority_html: str | None,
    current_authority_error: str | None,
    live_pub15_text: str | None,
    inventory: Mapping[str, Any] | None,
    checked_at: str,
    current_authority_source_url: str = IRS_TOPICS_IN_THE_NEWS_URL,
) -> dict[str, Any]:
    """Build live currentness from already-retrieved surfaces. Historical news is unused."""
    listing = parse_pub15_listing(listing_html) if listing_html else {}
    pub_year = listing.get("revision_year")
    if current_authority_error and not current_authority_html:
        authority = {
            "current_2026_inflation_authority": None,
            "current_authority_status": "UNRETRIEVED",
            "cited_authorities": [],
            "section_found": False,
            "successor_rev_proc": None,
        }
    else:
        authority = parse_current_2026_inflation_authority(current_authority_html)
    successor = authority.get("successor_rev_proc")
    identified = authority.get("current_2026_inflation_authority")
    status = authority.get("current_authority_status")
    rp_current: bool | None
    if status == "IDENTIFIED" and identified == CURRENT_2026_INFLATION_AUTHORITY and not successor:
        rp_current = True
    elif status == "IDENTIFIED" and successor:
        rp_current = False
    elif status == "IDENTIFIED" and identified and identified != CURRENT_2026_INFLATION_AUTHORITY:
        rp_current = False
        successor = identified
    else:
        rp_current = None
    payroll_match: bool | None = None
    if pub_year == 2026 and live_pub15_text is not None:
        payroll_match = compare_live_pub15_to_inventory(live_pub15_text, inventory)
    return {
        "pub15_revision_year": pub_year,
        "rev_proc_2025_32_current": rp_current,
        "successor_rev_proc": successor,
        "current_pub15_payroll_matches": payroll_match,
        "current_2026_inflation_authority": identified,
        "current_authority_checked_at": checked_at,
        "current_authority_source_url": current_authority_source_url,
        "current_authority_status": status,
        "current_authority_cited": authority.get("cited_authorities"),
        "listing_url": IRS_PUBLICATIONS_LISTING_URL,
        "news_url": IRS_2026_NEWS_URL,
    }


def evaluate_federal_tax_freshness(
    *,
    inventory_valid: bool,
    live: dict[str, Any] | None,
    live_error: str | None,
) -> tuple[str, bool | None, str]:
    """Separate evidence validity from live currentness.

    Returns (freshness_check_status, newer_data_exists, reason).
    """
    if live_error:
        return (
            "CHECK_FAILED",
            None,
            (
                "Live official IRS currentness discovery failed. "
                f"Cached inventory remains {'VALIDATED' if inventory_valid else 'unvalidated'}. "
                f"{live_error}"
            ),
        )
    live = live or {}
    pub_year = live.get("pub15_revision_year")
    successor = live.get("successor_rev_proc")
    rp_current = live.get("rev_proc_2025_32_current")
    payroll_match = live.get("current_pub15_payroll_matches")
    authority_status = live.get("current_authority_status")
    identified = live.get("current_2026_inflation_authority")
    if authority_status in {"NOT_FOUND", "AMBIGUOUS", "UNRETRIEVED", "PARSE_FAILED"}:
        return (
            "CHECK_FAILED",
            None,
            (
                "Current official IRS 2026 inflation-adjustment surface did not identify "
                "the applicable authority. Cached inventory remains VALIDATED if previously bound. "
                f"status={authority_status}."
            ),
        )
    if successor:
        return (
            "NEWER_AVAILABLE",
            True,
            f"Official IRS current material cites a superseding 2026 authority: {successor}.",
        )
    if identified and identified != CURRENT_2026_INFLATION_AUTHORITY:
        return (
            "NEWER_AVAILABLE",
            True,
            (
                "Official IRS current 2026 inflation-adjustment surface identifies "
                f"{identified}, not {CURRENT_2026_INFLATION_AUTHORITY}."
            ),
        )
    if isinstance(pub_year, int) and pub_year > 2026:
        return (
            "NEWER_AVAILABLE",
            True,
            f"Official IRS publications listing now shows Publication 15 ({pub_year}).",
        )
    if isinstance(pub_year, int) and pub_year != 2026:
        return (
            "CHECK_FAILED",
            None,
            f"Official IRS publications listing Publication 15 revision is {pub_year}, not 2026.",
        )
    if rp_current is False:
        return (
            "NEWER_AVAILABLE",
            True,
            "Official IRS 2026 inflation-adjustment material no longer presents Rev. Proc. 2025-32.",
        )
    if payroll_match is False:
        return (
            "CHECK_FAILED",
            None,
            "Current official Publication 15 payroll values disagree with the bound 2026 inventory.",
        )
    if payroll_match is None:
        return (
            "CHECK_FAILED",
            None,
            (
                "Live official Publication 15 payroll comparison did not complete. "
                "Cached inventory remains VALIDATED if previously bound. "
                "Do not claim VERIFIED_CURRENT without a successful compare."
            ),
        )
    if not inventory_valid:
        return (
            "CHECK_FAILED",
            None,
            "Federal tax inventory is not validated; VERIFIED_CURRENT is impossible.",
        )
    if inventory_valid and pub_year == 2026 and rp_current is True and payroll_match is True:
        return (
            "VERIFIED_CURRENT",
            False,
            (
                "Targeted official IRS discovery confirms Publication 15 (2026) and "
                "Rev. Proc. 2025-32 remain the applicable 2026 authorities, and current "
                "Publication 15 payroll values agree with the bound inventory."
            ),
        )
    return (
        "CHECK_FAILED",
        None,
        f"Live IRS currentness was incomplete: {live}.",
    )


def discover_federal_tax_live(
    inventory: Mapping[str, Any] | None = None,
    *,
    listing_html: str | None = None,
    current_authority_html: str | None = None,
    live_pub15_text: str | None = None,
    current_authority_error: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Targeted live IRS currentness from a current first-party surface.

    Does not treat the historical October 2025 announcement as proof of no successor.
    Does not use the generic IRB landing as proof.
    Payroll compare uses one captured validated inventory payload, not literals.
    """
    captured = load_captured_federal_tax_inventory(inventory)
    checked_at = _now_iso()
    listing_body = listing_html
    authority_body = current_authority_html
    authority_error = current_authority_error
    pub15_text = live_pub15_text
    if listing_body is None or (authority_body is None and authority_error is None):
        from foundation.living_cost.freshness_discovery import fetch_text

        try:
            if listing_body is None:
                listing_body, _ = fetch_text(IRS_PUBLICATIONS_LISTING_URL)
        except (OSError, RuntimeError, ValueError) as exc:
            return None, str(exc)
        if authority_body is None and authority_error is None:
            try:
                authority_body, checked_at = fetch_text(IRS_TOPICS_IN_THE_NEWS_URL)
            except (OSError, RuntimeError, ValueError) as exc:
                authority_error = str(exc)
    if pub15_text is None:
        listing = parse_pub15_listing(listing_body or "")
        if listing.get("revision_year") == 2026:
            try:
                from foundation.living_cost.freshness_currentness import download_temp_bytes
                from foundation.living_cost.freshness_discovery import _BROWSER_HEADERS

                tmp, _digest = download_temp_bytes(
                    IRS_PUB15_CURRENT_PDF_URL, headers=_BROWSER_HEADERS, suffix=".pdf"
                )
                try:
                    pub15_text = _extract_pdf_text(tmp)
                finally:
                    tmp.unlink(missing_ok=True)
            except (OSError, RuntimeError, ValueError) as exc:
                logger.warning("live current Pub 15 compare failed: %s", exc)
                pub15_text = None
    live = assemble_federal_tax_live_currentness(
        listing_html=listing_body,
        current_authority_html=authority_body,
        current_authority_error=authority_error,
        live_pub15_text=pub15_text,
        inventory=captured,
        checked_at=checked_at,
        current_authority_source_url=IRS_TOPICS_IN_THE_NEWS_URL,
    )
    return live, None
