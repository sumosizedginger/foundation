"""EIA weekly gasoline currentness. Does not calculate an MSLC."""

from __future__ import annotations

import hashlib
import json
import struct
from datetime import date
from pathlib import Path

from foundation.living_cost.freshness_currentness import eia_currentness_status
from foundation.sources.eia import (
    EIA_GAS_XLS_URL,
    eia_year_observation_dates,
    parse_eia_gas_prices_xls,
    selected_eia_workbook_sha256,
    summarize_eia_year,
)

ROOT = Path(__file__).resolve().parents[1]
FRESHNESS = ROOT / "data" / "metadata" / "living_cost_candidate_freshness.json"
EXCEL_EPOCH = date(1899, 12, 30)


def _excel_serial(value: date) -> float:
    return float((value - EXCEL_EPOCH).days)


def _biff_record(rec_type: int, data: bytes) -> bytes:
    return struct.pack("<HH", rec_type, len(data)) + data


def write_synthetic_eia_xls(path: Path, rows: list[tuple[date, float]]) -> Path:
    """Write a tiny BIFF2 workbook xlrd can parse. No xlwt dependency."""
    attr = b"\x00\x00\x00"
    parts = [
        _biff_record(0x0009, struct.pack("<HH", 0x0200, 0x0010)),
        _biff_record(0x0042, struct.pack("<H", 0x04E4)),
        _biff_record(0x0004, struct.pack("<HH", 0, 0) + attr + bytes([4]) + b"Date"),
        _biff_record(0x0004, struct.pack("<HH", 0, 1) + attr + bytes([4]) + b"Week"),
    ]
    for index, (observed, price) in enumerate(rows, start=1):
        parts.append(
            _biff_record(
                0x0003,
                struct.pack("<HH", index, 0) + attr + struct.pack("<d", _excel_serial(observed)),
            )
        )
        parts.append(
            _biff_record(
                0x0003,
                struct.pack("<HH", index, 1) + attr + struct.pack("<d", float(price)),
            )
        )
    parts.append(_biff_record(0x000A, b""))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(parts))
    return path


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


