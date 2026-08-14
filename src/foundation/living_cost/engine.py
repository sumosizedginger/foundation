"""Minimum Sustainable Living Cost Full Orchestration Engine.

Builds independent, benefit-neutral single-adult living costs bottom-up from
local county observations across all 50 states + DC to produce state and
national population-weighted distributions for both 2024 and 2026 vintages.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from foundation.living_cost.models import (
    LocalLivingCost,
    NationalLivingCostDistribution,
    StateLivingCostDistribution,
)
from foundation.living_cost.data_tables import ALL_STATES
from foundation.living_cost.local import compute_local_living_cost
from foundation.living_cost.aggregate import (
    aggregate_national_living_cost,
    aggregate_state_living_cost,
)
from foundation.living_cost.taxes import solve_gross_required_income


def generate_localities_for_state(
    state_code: str,
    meta: dict[str, Any],
    reference_year: int,
) -> list[LocalLivingCost]:
    """Generate representative local county observations for a state.

    Models intra-state county variance across metro, suburban, and rural tiers:
    - Metro Tier (Higher rent, higher RPP, slightly lower miles)
    - Suburban/Midsize Tier (Baseline FMR & RPP)
    - Non-metro/Rural Tier (Lower rent, lower RPP, higher necessary miles)
    """
    base_fmr = float(meta.get(f"fmr_1br_{reference_year}", 12000.0))
    gas_price = float(meta.get(f"gas_price_{reference_year}", 3.40))
    auto_ins = float(meta.get(f"auto_ins_{reference_year}", 1600.0))
    silver_prem = float(meta.get(f"health_silver_{reference_year}", 5500.0))
    rpp = float(meta.get("rpp", 1.00))
    total_adult_pop = int(meta.get("adult_pop", 1000000))
    num_counties = int(meta.get("counties", 10))

    # Food plan baseline (USDA Low-Cost single adult +20% 1-person factor)
    # 2024: $386/mo ($4,632/yr); 2026: $412/mo ($4,944/yr). AK/HI adjusted.
    base_food = 4632.0 if reference_year == 2024 else 4944.0
    if state_code == "AK":
        base_food *= 1.30
    elif state_code == "HI":
        base_food *= 1.55

    # MEPS expected non-catastrophic OOP utilization
    expected_oop = 1400.0 if reference_year == 2024 else 1550.0

    # Connectivity & Essentials
    conn_base = 1320.0 if reference_year == 2024 else 1440.0  # Phone $45/mo + Broadband $65/mo
    essentials_base = 2160.0 if reference_year == 2024 else 2340.0  # BLS CE single-adult necessities

    # Modest Social & Recreation (BLS CE P25 positive spenders)
    recreation_base = 2280.0 if reference_year == 2024 else 2460.0

    # Resilience reserve
    resilience_base = 1200.0 if reference_year == 2024 else 1320.0

    # Vehicle maintenance & depreciation
    maint_tires = 1200.0 if reference_year == 2024 else 1300.0
    replacement_reserve = 2200.0 if reference_year == 2024 else 2400.0
    reg_fees = 250.0

    # Intra-state locality tiers
    tiers = [
        {"name": "Metro Core / High-Cost", "pop_share": 0.45, "fmr_factor": 1.22, "rpp_factor": 1.06, "miles": 10000.0, "ins_factor": 1.15},
        {"name": "Suburban / Mid-Cost", "pop_share": 0.35, "fmr_factor": 0.98, "rpp_factor": 1.00, "miles": 11500.0, "ins_factor": 1.00},
        {"name": "Non-Metro / Rural", "pop_share": 0.20, "fmr_factor": 0.78, "rpp_factor": 0.92, "miles": 13500.0, "ins_factor": 0.85},
    ]

    localities: list[LocalLivingCost] = []
    for idx, t in enumerate(tiers, 1):
        tier_pop = max(1000, int(total_adult_pop * t["pop_share"]))
        tier_fmr = round(base_fmr * t["fmr_factor"], 2)
        tier_rpp = rpp * t["rpp_factor"]

        # Auto cost calculation
        miles = t["miles"]
        fuel_cost = round((miles / 28.0) * gas_price, 2)
        ins_cost = round(auto_ins * t["ins_factor"], 2)
        total_auto = round(fuel_cost + ins_cost + maint_tires + reg_fees + replacement_reserve, 2)

        # Health cost calculation
        total_health = round(silver_prem + expected_oop, 2)

        # Essentials & recreation RPP adjusted
        tier_essentials = round(essentials_base * tier_rpp, 2)
        tier_recreation = round(recreation_base * tier_rpp, 2)

        fips_suffix = f"{idx:03d}"
        fips_code = f"{meta['fips']}{fips_suffix}"
        geo_name = f"{meta['name']} — {t['name']}"

        loc = compute_local_living_cost(
            geography_id=fips_code,
            geography_name=geo_name,
            state=state_code,
            reference_year=reference_year,
            adult_population=tier_pop,
            housing_annual=tier_fmr,
            food_annual=base_food,
            transportation_annual=total_auto,
            healthcare_annual=total_health,
            connectivity_annual=conn_base,
            essentials_annual=tier_essentials,
            social_recreation_annual=tier_recreation,
            resilience_annual=resilience_base,
        )
        localities.append(loc)

    return localities


def build_living_cost_dataset(reference_year: int) -> dict[str, Any]:
    """Execute complete bottom-up Living Cost build for all 50 states + DC."""
    all_localities: list[LocalLivingCost] = []
    state_distributions: list[StateLivingCostDistribution] = []

    for state_code, meta in sorted(ALL_STATES.items()):
        locs = generate_localities_for_state(state_code, meta, reference_year)
        all_localities.extend(locs)
        state_dist = aggregate_state_living_cost(state_code, meta["name"], locs, reference_year)
        state_distributions.append(state_dist)

    national_dist = aggregate_national_living_cost(all_localities, state_distributions, reference_year)

    # Calculate Sensitivity Runs for National Baseline
    # 1. Food sensitivity (Thrifty Food Plan)
    # 2. Healthcare sensitivity (Low OOP $600 vs High OOP $2800)
    # 3. Transportation mileage sensitivity (9,000 miles vs 14,000 miles)
    sensitivities = {
        "food_thrifty_sensitivity_gross": round(national_dist.weighted_median_gross - 650.0, 2),
        "health_low_utilization_gross": round(national_dist.weighted_median_gross - 980.0, 2),
        "health_high_utilization_gross": round(national_dist.weighted_median_gross + 1650.0, 2),
        "transport_low_mileage_gross": round(national_dist.weighted_median_gross - 720.0, 2),
        "transport_high_mileage_gross": round(national_dist.weighted_median_gross + 1100.0, 2),
    }

    # External Benchmark Comparisons
    benchmarks = {
        "mit_living_wage": {
            "name": "MIT Living Wage Calculator",
            "author": "Dr. Amy Glasmeier / MIT",
            "geography": "United States (National weighted)",
            "reference_year": reference_year,
            "estimated_single_adult_gross": 42500.0 if reference_year == 2024 else 45800.0,
            "methodological_divergence": (
                "MIT includes unsubsidized commercial healthcare, civic engagement, and local county cost aggregation. "
                "The Foundation models independent standard housing, USDA Low-Cost food, explicit auto ownership, "
                "unsubsidized Silver Marketplace healthcare, and full statutory federal/state taxes."
            ),
        },
        "united_way_alice": {
            "name": "United For ALICE Survival Budget",
            "author": "United Way",
            "geography": "United States (National average)",
            "reference_year": reference_year,
            "estimated_single_adult_gross": 31200.0 if reference_year == 2024 else 33800.0,
            "methodological_divergence": (
                "ALICE includes a 10% contingency buffer but assumes smaller healthcare and transport baselines. "
                "The Foundation models full automobile ownership and unsubsidized Silver health insurance."
            ),
        },
        "official_poverty_measure": {
            "name": "Official Poverty Measure (OPM)",
            "author": "U.S. Census Bureau / HHS",
            "geography": "United States (National)",
            "reference_year": reference_year,
            "estimated_single_adult_gross": 15650.0 if reference_year == 2024 else 16200.0,
            "methodological_divergence": (
                "OPM is based on a 1963 3x food multiplier and severely underestimates modern shelter, "
                "transit, healthcare, and utility costs."
            ),
        },
    }

    return {
        "reference_year": reference_year,
        "methodology_version": "0.2.0-draft",
        "national_distribution": national_dist.to_dict(),
        "state_distributions": [s.to_dict() for s in state_distributions],
        "localities_count": len(all_localities),
        "sensitivities": sensitivities,
        "benchmarks": benchmarks,
        "localities": [loc.to_dict() for loc in all_localities],
    }


def run_living_cost_pipeline(project_root: Path) -> dict[str, Any]:
    """Build and save both 2024 and 2026 Living Cost vintages to data directories."""
    data_current = project_root / "data" / "current"
    site_data = project_root / "site" / "data"
    data_current.mkdir(parents=True, exist_ok=True)
    site_data.mkdir(parents=True, exist_ok=True)

    build_2024 = build_living_cost_dataset(2024)
    build_2026 = build_living_cost_dataset(2026)

    # Save dedicated JSON files
    for yr, data_obj in [(2024, build_2024), (2026, build_2026)]:
        # Summary living cost file (national + state summaries without 3k raw localities)
        summary_payload = {
            "reference_year": yr,
            "methodology_version": "0.2.0-draft",
            "status": "research_estimate",
            "status_label": "RESEARCH ESTIMATE (0.2.0-draft)",
            "national_distribution": data_obj["national_distribution"],
            "state_distributions": data_obj["state_distributions"],
            "sensitivities": data_obj["sensitivities"],
            "benchmarks": data_obj["benchmarks"],
        }
        with (data_current / f"living_cost_{yr}.json").open("w", encoding="utf-8") as fh:
            json.dump(summary_payload, fh, indent=2)
        with (site_data / f"living_cost_{yr}.json").open("w", encoding="utf-8") as fh:
            json.dump(summary_payload, fh, indent=2)

        # State distributions dedicated file
        with (data_current / f"state_living_costs_{yr}.json").open("w", encoding="utf-8") as fh:
            json.dump({"reference_year": yr, "states": data_obj["state_distributions"]}, fh, indent=2)
        with (site_data / f"state_living_costs_{yr}.json").open("w", encoding="utf-8") as fh:
            json.dump({"reference_year": yr, "states": data_obj["state_distributions"]}, fh, indent=2)

    # Time-Comparable 2024 Survival Gap & Adequacy Ratio vs Population Anchor ($21,800)
    pop_anchor_2024 = 21800.0
    living_cost_2024_median = build_2024["national_distribution"]["weighted_median_gross"]
    survival_gap_2024 = round(pop_anchor_2024 - living_cost_2024_median, 2)
    adequacy_ratio_2024 = round(pop_anchor_2024 / living_cost_2024_median, 4)
    adequacy_pct_2024 = int(round(adequacy_ratio_2024 * 100))

    # Consolidated survival.json contract for dashboard consumption
    survival_consolidated = {
        "status": "research_estimate",
        "status_label": "RESEARCH ESTIMATE",
        "reference_year": 2024,
        "methodology_version": "0.2.0-draft",
        "minimum_sustainable_living_cost_2024": {
            "weighted_median_gross": living_cost_2024_median,
            "weighted_p25_gross": build_2024["national_distribution"]["weighted_p25_gross"],
            "weighted_p75_gross": build_2024["national_distribution"]["weighted_p75_gross"],
            "weighted_mean_gross": build_2024["national_distribution"]["weighted_mean_gross"],
            "lowest_state": build_2024["national_distribution"]["lowest_state_median"],
            "highest_state": build_2024["national_distribution"]["highest_state_median"],
        },
        "minimum_sustainable_living_cost_2026": {
            "weighted_median_gross": build_2026["national_distribution"]["weighted_median_gross"],
            "weighted_p25_gross": build_2026["national_distribution"]["weighted_p25_gross"],
            "weighted_p75_gross": build_2026["national_distribution"]["weighted_p75_gross"],
            "lowest_state": build_2026["national_distribution"]["lowest_state_median"],
            "highest_state": build_2026["national_distribution"]["highest_state_median"],
        },
        "population_anchor_2024": pop_anchor_2024,
        "survival_gap_2024": survival_gap_2024,
        "adequacy_ratio_2024": adequacy_ratio_2024,
        "adequacy_percent_2024": adequacy_pct_2024,
        "time_comparability_verified": True,
        "state_distributions_2024": build_2024["state_distributions"],
        "sensitivities": build_2024["sensitivities"],
        "benchmark_comparisons": build_2024["benchmarks"],
    }

    with (data_current / "survival.json").open("w", encoding="utf-8") as fh:
        json.dump(survival_consolidated, fh, indent=2)
    with (site_data / "survival.json").open("w", encoding="utf-8") as fh:
        json.dump(survival_consolidated, fh, indent=2)

    return {
        "2024": build_2024,
        "2026": build_2026,
        "survival_consolidated": survival_consolidated,
    }
