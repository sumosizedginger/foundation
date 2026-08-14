from foundation.historical import (
    adjust_to_constant_dollars,
    get_historical_vintages_summary,
)


def test_adjust_to_constant_dollars():
    # In 2022, CPI-U = 292.655; In 2024, CPI-U = 314.072
    # $19,304.60 * (314.072 / 292.655) = $20,717.34
    res_2022 = adjust_to_constant_dollars(19304.60, 2022, 2024)
    assert res_2022 == 20717.34

    # Same year adjustment is identical
    assert adjust_to_constant_dollars(21800.00, 2024, 2024) == 21800.00


def test_historical_vintages_summary():
    vintages = get_historical_vintages_summary()
    assert len(vintages) == 3

    # Check 2022 vintage
    v2022 = vintages[0]
    assert v2022.income_year == 2022
    assert v2022.survey_year == 2023
    assert v2022.nominal_cutoff == 19304.60
    assert v2022.constant_2024_dollars == 20717.34

    # Check 2024 vintage
    v2024 = vintages[2]
    assert v2024.income_year == 2024
    assert v2024.survey_year == 2025
    assert v2024.nominal_cutoff == 21800.00
    assert v2024.constant_2024_dollars == 21800.00
