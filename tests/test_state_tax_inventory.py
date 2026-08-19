"""51-jurisdiction state-tax evidence. Does not calculate an MSLC."""

from __future__ import annotations

import json
from pathlib import Path

from foundation.living_cost.evidence_validators import validate_state_tax_inventory
from foundation.living_cost.taxes import (
    NO_INCOME_TAX_STATES,
    UnsupportedTaxYearError,
    calculate_state_income_tax,
)
from foundation.sources.state_tax import (
    ALL_JURISDICTIONS,
    STATUS_NO_WAGE_TAX,
    STATUS_TAXING,
    bind_state_tax_freshness_to_inventory,
    build_state_tax_inventory,
    detect_high_agi_income_tax,
    discover_state_tax_live,
    evaluate_state_tax_freshness,
    inventory_file_sha256,
    no_wage_tax_verified,
    parse_authority_effective_date,
    parse_future_income_tax,
    parse_no_wage_tax,
    parse_preexisting_no_wage_tax,
    state_tax_freshness_payload_binding,
    tax_applies_to_rule_year,
)
from foundation.sources.state_tax_schedules import extract_official_schedule


def test_unsupported_year_is_fail_closed() -> None:
    try:
        calculate_state_income_tax(40000.0, "CA", year=2025)
    except UnsupportedTaxYearError:
        return
    raise AssertionError("2025 must fail closed")


def test_no_tax_parser_requires_official_wording() -> None:
    assert parse_no_wage_tax("Florida does not impose a personal income tax.", "FL") is True
    assert parse_no_wage_tax("Florida does not have an individual income tax.", "FL") is True
    assert parse_no_wage_tax("Texas does not have a personal income tax.", "TX") is True
    assert (
        parse_no_wage_tax(
            "The Hall Income tax was repealed for tax periods that begin on January 1, 2021, or later.",
            "TN",
        )
        is True
    )
    assert (
        parse_no_wage_tax(
            "Reduces the tax rate of, and in 2027 eliminates, the interest and dividends tax.",
            "NH",
            2024,
        )
        is True
    )
    assert (
        parse_no_wage_tax(
            "Chapter 77 Repealed Entire Chapter was repealed [Repealed by 2021, 91:99, II, eff. Jan. 1, 2025.]",
            "NH",
            2026,
        )
        is True
    )
    assert parse_no_wage_tax("Welcome to the Department of Revenue.", "FL") is False
    assert parse_no_wage_tax("", "FL") is False
    assert parse_no_wage_tax("If you are at or below the no tax due threshold", "TX") is False


def test_washington_future_tax_does_not_apply_to_2024() -> None:
    combined = (
        "The Washington state legislature recently enacted an income tax on individuals "
        "with an annual adjusted gross income of $1,000,000 or more. "
        "Beginning January 1, 2028, a tax is imposed on the receipt of Washington taxable income."
    )
    info = parse_future_income_tax(combined)
    assert info["tax_exists"] is True
    assert info["first_tax_year"] == 2028
    assert info["effective_start"] == "2028-01-01"
    assert tax_applies_to_rule_year(info, 2024) is False
    assert parse_no_wage_tax(combined, "WA", 2024) is True


def test_washington_future_tax_does_not_apply_to_2026() -> None:
    combined = (
        "The Washington state legislature recently enacted an income tax on individuals "
        "with an annual adjusted gross income of $1,000,000 or more. "
        "Beginning January 1, 2028, a tax is imposed on the receipt of Washington taxable income."
    )
    assert tax_applies_to_rule_year(parse_future_income_tax(combined), 2026) is False
    assert parse_no_wage_tax(combined, "WA", 2026) is True


def test_washington_2028_tax_applies_but_project_year_fail_closed() -> None:
    combined = (
        "Beginning January 1, 2028, a tax is imposed on the receipt of Washington taxable income. "
        "households with annual adjusted gross income of $1,000,000 or more"
    )
    assert tax_applies_to_rule_year(parse_future_income_tax(combined), 2028) is True
    assert parse_no_wage_tax(combined, "WA", 2028) is False
    try:
        calculate_state_income_tax(40000.0, "WA", year=2028)
    except UnsupportedTaxYearError:
        return
    raise AssertionError("2028 must fail closed as an unsupported project year")


