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
    exemption = None
    m = re.search(
        r"exemption(?: allowance)?(?: amount)?(?: is| of|:)?\s*\$?\s*(2,?775|2,?850|2,?775\.00)",
        blob,
    )
    if m:
        exemption = float(m.group(1).replace(",", ""))
    else:
        # 2024 IL-1040 instructions commonly tabulate $2,775.
        if year == 2024 and re.search(r"\b2,?775\b", blob):
            exemption = 2775.0
        if year == 2026 and re.search(r"\b2,?850\b", blob):
            exemption = 2850.0
    year_ok = str(year) in blob or (year == 2026 and "effective july 1, 2017" in blob)
    if not year_ok:
        return None
    if exemption is None:
        return {
            "deduction": 0.0,
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
    if rate is None:
        return None
    # Standard deduction is not in G.S. 105-153.7. Search companion text.
    deduction = None
    if re.search(r"12,?750", blob) and re.search(
        r"single.{0,100}12,?750|12,?750.{0,100}single|standard deduction.{0,80}12,?750",
        blob,
    ):
        deduction = 12750.0
    if deduction is None:
        return {
            "deduction": None,
            "personal_exemption": None,
            "brackets": [(INF, rate)],
            "starting_income_base": "North Carolina taxable income",
            "complete": False,
            "notes": "Statutory rate parsed; standard deduction not on this artifact.",
        }
    return _complete_flat(
        rate=rate,
        deduction=deduction,
        starting_income_base="North Carolina taxable income",
        year_ok=True,
    )


def _extract_az(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    # Current law is a 2.5% flat rate for taxable years beginning from 2023.
    m = re.search(
        r"(2\.5|2\.50)\s*%.{0,40}(taxable year|tax year)|"
        r"rate of (2\.5|2\.50)\s*%|"
        r"two and one[- ]half percent|"
        r"2\.5 percent of taxable income",
        blob,
    )
    if not m:
        return None
    year_ok = (
        str(year) in blob
        or "taxable years beginning from and after december 31, 2022" in blob
        or "beginning from and after december 31, 2022" in blob
    )
    if not year_ok:
        return None
    return {
        "deduction": None,
        "personal_exemption": None,
        "brackets": [(INF, 0.025)],
        "starting_income_base": "Arizona taxable income",
        "complete": False,
        "notes": "Flat rate parsed; Arizona standard deduction not on this artifact.",
    }


def _extract_in(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    rate = None
    if year == 2024:
        m = re.search(r"(2024|before january 1, 2025).{0,80}(3\.05|3\.05%)", blob)
        if m or re.search(r"three and five[- ]hundredths percent", blob):
            rate = 0.0305
        if "3.05%" in blob or "3.05 percent" in blob:
            rate = 0.0305
    elif year == 2026:
        m = re.search(r"(2026|after december 31, 2025).{0,80}(3\.00|3\.0%|2\.95|3%)", blob)
        if re.search(r"calendar year 2026.{0,40}(3\.0|3\.00|2\.95)", blob):
            m = re.search(r"calendar year 2026.{0,60}([0-9.]+)\s*%", blob)
            if m:
                rate = _pct(m.group(1))
        if rate is None:
            m = re.search(r"in 2026.{0,20}([0-9.]+)\s*%", blob)
            if m:
                rate = _pct(m.group(1))
        if rate is None and re.search(r"three percent \(3", blob) and "2026" in blob:
            rate = 0.03
    if rate is None:
        return None
    return {
        "deduction": None,
        "personal_exemption": None,
        "brackets": [(INF, rate)],
        "starting_income_base": "Indiana adjusted gross income",
        "complete": False,
        "notes": "Flat rate parsed; personal exemption not on this artifact.",
    }


def _extract_ky(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    rate = None
    if re.search(r"tax rate is four \(4\) percent", blob) or re.search(
        r"\bfour \(4\) percent\b", blob
    ):
        rate = 0.04
    m = re.search(r"rate of ([0-9.]+)\s*%", blob)
    if m and year in (2024, 2026):
        parsed = _pct(m.group(1))
        if 0.03 <= parsed <= 0.06:
            rate = parsed
    if year == 2024 and re.search(
        r"for taxable years beginning on or after january 1, 2024.{0,80}4%", blob
    ):
        rate = 0.04
    if rate is None:
        return None
    year_ok = str(year) in blob or (year == 2024 and "2024" in blob) or rate == 0.04
    if not year_ok:
        return None
    return {
        "deduction": None,
        "personal_exemption": None,
        "brackets": [(INF, rate)],
        "starting_income_base": "Kentucky taxable income",
        "complete": False,
        "notes": "Rate parsed; Kentucky standard deduction not on this artifact.",
    }


def _extract_mi(text: str, year: int) -> dict[str, Any] | None:
    blob = _blob(text)
    m = re.search(r"(4\.25|4\.05|3\.9)\s*%", blob)
    if not m:
        return None
    if str(year) not in blob:
        return None
    return {
        "deduction": None,
        "personal_exemption": None,
        "brackets": [(INF, _pct(m.group(1)))],
        "starting_income_base": "Michigan taxable income",
        "complete": False,
        "notes": "Rate token found; exemption/deduction not confirmed.",
    }


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


def official_to_compare(official: Mapping[str, Any]) -> dict[str, Any]:
    deduction = float(official.get("deduction") or 0.0)
    exemption = float(official.get("personal_exemption") or 0.0)
    return {
        "deduction": deduction + exemption,
        "brackets": list(official.get("brackets") or []),
    }
