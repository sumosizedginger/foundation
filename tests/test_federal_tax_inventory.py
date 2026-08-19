"""Federal tax statutory inventory vs FEDERAL_TAX_RULES. Does not calculate an MSLC."""

from __future__ import annotations

import json
from pathlib import Path

from foundation.living_cost.evidence_validators import validate_federal_tax_inventory
from foundation.living_cost.taxes import (
    FEDERAL_TAX_RULES,
    UnsupportedTaxYearError,
    calculate_federal_income_tax,
    calculate_fica_taxes,
)
from foundation.sources.federal_tax import (
    ADDITIONAL_MEDICARE_RATE,
    ADDITIONAL_MEDICARE_THRESHOLD_SINGLE,
    parse_additional_medicare,
    parse_employee_medicare_rate,
    parse_employee_oasdi_rate,
    parse_oasdi_wage_base,
    parse_single_brackets,
    parse_standard_deduction_single,
)

ROOT = Path(__file__).resolve().parents[1]


RP_2024_SNIPPET = """
Rev. Proc. 2023-34
TABLE 3 - Section 1(j)(2)(C) – Unmarried Individuals (other than Surviving Spouses and
Heads of Households)
If Taxable Income Is: The Tax Is:
 Not over $11,600  10% of the taxable income
 Over $11,600 but
not over $47,150
 Over $47,150 but
not over $100,525
 Over $100,525 but
not over $191,950
 Over $191,950 but
not over $243,725
 Over $243,725 but
not over $609,350
 Over $609,350  $181,954.50 plus 37% of
     .15 Standard Deduction
        (1) In general.  For taxable years beginning in 2024, the standard deduction amounts
under § 63(c)(2) are as follows:
Unmarried Individuals (other than Surviving Spouses and Heads of
Households) (§ 1(j)(2)(C))
$14,600
"""

RP_2026_SNIPPET = """
Revenue Procedure 2025-32
TABLE 3 - Section 1(j)(2)(C) – Unmarried Individuals (other than Surviving Spouses and
Heads of Households)
If Taxable Income Is: The Tax Is:
 Not over $12,400   10% of the taxable income
 Over $12,400 but
not over $50,400
 Over $50,400 but
not over $105,700
 Over $105,700 but
not over $201,775
 Over $201,775 but
not over $256,225
 Over $256,225 but
not over $640,600
 Over $640,600   $192,979.25 plus 37% of
     .14 Standard Deduction.
        (1) In general.  For taxable years beginning in 2026, the standard deduction amounts
under § 63(c)(2) are as follows:
Unmarried Individuals (other than Surviving Spouses and Heads of
Households) (§ 1(j)(2)(C))
$16,100
"""

SSA_SNIPPET = """
The Social Security portion (OASDI) is 6.2 percent on earnings up to the applicable
taxable maximum amount. The Medicare portion (HI) is 1.45 percent on all earnings.
Also, as of January 2013, individuals with earned income of more than $200,000
($250,000 for married couples filing jointly) pay an additional 0.9 percent in Medicare taxes.
For earnings in 2024 this base is $168,600.
For earnings in 2026, this base is $184,500.
"""


def test_parsers_read_official_wording():
    assert parse_standard_deduction_single(RP_2024_SNIPPET, 2024) == 14600.0
    assert parse_standard_deduction_single(RP_2026_SNIPPET, 2026) == 16100.0
    b2024 = parse_single_brackets(RP_2024_SNIPPET, 2024)
    b2026 = parse_single_brackets(RP_2026_SNIPPET, 2026)
    assert b2024 is not None and b2024[0] == (11600.0, 0.10)
    assert b2024[-1][1] == 0.37
    assert b2026 is not None and b2026[0] == (12400.0, 0.10)
    assert parse_oasdi_wage_base(SSA_SNIPPET, 2024) == 168600.0
    assert parse_oasdi_wage_base(SSA_SNIPPET, 2026) == 184500.0
    assert parse_employee_oasdi_rate(SSA_SNIPPET) == 0.062
    assert parse_employee_medicare_rate(SSA_SNIPPET) == 0.0145
    addl = parse_additional_medicare(SSA_SNIPPET)
    assert addl is not None
    assert addl["threshold"] == 200000.0
    assert addl["rate"] == 0.009


def test_code_tables_include_additional_medicare():
    for year in (2024, 2026):
        rules = FEDERAL_TAX_RULES[year]
        assert rules["additional_medicare_rate"] == ADDITIONAL_MEDICARE_RATE
        assert rules["additional_medicare_threshold"] == ADDITIONAL_MEDICARE_THRESHOLD_SINGLE