def test_washington_undated_future_tax_is_not_zero() -> None:
    official = (
        "The Washington state legislature recently enacted an income tax on individuals "
        "with an annual adjusted gross income of $1,000,000 or more."
    )
    assert detect_high_agi_income_tax(official) is True
    info = parse_future_income_tax(official)
    assert info["unknown_effective_year"] is True
    assert tax_applies_to_rule_year(info, 2024) is None
    assert parse_no_wage_tax(official, "WA", 2024) is False
    assert parse_no_wage_tax(official, "WA", 2026) is False


def test_washington_2026_missing_authority_does_not_validate(tmp_path: Path) -> None:
    payload = build_state_tax_inventory(
        artifacts={
            "st_wa_2024_no_wage_tax": {
                **_art("WA", 2024, "aaa"),
            }
        }
    )
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_state_tax_inventory(path)
    assert result.ok is False
    assert any("WA:2026" in i for i in result.issues)


def test_washington_2026_sha_mismatch_fails(tmp_path: Path) -> None:
    payload = {
        "report_type": "living_cost_state_tax_inventory",
        "calculates_mslc": False,
        "family_complete": True,
        "retrieved_artifacts": [_art("WA", 2024, "aaa"), _art("WA", 2026, "bbb")],
        "jurisdictions": {
            "WA": {
                "years": {
                    "2024": {
                        "jurisdiction": "WA",
                        "tax_year": 2024,
                        "tax_status": STATUS_NO_WAGE_TAX,
                        "parsed_ok": True,
                        "validation_issues": [],
                        "official_authorities": [{"sha256": "aaa"}],
                        "standard_deduction": {
                            "source_artifact_key": "st_wa_2024_no_wage_tax",
                            "source_sha256": "aaa",
                        },
                    },
                    "2026": {
                        "jurisdiction": "WA",
                        "tax_year": 2026,
                        "tax_status": STATUS_NO_WAGE_TAX,
                        "parsed_ok": True,
                        "validation_issues": [],
                        "official_authorities": [{"sha256": "bbb"}],
                        "standard_deduction": {
                            "source_artifact_key": "st_wa_2026_no_wage_tax",
                            "source_sha256": "WRONG",
                        },
                    },
                }
            }
        },
    }
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_state_tax_inventory(path)
    assert result.ok is False
    assert any("STATE_TAX_AUTHORITY_SHA_MISMATCH" in i for i in result.issues)


def test_unverified_no_tax_candidate_is_not_zero() -> None:
    try:
        calculate_state_income_tax(40000.0, "FL", year=1999)
    except (UnsupportedTaxYearError, ValueError):
        return
    raise AssertionError("unverified year/state must not return zero")


def _art(state: str, year: int, sha: str, *, ok: bool = True) -> dict:
    return {
        "key": f"st_{state.lower()}_{year}_no_wage_tax",
        "state": state,
        "year": year,
        "url": f"https://revenue.{state.lower()}.gov/tax",
        "filename": f"st_{state.lower()}_{year}.html",
        "sha256": sha,
        "retrieved_at": "2026-08-19T00:00:00Z",
        "http_ok": ok,
        "byte_size": 100,
        "publisher": "Official DOR",
        "authority_type": "dor_page",
        "role": "wage_income_status",
        "path": None,
    }


def test_missing_authority_is_unbound(tmp_path: Path) -> None:
    payload = build_state_tax_inventory(artifacts={})
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_state_tax_inventory(path)
    assert result.ok is False
    assert any("STATE_TAX_FIELD_AUTHORITY_UNBOUND" in i for i in result.issues)


