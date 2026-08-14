from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foundation")
    sub = parser.add_subparsers(dest="command", required=True)

    update_cmd = sub.add_parser("update", help="Run the full deterministic calculation pipeline")
    update_cmd.add_argument("--all", action="store_true", help="Process all vintages and signals")

    sub.add_parser("validate", help="Run configuration and data validation")
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
    from foundation.pipeline import run_full_pipeline

    print("Running Foundation full pipeline...")
    result = run_full_pipeline()
    pop = result["population_anchor"]
    surv = result["survival_floor"]
    health = result["data_health"]
    print("\n=== PIPELINE SUCCESSFUL ===")
    print(
        f"Population Anchor (2024): ${pop['cutoff']:,.2f}/yr "
        f"(${pop.get('monthly_cutoff', pop['cutoff'] / 12):,.2f}/mo)"
    )
    print(
        "Minimum Sustainable Living Cost: "
        f"{surv.get('status_label', surv.get('status', 'UNAVAILABLE'))}"
    )
    print("Survival Gap:             not published (Axis 2 unpublished)")
    print("Adequacy:                 not published (Axis 2 unpublished)")
    print(f"Data Health:              {health.get('status', 'PARTIAL')}")
    print(f"Pressure signals:         {len(result.get('pressures', []))} observations")
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