def test_selected_workbook_sha_is_file_bytes_not_sidecar(tmp_path: Path):
    workbook = tmp_path / "pswrgvwall.xls"
    workbook.write_bytes(b"official-selected-bytes-A")
    (tmp_path / "pswrgvwall.xls.provenance.json").write_text(
        json.dumps({"sha256": "sidecar-sha-B", "retrieved_at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    digest_a = hashlib.sha256(b"official-selected-bytes-A").hexdigest()
    assert selected_eia_workbook_sha256(workbook) == digest_a
    assert selected_eia_workbook_sha256(workbook) != "sidecar-sha-B"
    assert selected_eia_workbook_sha256(tmp_path / "missing.xls") is None


def test_year_summary_is_year_specific_on_synthetic_xls(tmp_path: Path):
    path = write_synthetic_eia_xls(
        tmp_path / "pswrgvwall.xls",
        [
            (date(2024, 1, 8), 3.501),
            (date(2024, 12, 30), 3.612),
            (date(2026, 1, 5), 3.101),
            (date(2026, 8, 10), 3.204),
        ],
    )
    sha = selected_eia_workbook_sha256(path)
    y2024 = summarize_eia_year(path, reference_year=2024, sha256=sha)
    y2026 = summarize_eia_year(path, reference_year=2026, sha256=sha)
    assert y2024["covered"] is True
    assert y2026["covered"] is True
    assert y2024["source_data_year"] == 2024
    assert y2026["source_data_year"] == 2026
    assert y2024["first_observation_date"] == "2024-01-08"
    assert y2024["last_observation_date"] == "2024-12-30"
    assert y2026["first_observation_date"] == "2026-01-05"
    assert y2026["last_observation_date"] == "2026-08-10"
    assert y2024["last_observation_date"] != y2026["last_observation_date"]
    assert y2024["observation_count"] == 2
    assert y2026["observation_count"] == 2
    assert y2024["geographic_series_count"] >= 1
    assert y2024["sha256"] == sha
    assert y2026["sha256"] == sha
    assert y2024["artifact"] == "pswrgvwall.xls"
    obs_2024 = parse_eia_gas_prices_xls(path, reference_year=2024)
    obs_2026 = parse_eia_gas_prices_xls(path, reference_year=2026)
    assert obs_2024 and all(item.reference_year == 2024 for item in obs_2024)
    assert obs_2026 and all(item.reference_year == 2026 for item in obs_2026)
    assert eia_year_observation_dates(path, 2024)[-1] == date(2024, 12, 30)


def test_later_year_rows_do_not_cover_missing_earlier_year(tmp_path: Path):
    path = write_synthetic_eia_xls(
        tmp_path / "only_2026.xls",
        [
            (date(2026, 1, 5), 3.101),
            (date(2026, 8, 10), 3.204),
        ],
    )
    y2024 = summarize_eia_year(path, reference_year=2024)
    y2026 = summarize_eia_year(path, reference_year=2026)
    assert y2026["covered"] is True
    assert y2024["covered"] is False
    assert y2024["last_observation_date"] is None
    assert y2026["last_observation_date"] == "2026-08-10"


def test_missing_workbook_year_summary_is_uncovered(tmp_path: Path):
    missing = tmp_path / "pswrgvwall.xls"
    summary = summarize_eia_year(missing, reference_year=2024, sha256="ignored")
    assert summary["covered"] is False
    assert summary["sha256"] is None
    assert summary["observation_count"] == 0


def test_discover_uses_workbook_bytes_not_sidecar_sha(tmp_path: Path, monkeypatch):
    from foundation.living_cost import freshness_discovery as disc

    cache = tmp_path / "cache"
    cache.mkdir()
    path = write_synthetic_eia_xls(
        cache / "pswrgvwall.xls",
        [
            (date(2024, 1, 8), 3.501),
            (date(2024, 12, 30), 3.612),
            (date(2026, 1, 5), 3.101),
            (date(2026, 8, 10), 3.204),
        ],
    )
    digest_a = selected_eia_workbook_sha256(path)
    assert digest_a
    (cache / "pswrgvwall.xls.provenance.json").write_text(
        json.dumps({"sha256": "sidecar-sha-B", "retrieved_at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(disc, "CACHE_DIR", cache)

    def fake_fetch(url: str, **_kwargs: object):
        return ("<html>pswrgvwall.xls weekly gasoline</html>", "2026-08-18T00:00:00Z")

    def fake_inspect(url: str):
        return {"sha256": digest_a, "max_date": date(2026, 8, 10)}

    monkeypatch.setattr(disc, "fetch_text", fake_fetch)
    monkeypatch.setattr(disc, "inspect_eia_official_workbook", fake_inspect)
    check = disc.discover_eia()
    arts = check.selected_artifacts or ()
    assert arts and arts[0]["sha256"] == digest_a
    assert arts[0]["sha256"] != "sidecar-sha-B"
    assert check.extra["selected_sha256"] == digest_a
    assert check.year_coverage["2024"]["last_observation_date"] == "2024-12-30"
    assert check.year_coverage["2026"]["last_observation_date"] == "2026-08-10"
    assert (
        check.year_coverage["2024"]["last_observation_date"]
        != check.year_coverage["2026"]["last_observation_date"]
    )
    assert check.freshness_check_status == "VERIFIED_CURRENT"


def test_discover_missing_workbook_ignores_sidecar_and_fails_closed(tmp_path: Path, monkeypatch):
    from foundation.living_cost import freshness_discovery as disc

    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "pswrgvwall.xls.provenance.json").write_text(
        json.dumps({"sha256": "sidecar-sha-B", "retrieved_at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(disc, "CACHE_DIR", cache)

    def fake_fetch(url: str, **_kwargs: object):
        return ("<html>pswrgvwall.xls weekly gasoline</html>", "2026-08-18T00:00:00Z")

    def fake_inspect(url: str):
        return {"sha256": "official-now", "max_date": date(2026, 8, 17)}

    monkeypatch.setattr(disc, "fetch_text", fake_fetch)
    monkeypatch.setattr(disc, "inspect_eia_official_workbook", fake_inspect)
    check = disc.discover_eia()
    arts = check.selected_artifacts or ()
    assert arts and arts[0]["sha256"] is None
    assert check.extra["selected_sha256"] is None
    assert check.freshness_check_status == "CHECK_FAILED"
    assert check.year_coverage["2024"]["covered"] is False
    assert check.year_coverage["2026"]["covered"] is False


def test_official_year_coverage_assertion_fail_closes():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from validate_living_cost_sources import assert_official_eia_year_coverage

    try:
        assert_official_eia_year_coverage(
            {
                "selected_sha256": None,
                "2024": {"covered": True},
                "2026": {"covered": True},
            }
        )
        raise AssertionError("missing selected sha must fail closed")
    except RuntimeError as exc:
        assert "selected_sha" in str(exc) or "absent" in str(exc)
    try:
        assert_official_eia_year_coverage(
            {
                "selected_sha256": "abc",
                "2024": {
                    "covered": True,
                    "last_observation_date": "2026-08-17",
                },
                "2026": {
                    "covered": True,
                    "last_observation_date": "2026-08-17",
                },
            }
        )
        raise AssertionError("identical year last dates must fail closed")
    except RuntimeError as exc:
        assert "year-specific" in str(exc)


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
    cov = eia["year_coverage"]
    assert cov["2024"]["covered"] is True
    assert cov["2026"]["covered"] is True
    assert cov["2024"]["source_data_year"] == 2024
    assert cov["2026"]["source_data_year"] == 2026
    assert str(cov["2024"]["last_observation_date"]).startswith("2024-")
    assert str(cov["2026"]["last_observation_date"]).startswith("2026-")
    assert cov["2024"]["last_observation_date"] != cov["2026"]["last_observation_date"]
    assert cov["2024"]["sha256"] == arts[0]["sha256"]
    assert cov["2026"]["sha256"] == arts[0]["sha256"]
    assert payload["candidate_calculation_authorized"] is False
    assert payload["living_cost_release_authorized"] is False
    assert payload["candidate_inputs_bound"] is False
    assert payload["ready_for_private_candidate"] is False
