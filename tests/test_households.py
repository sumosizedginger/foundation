import pandas as pd

from foundation.households import prepare_person_records


def test_per_person_household_income():
    df = pd.DataFrame(
        {
            "HTOTVAL": [36000, 60000, 45000, 100000],
            "H_NUMPER": [1, 2, 3, 5],
            "MARSUPWT": [1, 1, 1, 1],
            "H_SEQ": [1, 2, 3, 4],
        }
    )

    prepared, report = prepare_person_records(df)

    assert prepared["household_income_per_person"].tolist() == [
        36000,
        30000,
        15000,
        20000,
    ]
    assert report.excluded_records == 0


def test_negative_income_is_retained():
    df = pd.DataFrame(
        {
            "HTOTVAL": [-10000],
            "H_NUMPER": [2],
            "MARSUPWT": [1],
            "H_SEQ": [1],
        }
    )

    prepared, report = prepare_person_records(df)
    assert prepared.iloc[0]["household_income_per_person"] == -5000
    assert report.valid_records == 1


def test_invalid_household_size_excluded():
    df = pd.DataFrame(
        {
            "HTOTVAL": [10000, 20000],
            "H_NUMPER": [0, 2],
            "MARSUPWT": [1, 1],
            "H_SEQ": [1, 2],
        }
    )

    prepared, report = prepare_person_records(df)
    assert len(prepared) == 1
    assert report.invalid_household_size == 1


def test_invalid_weight_excluded():
    df = pd.DataFrame(
        {
            "HTOTVAL": [10000, 20000],
            "H_NUMPER": [1, 2],
            "MARSUPWT": [0, 1],
            "H_SEQ": [1, 2],
        }
    )

    prepared, report = prepare_person_records(df)
    assert len(prepared) == 1
    assert report.invalid_weight == 1
