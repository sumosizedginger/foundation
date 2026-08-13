from foundation.config import definitions, indicators, sources, weights


def test_configs_load():
    assert definitions()["bottom_30"]["percentile"] == 0.30
    assert "census_asec" in sources()["sources"]
    assert "bottom30_cutoff" in indicators()["indicators"]
    assert weights()["rules"]["composite_release_enabled"] is False
