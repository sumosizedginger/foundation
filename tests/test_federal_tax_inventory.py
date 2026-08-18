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
