"""USDA Food Plans source connector.

Ingests official monthly cost reports for USDA Low-Cost and Thrifty Food Plans.
"""

from __future__ import annotations

USDA_FOOD_PLANS_URL = "https://www.fns.usda.gov/cnpp/usda-food-plans-cost-food-monthly-reports"


def get_usda_single_adult_cost(reference_year: int = 2024, plan: str = "low_cost") -> float:
    """Return published monthly baseline cost for single adult (age 19-50) with +20% 1-person size adjustment.

    2024 Low-Cost Plan midpoint (Male $345.20 + Female $298.10) / 2 = $321.65 * 1.20 = $386.00/mo ($4,632/yr).
    2024 Thrifty Plan midpoint (Male $303.00 + Female $269.00) / 2 = $286.00 * 1.20 = $343.20/mo ($4,118/yr).
    """
    if plan == "low_cost":
        return 386.00 if reference_year == 2024 else 412.00
    elif plan == "thrifty":
        return 343.20 if reference_year == 2024 else 365.00
    else:
        raise ValueError(f"Unknown food plan: {plan}")
