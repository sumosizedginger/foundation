"""Targeted live currentness for 2026 state-tax cells.

Evidence validity (cached SHA-bound inventory) is not currentness.
A 2026 cell is VERIFIED_CURRENT only when this module actually performs a
first-party check during the current freshness run.

Taxing cells require live official schedule extraction compared against every
material modeled field. A rate token appearing somewhere on a page is not
currentness.

Does not calculate an MSLC.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping, Sequence
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


def currentness_urls_for_cell(
    state: str,
    cell: Mapping[str, Any],
    surfaces: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Targeted URLs for one 2026 cell. Shared URLs are run-cached by the caller.

    No-tax cells use the single currentness surface. Taxing cells also include
    every bound official authority so live extraction can see all modeled fields.
    """
    from foundation.sources.state_tax import STATUS_TAXING

    urls: list[str] = []
    seen: set[str] = set()

    def _add(url: object) -> None:
        text = str(url or "").strip()
        if text and text not in seen:
            seen.add(text)
            urls.append(text)

    _add((surfaces.get(state) or {}).get("url"))
    if cell.get("tax_status") == STATUS_TAXING:
        for auth in cell.get("official_authorities") or []:
            if isinstance(auth, dict):
                _add(auth.get("url"))
    return urls


def collect_live_authority_text(
    urls: Sequence[str],
    *,
    cache: dict[str, dict[str, Any]],
    fetch_fn: FetchFn,
) -> dict[str, Any]:
    """GET each URL (run-cached). Fail closed if any targeted GET fails."""
    if not urls:
        return {
            "ok": False,
            "url": None,
            "sha256": None,
            "text": "",
            "retrieved_at": _now_iso(),
            "error": "no currentness URL",
            "live_checked": True,
        }
    texts: list[str] = []
    last_ok: dict[str, Any] | None = None
    for url in urls:
        rec = fetch_with_run_cache(url, cache=cache, fetch_fn=fetch_fn)
        if rec.get("ok") is not True:
            failed = dict(rec)
            failed["ok"] = False
            failed["url"] = url
            return failed
        texts.append(str(rec.get("text") or ""))
        last_ok = rec
    combined = "\n".join(texts)
    if not combined.strip():
        return {
            "ok": False,
            "url": urls[-1],
            "sha256": None,
            "text": "",
            "retrieved_at": _now_iso(),
            "error": "empty live currentness text",
            "live_checked": True,
        }
    out = dict(last_ok or {})
    out["ok"] = True
    out["url"] = urls[0]
    out["text"] = combined
    out["live_checked"] = True
    out["error"] = None
    return out


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


def _field_numeric(field: Any) -> float | None:
    if field is None:
        return None
    if isinstance(field, dict):
        value = field.get("value")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if isinstance(field, (int, float)):
        return float(field)
    return None


def _norm_brackets(brackets: Any) -> list[tuple[float | None, float]] | None:
    if not brackets:
        return None
    out: list[tuple[float | None, float]] = []
    for item in brackets:
        cap: Any
        rate: Any
        if isinstance(item, dict):
            cap = item.get("upper")
            rate = item.get("rate")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            cap, rate = item[0], item[1]
        else:
            return None
        try:
            rate_f = float(rate)
        except (TypeError, ValueError):
            return None
        if cap in (None, float("inf")):
            cap_f: float | None = None
        else:
            try:
                cap_f = float(cap)
            except (TypeError, ValueError):
                return None
        out.append((cap_f, rate_f))
    return out


def modeled_schedule_from_cell(cell: Mapping[str, Any]) -> dict[str, Any]:
    """Material modeled fields that live currentness must re-establish."""
    return {
        "deduction": _field_numeric(cell.get("standard_deduction")),
        "has_deduction": cell.get("standard_deduction") is not None,
        "personal_exemption": _field_numeric(cell.get("personal_exemption")),
        "has_exemption": cell.get("personal_exemption") is not None,
        "brackets": _norm_brackets(cell.get("brackets")),
    }


def compare_live_schedule_to_cell(
    cell: Mapping[str, Any],
    live_extracted: Mapping[str, Any] | None,
) -> str:
    """Return 'match', 'differ', or 'incomplete'.

    Compares every material field that exists on the stored cell. A live
    extraction that cannot re-establish those fields is incomplete, not current.
    """
    if not live_extracted:
        return "incomplete"
    if live_extracted.get("complete") is not True:
        return "incomplete"
    stored = modeled_schedule_from_cell(cell)
    if stored["has_deduction"]:
        live_ded = live_extracted.get("deduction")
        if live_ded is None:
            return "incomplete"
        try:
            if abs(float(live_ded) - float(stored["deduction"])) > 1e-6:
                return "differ"
        except (TypeError, ValueError):
            return "incomplete"
    if stored["has_exemption"]:
        live_ex = live_extracted.get("personal_exemption")
        if live_ex is None:
            return "incomplete"
        try:
            if abs(float(live_ex) - float(stored["personal_exemption"])) > 1e-6:
                return "differ"
        except (TypeError, ValueError):
            return "incomplete"
    stored_br = stored["brackets"]
    if stored_br:
        live_br = _norm_brackets(live_extracted.get("brackets"))
        if not live_br:
            return "incomplete"
        if len(live_br) != len(stored_br):
            return "differ"
        for (live_cap, live_rate), (stored_cap, stored_rate) in zip(
            live_br, stored_br, strict=True
        ):
            if live_cap != stored_cap:
                return "differ"
            if abs(live_rate - stored_rate) > 1e-6:
                return "differ"
    elif not stored["has_deduction"] and not stored["has_exemption"]:
        return "incomplete"
    return "match"


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
        "schedule_compare": None,
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
        from foundation.sources.state_tax_schedules import extract_official_schedule

        live_extracted = extract_official_schedule(state, 2026, text)
        comparison = compare_live_schedule_to_cell(cell, live_extracted)
        base["schedule_compare"] = comparison
        if comparison == "match":
            # A clearly future 2027+ change does not invalidate a proven 2026 schedule.
            base["currentness_status"] = STATUS_VERIFIED_CURRENT
            base["newer_data_exists"] = False
            return base
        if comparison == "differ":
            base["currentness_status"] = STATUS_NEWER_AVAILABLE
            base["newer_data_exists"] = True
            return base
        base["currentness_status"] = STATUS_CHECK_FAILED
        base["newer_data_exists"] = None
        return base

    base["currentness_status"] = STATUS_PENDING
    return base


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