def test_sha_mismatch_fails(tmp_path: Path) -> None:
    payload = {
        "report_type": "living_cost_state_tax_inventory",
        "calculates_mslc": False,
        "family_complete": True,
        "retrieved_artifacts": [_art("FL", 2024, "aaa"), _art("FL", 2026, "bbb")],
        "jurisdictions": {
            "FL": {
                "years": {
                    "2024": {
                        "jurisdiction": "FL",
                        "tax_year": 2024,
                        "tax_status": STATUS_NO_WAGE_TAX,
                        "parsed_ok": True,
                        "validation_issues": [],
                        "official_authorities": [{"sha256": "aaa"}],
                        "standard_deduction": {
                            "source_artifact_key": "st_fl_2024_no_wage_tax",
                            "source_sha256": "WRONG",
                        },
                    },
                    "2026": {
                        "jurisdiction": "FL",
                        "tax_year": 2026,
                        "tax_status": STATUS_NO_WAGE_TAX,
                        "parsed_ok": True,
                        "validation_issues": [],
                        "official_authorities": [{"sha256": "bbb"}],
                        "standard_deduction": {
                            "source_artifact_key": "st_fl_2026_no_wage_tax",
                            "source_sha256": "bbb",
                        },
                    },
                }
            }
        },
    }
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_state_tax_inventory(path)
    assert result.ok is False
    assert any("STATE_TAX_AUTHORITY_SHA_MISMATCH" in i for i in result.issues)


def test_wrong_year_authority_fails(tmp_path: Path) -> None:
    payload = {
        "report_type": "living_cost_state_tax_inventory",
        "calculates_mslc": False,
        "family_complete": True,
        "retrieved_artifacts": [_art("FL", 2024, "aaa")],
        "jurisdictions": {
            "FL": {
                "years": {
                    "2024": {
                        "jurisdiction": "FL",
                        "tax_year": 2024,
                        "tax_status": STATUS_NO_WAGE_TAX,
                        "parsed_ok": True,
                        "validation_issues": [],
                        "official_authorities": [{"sha256": "aaa"}],
                        "standard_deduction": {
                            "source_artifact_key": "st_fl_2024_no_wage_tax",
                            "source_sha256": "aaa",
                        },
                    },
                    "2026": {
                        "jurisdiction": "FL",
                        "tax_year": 2026,
                        "tax_status": STATUS_NO_WAGE_TAX,
                        "parsed_ok": True,
                        "validation_issues": [],
                        "official_authorities": [{"sha256": "aaa"}],
                        "standard_deduction": {
                            "source_artifact_key": "st_fl_2024_no_wage_tax",
                            "source_sha256": "aaa",
                        },
                    },
                }
            }
        },
    }
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_state_tax_inventory(path)
    assert result.ok is False
    assert any("STATE_TAX_AUTHORITY_YEAR_MISMATCH" in i for i in result.issues)


def test_fifty_of_fifty_one_is_not_validated(tmp_path: Path) -> None:
    jurisdictions = {}
    artifacts = []
    for state in ALL_JURISDICTIONS:
        years = {}
        for year in (2024, 2026):
            sha = f"{state}{year}"
            artifacts.append(_art(state, year, sha))
            complete = not (state == "CA" and year == 2026)
            years[str(year)] = {
                "jurisdiction": state,
                "tax_year": year,
                "tax_status": STATUS_NO_WAGE_TAX if complete else "STATE_EVIDENCE_INCOMPLETE",
                "parsed_ok": complete,
                "validation_issues": [] if complete else ["gap"],
                "official_authorities": [{"sha256": sha}],
                "standard_deduction": {
                    "source_artifact_key": f"st_{state.lower()}_{year}_no_wage_tax",
                    "source_sha256": sha,
                },
            }
        jurisdictions[state] = {"years": years}
    payload = {
        "report_type": "living_cost_state_tax_inventory",
        "calculates_mslc": False,
        "family_complete": False,
        "retrieved_artifacts": artifacts,
        "jurisdictions": jurisdictions,
    }
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_state_tax_inventory(path)
    assert result.ok is False
    assert result.evidence_status != "VALIDATED"


def test_live_failure_does_not_claim_verified_current() -> None:
    status, newer, reason = evaluate_state_tax_freshness(
        inventory_valid=True,
        live=None,
        live_error="timeout",
    )
    assert status == "CHECK_FAILED"
    assert newer is None
    assert "VALIDATED" in reason


def test_incomplete_2026_is_not_verified_current() -> None:
    status, newer, _reason = evaluate_state_tax_freshness(
        inventory_valid=False,
        live={"all_2026_current": False, "unresolved_2026": ["CA"]},
        live_error=None,
    )
    assert status != "VERIFIED_CURRENT"
    assert newer is None


def test_no_income_tax_candidate_set_is_not_evidence() -> None:
    assert "FL" in NO_INCOME_TAX_STATES
    assert parse_no_wage_tax("candidate python set", "FL") is False


