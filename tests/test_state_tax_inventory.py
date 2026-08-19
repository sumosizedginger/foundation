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
    build_state_tax_inventory,
    detect_high_agi_income_tax,
    evaluate_state_tax_freshness,
    no_wage_tax_verified,
    parse_future_income_tax,
    parse_no_wage_tax,
    tax_applies_to_rule_year,
)


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
