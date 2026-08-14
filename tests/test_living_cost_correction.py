"""Post-Deliverable-2A source/methodology correction tests."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

from foundation.living_cost.manifest import MEPS_HC251_LANDING, RetrievedSourceArtifact
from foundation.living_cost.owner_packet import DECISIONS, write_owner_decision_packet
from foundation.sources.acquisition import (
    provenance_is_complete,
    validation_status_after_parse,
)
from foundation.sources.cms_marketplace import (
    SBE_STANDALONE_STATES,
    SBE_STATE_ZIP_SLUGS,
    sbe_state_zip_url,
)
from foundation.sources.epa_mpg import build_mpg_candidates
from foundation.sources.fhwa_nhts import parse_fhwa_nhts_mileage
from foundation.sources.meps import MEPS_DATA_YEAR, MEPS_PUF_ID, check_meps_2024_full_year_listing
from foundation.sources.usda_food import canonicalize_month_label, month_coverage


def test_meps_refresh_does_not_invent_2024_file_from_schedule_html():
    html = """
    <html><body>
    <p>August 2026: 2024 Full Year Consolidated Data File</p>
    <a href="download_data_files_detail.jsp?cboPufNumber=HC-251">HC-251</a>
    </body></html>
    """
    result = check_meps_2024_full_year_listing(listing_html=html)
    assert result["released"] is False
    assert result["listed_puf_id"] is None
    assert "HC-251" in result["notes"] or "2023" in result["notes"]


def test_meps_refresh_prefers_listed_2024_puf_when_present():
    html = """
    <html><body>
    <h2>2024 Full Year Consolidated Data File</h2>
    <a href="download_data_files_detail.jsp?cboPufNumber=HC-256">HC-256</a>
    </body></html>
    """
    result = check_meps_2024_full_year_listing(listing_html=html)
    assert result["released"] is True
    assert result["listed_puf_id"] == "HC-256"


def test_meps_true_source_year_is_2023_until_listed():
    assert MEPS_PUF_ID == "HC-251"
    assert MEPS_DATA_YEAR == 2023
    assert "HC-251" in MEPS_HC251_LANDING
    assert "HC-243" not in MEPS_HC251_LANDING


def test_nhts_person_join_enforces_age_and_driver(tmp_path: Path):
    zip_path = tmp_path / "nhts_2022_csv.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        hh = io.StringIO()
        writer = csv.DictWriter(hh, fieldnames=["HOUSEID", "HHSIZE", "WRKCOUNT", "WTHHFIN"])
        writer.writeheader()
        writer.writerow({"HOUSEID": "1", "HHSIZE": "1", "WRKCOUNT": "1", "WTHHFIN": "10"})
        writer.writerow({"HOUSEID": "2", "HHSIZE": "1", "WRKCOUNT": "1", "WTHHFIN": "10"})
        writer.writerow({"HOUSEID": "3", "HHSIZE": "1", "WRKCOUNT": "1", "WTHHFIN": "10"})
        zf.writestr("hhv2pub.csv", hh.getvalue())

        per = io.StringIO()
        writer = csv.DictWriter(per, fieldnames=["HOUSEID", "R_AGE", "DRIVER"])
        writer.writeheader()
        writer.writerow({"HOUSEID": "1", "R_AGE": "40", "DRIVER": "01"})
        writer.writerow({"HOUSEID": "2", "R_AGE": "70", "DRIVER": "1"})
        writer.writerow({"HOUSEID": "3", "R_AGE": "30", "DRIVER": "2"})
        zf.writestr("perv2pub.csv", per.getvalue())

        veh = io.StringIO()
        writer = csv.DictWriter(veh, fieldnames=["HOUSEID", "ANNMILES"])
        writer.writeheader()
        writer.writerow({"HOUSEID": "1", "ANNMILES": "8000"})
        writer.writerow({"HOUSEID": "2", "ANNMILES": "20000"})
        writer.writerow({"HOUSEID": "3", "ANNMILES": "30000"})
        zf.writestr("vehv2pub.csv", veh.getvalue())

    obs = parse_fhwa_nhts_mileage(tmp_path, reference_year=2024)
    assert obs.value_annual == 8000.0
    assert "age-18-64" in obs.notes
    assert "DRIVER=1" in obs.notes
    assert "MINIMUM NECESSARY" in obs.notes
    assert "working-age drivers" not in obs.notes.lower() or "age-18-64" in obs.notes


def test_usda_month_coverage_from_labels_not_row_counts():
    coverage = month_coverage(["January", "February", "March", "April", "May", "May"])
    assert coverage["months_included"] == ["January", "February", "March", "April", "May"]
    assert coverage["month_count"] == 5
    assert coverage["first_month"] == "January"
    assert coverage["last_month"] == "May"
    assert canonicalize_month_label("01") == "January"
    assert canonicalize_month_label("2026-05") == "May"
    assert canonicalize_month_label("not-a-month") is None


def test_owner_packet_od_updates(tmp_path: Path):
    payload = write_owner_decision_packet(tmp_path)
    assert payload["headline_calculated"] is False
    assert payload["decisions_frozen"] is False
    by_id = {item["id"]: item for item in DECISIONS}
    assert "AUGUST 2026" in by_id["OD-002"]["source_support"]
    assert "HC-251" in by_id["OD-002"]["source_support"]
    assert "person file" in by_id["OD-003"]["source_support"]
    assert "REFERENCE" not in by_id["OD-004"]["question"] or "cohort" in by_id["OD-004"]["question"]
    assert "LICENSING_REVIEW" not in by_id["OD-006"]["question"]
    assert "average expenditure" in by_id["OD-006"]["option_a"].lower()
    assert "including zero" in by_id["OD-007"]["option_a"].lower()
    assert (
        "NOT a price source" in by_id["OD-009"]["why_it_matters"]
        or "not a price" in by_id["OD-009"]["why_it_matters"].lower()
    )
    assert "HYBRID" in by_id["OD-010"]["option_a"]
    assert "coterminous" in by_id["OD-011"]["option_a"]
    assert "09190" in by_id["OD-013"]["why_it_matters"]
    assert "09110-09170" not in by_id["OD-013"]["why_it_matters"]
    assert "FY2026" in by_id["OD-013"]["why_it_matters"]
    assert "legacy HUD county" in by_id["OD-013"]["option_a"]
    for item in DECISIONS:
        assert "ACCEPTED" not in item["recommended"]


def test_sbe_per_state_official_urls_are_year_specific():
    assert "NJ" in SBE_STANDALONE_STATES[2024]
    assert "OR" not in SBE_STANDALONE_STATES[2024]
    assert "OR" in SBE_STATE_ZIP_SLUGS[2024]
    assert "VA" in SBE_STANDALONE_STATES[2024]
    assert "GA" in SBE_STANDALONE_STATES[2026]
    assert "IL" in SBE_STANDALONE_STATES[2026]
    assert "GA" not in SBE_STANDALONE_STATES[2024]
    url = sbe_state_zip_url(2024, "CA")
    assert url.startswith("https://www.cms.gov/files/zip/")
    assert "2024" in url
    assert "sbe-puf-files-2024.zip" not in url
    assert SBE_STATE_ZIP_SLUGS[2026]["IL"] == "illinois-sbe-qhp-puf.zip"
    assert SBE_STATE_ZIP_SLUGS[2026]["DC"] == "districtofcolumbiapuf2026.zip"


def test_provenance_gate_rejects_validated_without_retrieved_at():
    incomplete = RetrievedSourceArtifact(
        source_id="hud_fmr_2024",
        retrieved_at="",
        sha256="a" * 64,
        byte_size=100,
        local_cache_filename="FMR2024_final_revised.xlsx",
        validation_status="RETRIEVED_UNVALIDATED",
        resolved_url="https://www.huduser.gov/portal/datasets/fmr/fmr2024/FMR2024_final_revised.xlsx",
    )
    assert provenance_is_complete(incomplete) is False
    assert validation_status_after_parse(incomplete, parsed_ok=True) == "INCOMPLETE_PROVENANCE"
    complete = RetrievedSourceArtifact(
        source_id="hud_fmr_2024",
        retrieved_at="2026-08-14T17:00:00+00:00",
        sha256="a" * 64,
        byte_size=100,
        local_cache_filename="FMR2024_final_revised.xlsx",
        validation_status="RETRIEVED_UNVALIDATED",
        resolved_url="https://www.huduser.gov/portal/datasets/fmr/fmr2024/FMR2024_final_revised.xlsx",
    )
    assert validation_status_after_parse(complete, parsed_ok=True) == "VALIDATED"


def test_epa_candidates_exclude_bev_and_do_not_use_28():
    rows = [
        {
            "year": "2014",
            "VClass": "Compact Cars",
            "fuelType": "Regular",
            "atvType": "",
            "comb08": "30",
        },
        {
            "year": "2014",
            "VClass": "Midsize Cars",
            "fuelType": "Regular",
            "atvType": "",
            "comb08": "26",
        },
        {
            "year": "2014",
            "VClass": "Compact Cars",
            "fuelType": "Electricity",
            "atvType": "EV",
            "comb08": "110",
        },
        {
            "year": "2024",
            "VClass": "Compact Cars",
            "fuelType": "Regular",
            "atvType": "",
            "comb08": "34",
        },
    ]
    cands = {c["id"]: c for c in build_mpg_candidates(rows, 2024)}
    used = cands["used_compact_midsize_gasoline"]
    assert used["n"] == 2
    assert used["median_mpg"] == 28.0 or used["mean_mpg"] == 28.0
    # BEV 110 MPG must not enter the gasoline cohort mean.
    assert used["mean_mpg"] == 28.0
    new = cands["new_compact_midsize_gasoline_my2024"]
    assert new["n"] == 1
    assert new["median_mpg"] == 34.0


def test_workflow_action_majors():
    root = Path(__file__).resolve().parents[1] / ".github" / "workflows"
    text = "\n".join(p.read_text(encoding="utf-8") for p in root.glob("*.yml"))
    assert "actions/checkout@v7" in text
    assert "actions/setup-python@v7" in text
    assert "actions/setup-node@v6" in text
    assert "actions/checkout@v5" not in text
    assert "actions/setup-python@v6" not in text
    assert "actions/setup-node@v5" not in text
    assert 'node-version: "24"' in text


def test_ct_reconstruction_uses_official_crosswalk_and_nine_planning_regions():
    from foundation.sources.census_ct import (
        CT_PLANNING_REGION_FIPS,
        assign_towns_to_legacy_counties,
        parse_acs_ct_cousub_adults,
        parse_ct_crosswalk,
        reconstruct_legacy_county_adult_pop,
    )

    assert CT_PLANNING_REGION_FIPS[-1] == "09190"
    assert "09180" in CT_PLANNING_REGION_FIPS
    cache = Path(__file__).resolve().parents[1] / "data" / "cache"
    xlsx = cache / "ct_cou_to_cousub_crosswalk.xlsx"
    dat = cache / "acsdt5y2024-b01001.dat"
    if not xlsx.exists() or not dat.exists():
        return
    rows = parse_ct_crosswalk(xlsx)
    mapping = assign_towns_to_legacy_counties(rows)
    assert mapping
    adults = parse_acs_ct_cousub_adults(dat)
    report = reconstruct_legacy_county_adult_pop(rows, adults)
    assert report["reproduced"] is True
    assert report["unmapped_towns"] == []
    assert report["duplicate_towns"] == []
    assert report.get("state_total_reconciles") is True
    from foundation.sources.census_ct import apply_legacy_ct_weights_to_universe

    dummy = {
        fips: {"adult_population": 1, "county_name": fips, "state": "CT"}
        for fips in CT_PLANNING_REGION_FIPS
    }
    dummy["06075"] = {"adult_population": 10, "county_name": "SF", "state": "CA"}
    joined = apply_legacy_ct_weights_to_universe(dummy, report)
    assert "09110" not in joined
    assert "09001" in joined
    assert joined["09001"]["adult_population"] == report["legacy_county_adult_population"]["09001"]
    assert set(report["legacy_county_adult_population"]) == {
        "09001",
        "09003",
        "09005",
        "09007",
        "09009",
        "09011",
        "09013",
        "09015",
    }


def test_no_headline_flags_in_owner_packet_and_coverage():
    coverage_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "metadata"
        / "living_cost_source_coverage.json"
    )
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    assert coverage["headline_calculated"] is False
    assert coverage["gap_calculated"] is False
    assert coverage["adequacy_calculated"] is False