def test_engine_zero_requires_official_inventory(tmp_path: Path, monkeypatch) -> None:
    from foundation.sources import state_tax as stmod

    payload = {
        "report_type": "living_cost_state_tax_inventory",
        "calculates_mslc": False,
        "jurisdictions": {
            "FL": {
                "years": {
                    "2024": {
                        "tax_status": STATUS_NO_WAGE_TAX,
                        "parsed_ok": True,
                    },
                    "2026": {
                        "tax_status": "STATE_EVIDENCE_INCOMPLETE",
                        "parsed_ok": False,
                    },
                }
            }
        },
    }
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(stmod, "INVENTORY_PATH", path)
    assert no_wage_tax_verified("FL", 2024, payload) is True
    assert calculate_state_income_tax(40000.0, "FL", year=2024) == 0.0
    try:
        calculate_state_income_tax(40000.0, "FL", year=2026)
    except ValueError as exc:
        assert "unknown is not zero" in str(exc)
        return
    raise AssertionError("unverified 2026 FL must not return zero")


def test_authority_effective_date_is_not_rule_year_start() -> None:
    i2111 = (
        "INITIATIVE 2111\nChapter 5, Laws of 2024\n"
        "PERSONAL INCOME TAX PROHIBITION\nEFFECTIVE DATE: June 6, 2024\n"
        "Neither the state nor any county, city, or other local jurisdiction "
        "in the state of Washington may tax any individual person on any form "
        "of personal income."
    )
    assert parse_authority_effective_date(i2111) == "2024-06-06"
    essb = (
        "ENGROSSED SUBSTITUTE SENATE BILL 6346\nChapter 238, Laws of 2026\n"
        "EFFECTIVE DATE: June 11, 2026 — Except for sections 901...\n"
        "Beginning January 1, 2028, a tax is imposed on the receipt of "
        "Washington taxable income."
    )
    assert parse_authority_effective_date(essb) == "2026-06-11"
    info = parse_future_income_tax(essb)
    assert info["effective_start"] == "2028-01-01"
    assert tax_applies_to_rule_year(info, 2026) is False
    assert parse_authority_effective_date("Florida does not impose a personal income tax.") is None


def test_washington_preexisting_status_from_2024_committee_report() -> None:
    report = (
        "The initiative is designed to do one thing, which is to codify in law "
        "the state's longstanding tradition of not having an income tax based on "
        "personal income. It does not capture any of the state's existing revenue "
        "sources."
    )
    assert parse_preexisting_no_wage_tax(report) is True
    assert parse_preexisting_no_wage_tax("Welcome to the Department of Revenue.") is False


def _fl_inv() -> dict:
    return {
        "report_type": "living_cost_state_tax_inventory",
        "calculates_mslc": False,
        "jurisdictions": {
            st: {
                "years": {
                    "2024": {"tax_status": STATUS_NO_WAGE_TAX, "parsed_ok": st == "FL"},
                    "2026": {
                        "jurisdiction": st,
                        "tax_year": 2026,
                        "tax_status": STATUS_NO_WAGE_TAX
                        if st == "FL"
                        else "STATE_EVIDENCE_INCOMPLETE",
                        "parsed_ok": st == "FL",
                        "official_authorities": [
                            {
                                "sha256": "abc",
                                "url": "https://floridarevenue.com/faq",
                                "retrieved_at": "2025-01-01T00:00:00Z",
                            }
                        ],
                    },
                }
            }
            for st in ALL_JURISDICTIONS
        },
    }


def test_currentness_a_cache_without_live_is_not_verified_current() -> None:
    live, err = discover_state_tax_live(_fl_inv(), perform_live=False)
    assert err is None
    assert live is not None
    assert live["evidence_valid_2026_count"] == 1
    assert live["live_verified_current_2026_count"] == 0
    assert live["verified_current_2026_count"] == 0
    assert live["live_check_performed"] is False
    status, newer, _reason = evaluate_state_tax_freshness(
        inventory_valid=True, live=live, live_error=None
    )
    assert status != "VERIFIED_CURRENT"
    assert newer is None


