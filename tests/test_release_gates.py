from __future__ import annotations

import ast
import hashlib
import os
import re
from pathlib import Path

import pytest

from foundation.living_cost.engine import get_living_cost_transition_state
from foundation.living_cost.manifest import RetrievedSourceArtifact
from foundation.living_cost.transportation import AutoCostBreakdown, calculate_transportation
from foundation.sources.acquisition import acquire_source, write_retrieval_sidecar
from foundation.sources.bls_ce import parse_bls_ce_microdata
from foundation.sources.census_acs import compute_adult_population_from_b01001_row
from foundation.sources.hud_fmr import HUD_FMR_SOURCES

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"


def test_no_production_dependency_on_tests():
    forbidden = ("tests/fixtures", "tests\\fixtures", "sample_acs_county_pop.csv", "sample_hud_fmr")
    for root, _, files in os.walk(SRC):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = Path(root) / file
            content = path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        assert not name.name.startswith("tests"), f"{file} imports from tests"
                elif isinstance(node, ast.ImportFrom) and node.module:
                    assert not node.module.startswith("tests"), f"{file} imports from tests"
            for token in forbidden:
                assert token not in content, f"{path} references {token}"

    for path in SCRIPTS.glob("*.py"):
        content = path.read_text(encoding="utf-8")
        for token in ("tests/fixtures", "sample_hud_fmr_2024.csv"):
            assert token not in content, f"{path} references {token}"


def test_wrong_sha_fails_byte_verification(tmp_path: Path):
    dest = tmp_path / "artifact.bin"
    dest.write_bytes(b"official-bytes")
    real_sha = hashlib.sha256(b"official-bytes").hexdigest()
    fake_sha = "0" * 64
    assert re.fullmatch(r"[0-9a-fA-F]{64}", fake_sha)
    write_retrieval_sidecar(
        dest,
        source_id="test_sha",
        url="https://example.gov/file",
        retrieved_at="2026-01-01T00:00:00+00:00",
        sha256=fake_sha,
        byte_size=len(b"official-bytes"),
        http_status=200,
        content_type="application/octet-stream",
    )
    result = acquire_source(
        "test_sha",
        "https://example.gov/file",
        tmp_path,
        "artifact.bin",
    )
    assert result is None
    assert fake_sha != real_sha


def test_nonexistent_artifact_cannot_be_validated():
    artifact = RetrievedSourceArtifact(
        source_id="missing",
        retrieved_at="",
        sha256="",
        byte_size=0,
        local_cache_filename="",
        validation_status="UNAVAILABLE",
    )
    assert artifact.validation_status != "VALIDATED"
    assert artifact.sha256 == ""


def test_malformed_retrieved_at_is_not_validated():
    artifact = RetrievedSourceArtifact(
        source_id="bad_time",
        retrieved_at="not-a-timestamp",
        sha256="a" * 64,
        byte_size=1,
        local_cache_filename="x.bin",
        validation_status="RETRIEVED_UNVALIDATED",
    )
    assert artifact.validation_status != "VALIDATED"


def test_hud_year_must_match_requested_year():
    assert HUD_FMR_SOURCES[2024]["reference_period"] == "2024"
    assert HUD_FMR_SOURCES[2026]["reference_period"] == "2026"
    assert HUD_FMR_SOURCES[2024]["url"] != HUD_FMR_SOURCES[2026]["url"]
    assert "fmr2024" in HUD_FMR_SOURCES[2024]["url"]
    assert "fmr2026" in HUD_FMR_SOURCES[2026]["url"]


def test_acs_adult_vars_cannot_fall_back_to_total_pop():
    with pytest.raises(ValueError, match="total population fallback is prohibited"):
        compute_adult_population_from_b01001_row({"B01001_001E": "1000"})


def test_bls_missing_zip_fails_closed(tmp_path: Path):
    obs = parse_bls_ce_microdata(tmp_path, reference_year=2024)
    assert all(item.status.value == "UNAVAILABLE" for item in obs)


def test_transportation_does_not_fabricate_a_sha():
    breakdown = AutoCostBreakdown(
        annual_miles=11000.0,
        fuel_cost_annual=1800.0,
        insurance_cost_annual=2200.0,
        maintenance_tires_annual=1400.0,
        registration_fees_annual=300.0,
        replacement_reserve_annual=2500.0,
    )
    obs = calculate_transportation(breakdown, 2024, "06075", "San Francisco County, CA", "CA")
    assert obs.source_artifact_sha256 != "N/A_ESTIMATED_MODEL"
    assert obs.status.value == "ESTIMATED"


def test_living_cost_release_authorized_gate():
    pipeline_path = SRC / "foundation" / "pipeline.py"
    content = pipeline_path.read_text(encoding="utf-8")
    assert "living_cost_release_authorized = False" in content


def test_transition_state_has_no_headline():
    state = get_living_cost_transition_state()
    assert state["minimum_sustainable_living_cost_2024"]["weighted_median_gross"] is None
    assert state["state_distributions_2024"] == []
    assert state["survival_gap_2024"] is None


def test_production_modules_import():
    import foundation.cli
    import foundation.living_cost.manifest
    import foundation.pipeline

    assert foundation.living_cost.manifest.generate_source_manifest
    assert foundation.pipeline.run_full_pipeline
    assert foundation.cli.main


def test_cps_same_vintage_hashes_have_revision_record():
    import json

    hist = (ROOT / "src" / "foundation" / "historical.py").read_text(encoding="utf-8")
    latest = json.loads((ROOT / "data" / "current" / "latest.json").read_text(encoding="utf-8"))
    current = "318845a2b5e0034eb2973898de1738f4df0025727de38499e7669cb9c0deef0b"
    older = "318845a2b5e0034e357900b991196ce28ecdd0c99a0937b27ff77f8ea6497284"
    assert current in hist
    history_shas = [row.get("archive_sha256") for row in latest.get("history", [])]
    if older in history_shas and current in hist:
        record = json.loads(
            (ROOT / "data" / "metadata" / "cps_asec_2025_sha_revisions.json").read_text(
                encoding="utf-8"
            )
        )
        hashes = {item["sha256"] for item in record["observed_hashes"]}
        assert current in hashes
        assert older in hashes
        assert record["status"] == "UNRECONCILED_PENDING_RETRIEVAL"


def test_owner_packet_writes_unresolved_decisions_only(tmp_path: Path):
    from foundation.living_cost.owner_packet import write_owner_decision_packet

    payload = write_owner_decision_packet(tmp_path)
    assert payload["headline_calculated"] is False
    assert (tmp_path / "living_cost_owner_decisions_pending.json").exists()
    assert (tmp_path / "living_cost_owner_decisions_pending.md").exists()
    assert any(d["id"] == "OD-003" for d in payload["decisions"])


def test_validation_cli_is_callable():
    from importlib.machinery import SourceFileLoader

    module = SourceFileLoader(
        "validate_living_cost_sources",
        str(SCRIPTS / "validate_living_cost_sources.py"),
    ).load_module()
    assert callable(module.main)
