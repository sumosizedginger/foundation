from __future__ import annotations

import json
from foundation.pipeline import run_full_pipeline


def main() -> int:
    print("Executing full Foundation pipeline update...")
    result = run_full_pipeline()
    print("\nUpdate completed successfully.")
    print(f"Population Anchor: ${result['population_anchor']['cutoff']:,.2f}")
    print(f"Survival Floor: ${result['survival_floor']['single_adult_floor_annual']:,.2f} ({result['survival_floor']['status_label']})")
    print(f"Survival Gap: ${result['survival_floor']['survival_gap_annual']:,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
