from foundation.sources.bls import REGISTERED_BLS_SERIES, get_economic_pressure_signals


def test_registered_bls_series_registry():
    assert "LNS13327709" in REGISTERED_BLS_SERIES
    assert "LNS11300000" in REGISTERED_BLS_SERIES
    assert "LNS12300000" in REGISTERED_BLS_SERIES
    assert "LNS15026639" in REGISTERED_BLS_SERIES
    assert "CUSR0000SA0" in REGISTERED_BLS_SERIES
    assert "CUSR0000SAH1" in REGISTERED_BLS_SERIES
    assert "CUSR0000SAF11" in REGISTERED_BLS_SERIES
    assert "CUSR0000SAM" in REGISTERED_BLS_SERIES
    assert "CUSR0000SETB01" in REGISTERED_BLS_SERIES


def test_get_economic_pressure_signals():
    signals = get_economic_pressure_signals()
    assert len(signals) >= 9

    u6_sig = next((s for s in signals if s.series_id == "LNS13327709"), None)
    assert u6_sig is not None
    assert u6_sig.unit == "percent"
    assert u6_sig.direction_desired == "lower_is_better"
    assert u6_sig.publisher == "U.S. Bureau of Labor Statistics"
    assert "National Economic Pressure Signal" in u6_sig.notes
