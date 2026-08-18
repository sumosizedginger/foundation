"""NAIC Auto Insurance Database Report evidence. Does not calculate an MSLC."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from foundation.living_cost.evidence_validators import validate_naic_derivation
from foundation.sources.naic_report import (
    US_STATE_NAMES,
    parse_naic_combined_average_premium,
    parse_naic_named_state_table,
    parse_naic_news_national_premium,
    selected_naic_pdf_sha256,
    write_naic_derivation_report,
)

ROOT = Path(__file__).resolve().parents[1]


def _table_page(
    *,
    table: str,
    column: str,
    year_header: str = "2023 2022",
    start: float = 1000.11,
    national: float = 1438.60,
) -> str:
    lines = [
        "2022/2023 Auto Insurance Database Report",
        table,
        "Average Premiums and Expenditures 2019-2023",
        column,
        f"STATE {year_header} 2021 2020 2019",
    ]
    premium = start
    for name in US_STATE_NAMES:
        lines.append(f"{name} {premium:,.2f} 900.00 800.00 700.00 600.00")
        premium += 1.0
    lines.append(f"Countrywide {national:,.2f} 1,257.31 1,189.16 1,176.81 1,207.71")
    return "\n".join(lines)


def test_selected_pdf_sha_is_file_bytes_not_sidecar(tmp_path: Path):
    pdf = tmp_path / "publication-aut-pb-auto-insurance-database.pdf"
    pdf.write_bytes(b"official-naic-bytes-A")
    (tmp_path / "publication-aut-pb-auto-insurance-database.pdf.provenance.json").write_text(
        json.dumps({"sha256": "sidecar-B"}),
        encoding="utf-8",
    )
    digest = hashlib.sha256(b"official-naic-bytes-A").hexdigest()
    assert selected_naic_pdf_sha256(pdf) == digest
    assert selected_naic_pdf_sha256(pdf) != "sidecar-B"
    assert selected_naic_pdf_sha256(tmp_path / "missing.pdf") is None


def test_table_5_parser_uses_combined_average_premium_not_expenditure():
    pages = [_table_page(table="Table 5", column="Combined Average Premium")]
    parsed = parse_naic_named_state_table(
        pages,
        table_marker="Table 5",
        column_marker="Combined Average Premium",
        data_year=2023,
    )
    assert parsed["ok"] is True
    assert len(parsed["jurisdictions"]) == 51
    assert parsed["national"]["value"] == 1438.60
    states = [row["state"] for row in parsed["jurisdictions"]]
    assert "DC" in states
    assert len(states) == len(set(states))
    assert all(row["value"] > 0 for row in parsed["jurisdictions"])


def test_expenditure_table_is_not_canonical_premium():
    pages = [_table_page(table="Table 4", column="Average Expenditure")]
    parsed = parse_naic_named_state_table(
        pages,
        table_marker="Table 5",
        column_marker="Combined Average Premium",
        data_year=2023,
    )
    assert parsed["ok"] is False
    assert parsed["jurisdictions"] == []


def test_news_national_sanity_parses_official_release_wording():
    html = (
        "The national combined average premium per issued vehicle was $1,438, "
        "a 14.42% increase from 2022 to 2023."
    )
    assert parse_naic_news_national_premium(html) == 1438.0


def test_derivation_fail_closes_on_sha_mismatch(tmp_path: Path):
    report = tmp_path / "naic.json"
    report.write_text(
        json.dumps(
            {
                "report_type": "living_cost_naic_auto_insurance",
                "canonical_measure": "combined_average_premium",
                "sha256": "aaa",
                "pdf_identifier_bound": True,
                "publication_identifier": "AUT-PB 2022-2023",
                "listing_identifier": "AUT-PB 2022-2023",
                "source_data_year": 2023,
                "data_year_range": {"start": 2022, "end": 2023},
                "jurisdictions": [],
                "validation_ok": True,
                "calculates_mslc": False,
            }
        ),
        encoding="utf-8",
    )
    result = validate_naic_derivation(report, selected_sha="bbb")
    assert result.ok is False
    assert "NAIC_REPORT_SHA_MISMATCH" in result.issues
    assert result.evidence_status != "VALIDATED"


def test_derivation_fail_closes_on_file_existence_only(tmp_path: Path):
    bogus = tmp_path / "exists.json"
    bogus.write_text("{}", encoding="utf-8")
    result = validate_naic_derivation(bogus, selected_sha="abc")
    assert result.ok is False
    assert result.evidence_status == "RETRIEVED_UNVALIDATED"


def test_write_derivation_uses_table_5_and_separate_national(tmp_path: Path, monkeypatch):
    from foundation.sources import naic_report as nr

    pages = [
        "2022/2023 Auto Insurance Database Report\nNational Association of Insurance Commissioners\n",
        _table_page(table="Table 5", column="Combined Average Premium", start=1000.11),
        _table_page(
            table="Table 4",
            column="Average Expenditure",
            start=800.11,
            national=1281.92,
        ),
    ]
    monkeypatch.setattr(nr, "extract_pdf_text_by_page", lambda _path: pages)
    pdf = tmp_path / "publication-aut-pb-auto-insurance-database.pdf"
    pdf.write_bytes(b"bytes")
    sha = hashlib.sha256(b"bytes").hexdigest()
    out = tmp_path / "living_cost_naic_auto_insurance.json"
    payload = write_naic_derivation_report(
        pdf,
        publication_identifier="AUT-PB 2022-2023",
        listing_identifier="AUT-PB 2022-2023",
        selected_sha=sha,
        retrieved_at="2026-08-18T00:00:00Z",
        resolved_url="https://content.naic.org/sites/default/files/publication-aut-pb-auto-insurance-database.pdf",
        news_national=1438.0,
        output_path=out,
    )
    assert payload["canonical_measure"] == "combined_average_premium"
    assert payload["source_data_year"] == 2023
    assert payload["jurisdiction_count"] == 51
    assert payload["national"]["combined_average_premium"] == 1438.60
    assert payload["national"]["not_state_average"] is True
    assert payload["calculates_mslc"] is False
    alabama = next(r for r in payload["jurisdictions"] if r["state"] == "AL")
    assert alabama["combined_average_premium"] != alabama["average_expenditure"]
    result = validate_naic_derivation(out, selected_sha=sha)
    assert result.ok is True
    assert result.evidence_status == "VALIDATED"


def test_official_pdf_table_5_if_cached():
    pdf = ROOT / "data" / "cache" / "publication-aut-pb-auto-insurance-database.pdf"
    if not pdf.is_file():
        parsed = parse_naic_named_state_table(
            [_table_page(table="Table 5", column="Combined Average Premium")],
            table_marker="Table 5",
            column_marker="Combined Average Premium",
            data_year=2023,
        )
        assert parsed["ok"] is True
        return
    parsed = parse_naic_combined_average_premium(pdf, data_year=2023)
    assert parsed["ok"] is True
    assert len(parsed["jurisdictions"]) == 51
    assert parsed["national"]["value"] == 1438.60
    assert parsed["identity"]["publication_identifier"] == "AUT-PB 2022-2023"
