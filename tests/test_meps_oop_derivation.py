"""Official HC-251 OD-002 derivation. Does not calculate an MSLC."""

from __future__ import annotations

import json
from pathlib import Path

from foundation.sources.meps import (
    HC251_LAYOUT,
    derive_od002_oop,
    parse_hc251_sas_layout,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "data" / "metadata" / "living_cost_meps_oop_derivation.json"
CACHE = ROOT / "data" / "cache" / "h251dat.zip"


def _line(fields: dict[str, str], length: int = 3903) -> bytes:
    buf = bytearray(b" " * length)
    for name, value in fields.items():
        start, end = HC251_LAYOUT[name]
        raw = value.encode("ascii")
        width = end - start + 1
        buf[start - 1 : end] = raw.rjust(width)[:width]
    return bytes(buf)


def test_sas_layout_parser_matches_official_codebook_positions():
    sas = """
     @194    AGELAST                           2.0
     @2090   INSCOV23                          1.0
     @2483   TOTSLF23                          6.0
     @3847   PERWT23F                          13.6
"""
    assert parse_hc251_sas_layout(sas) == HC251_LAYOUT


def test_fixture_weighted_mean_includes_zeros_and_private_adults_only():
    records = [
        _line({"AGELAST": "40", "INSCOV23": "1", "TOTSLF23": "100", "PERWT23F": "2.0"}),
        _line({"AGELAST": "40", "INSCOV23": "1", "TOTSLF23": "0", "PERWT23F": "2.0"}),
        _line({"AGELAST": "10", "INSCOV23": "1", "TOTSLF23": "999", "PERWT23F": "9.0"}),
        _line({"AGELAST": "40", "INSCOV23": "2", "TOTSLF23": "999", "PERWT23F": "9.0"}),
        _line({"AGELAST": "70", "INSCOV23": "1", "TOTSLF23": "999", "PERWT23F": "9.0"}),
    ]
    stats = derive_od002_oop(records)
    assert stats["in_universe_n"] == 2
    assert stats["weighted_mean"] == 50.0
    assert stats["weighted_median"] == 0.0
    assert stats["source_data_year"] == 2023
    assert stats["source_variable"] == "TOTSLF23"
    assert stats["includes_zero_oop"] is True


def test_committed_derivation_is_2023_and_not_an_mslc():
    if not REPORT.exists():
        return
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    assert payload["report_type"] == "living_cost_meps_oop_derivation"
    assert payload["calculates_mslc"] is False
    assert payload["download_is_not_derivation"] is True
    assert payload["source_data_year"] == 2023
    assert payload["puf_id"] == "HC-251"
    assert payload["source_variable"] == "TOTSLF23"
    assert payload["weighted_mean"] > 0
    assert payload["in_universe_n"] > 1000
    assert payload["evidence_status"] == "MODELED_FROM_MEASURED_INPUTS"
    if CACHE.exists():
        import hashlib

        assert payload["sha256"] == hashlib.sha256(CACHE.read_bytes()).hexdigest()
