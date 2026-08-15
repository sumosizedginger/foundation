"""Listing vs artifact currentness helpers.

Does not calculate or publish an MSLC. These functions decide whether a
stable URL's current official bytes/period still match the selected local
artifact. Fail closed when currentness cannot be established.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

MONTH_ORDER = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
MONTH_INDEX = {name.lower(): i for i, name in enumerate(MONTH_ORDER, start=1)}
MONTH_INDEX.update(
    {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "sept": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
)


def month_tuple(year: int, month: int) -> tuple[int, int]:
    return (int(year), int(month))


def parse_month_token(token: str) -> int | None:
    key = token.strip().lower().replace(".", "")
    return MONTH_INDEX.get(key)


def parse_usda_latest_report_month(html: str) -> tuple[int, int] | None:
    """Return (year, month) of the newest official monthly Cost of Food report.

    Uses explicit report filenames and report titles. Does not treat a generic
    "page updated" date as a food-plan month.
    """
    found: list[tuple[int, int]] = []
    for match in re.finditer(
        r"cnpp-costfood-3levels-([a-z]+)(20\d{2})",
        html,
        re.IGNORECASE,
    ):
        month = parse_month_token(match.group(1))
        if month:
            found.append((int(match.group(2)), month))
    for match in re.finditer(
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|"
        r"Oct|Nov|Dec)\s+(20\d{2})\s+(?:Cost of Food|Monthly Cost of Food)",
        html,
        re.IGNORECASE,
    ):
        month = parse_month_token(match.group(1))
        if month:
            found.append((int(match.group(2)), month))
    for match in re.finditer(
        r"(?:Cost of Food|Monthly Cost of Food Report)\D{0,40}"
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(20\d{2})",
        html,
        re.IGNORECASE,
    ):
        month = parse_month_token(match.group(1))
        if month:
            found.append((int(match.group(2)), month))
    return max(found) if found else None


def latest_month_from_names(year: int, months: list[str]) -> tuple[int, int] | None:
    indexes = [MONTH_INDEX[name.lower()] for name in months if name.lower() in MONTH_INDEX]
    if not indexes:
        return None
    return (year, max(indexes))


def usda_currentness_status(
    *,
    official_latest: tuple[int, int] | None,
    selected_latest: tuple[int, int] | None,
    official_sha: str | None,
    selected_sha: str | None,
) -> dict[str, Any]:
    """Compare official USDA workbook currentness to the selected local artifact."""
    if official_latest is None or selected_latest is None:
        return {
            "listing_freshness_status": "CHECK_FAILED"
            if official_latest is None
            else "VERIFIED_CURRENT",
            "artifact_currentness_status": "CHECK_FAILED",
            "selected_artifact_matches_latest": None,
            "freshness_check_status": "CHECK_FAILED",
            "newer_data_exists": None,
            "reason": (
                "USDA currentness could not be established: official latest month "
                f"={official_latest!r}, selected latest month={selected_latest!r}."
            ),
        }
    listing_status = "NEWER_AVAILABLE" if official_latest > selected_latest else "VERIFIED_CURRENT"
    hash_mismatch = bool(official_sha and selected_sha and official_sha != selected_sha)
    bytes_unknown = not official_sha or not selected_sha
    if official_latest > selected_latest:
        return {
            "listing_freshness_status": listing_status,
            "artifact_currentness_status": "NEWER_AVAILABLE",
            "selected_artifact_matches_latest": False,
            "freshness_check_status": "NEWER_AVAILABLE",
            "newer_data_exists": True,
            "reason": (
                f"Official latest USDA month {official_latest} is newer than "
                f"selected workbook month {selected_latest}."
            ),
        }
    if hash_mismatch:
        return {
            "listing_freshness_status": listing_status,
            "artifact_currentness_status": "NEWER_AVAILABLE",
            "selected_artifact_matches_latest": False,
            "freshness_check_status": "NEWER_AVAILABLE",
            "newer_data_exists": True,
            "reason": (
                "USDA archive URL is stable but official workbook bytes no longer "
                "match the selected local hash."
            ),
        }
    if bytes_unknown:
        return {
            "listing_freshness_status": listing_status,
            "artifact_currentness_status": "CHECK_FAILED",
            "selected_artifact_matches_latest": None,
            "freshness_check_status": "CHECK_FAILED",
            "newer_data_exists": None,
            "reason": (
                "USDA official latest month matches selected month, but artifact "
                "byte currentness was not established."
            ),
        }
    return {
        "listing_freshness_status": "VERIFIED_CURRENT",
        "artifact_currentness_status": "VERIFIED_CURRENT",
        "selected_artifact_matches_latest": True,
        "freshness_check_status": "VERIFIED_CURRENT",
        "newer_data_exists": False,
        "reason": (
            f"Official latest USDA month {official_latest} matches selected "
            "workbook month and official bytes match the selected hash."
        ),
    }


def eia_currentness_status(
    *,
    official_max_date: date | None,
    selected_max_date: date | None,
    official_sha: str | None = None,
    selected_sha: str | None = None,
) -> dict[str, Any]:
    """Compare EIA workbook max observation date to the selected local series."""
    if official_max_date is None or selected_max_date is None:
        return {
            "listing_freshness_status": "CHECK_FAILED"
            if official_max_date is None
            else "VERIFIED_CURRENT",
            "artifact_currentness_status": "CHECK_FAILED",
            "selected_artifact_matches_latest": None,
            "freshness_check_status": "CHECK_FAILED",
            "newer_data_exists": None,
            "reason": (
                "EIA observation currentness could not be established: official "
                f"max={official_max_date!r}, selected max={selected_max_date!r}."
            ),
        }
    if official_max_date > selected_max_date:
        return {
            "listing_freshness_status": "NEWER_AVAILABLE",
            "artifact_currentness_status": "NEWER_AVAILABLE",
            "selected_artifact_matches_latest": False,
            "freshness_check_status": "NEWER_AVAILABLE",
            "newer_data_exists": True,
            "reason": (
                f"Official EIA workbook latest observation {official_max_date.isoformat()} "
                f"is newer than selected {selected_max_date.isoformat()}."
            ),
        }
    if official_sha and selected_sha and official_sha != selected_sha:
        return {
            "listing_freshness_status": "VERIFIED_CURRENT",
            "artifact_currentness_status": "NEWER_AVAILABLE",
            "selected_artifact_matches_latest": False,
            "freshness_check_status": "NEWER_AVAILABLE",
            "newer_data_exists": True,
            "reason": "EIA pswrgvwall.xls URL is stable but official bytes changed.",
        }
    if not official_sha or not selected_sha:
        return {
            "listing_freshness_status": "VERIFIED_CURRENT",
            "artifact_currentness_status": "CHECK_FAILED",
            "selected_artifact_matches_latest": None,
            "freshness_check_status": "CHECK_FAILED",
            "newer_data_exists": None,
            "reason": (
                "EIA max observation dates match, but artifact byte currentness "
                "was not established."
            ),
        }
    return {
        "listing_freshness_status": "VERIFIED_CURRENT",
        "artifact_currentness_status": "VERIFIED_CURRENT",
        "selected_artifact_matches_latest": True,
        "freshness_check_status": "VERIFIED_CURRENT",
        "newer_data_exists": False,
        "reason": (
            f"Official EIA latest observation {official_max_date.isoformat()} matches "
            "the selected artifact and hashes match."
        ),
    }


def mutable_artifact_status(
    *,
    listing_ok: bool,
    official_sha: str | None,
    selected_sha: str | None,
    official_identifier: str | None = None,
    selected_identifier: str | None = None,
) -> dict[str, Any]:
    """Currentness for a stable URL whose contents may change."""
    if not listing_ok:
        return {
            "listing_freshness_status": "CHECK_FAILED",
            "artifact_currentness_status": "CHECK_FAILED",
            "selected_artifact_matches_latest": None,
            "freshness_check_status": "CHECK_FAILED",
            "newer_data_exists": None,
            "reason": "Authoritative listing/source currentness was not established.",
        }
    if official_identifier and selected_identifier and official_identifier != selected_identifier:
        return {
            "listing_freshness_status": "NEWER_AVAILABLE",
            "artifact_currentness_status": "NEWER_AVAILABLE",
            "selected_artifact_matches_latest": False,
            "freshness_check_status": "NEWER_AVAILABLE",
            "newer_data_exists": True,
            "reason": (
                f"Official identifier {official_identifier!r} does not match selected "
                f"{selected_identifier!r}."
            ),
        }
    if official_sha and selected_sha and official_sha != selected_sha:
        return {
            "listing_freshness_status": "VERIFIED_CURRENT",
            "artifact_currentness_status": "NEWER_AVAILABLE",
            "selected_artifact_matches_latest": False,
            "freshness_check_status": "NEWER_AVAILABLE",
            "newer_data_exists": True,
            "reason": "Stable official URL contents no longer match the selected local bytes.",
        }
    if not official_sha or not selected_sha:
        return {
            "listing_freshness_status": "VERIFIED_CURRENT",
            "artifact_currentness_status": "CHECK_FAILED",
            "selected_artifact_matches_latest": None,
            "freshness_check_status": "CHECK_FAILED",
            "newer_data_exists": None,
            "reason": (
                "Listing is current but selected artifact bytes were not proven to "
                "match the currently advertised official release."
            ),
        }
    return {
        "listing_freshness_status": "VERIFIED_CURRENT",
        "artifact_currentness_status": "VERIFIED_CURRENT",
        "selected_artifact_matches_latest": True,
        "freshness_check_status": "VERIFIED_CURRENT",
        "newer_data_exists": False,
        "reason": "Listing is current and selected local bytes match the official artifact.",
    }


@dataclass(frozen=True)
class NaicReportIdentifier:
    publication_code: str | None
    start_year: int
    end_year: int
    display_identifier: str


def parse_naic_report_identifiers(html: str) -> list[NaicReportIdentifier]:
    """Parse every Auto Insurance Database Report year range on a listing page."""
    found: dict[tuple[int, int], NaicReportIdentifier] = {}

    def _add(start: int, end: int, code: str | None) -> None:
        if end < start:
            start, end = end, start
        key = (start, end)
        display = f"{code} {start}-{end}" if code else f"{start}-{end}"
        prev = found.get(key)
        if prev is None or (code and not prev.publication_code):
            found[key] = NaicReportIdentifier(
                publication_code=code,
                start_year=start,
                end_year=end,
                display_identifier=display,
            )

    for match in re.finditer(
        r"(AUT-PB)\s+(20\d{2})\s*[–\-/]\s*(20\d{2})",
        html,
        re.IGNORECASE,
    ):
        _add(int(match.group(2)), int(match.group(3)), match.group(1).upper())
    for match in re.finditer(
        r"(20\d{2})\s*[–/]\s*(20\d{2})\s+Auto Insurance Database Report",
        html,
        re.IGNORECASE,
    ):
        _add(int(match.group(1)), int(match.group(2)), "AUT-PB")
    for match in re.finditer(
        r"Auto Insurance Database Report[^.<]{0,80}?(20\d{2})\s*[–\-/]\s*(20\d{2})",
        html,
        re.IGNORECASE,
    ):
        _add(int(match.group(1)), int(match.group(2)), "AUT-PB")
    for match in re.finditer(
        r"(20\d{2})\s*-\s*(20\d{2})\s+Auto Insurance Database",
        html,
        re.IGNORECASE,
    ):
        _add(int(match.group(1)), int(match.group(2)), "AUT-PB")
    return sorted(found.values(), key=lambda item: (item.end_year, item.start_year))


def select_latest_naic_report(reports: list[NaicReportIdentifier]) -> NaicReportIdentifier | None:
    if not reports:
        return None
    return max(reports, key=lambda item: (item.end_year, item.start_year))


def parse_naic_report_identifier(html: str) -> str | None:
    """Return the latest structured display identifier, or None if no year range."""
    latest = select_latest_naic_report(parse_naic_report_identifiers(html))
    return None if latest is None else latest.display_identifier


def local_pdf_matches_naic(path: Path, report: NaicReportIdentifier) -> bool | None:
    """Best-effort bind of a retrieved PDF to a discovered NAIC vintage."""
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()[:800_000]
    except OSError:
        return None
    text = raw.decode("latin-1", errors="ignore")
    needles = (
        report.display_identifier,
        f"{report.start_year}-{report.end_year}",
        f"{report.start_year}/{report.end_year}",
        f"{report.start_year}–{report.end_year}",
    )
    if any(needle.lower() in text.lower() for needle in needles if needle):
        return True
    if "auto insurance database" not in text.lower():
        return None
    return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_remote_bytes(
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[float, float] = (12.0, 60.0),
    max_bytes: int = 40_000_000,
) -> dict[str, Any]:
    """GET official bytes to a temp file, hash them, delete the temp file.

    Does not write into the project cache.
    """
    import requests

    response = requests.get(
        url,
        timeout=timeout,
        headers=headers,
        allow_redirects=True,
        stream=True,
    )
    response.raise_for_status()
    digest = hashlib.sha256()
    total = 0
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise RuntimeError(f"remote artifact exceeded {max_bytes} bytes: {url}")
        digest.update(chunk)
    return {
        "sha256": digest.hexdigest(),
        "bytes": total,
        "url": url,
        "content_type": response.headers.get("Content-Type"),
        "last_modified": response.headers.get("Last-Modified"),
        "content_length": response.headers.get("Content-Length"),
    }


def download_temp_bytes(
    url: str,
    *,
    headers: dict[str, str],
    timeout: tuple[float, float] = (12.0, 60.0),
    max_bytes: int = 40_000_000,
    suffix: str = "",
) -> tuple[Path, str]:
    """Download official bytes to a caller-owned temp file. Does not touch cache."""
    import requests

    response = requests.get(
        url,
        timeout=timeout,
        headers=headers,
        allow_redirects=True,
        stream=True,
    )
    response.raise_for_status()
    digest = hashlib.sha256()
    total = 0
    handle, name = tempfile.mkstemp(suffix=suffix)
    path = Path(name)
    try:
        with os.fdopen(handle, "wb") as tmp:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise RuntimeError(f"remote artifact exceeded {max_bytes} bytes: {url}")
                tmp.write(chunk)
                digest.update(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path, digest.hexdigest()
