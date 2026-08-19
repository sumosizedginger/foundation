"""Official SINGLE wage-earner state-tax schedule extraction.

Values come only from bound official artifact text. Candidate
STATE_STATUTORY_SCHEDULES are never copied into evidence.
Does not calculate an MSLC.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

INF = float("inf")


def _blob(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").lower()


def _pct(num: str) -> float:
    return round(float(num) / 100.0, 6)


def extract_official_schedule(state: str, year: int, text: str) -> dict[str, Any] | None:
    """Return an official schedule dict or None if the artifact does not parse."""
    if not (text or "").strip():
        return None
    fn = {
        "PA": _extract_pa,
        "IL": _extract_il,
        "NC": _extract_nc,
        "AZ": _extract_az,
        "IN": _extract_in,
        "KY": _extract_ky,
        "MI": _extract_mi,
        "UT": _extract_ut,
        "IA": _extract_ia,
        "GA": _extract_ga,
        "CO": _extract_co,
        "ID": _extract_id,
        "MS": _extract_ms,
        "OH": _extract_oh,
    }.get(state.upper())
    if fn is None:
        return None
    return fn(text, int(year))


def _complete_flat(
    *,
    rate: float,
    deduction: float,
    personal_exemption: float | None = None,
    starting_income_base: str,
    year_ok: bool,
    notes: str = "",
) -> dict[str, Any] | None:
    if not year_ok or rate is None:
        return None
    rec: dict[str, Any] = {
        "deduction": float(deduction),
        "personal_exemption": None if personal_exemption is None else float(personal_exemption),
        "brackets": [(INF, float(rate))],
        "starting_income_base": starting_income_base,
        "complete": True,
        "notes": notes,
    }
    return rec


def _extract_pa(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    rate_ok = (
        "3.07%" in blob
        or "3.07 percent" in blob
        or "rate of 3.07" in blob
        or re.search(r"\b3\.07\s*%", blob) is not None
    )
    if not rate_ok:
        return None
    historic = bool(re.search(r"2004\s*[–—\-]\s*present", blob))
    if year == 2026:
        year_ok = historic or "levied at the rate of 3.07" in blob
    elif year == 2024:
        year_ok = historic or "2024" in blob or "tax year 2024" in blob
    else:
        year_ok = False
    if not year_ok:
        return None
    return _complete_flat(
        rate=0.0307,
        deduction=0.0,
        personal_exemption=0.0,
        starting_income_base="Pennsylvania taxable income (no standard deduction)",
        year_ok=True,
        notes="PA PIT is a flat statutory rate with no standard deduction.",
    )


def _extract_il(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    rate_ok = "4.95 percent" in blob or "4.95%" in blob
    if not rate_ok:
        return None
    # A 2025 IL-1040 booklet mentions April 15, 2026 as a due date. That is not
    # tax-year 2026 identity for the exemption amount.
    exemption = None
    if year == 2024:
        if re.search(
            r"(?:personal )?exemption(?: allowance)?(?: amount)?(?: for tax year 2024)?(?: is| of|:)?\s*\$?\s*2,?775",
            blob,
        ) or ("2,775" in blob and "exemption" in blob and "2024" in blob):
            exemption = 2775.0
    elif year == 2026:
        m = re.search(
            r"personal exemption amount for tax year 2026 is \$?([0-9,]+)",
            blob,
        )
        if m:
            exemption = float(m.group(1).replace(",", ""))
    rate_year_ok = (year == 2024 and "2024" in blob) or (
        year == 2026 and ("effective july 1, 2017" in blob or "2026 form il-1040" in blob)
    )
    if not rate_year_ok:
        return None
    if exemption is None:
        return {
            "deduction": None,
            "personal_exemption": None,
            "brackets": [(INF, 0.0495)],
            "starting_income_base": "Illinois net income",
            "complete": False,
            "notes": "Rate parsed; personal exemption not found on this artifact.",
        }
    return _complete_flat(
        rate=0.0495,
        deduction=0.0,
        personal_exemption=exemption,
        starting_income_base="Illinois net income after personal exemption",
        year_ok=True,
    )


def _extract_nc(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    rate = None
    if year == 2024:
        if re.search(r"in 2024\s+4\.5\s*%", blob) or re.search(
            r"tax year 2024.{0,80}4\.50?\s*%", blob
        ):
            rate = 0.045
    elif year == 2026:
        # G.S. 105-153.7: After 2025 3.99% unless a later trigger applies (2027+).
        if re.search(r"after 2025\s+3\.99\s*%", blob) or re.search(
            r"tax year 2026.{0,80}3\.99\s*%", blob
        ):
            rate = 0.0399
        m2 = re.search(r"in 2026\s+([0-9.]+)\s*%", blob)
        if m2:
            rate = _pct(m2.group(1))
    # Standard deduction is not in G.S. 105-153.7. Require year identity on
    # the same artifact as $12,750 (do not use a 2025 landing as 2026 proof).
    deduction = None
    has_amount = bool(re.search(r"12,?750", blob)) and bool(
        re.search(
            r"single.{0,120}12,?750|12,?750.{0,120}single|standard deduction.{0,80}12,?750",
            blob,
        )
    )
    if year == 2024 and has_amount and re.search(r"tax year 2024|2024 d-400|\b2024\b", blob):
        if "tax year 2025" in blob and "tax year 2024" not in blob and "2024" not in blob[:400]:
            has_amount = False
        if has_amount:
            deduction = 12750.0
    elif year == 2026 and has_amount and re.search(r"tax year 2026|for tax year 2026", blob):
        deduction = 12750.0
    if rate is None and deduction is None:
        return None
    return {
        "deduction": deduction,
        "personal_exemption": None,
        "brackets": [(INF, rate)] if rate is not None else None,
        "starting_income_base": "North Carolina taxable income",
        "complete": rate is not None and deduction is not None,
        "notes": (
            "Statutory rate parsed; standard deduction not on this artifact."
            if rate is not None and deduction is None
            else (
                "Standard deduction parsed; statutory rate not on this artifact."
                if deduction is not None and rate is None
                else ""
            )
        ),
    }


def _extract_az(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    # A.R.S. 43-1041 $12,200 is the unindexed base, not the modeled year amount.
    # Year-specific Form 140 booklet amounts are required. A 2025 booklet is
    # not 2026 authority.
    year_booklet = bool(
        re.search(rf"{year} arizona standard deduction", blob)
        or re.search(rf"{year} new tax rate of 2\.5", blob)
        or (re.search(rf"{year} form 140", blob) and f"{year} arizona" in blob)
    )
    rate_ok = bool(
        re.search(r"2\.5\s*%", blob)
        or "2.5 percent" in blob
        or "two and one-half percent" in blob
        or "multiply line 45 by 2.5%" in blob
        or "new tax rate of 2.5%" in blob
    )
    if not rate_ok:
        return None
    historical_brackets = "2.59%" in blob and "2.5%" not in blob and "2.5 percent" not in blob
    if historical_brackets and not year_booklet:
        return None
    deduction = None
    if (
        year == 2024
        and year_booklet
        and (
            re.search(r"\$?\s*14,?600 for a single", blob)
            or re.search(r"single \$\s*14,?600", blob)
        )
    ):
        deduction = 14600.0
    elif year == 2026 and "2026 arizona standard deduction" in blob:
        m = re.search(r"2026 arizona standard deduction.{0,200}single \$\s*([0-9,]+)", blob)
        if m:
            deduction = float(m.group(1).replace(",", ""))
        else:
            m = re.search(
                r"the 2026 arizona standard deduction amounts are:.{0,120}\$?\s*([0-9,]+) for a single",
                blob,
            )
            if m:
                deduction = float(m.group(1).replace(",", ""))
    if deduction is None:
        return {
            "deduction": None,
            "personal_exemption": None,
            "brackets": [(INF, 0.025)],
            "starting_income_base": "Arizona taxable income",
            "complete": False,
            "notes": "Flat rate parsed; Arizona year-specific standard deduction not on this artifact.",
        }
    return _complete_flat(
        rate=0.025,
        deduction=deduction,
        personal_exemption=0.0,
        starting_income_base="Arizona taxable income after standard deduction",
        year_ok=True,
        notes=(
            "Arizona Form 140 single standard deduction; no taxpayer personal "
            "exemption subtracted from income."
        ),
    )


def _extract_in(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    rate = None
    # Official DOR Schedule EZ / IC 6-3-2-1 window table. Do not take the first
    # percentage on a page that lists 2023–2027 rates.
    if year == 2024 and (
        re.search(
            r"after dec(?:ember)?\.?\s*31,?\s*2023.{0,80}before jan(?:uary)?\.?\s*1,?\s*2025.{0,40}3\.05",
            blob,
        )
        or re.search(r"3\.05%\s*\(\.0305\)", blob)
    ):
        rate = 0.0305
    elif year == 2026 and (
        re.search(
            r"after dec(?:ember)?\.?\s*31,?\s*2025.{0,80}before jan(?:uary)?\.?\s*1,?\s*2027.{0,40}2\.95",
            blob,
        )
        or re.search(r"calendar year 2026.{0,40}2\.95", blob)
    ):
        rate = 0.0295
    if rate is None:
        return None
    exemption = None
    if (
        year == 2024
        and (
            re.search(r"indiana allows a \$1,000 exemption for you", blob)
            or re.search(r"\$1,000 personal exemption", blob)
        )
    ) or (
        year == 2026
        and (
            re.search(r"tax year 2026.{0,80}\$1,000 exemption for you", blob)
            or re.search(r"2026 it-40.{0,200}\$1,000 exemption for you", blob)
            or re.search(r"2026.{0,40}\$1,000 personal exemption", blob)
        )
    ):
        exemption = 1000.0
    if exemption is None:
        return {
            "deduction": None,
            "personal_exemption": None,
            "brackets": [(INF, rate)],
            "starting_income_base": "Indiana adjusted gross income",
            "complete": False,
            "notes": "State AGI tax rate parsed; personal exemption not on this artifact. County tax is not included.",
        }
    return _complete_flat(
        rate=rate,
        deduction=0.0,
        personal_exemption=exemption,
        starting_income_base="Indiana adjusted gross income after personal exemption",
        year_ok=True,
        notes="Indiana state AGI tax only; county/local income tax is a separate family.",
    )


def _extract_ky(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    rate = None
    # KRS 141.020 year windows. A page with 4.5%, 4%, and 3.5% must not let
    # the first token win.
    if year == 2024 and re.search(
        r"beginning on or after january 1, 2024, but before january 1, 2026, "
        r"the tax shall be four percent \(4%\)",
        blob,
    ):
        rate = 0.04
    elif year == 2026 and re.search(
        r"beginning on or after january 1, 2026, the tax shall be three and "
        r"one-half percent \(3\.5%\)",
        blob,
    ):
        rate = 0.035
    if rate is None:
        return None
    deduction = None
    if year == 2024:
        m = re.search(
            r"(?:for 2024|tax year 2024|2024.{0,40}).{0,40}standard deduction is \$?([0-9,]+)",
            blob,
        )
        if m:
            deduction = float(m.group(1).replace(",", ""))
    elif year == 2026:
        m = re.search(
            r"(?:for 2026|tax year 2026|2026.{0,40}).{0,40}standard deduction is \$?([0-9,]+)",
            blob,
        )
        if m:
            deduction = float(m.group(1).replace(",", ""))
    if deduction is None:
        return {
            "deduction": None,
            "personal_exemption": None,
            "brackets": [(INF, rate)],
            "starting_income_base": "Kentucky net income",
            "complete": False,
            "notes": "Statutory rate parsed; year-specific standard deduction not on this artifact.",
        }
    return _complete_flat(
        rate=rate,
        deduction=deduction,
        personal_exemption=0.0,
        starting_income_base="Kentucky net income after standard deduction",
        year_ok=True,
    )


def _extract_mi(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    rate = None
    exemption = None
    # MCL 206.51 and instructions contain both 4.25% and 4.05% trigger language.
    # Select only the rate legally identified for the requested tax year.
    if year == 2024:
        if re.search(r"income tax rate for 2024 is 4\.25", blob) or re.search(
            r"for tax year 2024, the michigan income tax rate is 4\.25", blob
        ):
            rate = 0.0425
        if re.search(
            r"for tax year 2024, the personal and stillbirth exemption allowances are \$5,?600",
            blob,
        ) or re.search(r"exemption allowance of \$5,?600", blob):
            exemption = 5600.0
    elif year == 2026:
        m_rate = re.search(r"income tax rate for 2026 is ([0-9.]+)", blob)
        if m_rate:
            rate = _pct(m_rate.group(1))
        m_ex = re.search(
            r"for tax year 2026, the personal(?: and stillbirth)? exemption allowances are \$([0-9,]+)",
            blob,
        )
        if m_ex:
            exemption = float(m_ex.group(1).replace(",", ""))
    if rate is None:
        return None
    if exemption is None:
        return {
            "deduction": None,
            "personal_exemption": None,
            "brackets": [(INF, rate)],
            "starting_income_base": "Michigan taxable income",
            "complete": False,
            "notes": "Year-specific rate parsed; personal exemption not on this artifact.",
        }
    return _complete_flat(
        rate=rate,
        deduction=0.0,
        personal_exemption=exemption,
        starting_income_base="Federal AGI less Michigan personal exemption",
        year_ok=True,
        notes="Michigan uses a personal exemption rather than a federal-style standard deduction on MI-1040.",
    )


def _extract_ut(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    m = re.search(r"(4\.55|4\.65|4\.5)\s*%", blob)
    if not m or str(year) not in blob:
        return None
    return {
        "deduction": 0.0,
        "personal_exemption": None,
        "brackets": [(INF, _pct(m.group(1)))],
        "starting_income_base": "Utah taxable income",
        "complete": False,
        "notes": "Rate token found; credit-in-lieu-of-deduction not confirmed.",
    }


def _extract_ia(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    m = re.search(r"(3\.8|3\.80|5\.7)\s*%", blob)
    if not m or str(year) not in blob:
        return None
    return {
        "deduction": 0.0,
        "personal_exemption": None,
        "brackets": [(INF, _pct(m.group(1)))],
        "starting_income_base": "Iowa taxable income",
        "complete": False,
        "notes": "Rate token found; Iowa deduction mechanics not confirmed.",
    }


def _extract_ga(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    m = re.search(r"(5\.49|5\.39|5\.19)\s*%", blob)
    if not m or str(year) not in blob:
        return None
    return {
        "deduction": None,
        "personal_exemption": None,
        "brackets": [(INF, _pct(m.group(1)))],
        "starting_income_base": "Georgia taxable income",
        "complete": False,
        "notes": "Rate token found; standard deduction not confirmed.",
    }


def _extract_co(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    m = re.search(r"(4\.40|4\.4|4\.25)\s*%", blob)
    if not m or str(year) not in blob:
        return None
    return {
        "deduction": None,
        "personal_exemption": None,
        "brackets": [(INF, _pct(m.group(1)))],
        "starting_income_base": "Colorado taxable income / federal taxable income start",
        "complete": False,
        "notes": "Rate token found; TABOR/standard deduction not confirmed.",
    }


def _extract_id(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    m = re.search(r"(5\.695|5\.8|5\.695%)", blob)
    if not m or str(year) not in blob:
        return None
    rate_s = m.group(1).rstrip("%")
    try:
        rate = float(rate_s) / 100.0 if float(rate_s) > 1 else float(rate_s)
    except ValueError:
        return None
    return {
        "deduction": None,
        "personal_exemption": None,
        "brackets": [(INF, rate)],
        "starting_income_base": "Idaho taxable income",
        "complete": False,
        "notes": "Rate token found; standard deduction not confirmed.",
    }


def _extract_ms(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    m = re.search(r"(4\.7|4\.4|4\.0|5)\s*%", blob)
    if not m or str(year) not in blob:
        return None
    return {
        "deduction": None,
        "personal_exemption": None,
        "brackets": [(INF, _pct(m.group(1)))],
        "starting_income_base": "Mississippi taxable income",
        "complete": False,
        "notes": "Rate token found; exemption/zero bracket not confirmed.",
    }


def _extract_oh(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    if str(year) not in blob:
        return None
    m = re.search(r"(2\.75|3\.5|3\.125)\s*%", blob)
    if not m:
        return None
    return {
        "deduction": None,
        "personal_exemption": None,
        "brackets": [(INF, _pct(m.group(1)))],
        "starting_income_base": "Ohio taxable income",
        "complete": False,
        "notes": "Rate token found; Ohio brackets/exemption not confirmed.",
    }


def merge_extracted_schedules(
    parts: list[tuple[dict[str, Any], Mapping[str, Any]]],
) -> dict[str, Any] | None:
    """Merge per-artifact extracts. Each field keeps the artifact that supplied it."""
    if not parts:
        return None
    merged: dict[str, Any] = {
        "deduction": None,
        "personal_exemption": None,
        "brackets": None,
        "starting_income_base": "ordinary wage income of a single independent adult",
        "complete": False,
        "notes": "",
        "field_sources": {},
    }
    notes: list[str] = []
    for part, art in parts:
        if part.get("brackets") and not merged.get("brackets"):
            merged["brackets"] = part["brackets"]
            merged["field_sources"]["brackets"] = art
            if part.get("starting_income_base"):
                merged["starting_income_base"] = part["starting_income_base"]
        if part.get("deduction") is not None and merged.get("deduction") is None:
            merged["deduction"] = part["deduction"]
            merged["field_sources"]["deduction"] = art
        if part.get("personal_exemption") is not None and merged.get("personal_exemption") is None:
            merged["personal_exemption"] = part["personal_exemption"]
            merged["field_sources"]["personal_exemption"] = art
        if part.get("notes"):
            notes.append(str(part["notes"]))
    merged["notes"] = "; ".join(notes)
    merged["complete"] = bool(merged.get("brackets")) and merged.get("deduction") is not None
    return merged


def official_to_compare(official: Mapping[str, Any]) -> dict[str, Any]:
    deduction = float(official.get("deduction") or 0.0)
    exemption = float(official.get("personal_exemption") or 0.0)
    return {
        "deduction": deduction + exemption,
        "brackets": list(official.get("brackets") or []),
    }
