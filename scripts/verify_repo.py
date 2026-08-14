from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    required = [
        "AGENT.md",
        "PRD.md",
        "CONTEXT.md",
        "METHODOLOGY.md",
        "VALIDATION.md",
        "DECISIONS.md",
        "LICENSE",
        "LICENSING.md",
        "config/definitions.yml",
        "config/sources.yml",
        "config/indicators.yml",
        "data/current/latest.json",
        "data/current/population.json",
        "data/current/survival.json",
        "data/current/pressures.json",
        "data/current/history.json",
        "data/current/living_cost_2024.json",
        "data/current/living_cost_2026.json",
        "data/current/state_living_costs_2024.json",
        "data/current/state_living_costs_2026.json",
        "data/metadata/validation_report_2025.json",
        "data/metadata/validation_report_2024.json",
        "data/metadata/validation_report_2023.json",
        "site/index.html",
        "site/methodology.html",
        "site/sources.html",
        "site/history.html",
        "site/404.html",
        "site/robots.txt",
        "site/sitemap.xml",
        "site/site.webmanifest",
        "site/assets/app.css",
        "site/assets/app.js",
        "site/assets/favicon.svg",
        "site/assets/og-preview.svg",
        "site/data/latest.json",
    ]
    missing = [rel for rel in required if not (ROOT / rel).exists()]
    if missing:
        raise SystemExit(f"Missing required project files: {missing}")

    for rel in ("config/definitions.yml", "config/sources.yml", "config/indicators.yml"):
        with (ROOT / rel).open("r", encoding="utf-8") as fh:
            yaml.safe_load(fh)

    with (ROOT / "data/current/latest.json").open("r", encoding="utf-8") as fh:
        latest = json.load(fh)

    if latest["project"]["composite_release_enabled"]:
        raise SystemExit("Composite score cannot be enabled in starter/prelaunch state")

    if latest["composite"]["status"] != "prelaunch":
        raise SystemExit("Composite status must remain locked in prelaunch")

    if latest["population_anchor"]["cutoff"] != 21800.00:
        raise SystemExit(f"Unexpected Population Anchor cutoff: {latest['population_anchor']['cutoff']}")

    surv_status = latest["survival_floor"]["status"]
    if surv_status not in ("pipeline_validation_in_progress", "research_estimate"):
        raise SystemExit(f"Survival floor must be pipeline_validation_in_progress or research_estimate, got: {surv_status}")

    print("Repository structural, schema, living cost, and release-gate verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
