"""Deterministic Gross-Income Tax Engine for Minimum Sustainable Living Cost.

Solves for gross required income G such that:
    G - applicable_taxes(G, state, year) >= CoreNetNeeds

Calculates:
- Employee Social Security Tax (6.2% up to statutory cap)
- Employee Medicare Tax (1.45%)
- Federal Statutory Income Tax (incorporating single standard deduction & marginal brackets)
- State Statutory Income Tax (incorporating state standard deduction & rate schedules for all 50 states + DC)
- Local Income Tax where applicable
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

# States with zero earned income tax
NO_INCOME_TAX_STATES = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}

# State-specific standard deductions and simplified marginal rate schedules (Single Filer)
STATE_TAX_SCHEDULES: dict[str, dict[str, Any]] = {
    "AL": {"deduction": 3000.0, "brackets": [(500.0, 0.02), (3000.0, 0.04), (float("inf"), 0.05)]},
    "AZ": {"deduction": 14600.0, "brackets": [(float("inf"), 0.025)]},
    "AR": {"deduction": 2340.0, "brackets": [(4400.0, 0.02), (8800.0, 0.03), (float("inf"), 0.044)]},
    "CA": {"deduction": 5540.0, "brackets": [(10412.0, 0.01), (24684.0, 0.02), (38959.0, 0.04), (54081.0, 0.06), (68350.0, 0.08), (float("inf"), 0.093)]},
    "CO": {"deduction": 14600.0, "brackets": [(float("inf"), 0.044)]},
    "CT": {"deduction": 0.0, "brackets": [(10000.0, 0.03), (50000.0, 0.05), (100000.0, 0.055), (float("inf"), 0.06)]},
    "DC": {"deduction": 14600.0, "brackets": [(10000.0, 0.04), (40000.0, 0.06), (60000.0, 0.065), (float("inf"), 0.085)]},
    "DE": {"deduction": 3250.0, "brackets": [(2000.0, 0.0), (5000.0, 0.022), (10000.0, 0.039), (20000.0, 0.048), (25000.0, 0.052), (60000.0, 0.0555), (float("inf"), 0.066)]},
    "GA": {"deduction": 12000.0, "brackets": [(float("inf"), 0.0549)]},
    "HI": {"deduction": 2200.0, "brackets": [(2400.0, 0.014), (4800.0, 0.032), (9600.0, 0.055), (14400.0, 0.064), (19200.0, 0.068), (24000.0, 0.072), (36000.0, 0.076), (48000.0, 0.079), (float("inf"), 0.0825)]},
    "IA": {"deduction": 0.0, "brackets": [(float("inf"), 0.038)]},
    "ID": {"deduction": 14600.0, "brackets": [(float("inf"), 0.058)]},
    "IL": {"deduction": 2775.0, "brackets": [(float("inf"), 0.0495)]},
    "IN": {"deduction": 1000.0, "brackets": [(float("inf"), 0.0305)]},
    "KS": {"deduction": 3500.0, "brackets": [(15000.0, 0.031), (30000.0, 0.0525), (float("inf"), 0.057)]},
    "KY": {"deduction": 3160.0, "brackets": [(float("inf"), 0.040)]},
    "LA": {"deduction": 4500.0, "brackets": [(12500.0, 0.0185), (50000.0, 0.035), (float("inf"), 0.0425)]},
    "MA": {"deduction": 4400.0, "brackets": [(float("inf"), 0.050)]},
    "MD": {"deduction": 2550.0, "brackets": [(1000.0, 0.02), (2000.0, 0.03), (3000.0, 0.04), (100000.0, 0.0475), (float("inf"), 0.05)]},
    "ME": {"deduction": 14600.0, "brackets": [(26050.0, 0.058), (61600.0, 0.0675), (float("inf"), 0.0715)]},
    "MI": {"deduction": 5600.0, "brackets": [(float("inf"), 0.0425)]},
    "MN": {"deduction": 14575.0, "brackets": [(31690.0, 0.0535), (104090.0, 0.068), (float("inf"), 0.0785)]},
    "MO": {"deduction": 14600.0, "brackets": [(1273.0, 0.0), (2546.0, 0.02), (3819.0, 0.025), (5092.0, 0.03), (6365.0, 0.035), (7638.0, 0.04), (8911.0, 0.045), (float("inf"), 0.048)]},
    "MS": {"deduction": 2300.0, "brackets": [(10000.0, 0.0), (float("inf"), 0.047)]},
    "MT": {"deduction": 14600.0, "brackets": [(20500.0, 0.047), (float("inf"), 0.059)]},
    "NC": {"deduction": 12750.0, "brackets": [(float("inf"), 0.045)]},
    "ND": {"deduction": 14600.0, "brackets": [(44725.0, 0.0), (225975.0, 0.0195), (float("inf"), 0.025)]},
    "NE": {"deduction": 7900.0, "brackets": [(3700.0, 0.0246), (22100.0, 0.0351), (35000.0, 0.0501), (float("inf"), 0.0584)]},
    "NJ": {"deduction": 1000.0, "brackets": [(20000.0, 0.014), (35000.0, 0.0175), (40000.0, 0.035), (75000.0, 0.05525), (float("inf"), 0.0637)]},
    "NM": {"deduction": 14600.0, "brackets": [(5500.0, 0.017), (11000.0, 0.032), (16000.0, 0.047), (float("inf"), 0.049)]},
    "NY": {"deduction": 8000.0, "brackets": [(8500.0, 0.04), (11700.0, 0.045), (13900.0, 0.0525), (80650.0, 0.055), (float("inf"), 0.06)]},
    "OH": {"deduction": 0.0, "brackets": [(26050.0, 0.0), (100000.0, 0.0275), (float("inf"), 0.035)]},
    "OK": {"deduction": 6350.0, "brackets": [(1000.0, 0.0025), (2500.0, 0.0075), (3750.0, 0.0175), (4900.0, 0.0275), (7200.0, 0.0375), (float("inf"), 0.0475)]},
    "OR": {"deduction": 2745.0, "brackets": [(4050.0, 0.0475), (10200.0, 0.0675), (125000.0, 0.0875), (float("inf"), 0.099)]},
    "PA": {"deduction": 0.0, "brackets": [(float("inf"), 0.0307)]},
    "RI": {"deduction": 10000.0, "brackets": [(73450.0, 0.0375), (166950.0, 0.0475), (float("inf"), 0.0599)]},
    "SC": {"deduction": 14600.0, "brackets": [(3460.0, 0.0), (17330.0, 0.03), (float("inf"), 0.064)]},
    "UT": {"deduction": 0.0, "brackets": [(float("inf"), 0.0465)]},
    "VA": {"deduction": 8500.0, "brackets": [(3000.0, 0.02), (5000.0, 0.03), (17000.0, 0.05), (float("inf"), 0.0575)]},
    "VT": {"deduction": 7400.0, "brackets": [(45400.0, 0.0335), (110050.0, 0.066), (float("inf"), 0.076)]},
    "WI": {"deduction": 13810.0, "brackets": [(14320.0, 0.0354), (28640.0, 0.0465), (315310.0, 0.053), (float("inf"), 0.0765)]},
    "WV": {"deduction": 0.0, "brackets": [(10000.0, 0.0236), (25000.0, 0.0315), (40000.0, 0.0354), (60000.0, 0.0472), (float("inf"), 0.0512)]},
}

# Average material local earnings tax rates by state
LOCAL_TAX_RATES: dict[str, float] = {
    "MD": 0.032,   # County income tax average (~3.2%)
    "IN": 0.0175,  # County income tax average (~1.75%)
    "PA": 0.012,   # Local earned income tax (~1.2%)
    "OH": 0.015,   # Municipal income tax average (~1.5%)
    "MI": 0.005,   # City income tax average (~0.5%)
    "NY": 0.010,   # Local / MCTMT / NYC average contribution (~1.0%)
    "KY": 0.015,   # Occupational license fee average (~1.5%)
    "MO": 0.005,   # St. Louis / Kansas City earnings tax (~0.5%)
}


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
    """Calculate statutory single state income tax for given state."""
    st = state.upper()
    if st in NO_INCOME_TAX_STATES or st == "US":
        return 0.0

    sched = STATE_TAX_SCHEDULES.get(st)
    if not sched:
        # Fallback graduated rule if state not explicitly scheduled
        state_std_ded = 5000.0
        taxable = max(0.0, gross - state_std_ded)
        if taxable <= 0:
            return 0.0
        return taxable * 0.045

    std_ded = sched["deduction"]
    if year == 2026 and std_ded > 0:
        std_ded = round(std_ded * 1.07, 2)  # CPI statutory indexation for 2026

    taxable = max(0.0, gross - std_ded)
    if taxable <= 0:
        return 0.0

    tax = 0.0
    prev_threshold = 0.0
    for threshold, rate in sched["brackets"]:
        if taxable > prev_threshold:
            chunk = min(taxable - prev_threshold, threshold - prev_threshold)
            tax += chunk * rate
            prev_threshold = threshold
        else:
            break
    return tax


def calculate_local_income_tax(gross: float, state: str) -> float:
    """Calculate material local/county income tax if applicable."""
    st = state.upper()
    rate = LOCAL_TAX_RATES.get(st, 0.0)
    return gross * rate


def evaluate_taxes_for_gross(gross: float, state: str, year: int = 2024) -> TaxCalculationResult:
    """Compute all mandatory statutory taxes for a given gross income."""
    ss_tax, med_tax = calculate_fica_taxes(gross, year)
    fed_tax = calculate_federal_income_tax(gross, year)
    state_tax = calculate_state_income_tax(gross, state, year)
    local_tax = calculate_local_income_tax(gross, state)
    total_tax = ss_tax + med_tax + fed_tax + state_tax + local_tax
    net = gross - total_tax

    return TaxCalculationResult(
        gross_income=gross,
        net_income=net,
        fica_social_security=ss_tax,
        fica_medicare=med_tax,
        federal_income_tax=fed_tax,
        state_income_tax=state_tax,
        local_income_tax=local_tax,
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
    high = net_needs * 3.0  # Safe upper bound for tax gross-up

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
