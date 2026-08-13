from pathlib import Path
from unittest.mock import patch
import pandas as pd
import pytest

from foundation.pipeline import run_full_pipeline
from foundation.models import Bottom30Result, SourceArtifact


def test_pipeline_with_mocked_archive(tmp_path: Path):
    fixture_csv = Path(__file__).resolve().parent / "fixtures" / "sample_asec.csv"
    assert fixture_csv.exists()

    df = pd.read_csv(fixture_csv)

    def mock_extract_and_merge(zip_path, survey_year):
        return df, {
            "archive_filename": zip_path.name,
            "sha256": "mock_sha256",
            "bytes": 1000,
            "survey_year": survey_year,
            "household_records": 5,
            "person_records": 12,
            "matched_person_records": 12,
            "unmatched_person_records": 0,
            "unmatched_household_records": 0,
            "duplicate_household_keys": 0,
        }

    # Create dummy cache files
    cache_dir = tmp_path / ".cache" / "census"
    cache_dir.mkdir(parents=True)
    for yy in ["23", "24", "25"]:
        (cache_dir / f"asecpub{yy}csv.zip").write_text("dummy zip content")

    with patch("foundation.sources.census_asec.extract_and_merge_asec_zip", side_effect=mock_extract_and_merge):
        result = run_full_pipeline(project_root=tmp_path)

        assert result["project"]["name"] == "The Foundation"
        assert result["composite"]["status"] == "prelaunch"
        assert (tmp_path / "data" / "current" / "latest.json").exists()
        assert (tmp_path / "data" / "current" / "population.json").exists()
        assert (tmp_path / "data" / "current" / "survival.json").exists()
        assert (tmp_path / "data" / "current" / "pressures.json").exists()
        assert (tmp_path / "data" / "current" / "history.json").exists()