def test_currentness_b_live_failure_keeps_evidence_valid() -> None:
    def fail(_url: str) -> dict:
        return {"ok": False, "url": _url, "text": "", "error": "timeout", "live_checked": True}

    live, err = discover_state_tax_live(_fl_inv(), fetch_fn=fail, perform_live=True)
    assert err is None
    assert live is not None
    assert live["evidence_valid_2026_count"] == 1
    assert live["live_verified_current_2026_count"] == 0
    assert "FL" in live["live_failed_2026"]
    status, newer, reason = evaluate_state_tax_freshness(
        inventory_valid=True, live=live, live_error=None
    )
    assert status == "CHECK_FAILED"
    assert newer is None
    assert "not demoted" in reason.lower() or "Cached" in reason or "failed" in reason.lower()


def test_currentness_c_live_agreement_may_verify_cell() -> None:
    def ok(_url: str) -> dict:
        return {
            "ok": True,
            "url": _url,
            "text": "Florida does not impose a personal income tax.",
            "error": None,
            "live_checked": True,
        }

    live, err = discover_state_tax_live(_fl_inv(), fetch_fn=ok, perform_live=True)
    assert err is None
    assert live is not None
    assert live["live_verified_current_2026_count"] == 1
    assert live["all_2026_current"] is False


def test_currentness_d_2027_law_does_not_disturb_2026() -> None:
    def future(_url: str) -> dict:
        return {
            "ok": True,
            "url": _url,
            "text": (
                "Florida does not impose a personal income tax. "
                "Beginning January 1, 2027, a tax is imposed on the receipt of Florida taxable income."
            ),
            "error": None,
            "live_checked": True,
        }

    live, err = discover_state_tax_live(_fl_inv(), fetch_fn=future, perform_live=True)
    assert err is None
    assert live is not None
    assert live["live_verified_current_2026_count"] == 1
    assert live["newer_available_2026"] == []


def test_currentness_e_2026_applicable_change_is_newer_available() -> None:
    def changed(_url: str) -> dict:
        return {
            "ok": True,
            "url": _url,
            "text": (
                "The Florida legislature recently enacted an income tax on individuals "
                "with an annual adjusted gross income of $1,000,000 or more. "
                "Beginning January 1, 2026, a tax is imposed on the receipt of Florida taxable income."
            ),
            "error": None,
            "live_checked": True,
        }

    live, err = discover_state_tax_live(_fl_inv(), fetch_fn=changed, perform_live=True)
    assert err is None
    assert live is not None
    assert live["live_verified_current_2026_count"] == 0
    assert "FL" in live["newer_available_2026"]
    status, newer, _reason = evaluate_state_tax_freshness(
        inventory_valid=False, live=live, live_error=None
    )
    assert status == "NEWER_AVAILABLE"
    assert newer is True


def test_currentness_f_retrieval_timestamp_alone_is_not_currentness() -> None:
    live, err = discover_state_tax_live(_fl_inv(), perform_live=False)
    assert err is None
    assert live is not None
    assert live["verified_current_2026_count"] == 0
    status, _newer, reason = evaluate_state_tax_freshness(
        inventory_valid=True, live=live, live_error=None
    )
    assert status != "VERIFIED_CURRENT"
    assert "not currentness" in reason.lower() or "No targeted" in reason


def test_pa_schedule_extracts_from_official_rate_table() -> None:
    text_2026 = "Personal Income Tax Rates Tax Year Rate 2004 – Present 3.07% 1993 – 2003 2.8%"
    rec = extract_official_schedule("PA", 2026, text_2026)
    assert rec is not None
    assert rec["complete"] is True
    assert rec["deduction"] == 0.0
    assert rec["brackets"][0][1] == 0.0307
    text_2024 = "2024 PA-40 Instructions. Pennsylvania personal income tax is levied at the rate of 3.07 percent against taxable income."
    rec24 = extract_official_schedule("PA", 2024, text_2024)
    assert rec24 is not None and rec24["complete"] is True
    assert extract_official_schedule("PA", 2024, "Welcome to Revenue.") is None


