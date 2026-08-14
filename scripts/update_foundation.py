from __future__ import annotations

from foundation.pipeline import run_full_pipeline


def main() -> int:
    print("Executing full Foundation pipeline update...")
    result = run_full_pipeline()
    surv = result["survival_floor"]
    lc_2024 = surv["minimum_sustainable_living_cost_2024"].get("weighted_median_gross")
    lc_2026 = surv["minimum_sustainable_living_cost_2026"].get("weighted_median_gross")

    print("\nUpdate completed successfully.")
    print(f"Population Anchor (2024 Income): ${result['population_anchor']['cutoff']:,.2f}")
    if lc_2024 is not None:
        print(
            f"Minimum Sustainable Living Cost (2024 National Weighted Median): ${lc_2024:,.2f} ({surv['status_label']})"
        )
        print(
            f"Time-Comparable 2024 Survival Gap: ${surv['survival_gap_2024']:,.2f} (Adequacy Ratio: {surv['adequacy_ratio_2024']:.2f})"
        )
    else:
        print(f"Minimum Sustainable Living Cost: {surv['status_label']}")
    if lc_2026 is not None:
        print(
            f"Current Minimum Sustainable Living Cost (2026 National Weighted Median): ${lc_2026:,.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
