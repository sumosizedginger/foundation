"""NAIC Auto Insurance Database Report extraction.

Parses official PDF Table 5 Combined Average Premium. Does not calculate an MSLC.
OD-006 canonical measure is combined average premium, not average expenditure.
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

NAIC_LANDING = "https://content.naic.org/publications"
NAIC_NEWS_URL = (
    "https://content.naic.org/article/naic-releases-20222023-auto-insurance-database-report"
)
NAIC_REPORT_URL = (
    "https://content.naic.org/sites/default/files/publication-aut-pb-auto-insurance-database.pdf"
)
NAIC_EXPECTED_FILENAME = "publication-aut-pb-auto-insurance-database.pdf"
NAIC_REDISTRIBUTION_STATUS = "FREE_DOWNLOAD_REDISTRIBUTION_UNCONFIRMED"
NAIC_REPORT_TYPE = "living_cost_naic_auto_insurance"
CANONICAL_MEASURE = "combined_average_premium"
SENSITIVITY_MEASURE = "average_expenditure"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
NAIC_DERIVATION_PATH = METADATA_DIR / "living_cost_naic_auto_insurance.json"

US_STATE_NAMES: dict[str, str] = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}

NATIONAL_LABELS = ("Countrywide", "United States", "U.S.", "US")


def selected_naic_pdf_sha256(file_path: Path) -> str | None:
    """SHA-256 of the selected NAIC PDF bytes. Sidecar is not identity."""
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_pdf_text_by_page(file_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.error("pypdf is required to parse the NAIC Auto Insurance Database Report")
        return []
    try:
        reader = PdfReader(str(file_path))
    except (OSError, ValueError) as exc:
        logger.error("Failed to open NAIC PDF: %s", exc)
        return []
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001 — PDF extractors raise various types
            logger.warning("NAIC PDF page extract failed: %s", exc)
            pages.append("")
    return pages


def identify_naic_pdf(file_path: Path) -> dict[str, Any]:
    """Bind PDF text to a publication identifier. Missing file is unbound."""
    pages = extract_pdf_text_by_page(file_path) if file_path.is_file() else []
    head = "\n".join(pages[:6])
    blob = "\n".join(pages)
    title = None
    if re.search(r"Auto Insurance\s+Database Report", head, re.IGNORECASE):
        title = "Auto Insurance Database Report"
    years = re.search(
        r"(20\d{2})\s*/\s*(20\d{2})\s+Auto Insurance",
        head,
        re.IGNORECASE,
    )
    if years is None:
        years = re.search(r"(20\d{2})\s*/\s*(20\d{2})", head)
    start_year = int(years.group(1)) if years else None
    end_year = int(years.group(2)) if years else None
    has_naic = "national association of insurance commissioners" in blob[:8000].lower()
    identifier = None
    if start_year and end_year:
        identifier = f"AUT-PB {start_year}-{end_year}"
    return {
        "title": title,
        "start_year": start_year,
        "end_year": end_year,
        "publication_identifier": identifier,
        "has_naic_identity": has_naic,
        "page_count": len(pages),
    }


def _money_tokens(line: str) -> list[float]:
    values: list[float] = []
    for token in re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", line):
        values.append(float(token.replace(",", "")))
    return values


def parse_naic_named_state_table(
    pages: list[str],
    *,
    table_marker: str,
    column_marker: str,
    data_year: int,
) -> dict[str, Any]:
    """Parse a state-name + year-column table from extracted PDF pages."""
    page_hits: list[int] = []
    text_hits: list[str] = []
    for idx, page in enumerate(pages):
        low = page.lower()
        if table_marker.lower() in low and column_marker.lower() in low:
            page_hits.append(idx + 1)
            text_hits.append(page)
    if not text_hits:
        return {
            "ok": False,
            "reason": f"table not found: {table_marker} / {column_marker}",
            "pages": [],
            "jurisdictions": [],
            "national": None,
        }
    blob = "\n".join(text_hits)
    jurisdictions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name, alpha in US_STATE_NAMES.items():
        match = re.search(rf"{re.escape(name)}\s+((?:\d{{1,3}}(?:,\d{{3}})*\.\d{{2}}\s*)+)", blob)
        if not match:
            continue
        values = _money_tokens(match.group(1))
        if not values:
            continue
        value = values[0]
        if value <= 0:
            continue
        if alpha in seen:
            continue
        seen.add(alpha)
        jurisdictions.append(
            {
                "state": alpha,
                "state_name": name,
                "source_data_year": data_year,
                "value": round(value, 2),
            }
        )
    national = None
    for label in NATIONAL_LABELS:
        match = re.search(rf"{re.escape(label)}\s+((?:\d{{1,3}}(?:,\d{{3}})*\.\d{{2}}\s*)+)", blob)
        if not match:
            continue
        values = _money_tokens(match.group(1))
        if values and values[0] > 0:
            national = {
                "geography": "Countrywide",
                "source_data_year": data_year,
                "value": round(values[0], 2),
            }
            break
    return {
        "ok": bool(jurisdictions),
        "reason": None if jurisdictions else "no state rows parsed",
        "pages": page_hits,
        "table_title": table_marker,
        "column_name": column_marker,
        "jurisdictions": jurisdictions,
        "national": national,
    }


def parse_naic_combined_average_premium(
    file_path: Path,
    *,
    data_year: int | None = None,
) -> dict[str, Any]:
    identity = identify_naic_pdf(file_path)
    year = data_year if data_year is not None else identity.get("end_year")
    if not file_path.is_file() or year is None:
        return {
            "ok": False,
            "reason": "workbook missing or data year unknown",
            "identity": identity,
            "jurisdictions": [],
            "national": None,
        }
    pages = extract_pdf_text_by_page(file_path)
    parsed = parse_naic_named_state_table(
        pages,
        table_marker="Table 5",
        column_marker="Combined Average Premium",
        data_year=int(year),
    )
    expenditure = parse_naic_named_state_table(
        pages,
        table_marker="Table 4",
        column_marker="Average Expenditure",
        data_year=int(year),
    )
    parsed["identity"] = identity
    parsed["expenditure"] = expenditure
    parsed["data_year"] = int(year)
    return parsed


def parse_naic_news_national_premium(html: str) -> float | None:
    match = re.search(
        r"national combined average premium[^$]{0,80}\$([0-9,]+(?:\.[0-9]+)?)",
        html,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def write_naic_derivation_report(
    file_path: Path,
    *,
    publication_identifier: str,
    listing_identifier: str,
    selected_sha: str | None,
    retrieved_at: str | None,
    resolved_url: str,
    news_national: float | None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Write deterministic NAIC evidence artifact. Does not calculate an MSLC."""
    parsed = parse_naic_combined_average_premium(file_path)
    identity = parsed.get("identity") or {}
    data_year = parsed.get("data_year") or identity.get("end_year")
    jurisdictions = []
    for row in parsed.get("jurisdictions") or []:
        exp = None
        for item in (parsed.get("expenditure") or {}).get("jurisdictions") or []:
            if item.get("state") == row["state"]:
                exp = item.get("value")
                break
        jurisdictions.append(
            {
                "state": row["state"],
                "state_name": row["state_name"],
                "source_data_year": data_year,
                "combined_average_premium": row["value"],
                "average_expenditure": exp,
                "publication_identifier": publication_identifier,
                "source_artifact_sha256": selected_sha,
                "table_identity": {
                    "table_number": "Table 5",
                    "table_title": "Combined Average Premium, 2019-2023",
                    "column_name": "Combined Average Premium",
                    "pages": parsed.get("pages"),
                    "unit": "USD_PER_INSURED_VEHICLE",
                },
                "validation_status": "MEASURED",
            }
        )
    national = parsed.get("national")
    national_rec = None
    if isinstance(national, dict):
        national_rec = {
            "geography": "Countrywide",
            "source_data_year": data_year,
            "combined_average_premium": national.get("value"),
            "publication_identifier": publication_identifier,
            "source_artifact_sha256": selected_sha,
            "not_state_average": True,
        }
    issues: list[str] = []
    if selected_sha is None:
        issues.append("NAIC_SELECTED_PDF_MISSING")
    if not parsed.get("ok"):
        issues.append(f"NAIC_TABLE_PARSE:{parsed.get('reason')}")
    if identity.get("publication_identifier") != listing_identifier:
        issues.append("NAIC_PDF_IDENTIFIER_MISMATCH")
    if identity.get("publication_identifier") != publication_identifier:
        issues.append("NAIC_PUBLICATION_IDENTIFIER_MISMATCH")
    states = [j["state"] for j in jurisdictions]
    if len(states) != len(set(states)):
        issues.append("NAIC_DUPLICATE_STATES")
    expected = set(US_STATE_NAMES.values())
    if set(states) != expected:
        issues.append(f"NAIC_STATE_SET_INCOMPLETE:{sorted(expected - set(states))}")
    for row in jurisdictions:
        prem = row["combined_average_premium"]
        if not isinstance(prem, (int, float)) or prem <= 0:
            issues.append(f"NAIC_PREMIUM_INVALID:{row['state']}")
    if national_rec is None or not (national_rec.get("combined_average_premium") or 0) > 0:
        issues.append("NAIC_NATIONAL_ROW_MISSING")
    if news_national is not None and national_rec is not None:
        pdf_nat = float(national_rec["combined_average_premium"])
        if abs(round(pdf_nat) - round(news_national)) > 1:
            issues.append(f"NAIC_NATIONAL_RELEASE_MISMATCH:pdf={pdf_nat}:release={news_national}")
    ok = not issues
    payload = {
        "report_type": NAIC_REPORT_TYPE,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "publisher": "National Association of Insurance Commissioners",
        "report_title": identity.get("title") or "Auto Insurance Database Report",
        "publication_identifier": publication_identifier,
        "listing_identifier": listing_identifier,
        "data_year_range": {
            "start": identity.get("start_year"),
            "end": identity.get("end_year"),
        },
        "source_data_year": data_year,
        "canonical_measure": CANONICAL_MEASURE,
        "sensitivity_measure": SENSITIVITY_MEASURE,
        "landing_url": NAIC_LANDING,
        "resolved_url": resolved_url,
        "retrieved_at": retrieved_at,
        "sha256": selected_sha,
        "redistribution_status": NAIC_REDISTRIBUTION_STATUS,
        "table_identity": {
            "table_number": "Table 5",
            "table_title": "Combined Average Premium",
            "column_name": "Combined Average Premium",
            "pages": parsed.get("pages"),
            "unit": "USD_PER_INSURED_VEHICLE",
            "data_year": data_year,
        },
        "jurisdiction_count": len(jurisdictions),
        "jurisdictions": jurisdictions,
        "national": national_rec,
        "official_release_national_combined_average_premium": news_national,
        "pdf_identifier_bound": identity.get("publication_identifier") == listing_identifier,
        "validation_ok": ok,
        "issues": issues,
        "evidence_status": "VALIDATED" if ok else "RETRIEVED_UNVALIDATED",
        "calculates_mslc": False,
        "headline_calculated": False,
    }
    dest = output_path or NAIC_DERIVATION_PATH
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
