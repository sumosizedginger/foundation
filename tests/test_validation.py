import pandas as pd
import pytest

from foundation.validation import ValidationError, require_columns, validate_bottom30_prepared


def test_require_columns_raises():
    with pytest.raises(ValidationError):
        require_columns(pd.DataFrame({"x": [1]}), ["x", "y"])


def test_negative_income_is_info_not_failure():
    frame = pd.DataFrame(
        {
            "household_income_per_person": [-5, 10],
            "person_weight": [1, 1],
        }
    )
    messages = validate_bottom30_prepared(frame)
    assert any(m.code == "negative-income-retained" for m in messages)
