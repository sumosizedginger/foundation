"""Targeted live currentness for 2026 state-tax cells.

Evidence validity (cached SHA-bound inventory) is not currentness.
A 2026 cell is VERIFIED_CURRENT only when this module actually performs a
first-party check during the current freshness run.

Does not calculate an MSLC.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

STATUS_VERIFIED_CURRENT = "VERIFIED_CURRENT"
STATUS_CHECK_FAILED = "CHECK_FAILED"
STATUS_NEWER_AVAILABLE = "NEWER_AVAILABLE"
STATUS_PENDING = "CURRENTNESS_PENDING"
STATUS_HISTORICAL = "HISTORICAL_RULE_YEAR"

FetchFn = Callable[[str], dict[str, Any]]


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_fetch_currentness(url: str) -> dict[str, Any]:
    """GET one official currentness URL. Does not write inventory cache."""
    from foundation.living_cost.freshness_currentness import download_temp_bytes
    from foundation.living_cost.freshness_discovery import _BROWSER_HEADERS
    from foundation.sources.state_tax import _extract_pdf_text, _html_to_text

    suffix = ".pdf" if url.lower().endswith(".pdf") else ".html"
    try:
        tmp, digest = download_temp_bytes(url, headers=_BROWSER_HEADERS, suffix=suffix)
        try:
            if suffix == ".pdf":
                text = _extract_pdf_text(tmp)
            else:
                text = _html_to_text(tmp.read_text(encoding="utf-8", errors="replace"))
        finally:
            tmp.unlink(missing_ok=True)
        return {
            "ok": True,
            "url": url,
            "sha256": digest,
            "text": text,
            "retrieved_at": _now_iso(),
            "error": None,
            "live_checked": True,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("state-tax currentness GET failed for %s: %s", url, exc)
        return {
            "ok": False,
            "url": url,
            "sha256": None,
            "text": "",
            "retrieved_at": _now_iso(),
            "error": str(exc),
            "live_checked": True,
        }


def fetch_with_run_cache(
    url: str,
    *,
    cache: dict[str, dict[str, Any]],
    fetch_fn: FetchFn,
) -> dict[str, Any]:
    if url in cache:
        rec = dict(cache[url])
        rec["from_run_cache"] = True
        return rec
    rec = fetch_fn(url)
    rec["from_run_cache"] = False
    cache[url] = rec
    return rec


def parse_superseding_tax_year(text: str) -> dict[str, Any]:
    """Detect a newly described wage/personal income tax and its first year.

    A law effective in 2027 does not, by itself, change RULE_YEAR 2026.
    An undated new wage tax is fail-closed (not current).
    """
    from foundation.sources.state_tax import parse_future_income_tax, tax_applies_to_rule_year

    future = parse_future_income_tax(text)
    blob = re.sub(r"\s+", " ", text or "").lower()
    retro = bool(
        re.search(
            r"(effective|beginning|for)\s+(tax\s+year\s+)?2026|"
            r"retroactiv(?:e|ely).{0,40}2026|"
            r"applies to (?:the\s+)?2026",
            blob,
        )
    )
    return {
        "future": future,
        "applies_2026": tax_applies_to_rule_year(future, 2026),
        "applies_2027": tax_applies_to_rule_year(future, 2027),
        "mentions_2026_applicability": retro,
        "unknown_effective_year": bool(future.get("unknown_effective_year")),
    }


def assess_2026_currentness(
    *,
    state: str,
    cell: Mapping[str, Any],
    live: Mapping[str, Any] | None,
    live_check_performed: bool,
) -> dict[str, Any]:
    """Score one 2026 cell. Never promotes cache-only validity to VERIFIED_CURRENT."""
    evidence_valid = cell.get("parsed_ok") is True and bool(cell.get("tax_status"))
    base = {
        "state": state,
        "year": 2026,
        "evidence_valid": evidence_valid,
        "live_check_performed": bool(live_check_performed),
        "live_url": (live or {}).get("url"),
        "live_error": (live or {}).get("error"),
        "newer_data_exists": None,
        "currentness_status": STATUS_PENDING,
    }
    if not live_check_performed:
        base["currentness_status"] = STATUS_PENDING
        return base
    if not live or live.get("ok") is not True:
        base["currentness_status"] = STATUS_CHECK_FAILED
        base["newer_data_exists"] = None
        return base

    text = str(live.get("text") or "")
    if not text.strip():
        base["currentness_status"] = STATUS_CHECK_FAILED
        base["newer_data_exists"] = None
        return base

    from foundation.sources.state_tax import (
        STATUS_NO_WAGE_TAX,
        STATUS_TAXING,
        parse_no_wage_tax,
    )

    supersede = parse_superseding_tax_year(text)
    tax_status = cell.get("tax_status")

    if tax_status == STATUS_NO_WAGE_TAX:
        still_no_tax = parse_no_wage_tax(text, state, 2026)
        if supersede["applies_2026"] is True or (
            supersede["mentions_2026_applicability"] and not still_no_tax
        ):
            base["currentness_status"] = STATUS_NEWER_AVAILABLE
            base["newer_data_exists"] = True
            return base
        if supersede["unknown_effective_year"] and supersede["future"].get("tax_exists"):
            base["currentness_status"] = STATUS_CHECK_FAILED
            base["newer_data_exists"] = None
            return base
        # Law beginning 2027+ does not disturb 2026.
        if still_no_tax or (
            supersede["applies_2026"] is False and supersede["future"].get("tax_exists")
        ):
            if evidence_valid:
                base["currentness_status"] = STATUS_VERIFIED_CURRENT
                base["newer_data_exists"] = False
            else:
                base["currentness_status"] = STATUS_PENDING
            return base
        if not still_no_tax:
            base["currentness_status"] = STATUS_CHECK_FAILED
            base["newer_data_exists"] = None
            return base

    if tax_status == STATUS_TAXING and evidence_valid:
        official_rate = _cell_primary_rate(cell)
        live_rate = _extract_live_rate(text, official_rate)
        if official_rate is not None and live_rate is not None:
            if abs(float(official_rate) - float(live_rate)) > 1e-6:
                # Distinguish 2027+ change from 2026 change.
                if re.search(r"(beginning|effective|for)\s+(tax\s+year\s+)?2027", text.lower()):
                    base["currentness_status"] = STATUS_VERIFIED_CURRENT
                    base["newer_data_exists"] = False
                    return base
                base["currentness_status"] = STATUS_NEWER_AVAILABLE
                base["newer_data_exists"] = True
                return base
            base["currentness_status"] = STATUS_VERIFIED_CURRENT
            base["newer_data_exists"] = False
            return base
        if official_rate is not None and _rate_still_stated(text, official_rate):
            base["currentness_status"] = STATUS_VERIFIED_CURRENT
            base["newer_data_exists"] = False
            return base
        base["currentness_status"] = STATUS_CHECK_FAILED
        base["newer_data_exists"] = None
        return base

    base["currentness_status"] = STATUS_PENDING
    return base


def _cell_primary_rate(cell: Mapping[str, Any]) -> float | None:
    rates = cell.get("rates") or []
    if rates and isinstance(rates[0], (int, float)):
        return float(rates[0])
    brackets = cell.get("brackets") or []
    if brackets and isinstance(brackets[0], dict) and brackets[0].get("rate") is not None:
        try:
            return float(brackets[0]["rate"])
        except (TypeError, ValueError):
            return None
    return None


def _rate_still_stated(text: str, rate: float) -> bool:
    pct = rate * 100.0
    blob = re.sub(r"\s+", " ", text or "")
    # Accept 3.07, 3.07%, 4.95 percent, 0.0307.
    variants = {
        f"{pct:.2f}",
        f"{pct:.2f}%",
        f"{pct:g}",
        f"{pct:g} percent",
        f"{rate:.4f}",
    }
    low = blob.lower()
    return any(v.lower() in low for v in variants)


def _extract_live_rate(text: str, expected: float | None) -> float | None:
    if expected is None:
        return None
    if _rate_still_stated(text, expected):
        return expected
    return None


def currentness_surfaces() -> dict[str, dict[str, Any]]:
    """One targeted 2026 surface per jurisdiction. Shared URLs are run-cached."""
    from foundation.sources.state_tax import authority_catalog

    surfaces: dict[str, dict[str, Any]] = {}
    for spec in authority_catalog():
        if int(spec.get("year") or 0) != 2026:
            continue
        state = str(spec["state"])
        # Prefer wage-status / schedule artifacts already bound for 2026.
        if state not in surfaces:
            surfaces[state] = {
                "state": state,
                "url": spec["url"],
                "publisher": spec.get("publisher"),
                "role": spec.get("role"),
            }
    # Stronger current Texas surface than the 2016 Fiscal Notes article.
    surfaces["TX"] = {
        "state": "TX",
        "url": "https://statutes.capitol.texas.gov/Docs/CN/htm/CN.8.htm",
        "publisher": "Texas Constitution Art. 8 (statutes.capitol.texas.gov)",
        "role": "currentness",
    }
    # Washington: live-check the enacted 2026 session law (tax imposed 2028).
    surfaces["WA"] = {
        "state": "WA",
        "url": (
            "https://lawfilesext.leg.wa.gov/biennium/2025-26/Pdf/Bills/"
            "Session%20Laws/Senate/6346-S.sl.pdf"
        ),
        "publisher": "Washington State Legislature / ESSB 6346 Chapter 238",
        "role": "currentness",
    }
    return surfaces