def test_nc_2024_and_2026_rates_from_statute() -> None:
    statute = (
        "G.S. 105-153.7 Individual income tax imposed. Taxable Years Beginning Tax "
        "In 2022 4.99% In 2023 4.75% In 2024 4.5% In 2025 4.25% After 2025 3.99%."
    )
    rec24 = extract_official_schedule("NC", 2024, statute)
    rec26 = extract_official_schedule("NC", 2026, statute)
    assert rec24 is not None and rec24["brackets"][0][1] == 0.045
    assert rec26 is not None and rec26["brackets"][0][1] == 0.0399
    assert rec24["complete"] is False
    assert rec26["complete"] is False
    complete = (
        statute + " For tax year 2026, the N.C. standard deduction for the "
        "single filing status ($12,750)"
    )
    rec26c = extract_official_schedule("NC", 2026, complete)
    assert rec26c is not None and rec26c["complete"] is True
    assert rec26c["deduction"] == 12750.0
    ty2025 = (
        statute + " The following information applies to individuals for tax year 2025. "
        "Single $12,750 N.C. standard deduction"
    )
    rec_wrong_year = extract_official_schedule("NC", 2026, ty2025)
    assert rec_wrong_year is None or rec_wrong_year.get("complete") is not True


def test_nc_2026_engine_uses_official_after_2025_rate() -> None:
    """Old candidate table used 4.25%; G.S. 105-153.7 After 2025 is 3.99%."""
    from foundation.living_cost.taxes import STATE_STATUTORY_SCHEDULES, calculate_state_income_tax

    sched = STATE_STATUTORY_SCHEDULES[2026]["NC"]
    assert sched["brackets"][0][1] == 0.0399
    taxable = 40000.0 - 12750.0
    assert abs(calculate_state_income_tax(40000.0, "NC", year=2026) - taxable * 0.0399) < 0.02
    # Record superseded candidate behavior: 4.25% is not the 2026 statutory rate.
    assert abs(calculate_state_income_tax(40000.0, "NC", year=2026) - taxable * 0.0425) > 1.0


def _taxing_inv(
    *,
    state: str = "PA",
    cell: dict | None = None,
    retrieved: list | None = None,
) -> dict:
    rec = {
        "jurisdiction": state,
        "tax_year": 2026,
        "tax_status": STATUS_TAXING,
        "parsed_ok": True,
        "standard_deduction": {"value": 0.0},
        "personal_exemption": {"value": 0.0},
        "brackets": [{"upper": None, "rate": 0.0307}],
        "rates": [0.0307],
        "official_authorities": [
            {"url": "https://www.pa.gov/agencies/revenue/pit", "sha256": "abc"}
        ],
    }
    if cell:
        rec.update(cell)
    return {
        "report_type": "living_cost_state_tax_inventory",
        "generated_at": "2026-08-19T17:32:42+00:00",
        "calculates_mslc": False,
        "retrieved_artifacts": retrieved
        or [
            {
                "key": "st_pa_2026_schedule",
                "filename": "st_pa_2026_schedule.html",
                "sha256": "abc",
                "http_ok": True,
            }
        ],
        "jurisdictions": {
            st: {
                "years": {
                    "2024": {"tax_status": STATUS_NO_WAGE_TAX, "parsed_ok": False},
                    "2026": rec
                    if st == state
                    else {
                        "jurisdiction": st,
                        "tax_year": 2026,
                        "tax_status": "STATE_EVIDENCE_INCOMPLETE",
                        "parsed_ok": False,
                    },
                }
            }
            for st in ALL_JURISDICTIONS
        },
    }


def _live_ok(text: str):
    def fetch(_url: str) -> dict:
        return {
            "ok": True,
            "url": _url,
            "text": text,
            "error": None,
            "live_checked": True,
        }

    return fetch


def test_taxing_historical_rate_with_different_2026_rate_is_not_current() -> None:
    """A leftover 3.99% on a page that states a different 2026 rate is not current."""
    inv = _taxing_inv(
        state="NC",
        cell={
            "standard_deduction": {"value": 12750.0},
            "personal_exemption": None,
            "brackets": [{"upper": None, "rate": 0.0399}],
            "rates": [0.0399],
            "official_authorities": [
                {"url": "https://www.ncleg.gov/GS_105-153.7.html", "sha256": "statute"}
            ],
        },
    )
    text = (
        "G.S. 105-153.7 Individual income tax imposed. "
        "In 2025 3.99%. In 2026 4.10%. After 2025 3.99%. "
        "For tax year 2026, the N.C. standard deduction for the single filing status ($12,750)"
    )
    live, err = discover_state_tax_live(inv, fetch_fn=_live_ok(text), perform_live=True)
    assert err is None
    assert live is not None
    assert live["live_verified_current_2026_count"] == 0
    assert live["verified_current_2026_count"] == 0
    assert "NC" in live["newer_available_2026"] or "NC" in live["live_failed_2026"]


