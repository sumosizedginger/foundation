import pandas as pd

from foundation.bottom30 import calculate_bottom30


def test_bottom30_uses_people_not_raw_household_income():
    # Four person records, each representing a different household for this synthetic test.
    # The $100k household supports 5 people and therefore ranks below the $60k / 2 household.
    frame = pd.DataFrame(
        {
            "HTOTVAL": [36000, 60000, 45000, 100000],
            "H_NUMPER": [1, 2, 3, 5],
            "MARSUPWT": [1, 1, 1, 1],
            "H_SEQ": [1, 2, 3, 4],
        }
    )

    result = calculate_bottom30(frame, survey_year=2025, income_year=2024)
    # Sorted per-person: 15k, 20k, 30k, 36k.
    # 30% of total weight 4 = 1.2 -> second observation.
    assert result.cutoff == 20000


def test_bottom30_weight_can_change_cutoff():
    frame = pd.DataFrame(
        {
            "HTOTVAL": [10000, 20000, 30000],
            "H_NUMPER": [1, 1, 1],
            "MARSUPWT": [1, 8, 1],
            "H_SEQ": [1, 2, 3],
        }
    )

    result = calculate_bottom30(frame, survey_year=2025, income_year=2024)
    assert result.cutoff == 20000
