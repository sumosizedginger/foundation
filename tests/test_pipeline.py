from pathlib import Path
import pytest
from foundation.pipeline import run_full_pipeline


def test_full_pipeline_execution():
    project_root = Path(__file__).resolve().parents[1]
    result = run_full_pipeline(project_root)

    assert result["project"]["name"] == "The Foundation"
    assert result["project"]["stage"] == "prelaunch"
    assert result["composite"]["status"] == "prelaunch"
    assert result["composite"]["score"] is None

    # Population Anchor checks
    pop = result["population_anchor"]
    assert pop["cutoff"] == 21800.00
    assert pop["income_year"] == 2024
    assert pop["survey_year"] == 2025
    assert pop["status"] == "measured"
    assert "P10" in pop["quantiles"]
    assert "P90" in pop["quantiles"]

    # Survival Floor checks
    surv = result["survival_floor"]
    assert surv["status"] == "research_estimate"
    assert surv["single_adult_floor_annual"] == 27960.00
    assert surv["survival_gap_annual"] == -6160.00
    assert len(surv["household_matrix"]) == 5

    # Check generated files exist
    assert (project_root / "data" / "current" / "latest.json").exists()
    assert (project_root / "data" / "current" / "population.json").exists()
    assert (project_root / "data" / "current" / "survival.json").exists()
    assert (project_root / "data" / "current" / "pressures.json").exists()
    assert (project_root / "data" / "current" / "history.json").exists()
    assert (project_root / "data" / "metadata" / "validation_report_2025.json").exists()