def test_taxing_same_rate_changed_2026_deduction_is_not_current() -> None:
    inv = _taxing_inv(
        state="NC",
        cell={
            "standard_deduction": {"value": 12750.0},
            "personal_exemption": None,
            "brackets": [{"upper": None, "rate": 0.0399}],
            "rates": [0.0399],
            "official_authorities": [{"url": "https://www.ncdor.gov/withholding", "sha256": "wh"}],
        },
    )
    text = (
        "G.S. 105-153.7 After 2025 3.99%. "
        "For tax year 2026, the N.C. standard deduction for the single filing status ($13,000)"
    )
    live, err = discover_state_tax_live(inv, fetch_fn=_live_ok(text), perform_live=True)
    assert err is None
    assert live is not None
    assert live["live_verified_current_2026_count"] == 0
    assert live["verified_current_2026_count"] == 0


def test_taxing_progressive_one_rate_present_changed_brackets_is_not_current() -> None:
    inv = _taxing_inv(
        cell={
            "standard_deduction": {"value": 0.0},
            "personal_exemption": {"value": 0.0},
            "brackets": [
                {"upper": 10000.0, "rate": 0.0307},
                {"upper": None, "rate": 0.0495},
            ],
            "rates": [0.0307, 0.0495],
        }
    )
    text = "Personal Income Tax Rates Tax Year Rate 2004 – Present 3.07% 1993 – 2003 2.8%"
    live, err = discover_state_tax_live(inv, fetch_fn=_live_ok(text), perform_live=True)
    assert err is None
    assert live is not None
    assert live["live_verified_current_2026_count"] == 0
    assert live["verified_current_2026_count"] == 0


def test_taxing_exact_live_schedule_agreement_may_verify() -> None:
    text = "Personal Income Tax Rates Tax Year Rate 2004 – Present 3.07% 1993 – 2003 2.8%"
    live, err = discover_state_tax_live(_taxing_inv(), fetch_fn=_live_ok(text), perform_live=True)
    assert err is None
    assert live is not None
    assert live["live_verified_current_2026_count"] == 1
    assert live["all_2026_current"] is False


def test_taxing_future_only_2027_change_does_not_invalidate_2026_schedule() -> None:
    text = (
        "Personal Income Tax Rates Tax Year Rate 2004 – Present 3.07% 1993 – 2003 2.8%. "
        "Beginning tax year 2027 the rate is 4.00 percent."
    )
    live, err = discover_state_tax_live(_taxing_inv(), fetch_fn=_live_ok(text), perform_live=True)
    assert err is None
    assert live is not None
    assert live["live_verified_current_2026_count"] == 1
    assert live["newer_available_2026"] == []


def test_nc_2025_labeled_page_cannot_complete_or_verify_2026() -> None:
    statute = (
        "G.S. 105-153.7 Individual income tax imposed. Taxable Years Beginning Tax "
        "In 2022 4.99% In 2023 4.75% In 2024 4.5% In 2025 4.25% After 2025 3.99%."
    )
    ty2025 = (
        "The following information applies to individuals for tax year 2025. "
        "Single $12,750 N.C. standard deduction"
    )
    rec = extract_official_schedule("NC", 2026, statute + " " + ty2025)
    assert rec is None or rec.get("complete") is not True
    inv = _taxing_inv(
        state="NC",
        cell={
            "standard_deduction": {"value": 12750.0},
            "personal_exemption": None,
            "brackets": [{"upper": None, "rate": 0.0399}],
            "rates": [0.0399],
            "official_authorities": [
                {"url": "https://www.ncdor.gov/2025-landing", "sha256": "landing"}
            ],
        },
    )
    live, err = discover_state_tax_live(inv, fetch_fn=_live_ok(ty2025), perform_live=True)
    assert err is None
    assert live is not None
    assert live["live_verified_current_2026_count"] == 0
    assert live["verified_current_2026_count"] == 0


