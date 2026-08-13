from pathlib import Path
import pytest
from foundation.bottom30 import calculate_bottom30_from_zip


@pytest.mark.integration
def test_real_2025_asec_archive():
    project_root = Path(__file__).resolve().parents[1]
    archive_2025 = project_root / ".cache" / "census" / "asecpub25csv.zip"
    if not archive_2025.exists():
        pytest.skip("Live 2025 CPS ASEC archive not present in local cache")

    result = calculate_bottom30_from_zip(archive_2025, survey_year=2025, income_year=2024)
    assert result.cutoff == 21800.00
    assert result.valid_records == 142125
    assert result.represented_population == 337689642
