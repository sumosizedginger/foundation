from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from typing import Tuple

import pandas as pd
from foundation.sources.http import DownloadResult, download_file


def asec_archive_url(survey_year: int) -> str:
    if survey_year < 2000 or survey_year > 2100:
        raise ValueError("survey_year is outside supported sanity range")
    yy = str(survey_year)[-2:]
    return (
        "https://www2.census.gov/programs-surveys/cps/datasets/"
        f"{survey_year}/march/asecpub{yy}csv.zip"
    )


def download_asec_archive(survey_year: int, cache_dir: Path) -> DownloadResult:
    url = asec_archive_url(survey_year)
    destination = cache_dir / f"asecpub{str(survey_year)[-2:]}csv.zip"
    return download_file(url, destination)


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def extract_and_merge_asec_zip(
    archive_path: Path,
    survey_year: int,
) -> Tuple[pd.DataFrame, dict]:
    """Extract and merge household and person tables from an official CPS ASEC CSV ZIP archive.

    Returns the merged DataFrame and raw extraction audit statistics.
    """
    yy = str(survey_year)[-2:]
    sha256_hash = compute_file_sha256(archive_path)

    with zipfile.ZipFile(archive_path) as zf:
        # Check files inside zip
        member_names = zf.namelist()
        hh_candidates = [m for m in member_names if f"hhpub{yy}" in m.lower() and m.lower().endswith(".csv")]
        pp_candidates = [m for m in member_names if f"pppub{yy}" in m.lower() and m.lower().endswith(".csv")]

        if not hh_candidates or not pp_candidates:
            # Fallback: look for generic names
            hh_candidates = [m for m in member_names if "hhpub" in m.lower() and m.lower().endswith(".csv")]
            pp_candidates = [m for m in member_names if "pppub" in m.lower() and m.lower().endswith(".csv")]

        if not hh_candidates or not pp_candidates:
            raise RuntimeError(f"Could not locate hhpub and pppub CSV files in {archive_path}")

        hh_name = hh_candidates[0]
        pp_name = pp_candidates[0]

        with zf.open(hh_name) as f_hh:
            hh = pd.read_csv(
                f_hh,
                usecols=["H_SEQ", "HTOTVAL", "H_NUMPER"],
                low_memory=False,
            )
        with zf.open(pp_name) as f_pp:
            pp = pd.read_csv(
                f_pp,
                usecols=["PH_SEQ", "MARSUPWT", "A_LINENO"],
                low_memory=False,
            )

    hh_records = len(hh)
    pp_records = len(pp)
    duplicate_hh = int(hh["H_SEQ"].duplicated().sum())

    merged = pp.merge(hh, left_on="PH_SEQ", right_on="H_SEQ", how="inner")
    matched_records = len(merged)
    unmatched_pp = pp_records - matched_records
    unmatched_hh = hh_records - len(set(merged["H_SEQ"]))

    audit = {
        "archive_filename": archive_path.name,
        "sha256": sha256_hash,
        "bytes": archive_path.stat().st_size,
        "survey_year": survey_year,
        "household_records": hh_records,
        "person_records": pp_records,
        "matched_person_records": matched_records,
        "unmatched_person_records": unmatched_pp,
        "unmatched_household_records": unmatched_hh,
        "duplicate_household_keys": duplicate_hh,
    }

    return merged, audit
