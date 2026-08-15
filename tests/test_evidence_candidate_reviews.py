"""Candidate-review artifacts for unclosed evidence families. No MSLC."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "data" / "metadata"


def test_mobile_broadband_replacement_reviews_do_not_invent_prices():
    mobile = json.loads((METADATA / "mobile_price_source_candidate_review.json").read_text())
    broadband = json.loads((METADATA / "broadband_source_candidate_review.json").read_text())
    replacement = json.loads(
        (METADATA / "vehicle_replacement_source_candidate_review.json").read_text()
    )
    assert mobile["calculates_mslc"] is False
    assert broadband["calculates_mslc"] is False
    assert replacement["calculates_mslc"] is False
    assert mobile["evidence_status"] == "SOURCE_GAP"
    assert broadband["status"] == "SOURCE_GAP"
    assert replacement["status"] == "FORMULA_FROZEN_INPUTS_PENDING"
    assert mobile.get("canonical_monthly_price") is None
    assert replacement["inputs"]["acquisition"]["bound"] is False
