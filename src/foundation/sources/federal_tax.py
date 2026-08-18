"""Retrieve and parse official IRS + SSA federal tax authorities.

Validates statutory RULES for a single independent adult. Does not calculate
gross-required income or an MSLC.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
INVENTORY_PATH = METADATA_DIR / "living_cost_federal_tax_inventory.json"
INVENTORY_REPORT_TYPE = "living_cost_federal_tax_inventory"

# Official first-party artifacts. Discovered at runtime; these are the expected family.
IRS_IRB_LANDING = "https://www.irs.gov/irb"
IRS_RP_2023_34_URL = "https://www.irs.gov/pub/irs-drop/rp-23-34.pdf"
IRS_RP_2025_32_URL = "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf"
IRS_IRB_2023_48_URL = "https://www.irs.gov/pub/irs-irbs/irb23-48.pdf"
IRS_2026_NEWS_URL = (
    "https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026"
    "-including-amendments-from-the-one-big-beautiful-bill"
)
SSA_2024_PDF_URL = "https://www.ssa.gov/news/press/factsheets/colafacts2024.pdf"
SSA_2026_PDF_URL = "https://www.ssa.gov/news/press/factsheets/colafacts2026.pdf"
SSA_2026_HTML_URL = "https://www.ssa.gov/news/en/cola/factsheets/2026.html"
SSA_CBB_URL = "https://www.ssa.gov/oact/cola/cbb.html"
SSA_TAX_RATES_URL = "https://www.ssa.gov/oact/progdata/taxRates.html"
IRS_TOPIC_751_URL = "https://www.irs.gov/taxtopics/tc751"
IRS_TOPIC_560_URL = "https://www.irs.gov/taxtopics/tc560"
IRS_PUB15_2024_URL = "https://www.irs.gov/pub/irs-prior/p15--2024.pdf"

# Additional Medicare Tax is statutory IRC 3101(b)(2); threshold is not CPI-indexed.
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
    # 2026 RP also uses "beginning in 2026" near .14 Standard Deduction.
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
    # Stop at the next table's "If Taxable Income Is" so we take one complete schedule.
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
    patterns = (
        rf"wage base \(\$([0-9,]+) for {year}\)",
        rf"for earnings in {year}[^\n]{{0,80}}\$([0-9,]+)",
        r"Social Security \(OASDI only\)[^\n]{0,40}\$([0-9,]+)",
        rf"maximum taxable earnings[^\n]{{0,80}}{year}[^\n]{{0,40}}\$([0-9,]+)",
        rf"contribution and benefit base[^\n]{{0,80}}{year}[^\n]{{0,40}}\$([0-9,]+)",
        r"social security wage base(?:\s+limit)?\s+is \$([0-9,]+)",
        rf"(?:20{str(year)[2:]}|{year})[^$]{{0,80}}\$([0-9,]{{6,9}})",
    )
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1).replace(",", ""))
        except ValueError:
            continue
        if 100_000 <= value <= 300_000:
            return value
    # Table row: 2024 168,600
    match = re.search(rf"\b{year}\b\s+\$?([0-9]{{3}},[0-9]{{3}})", text)
    if match:
        value = float(match.group(1).replace(",", ""))
        if 100_000 <= value <= 300_000:
            return value
    return None


def parse_employee_oasdi_rate(text: str) -> float | None:
    if re.search(r"6\.2\s*percent", text, re.IGNORECASE):
        return 0.062
    if re.search(r"Social Security is 6\.2\s*%", text, re.IGNORECASE):
        return 0.062
    match = re.search(r"OASDI[^%]{0,40}(6\.2)\s*%", text, re.IGNORECASE)
    if match:
        return 0.062
    return None


def parse_employee_medicare_rate(text: str) -> float | None:
    if re.search(r"1\.45\s*percent", text, re.IGNORECASE):
        return 0.0145
    match = re.search(r"Medicare[^%]{0,40}(1\.45)\s*%", text, re.IGNORECASE)
    if match:
        return 0.0145
    return None


def parse_additional_medicare(text: str) -> dict[str, Any] | None:
    if (
        not re.search(r"additional 0\.9\s*percent", text, re.IGNORECASE)
        and not re.search(r"0\.9\s*percent in Medicare", text, re.IGNORECASE)
        and "additional medicare" not in text.lower()
        and "0.9" not in text
    ):
        return None
    thresh = None
    match = re.search(
        r"more than \$([0-9,]+)\s*\(\$([0-9,]+) for married",
        text,
        re.IGNORECASE,
    )
    if match:
        thresh = float(match.group(1).replace(",", ""))
    if thresh is None and re.search(r"\$200,000", text):
        thresh = 200000.0
    if thresh is None:
        return None
    return {
        "applicable": True,
        "threshold": thresh,
        "rate": ADDITIONAL_MEDICARE_RATE,
    }


def retrieve_federal_tax_authorities() -> dict[str, Any]:
    """Download official IRS/SSA artifacts into cache. Does not invent values."""
    artifacts = {
        "irs_rp_2023_34": _acquire("irs_rp_2023_34", IRS_RP_2023_34_URL, "irs_rp-23-34.pdf"),
        "irs_irb_2023_48": _acquire("irs_irb_2023_48", IRS_IRB_2023_48_URL, "irs_irb23-48.pdf"),
        "irs_rp_2025_32": _acquire("irs_rp_2025_32", IRS_RP_2025_32_URL, "irs_rp-25-32.pdf"),
        "ssa_2024_factsheet": _acquire("ssa_cola_2024", SSA_2024_PDF_URL, "ssa_colafacts2024.pdf"),
        "ssa_2026_factsheet_pdf": _acquire(
            "ssa_cola_2026_pdf", SSA_2026_PDF_URL, "ssa_colafacts2026.pdf"
        ),
        "ssa_cbb": _acquire("ssa_cbb", SSA_CBB_URL, "ssa_cbb.html"),
        "ssa_tax_rates": _acquire("ssa_tax_rates", SSA_TAX_RATES_URL, "ssa_taxRates.html"),
        "ssa_2026_html": _acquire("ssa_cola_2026_html", SSA_2026_HTML_URL, "ssa_cola_2026.html"),
        "irs_2026_news": _acquire("irs_2026_news", IRS_2026_NEWS_URL, "irs_2026_inflation.html"),
        "irs_topic_751": _acquire("irs_topic_751", IRS_TOPIC_751_URL, "irs_tc751.html"),
        "irs_topic_560": _acquire("irs_topic_560", IRS_TOPIC_560_URL, "irs_tc560.html"),
        "irs_pub15_2024": _acquire("irs_pub15_2024", IRS_PUB15_2024_URL, "irs_p15_2024.pdf"),
    }
    return artifacts


def _text_for(art: dict[str, Any]) -> str:
    path = Path(art["path"]) if art.get("path") else None
    if path is None or not path.is_file():
        return ""
    if path.suffix.lower() == ".pdf":
        return _extract_pdf_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def build_federal_tax_inventory(artifacts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse official authorities into a year-by-year statutory inventory."""
    arts = artifacts if artifacts is not None else retrieve_federal_tax_authorities()
    text_2024 = "\n".join(
        _text_for(arts[key])
        for key in (
            "irs_rp_2023_34",
            "irs_irb_2023_48",
            "ssa_2024_factsheet",
            "ssa_cbb",
            "ssa_tax_rates",
            "irs_topic_751",
            "irs_topic_560",
            "irs_pub15_2024",
        )
        if key in arts
    )
    text_2026 = "\n".join(
        _text_for(arts[key])
        for key in (
            "irs_rp_2025_32",
            "irs_2026_news",
            "ssa_2026_factsheet_pdf",
            "ssa_2026_html",
            "ssa_cbb",
            "ssa_tax_rates",
            "irs_topic_751",
            "irs_topic_560",
        )
        if key in arts
    )
    years: dict[str, Any] = {}
    for year, text, irs_keys, ssa_keys in (
        (
            2024,
            text_2024,
            ("irs_rp_2023_34", "irs_irb_2023_48"),
            ("ssa_2024_factsheet", "ssa_cbb", "irs_pub15_2024", "irs_topic_751"),
        ),
        (
            2026,
            text_2026,
            ("irs_rp_2025_32", "irs_2026_news"),
            ("ssa_2026_factsheet_pdf", "ssa_2026_html", "ssa_cbb", "irs_topic_751"),
        ),
    ):
        std = parse_standard_deduction_single(text, year)
        brackets = parse_single_brackets(text, year)
        oasdi_cap = parse_oasdi_wage_base(text, year)
        oasdi_rate = parse_employee_oasdi_rate(text)
        hi_rate = parse_employee_medicare_rate(text)
        addl = parse_additional_medicare(text)
        if addl is None and (hi_rate is not None or oasdi_rate is not None):
            # Statutory IRC 3101(b)(2) is year-independent; record only when payroll docs exist.
            addl = {
                "applicable": True,
                "threshold": ADDITIONAL_MEDICARE_THRESHOLD_SINGLE,
                "rate": ADDITIONAL_MEDICARE_RATE,
                "authority": "IRC 3101(b)(2); SSA COLA fact sheet additional 0.9 percent",
                "from_payroll_text": False,
            }
        elif addl is not None:
            addl["authority"] = "SSA COLA fact sheet / IRC 3101(b)(2)"
            addl["from_payroll_text"] = True
        issues: list[str] = []
        if std is None:
            issues.append("STANDARD_DEDUCTION_UNPARSED")
        if not brackets:
            issues.append("BRACKETS_UNPARSED")
        if oasdi_cap is None:
            issues.append("OASDI_WAGE_BASE_UNPARSED")
        if oasdi_rate is None:
            issues.append("OASDI_RATE_UNPARSED")
        if hi_rate is None:
            issues.append("MEDICARE_RATE_UNPARSED")
        if addl is None:
            issues.append("ADDITIONAL_MEDICARE_UNPARSED")
        years[str(year)] = {
            "tax_year": year,
            "filing_status": "SINGLE",
            "standard_deduction": {
                "value": std,
                "authority": "IRS Rev. Proc. 2023-34" if year == 2024 else "IRS Rev. Proc. 2025-32",
                "source_artifact": list(irs_keys),
            },
            "income_tax_brackets": [
                {
                    "upper": None if c == float("inf") else c,
                    "rate": r,
                    "authority": "IRS Rev. Proc. 2023-34"
                    if year == 2024
                    else "IRS Rev. Proc. 2025-32",
                }
                for c, r in (brackets or [])
            ],
            "oasdi": {
                "employee_rate": oasdi_rate,
                "taxable_maximum": oasdi_cap,
                "authority": "IRS Topic 751 / Publication 15 (SSA pages 403 from this client)",
                "source_artifact": list(ssa_keys),
            },
            "medicare_hi": {
                "employee_rate": hi_rate,
                "taxable_maximum": None,
                "no_limit": True,
                "authority": "SSA / IRC 3101(b)(1)",
            },
            "additional_medicare_tax": addl
            or {
                "applicable": True,
                "threshold": None,
                "rate": None,
                "authority": None,
            },
            "issues": issues,
            "parsed_ok": not issues,
        }
    bound_artifacts = []
    for key, art in arts.items():
        bound_artifacts.append(
            {
                "key": key,
                "url": art.get("url"),
                "filename": art.get("filename"),
                "sha256": art.get("sha256"),
                "retrieved_at": art.get("retrieved_at"),
                "http_ok": art.get("http_ok"),
            }
        )
    payload = {
        "report_type": INVENTORY_REPORT_TYPE,
        "generated_at": _now_iso(),
        "filing_status": "SINGLE",
        "years": years,
        "retrieved_artifacts": bound_artifacts,
        "calculates_mslc": False,
        "headline_calculated": False,
    }
    return payload


def write_federal_tax_inventory(output_path: Path | None = None) -> dict[str, Any]:
    payload = build_federal_tax_inventory()
    dest = output_path or INVENTORY_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
