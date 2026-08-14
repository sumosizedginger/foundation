from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from foundation.config import definitions
from foundation.households import prepare_person_records
from foundation.independent_check import weighted_percentile_reference
from foundation.models import Bottom30Result, SourceArtifact, ValidationReport
from foundation.percentiles import weighted_percentiles
from foundation.validation import validate_bottom30_prepared


def calculate_bottom30(
    frame: pd.DataFrame,
    *,
    survey_year: int,
    income_year: int,
    source_artifact: SourceArtifact | None = None,
    audit_metadata: dict | None = None,
) -> Bottom30Result:
    defs = definitions()
    cfg = defs["bottom_30"]
    methodology_version = defs["project"]["methodology_version"]
    percentile = float(cfg["percentile"])

    # Ensure H_SEQ column exists if PH_SEQ is present
    if "H_SEQ" not in frame.columns and "PH_SEQ" in frame.columns:
        frame = frame.copy()
        frame["H_SEQ"] = frame["PH_SEQ"]

    prepared, report = prepare_person_records(
        frame,
        income_col=cfg.get("household_income_variable", "HTOTVAL"),
        people_col=cfg.get("household_person_count_variable", "H_NUMPER"),
        weight_col=cfg.get("person_weight_variable", "MARSUPWT"),
        household_id_col=cfg.get("household_id_variable", "H_SEQ"),
    )
    validate_bottom30_prepared(prepared)

    # Compute full ladder quantiles
    quantile_targets = [0.10, 0.20, 0.30, 0.40, 0.50, 0.75, 0.90]
    quants_raw = weighted_percentiles(
        prepared["household_income_per_person"],
        prepared["person_weight"],
        quantile_targets,
    )
    quants_formatted = {f"P{int(p * 100):02d}": round(val, 2) for p, val in quants_raw.items()}

    cutoff = quants_raw[0.30]

    # Independent reference check
    ref_cutoff = weighted_percentile_reference(
        prepared["household_income_per_person"],
        prepared["person_weight"],
        percentile,
    )
    diff = abs(cutoff - ref_cutoff)
    if diff > 1e-6:
        raise RuntimeError(
            f"Percentile cross-check failed! Canonical={cutoff}, Reference={ref_cutoff}, Diff={diff}"
        )

    # Weight scaling: MARSUPWT has 2 implied decimal places (scale factor 100)
    weight_scale = 100
    raw_marsupwt = float(prepared["person_weight"].sum())
    represented_population = round(raw_marsupwt / weight_scale, 0)

    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()

    validation_rep = None
    if audit_metadata:
        validation_rep = ValidationReport(
            archive_filename=str(audit_metadata.get("archive_filename", "")),
            sha256=str(audit_metadata.get("sha256", "")),
            survey_year=survey_year,
            income_year=income_year,
            household_records=int(audit_metadata.get("household_records", report.input_records)),
            person_records=int(audit_metadata.get("person_records", report.input_records)),
            matched_person_records=int(
                audit_metadata.get("matched_person_records", report.valid_records)
            ),
            unmatched_person_records=int(audit_metadata.get("unmatched_person_records", 0)),
            unmatched_household_records=int(audit_metadata.get("unmatched_household_records", 0)),
            duplicate_household_keys=int(audit_metadata.get("duplicate_household_keys", 0)),
            raw_marsupwt_total=raw_marsupwt,
            scaled_represented_population=represented_population,
            weight_scale=weight_scale,
            quantiles=quants_formatted,
            canonical_p30=round(cutoff, 2),
            independent_reference_p30=round(ref_cutoff, 2),
            implementation_diff=diff,
            parser_version="1.0.0",
            methodology_version=methodology_version,
            calculated_at=now_iso,
        )

    return Bottom30Result.create(
        survey_year=survey_year,
        income_year=income_year,
        percentile=percentile,
        cutoff=round(cutoff, 2),
        valid_records=report.valid_records,
        excluded_records=report.excluded_records,
        total_relative_weight=raw_marsupwt,
        represented_population=represented_population,
        weight_scale=weight_scale,
        quantiles=quants_formatted,
        methodology_version=methodology_version,
        source_artifact=source_artifact,
        validation_report=validation_rep,
    )


def calculate_bottom30_from_zip(
    zip_path: Path,
    *,
    survey_year: int,
    income_year: int,
) -> Bottom30Result:
    from foundation.sources.census_asec import extract_and_merge_asec_zip

    frame, audit = extract_and_merge_asec_zip(zip_path, survey_year)
    artifact = SourceArtifact(
        source_id="census_asec",
        url=f"https://www2.census.gov/programs-surveys/cps/datasets/{survey_year}/march/asecpub{str(survey_year)[-2:]}csv.zip",
        retrieved_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        sha256=audit["sha256"],
        bytes=audit["bytes"],
        content_type="application/zip",
    )
    return calculate_bottom30(
        frame,
        survey_year=survey_year,
        income_year=income_year,
        source_artifact=artifact,
        audit_metadata=audit,
    )
