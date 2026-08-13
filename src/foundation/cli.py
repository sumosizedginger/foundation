from __future__ import annotations

import argparse
import json
from pathlib import Path

from foundation.pipeline import run_full_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundation")
    sub = parser.add_subparsers(dest="command", required=True)

    update_cmd = sub.add_parser("update", help="Run the full deterministic calculation pipeline")
    update_cmd.add_argument("--all", action="store_true", help="Process all vintages and signals")

    validate = sub.add_parser("validate", help="Run configuration and data validation")
    return parser


def cmd_validate() -> int:
    from foundation.config import definitions, indicators, sources, weights

    definitions()
    indicators()
    sources()
    weights()
    print("Configuration validation passed.")
    return 0


def cmd_update() -> int:
    print("Running Foundation full pipeline...")
    result = run_full_pipeline()
    pop = result["population_anchor"]
    surv = result["survival_floor"]
    print("\n=== PIPELINE SUCCESSFUL ===")
    print(f"Population Anchor (2024): ${pop['cutoff']:,.2f}/yr (${pop['monthly_cutoff']:,.2f}/mo)")
    print(f"Survival Floor:           ${surv['single_adult_floor_annual']:,.2f}/yr ({surv['status_label']})")
    print(f"Survival Gap:             ${surv['survival_gap_annual']:,.2f}/yr (Adequacy: {surv['adequacy_ratio']:.2f})")
    print(f"Pressure signals:         {len(result['pressures'])} observations")
    print(f"Composite score:          {result['composite']['status'].upper()} (Locked)")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "validate":
        return cmd_validate()

    if args.command == "update":
        return cmd_update()

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
