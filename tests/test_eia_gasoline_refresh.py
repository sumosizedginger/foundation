"""EIA weekly gasoline currentness. Does not calculate an MSLC."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from foundation.living_cost.freshness_currentness import eia_currentness_status
from foundation.sources.eia import (
    EIA_GAS_XLS_URL,
    max_eia_observation_date,
    parse_eia_gas_prices_xls,
)

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "pswrgvwall.xls"
FRESHNESS = ROOT / "data" / "metadata" / "living_cost_candidate_freshness.json"


def test_matching_official_and_selected_eia_is_verified_current():
    result = eia_currentness_status(
        official_max_date=date(2026, 8, 17),
        selected_max_date=date(2026, 8, 17),
        official_sha="same",
        selected_sha="same",
    )
    assert result["freshness_check_status"] == "VERIFIED_CURRENT"
    assert result["newer_data_exists"] is False
    assert result["selected_artifact_matches_latest"] is True


def test_older_selected_eia_observation_is_newer_available():
    result = eia_currentness_status(
        official_max_date=date(2026, 8, 17),
        selected_max_date=date(2026, 8, 10),
        official_sha="new",
        selected_sha="old",
    )
    assert result["freshness_check_status"] == "NEWER_AVAILABLE"
    assert result["newer_data_exists"] is True


def test_official_eia_url_is_publisher_workbook():
    assert EIA_GAS_XLS_URL == "https://www.eia.gov/petroleum/gasdiesel/xls/pswrgvwall.xls"


def test_cached_workbook_preserves_2024_and_has_2026_weeks():
    if not CACHE.exists():
        return
    latest = max_eia_observation_date(CACHE)
    assert latest is not None
    assert latest.year == 2026
    obs_2024 = parse_eia_gas_prices_xls(CACHE, reference_year=2024)
    obs_2026 = parse_eia_gas_prices_xls(CACHE, reference_year=2026)
    assert len(obs_2024) >= 1
    assert len(obs_2026) >= 1
    assert all(item.reference_year == 2024 for item in obs_2024)
    assert all(item.reference_year == 2026 for item in obs_2026)


def test_committed_freshness_eia_matches_selected_to_official():
    payload = json.loads(FRESHNESS.read_text(encoding="utf-8"))
    eia = payload["checks"]["eia_gasoline"]
    assert eia["freshness_check_status"] == "VERIFIED_CURRENT"
    assert eia["newer_data_exists"] is False
    assert eia["latest_authoritative_vintage_found"] == eia["selected_vintage"]
    assert eia["latest_authoritative_vintage_found"]
    assert "EIA weekly retail gasoline through 2026-" in eia["selected_vintage"]
    arts = eia.get("selected_artifacts") or []
    assert arts and arts[0].get("sha256")
    assert payload["candidate_calculation_authorized"] is False
    assert payload["living_cost_release_authorized"] is False
    assert payload["candidate_inputs_bound"] is False
    assert payload["ready_for_private_candidate"] is False