def test_unsupported_year_is_fail_closed():
    try:
        calculate_federal_income_tax(20000.0, year=2025)
        raise AssertionError("2025 must be unsupported")
    except UnsupportedTaxYearError:
        pass


def test_bracket_boundaries_from_inventory():
    for year, std, first_cap, first_rate in (
        (2024, 14600.0, 11600.0, 0.10),
        (2026, 16100.0, 12400.0, 0.10),
    ):
        assert calculate_federal_income_tax(0.0, year=year) == 0.0
        assert calculate_federal_income_tax(std, year=year) == 0.0
        assert calculate_federal_income_tax(std + 1.0, year=year) == first_rate
        at_first = calculate_federal_income_tax(std + first_cap, year=year)
        assert round(at_first, 2) == round(first_cap * first_rate, 2)
        above = calculate_federal_income_tax(std + first_cap + 1.0, year=year)
        second_rate = FEDERAL_TAX_RULES[year]["brackets"][1][1]
        assert round(above, 2) == round(first_cap * first_rate + second_rate, 2)


def test_oasdi_cap_minus_at_plus():
    for year in (2024, 2026):
        cap = FEDERAL_TAX_RULES[year]["ss_wage_cap"]
        rate = FEDERAL_TAX_RULES[year]["ss_tax_rate"]
        ss_lo, _ = calculate_fica_taxes(cap - 1.0, year=year)
        ss_at, _ = calculate_fica_taxes(cap, year=year)
        ss_hi, _ = calculate_fica_taxes(cap + 1.0, year=year)
        assert round(ss_lo, 2) == round((cap - 1.0) * rate, 2)
        assert round(ss_at, 2) == round(cap * rate, 2)
        assert round(ss_hi, 2) == round(cap * rate, 2)


def test_medicare_ordinary_and_additional_threshold():
    for year in (2024, 2026):
        hi = FEDERAL_TAX_RULES[year]["medicare_rate"]
        _, med_low = calculate_fica_taxes(50000.0, year=year)
        assert round(med_low, 2) == round(50000.0 * hi, 2)
        _, at_thr = calculate_fica_taxes(200000.0, year=year)
        assert round(at_thr, 2) == round(200000.0 * hi, 2)
        _, above = calculate_fica_taxes(200001.0, year=year)
        expected = 200001.0 * hi + 1.0 * ADDITIONAL_MEDICARE_RATE
        assert round(above, 2) == round(expected, 2)


def test_inventory_mismatch_fail_closes(tmp_path: Path):
    payload = {
        "report_type": "living_cost_federal_tax_inventory",
        "calculates_mslc": False,
        "retrieved_artifacts": [
            {"sha256": "aa", "http_ok": True},
            {"sha256": "bb", "http_ok": True},
        ],
        "years": {
            "2024": {
                "parsed_ok": True,
                "issues": [],
                "standard_deduction": {"value": 1.0},
                "oasdi": {"employee_rate": 0.062, "taxable_maximum": 168600.0},
                "medicare_hi": {"employee_rate": 0.0145, "no_limit": True},
                "additional_medicare_tax": {
                    "applicable": True,
                    "threshold": 200000.0,
                    "rate": 0.009,
                },
                "income_tax_brackets": [],
            },
            "2026": {
                "parsed_ok": True,
                "issues": [],
                "standard_deduction": {"value": 16100.0},
                "oasdi": {"employee_rate": 0.062, "taxable_maximum": 184500.0},
                "medicare_hi": {"employee_rate": 0.0145, "no_limit": True},
                "additional_medicare_tax": {
                    "applicable": True,
                    "threshold": 200000.0,
                    "rate": 0.009,
                },
                "income_tax_brackets": [],
            },
        },
    }
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is False
    assert any("FEDERAL_TAX_RULES_MISMATCH" in item for item in result.issues)
    assert result.evidence_status == "INVENTORY_NOT_VALIDATED"


