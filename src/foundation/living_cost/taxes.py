"""Deterministic Gross-Income Tax Engine for Minimum Sustainable Living Cost.

Solves for gross required income G such that:
    G - applicable_taxes(G, state, year) >= CoreNetNeeds

Calculates:
- Employee Social Security Tax (6.2% up to cap)
- Employee Medicare Tax (1.45%)
- Federal Statutory Income Tax (incorporating standard deduction & marginal brackets)
- State Statutory Income Tax (incorporating state deductions & rate schedules)
- Zero means-tested subsidies or refundable credits applied.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any

# Statutory Federal Tax Schedules by Reference Year (Single Filer)
FEDERAL_TAX_RULES = {
    2024: {
        "standard_deduction": 14600.0,
        "ss_tax_rate": 0.062,
        "ss_wage_cap": 168600.0,
        "medicare_rate": 0.0145,
        "brackets": [
            (11600.0, 0.10),
            (47150.0, 0.12),
            (100525.0, 0.22),
            (191950.0, 0.24),
            (243725.0, 0.32),
            (609350.0, 0.35),
            (float("inf"), 0.37),
        ],
    },
    2026: {
        "standard_deduction": 15700.0,
        "ss_tax_rate": 0.062,
        "ss_wage_cap": 176100.0,
        "medicare_rate": 0.0145,
        "brackets": [
            (12400.0, 0.10),
            (50400.0, 0.12),
            (107400.0, 0.22),
            (205050.0, 0.24),
            (260350.0, 0.32),
            (651000.0, 0.35),
            (float("inf"), 0.37),
        ],
    },
}

# Simplified Representative State Income Tax Rules (Standard deduction + progressive/flat top rate)
# States with zero earned income tax: AK, FL, NV, NH, SD, TN, TX, WA, WY
NO_INCOME_TAX_STATES = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}


@dataclass(frozen=True)
class TaxCalculationResult:
    gross_income: float
    net_income: float
    fica_social_security: float
    fica_medicare: float
    federal_income_tax: float
    state_income_tax: float
    local_income_tax: float
    total_tax: float

    def to_dict(self) -> dict[str, float]:
        return {
            "gross_income": round(self.gross_income, 2),
            "net_income": round(self.net_income, 2),
            "fica_social_security": round(self.fica_social_security, 2),
            "fica_medicare": round(self.fica_medicare, 2),
            "federal_income_tax": round(self.federal_income_tax, 2),
            "state_income_tax": round(self.state_income_tax, 2),
            "local_income_tax": round(self.local_income_tax, 2),
            "total_tax": round(self.total_tax, 2),
        }


def calculate_federal_income_tax(gross: float, year: int = 2024) -> float:
    """Calculate statutory single federal income tax with standard deduction."""
    rules = FEDERAL_TAX_RULES.get(year, FEDERAL_TAX_RULES[2024])
    taxable = max(0.0, gross - rules["standard_deduction"])
    if taxable <= 0:
        return 0.0

    tax = 0.0
    prev_threshold = 0.0
    for threshold, rate in rules["brackets"]:
        if taxable > prev_threshold:
            chunk = min(taxable - prev_threshold, threshold - prev_threshold)
            tax += chunk * rate
            prev_threshold = threshold
        else:
            break
    return tax


def calculate_fica_taxes(gross: float, year: int = 2024) -> tuple[float, float]:
    """Calculate employee Social Security and Medicare FICA taxes."""
    rules = FEDERAL_TAX_RULES.get(year, FEDERAL_TAX_RULES[2024])
    ss_taxable = min(gross, rules["ss_wage_cap"])
    ss_tax = ss_taxable * rules["ss_tax_rate"]
    medicare_tax = gross * rules["medicare_rate"]
    return ss_tax, medicare_tax


def calculate_state_income_tax(gross: float, state: str, year: int = 2024) -> float:
    """Calculate statutory single state income tax."""
    st = state.upper()
    if st in NO_INCOME_TAX_STATES or st == "US":
        return 0.0

    # Representative effective state rate model (baseline state progressive schedule)
    # Average state standard deduction ~$5,000; graduated marginal rates 3.0% to 5.5%
    state_std_ded = 5000.0
    taxable = max(0.0, gross - state_std_ded)
    if taxable <= 0:
        return 0.0

    if taxable <= 10000.0:
        return taxable * 0.03
    elif taxable <= 50000.0:
        return 300.0 + (taxable - 10000.0) * 0.045
    else:
        return 2100.0 + (taxable - 50000.0) * 0.0575


def evaluate_taxes_for_gross(gross: float, state: str, year: int = 2024) -> TaxCalculationResult:
    """Compute all mandatory statutory taxes for a given gross income."""
    ss_tax, med_tax = calculate_fica_taxes(gross, year)
    fed_tax = calculate_federal_income_tax(gross, year)
    state_tax = calculate_state_income_tax(gross, state, year)
    total_tax = ss_tax + med_tax + fed_tax + state_tax
    net = gross - total_tax

    return TaxCalculationResult(
        gross_income=gross,
        net_income=net,
        fica_social_security=ss_tax,
        fica_medicare=med_tax,
        federal_income_tax=fed_tax,
        state_income_tax=state_tax,
        local_income_tax=0.0,
        total_tax=total_tax,
    )


def solve_gross_required_income(
    net_needs: float,
    state: str = "US",
    year: int = 2024,
    tolerance: float = 0.01,
    max_iter: int = 100,
) -> TaxCalculationResult:
    """Solve for gross required income G using deterministic bisection."""
    if net_needs <= 0:
        return evaluate_taxes_for_gross(0.0, state, year)

    low = net_needs
    high = net_needs * 2.5  # Safe upper bound for tax gross-up

    for _ in range(max_iter):
        mid = (low + high) / 2.0
        res = evaluate_taxes_for_gross(mid, state, year)
        diff = res.net_income - net_needs

        if abs(diff) <= tolerance:
            return res
        elif diff < 0:
            low = mid
        else:
            high = mid

    return evaluate_taxes_for_gross((low + high) / 2.0, state, year)
