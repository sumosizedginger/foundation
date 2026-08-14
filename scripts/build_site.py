from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PUBLIC_DATA = SITE / "data"
CURRENT = ROOT / "data" / "current"
METADATA = ROOT / "data" / "metadata"


def validate_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)

    json_files = [
        "latest.json",
        "population.json",
        "survival.json",
        "pressures.json",
        "history.json",
        "living_cost_2024.json",
        "living_cost_2026.json",
        "state_living_costs_2024.json",
        "state_living_costs_2026.json",
    ]
    for fname in json_files:
        src = CURRENT / fname
        if src.exists():
            validate_json(src)
            shutil.copy2(src, PUBLIC_DATA / fname)
            print(f"Copied {fname} to {PUBLIC_DATA}")

    # Copy validation reports
    if METADATA.exists():
        for report_file in METADATA.glob("validation_report_*.json"):
            validate_json(report_file)
            shutil.copy2(report_file, PUBLIC_DATA / report_file.name)
            print(f"Copied {report_file.name} to {PUBLIC_DATA}")

    print(f"Successfully built static site data into {PUBLIC_DATA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