def test_empty_inventory_is_not_validated(tmp_path: Path):
    path = tmp_path / "empty.json"
    path.write_text("{}", encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is False
    assert result.evidence_status == "INVENTORY_NOT_VALIDATED"


def test_coverage_status_dimensions_use_federal_tax_validator():
    """status_dimensions must not hard-code INVENTORY_NOT_VALIDATED over the validator."""
    coverage = json.loads(
        (ROOT / "data" / "metadata" / "living_cost_source_coverage.json").read_text(
            encoding="utf-8"
        )
    )
    expected = validate_federal_tax_inventory().evidence_status
    assert coverage["coverage_by_year"]["2024"]["federal_tax"] == expected
    assert coverage["coverage_by_year"]["2026"]["federal_tax"] == expected
    for year in ("2024", "2026"):
        assert (
            coverage["status_dimensions"]["by_year"][year]["federal_tax"]["evidence_status"]
            == expected
        )


def _art(key: str, sha: str, *, ok: bool = True, url: str | None = None) -> dict:
    return {
        "key": key,
        "url": url or f"https://www.irs.gov/pub/{key}.pdf",
        "filename": f"{key}.pdf",
        "sha256": sha,
        "http_ok": ok,
        "retrieved_at": "2026-01-01T00:00:00Z",
    }


def _field(value_key: str, value, key: str, sha: str, extra: dict | None = None) -> dict:
    rec = {
        value_key: value,
        "authority_id": key.upper(),
        "source_artifact_key": key,
        "source_sha256": sha,
        "extraction_identity": "test",
    }
    if extra:
        rec.update(extra)
    return rec


def _complete_year(year: int, income_key: str, payroll_key: str, sha_income: str, sha_pay: str):
    std = 14600.0 if year == 2024 else 16100.0
    cap = 168600.0 if year == 2024 else 184500.0
    brackets_caps = (
        [11600.0, 47150.0, 100525.0, 191950.0, 243725.0, 609350.0]
        if year == 2024
        else [12400.0, 50400.0, 105700.0, 201775.0, 256225.0, 640600.0]
    )
    rates = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
    return {
        "parsed_ok": True,
        "issues": [],
        "standard_deduction": _field("value", std, income_key, sha_income),
        "income_tax_brackets": [
            _field("upper", cap_v, income_key, sha_income, extra={"rate": rate})
            for cap_v, rate in zip(brackets_caps + [None], rates, strict=True)
        ],
        "oasdi": _field(
            "employee_rate",
            0.062,
            payroll_key,
            sha_pay,
            extra={"taxable_maximum": cap},
        ),
        "medicare_hi": _field(
            "employee_rate",
            0.0145,
            payroll_key,
            sha_pay,
            extra={"no_limit": True, "taxable_maximum": None},
        ),
        "additional_medicare_tax": _field(
            "applicable",
            True,
            payroll_key,
            sha_pay,
            extra={"threshold": 200000.0, "rate": 0.009},
        ),
    }


def _valid_payload() -> dict:
    return {
        "report_type": "living_cost_federal_tax_inventory",
        "calculates_mslc": False,
        "retrieved_artifacts": [
            _art("irs_rp_2023_34", "sha24rp"),
            _art("irs_rp_2025_32", "sha26rp"),
            _art("irs_pub15_2024", "sha24p15"),
            _art("irs_pub15_2026", "sha26p15"),
        ],
        "years": {
            "2024": _complete_year(2024, "irs_rp_2023_34", "irs_pub15_2024", "sha24rp", "sha24p15"),
            "2026": _complete_year(2026, "irs_rp_2025_32", "irs_pub15_2026", "sha26rp", "sha26p15"),
        },
    }


def test_rev_procs_without_publication_15_fail(tmp_path: Path):
    payload = _valid_payload()
    payload["retrieved_artifacts"] = [
        _art("irs_rp_2023_34", "sha24rp"),
        _art("irs_rp_2025_32", "sha26rp"),
    ]
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is False
    assert any("FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND" in item for item in result.issues)


def test_2026_pub15_missing_fails(tmp_path: Path):
    payload = _valid_payload()
    payload["retrieved_artifacts"] = [
        item for item in payload["retrieved_artifacts"] if item["key"] != "irs_pub15_2026"
    ]
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is False
    assert any("2026:oasdi" in item for item in result.issues)


def test_http_ok_false_field_reference_fails(tmp_path: Path):
    payload = _valid_payload()
    for item in payload["retrieved_artifacts"]:
        if item["key"] == "irs_pub15_2024":
            item["http_ok"] = False
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is False
    assert any("FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:2024:" in item for item in result.issues)


def test_nonexistent_artifact_key_fails(tmp_path: Path):
    payload = _valid_payload()
    payload["years"]["2024"]["oasdi"]["source_artifact_key"] = "not_a_real_key"
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is False
    assert "FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:2024:oasdi" in result.issues


def test_field_sha_mismatch_fails(tmp_path: Path):
    payload = _valid_payload()
    payload["years"]["2024"]["standard_deduction"]["source_sha256"] = "other"
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is False
    assert "FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:2024:standard_deduction" in result.issues


def test_2026_brackets_claiming_2023_34_fail(tmp_path: Path):
    payload = _valid_payload()
    for bracket in payload["years"]["2026"]["income_tax_brackets"]:
        bracket["source_artifact_key"] = "irs_rp_2023_34"
        bracket["source_sha256"] = "sha24rp"
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is False
    assert any(
        "FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:2026:brackets" in item for item in result.issues
    )


def test_additional_medicare_without_source_fails(tmp_path: Path):
    payload = _valid_payload()
    payload["years"]["2024"]["additional_medicare_tax"] = {
        "applicable": True,
        "threshold": 200000.0,
        "rate": 0.009,
    }
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is False
    assert "FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:2024:additional_medicare_tax" in result.issues


def test_two_arbitrary_hashed_artifacts_fail(tmp_path: Path):
    payload = {
        "report_type": "living_cost_federal_tax_inventory",
        "calculates_mslc": False,
        "retrieved_artifacts": [
            _art("irs_irb_2023_48", "aa"),
            _art("irs_topic_751", "bb", url="https://www.irs.gov/taxtopics/tc751"),
        ],
        "years": {
            "2024": _complete_year(2024, "irs_rp_2023_34", "irs_pub15_2024", "sha24rp", "sha24p15"),
            "2026": _complete_year(2026, "irs_rp_2025_32", "irs_pub15_2026", "sha26rp", "sha26p15"),
        },
    }
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is False
    assert any("FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND" in item for item in result.issues)


def test_complete_year_specific_authorities_may_validate(tmp_path: Path):
    path = tmp_path / "inv.json"
    path.write_text(json.dumps(_valid_payload()), encoding="utf-8")
    result = validate_federal_tax_inventory(path)
    assert result.ok is True
    assert result.evidence_status == "VALIDATED"


def test_live_failure_does_not_claim_verified_current():
    from foundation.sources.federal_tax import evaluate_federal_tax_freshness

    status, newer, reason = evaluate_federal_tax_freshness(
        inventory_valid=True,
        live=None,
        live_error="connection reset",
    )
    assert status == "CHECK_FAILED"
    assert newer is None
    assert "VALIDATED" in reason
    assert status != "VERIFIED_CURRENT"


def test_newer_pub15_revision_is_not_verified_current():
    from foundation.sources.federal_tax import evaluate_federal_tax_freshness

    status, newer, _reason = evaluate_federal_tax_freshness(
        inventory_valid=True,
        live={
            "pub15_revision_year": 2027,
            "rev_proc_2025_32_current": True,
            "successor_rev_proc": None,
            "current_pub15_payroll_matches": True,
        },
        live_error=None,
    )
    assert status in {"NEWER_AVAILABLE", "CHECK_FAILED"}
    assert status != "VERIFIED_CURRENT"
    assert newer is True


def test_unknown_payroll_compare_is_not_verified_current():
    from foundation.sources.federal_tax import evaluate_federal_tax_freshness

    status, newer, _reason = evaluate_federal_tax_freshness(
        inventory_valid=True,
        live={
            "pub15_revision_year": 2026,
            "rev_proc_2025_32_current": True,
            "successor_rev_proc": None,
            "current_pub15_payroll_matches": None,
        },
        live_error=None,
    )
    assert status == "CHECK_FAILED"
    assert newer is None


def test_agreeing_live_discovery_may_be_verified_current():
    from foundation.sources.federal_tax import evaluate_federal_tax_freshness

    status, newer, _reason = evaluate_federal_tax_freshness(
        inventory_valid=True,
        live={
            "pub15_revision_year": 2026,
            "rev_proc_2025_32_current": True,
            "successor_rev_proc": None,
            "current_pub15_payroll_matches": True,
        },
        live_error=None,
    )
    assert status == "VERIFIED_CURRENT"
    assert newer is False


def test_additional_medicare_is_not_invented_from_constants():
    from foundation.sources.federal_tax import parse_additional_medicare

    payroll_without_addl = (
        "The rate of social security tax on taxable wages is 6.2% each. "
        "The Medicare tax rate is 1.45% each."
    )
    assert parse_additional_medicare(payroll_without_addl) is None


def test_pub15_listing_parser_reads_official_2026_row():
    from foundation.sources.federal_tax import parse_pub15_listing

    html = (
        "Publication 15 (2026), (Circular E), Employer&#8217;s Tax Guide "
        '<a href="https://www.irs.gov/pub/irs-pdf/p15.pdf">p15.pdf</a>'
    )
    parsed = parse_pub15_listing(html)
    assert parsed["revision_year"] == 2026
    assert parsed["listed_pdf_url"].endswith("p15.pdf")