def test_inventory_sha_is_newline_invariant(tmp_path: Path) -> None:
    payload = {"report_type": "living_cost_state_tax_inventory", "generated_at": "x"}
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    text = json.dumps(payload, indent=2) + "\n"
    lf.write_bytes(text.encode("utf-8"))
    crlf.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert inventory_file_sha256(lf) == inventory_file_sha256(crlf)


def test_stale_freshness_cannot_claim_sync_with_newer_inventory(tmp_path: Path) -> None:
    inventory = {
        "report_type": "living_cost_state_tax_inventory",
        "generated_at": "2026-08-19T17:32:42+00:00",
        "retrieved_artifacts": [
            {
                "key": "st_nc_2026_standard_deduction",
                "filename": "st_nc_2026_standard_deduction.html",
                "sha256": "56a00f94",
                "http_ok": True,
            }
        ],
    }
    path = tmp_path / "living_cost_state_tax_inventory.json"
    path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    current_sha = inventory_file_sha256(path)
    assert current_sha is not None
    stale = bind_state_tax_freshness_to_inventory(
        freshness_inventory_sha="0" * 64,
        freshness_inventory_generated_at="2026-08-19T16:45:51Z",
        selected_artifact_ids=["st_nc_2026_std_ded_page.html"],
        inventory_path=path,
        inventory_payload=inventory,
    )
    assert stale["ok"] is False
    assert "STATE_TAX_FRESHNESS_INVENTORY_SHA_MISMATCH" in stale["issues"]
    assert any("st_nc_2026_std_ded_page.html" in issue for issue in stale["issues"])
    status, newer, reason = evaluate_state_tax_freshness(
        inventory_valid=False,
        live={"live_check_performed": True, "evidence_valid_2026_count": 11},
        live_error=None,
        inventory_binding=stale,
    )
    assert status == "CHECK_FAILED"
    assert newer is None
    assert "not bound" in reason.lower() or "stale" in reason.lower()
    matched = bind_state_tax_freshness_to_inventory(
        freshness_inventory_sha=current_sha,
        freshness_inventory_generated_at="2026-08-19T17:32:42+00:00",
        selected_artifact_ids=["st_nc_2026_standard_deduction.html"],
        inventory_path=path,
        inventory_payload=inventory,
    )
    assert matched["ok"] is True
    freshness = {
        "checks": {
            "state_tax_law": {
                "selected_artifacts": [
                    {"artifact_id": "st_nc_2026_std_ded_page.html", "sha256": "old"}
                ],
                "extra": {
                    "inventory_sha256": "deadbeef",
                    "inventory_generated_at": "2026-08-19T16:45:51Z",
                },
            }
        }
    }
    payload_binding = state_tax_freshness_payload_binding(
        freshness, inventory_path=path, inventory_payload=inventory
    )
    assert payload_binding["ok"] is False


def test_inventory_does_not_fabricate_effective_dates() -> None:
    payload = build_state_tax_inventory(artifacts={})
    fl = payload["jurisdictions"]["FL"]["years"]["2026"]
    assert fl.get("effective_date") in (None, fl.get("authority_effective_date"))
    assert (
        fl.get("effective_date") != "2026-01-01"
        or fl.get("authority_effective_date") == "2026-01-01"
    )
    # Unbound cell must not invent a RULE_YEAR start date.
    assert fl.get("authority_effective_date") is None


def test_production_freshness_is_bound_to_current_inventory() -> None:
    meta = Path(__file__).resolve().parents[1] / "data" / "metadata"
    freshness = json.loads(
        (meta / "living_cost_candidate_freshness.json").read_text(encoding="utf-8")
    )
    inventory_path = meta / "living_cost_state_tax_inventory.json"
    binding = state_tax_freshness_payload_binding(freshness, inventory_path=inventory_path)
    assert binding["ok"] is True, binding["issues"]
    extra = ((freshness.get("checks") or {}).get("state_tax_law") or {}).get("extra") or {}
    assert extra.get("inventory_sha256") == inventory_file_sha256(inventory_path)
    artifacts = ((freshness.get("checks") or {}).get("state_tax_law") or {}).get(
        "selected_artifacts"
    ) or []
    ids = [str(item.get("artifact_id") or item.get("filename") or "") for item in artifacts]
    assert "st_nc_2026_std_ded_page.html" not in ids
