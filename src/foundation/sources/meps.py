"""Medical Expenditure Panel Survey (MEPS) Source Adapter.

Calculates realistic expected annual out-of-pocket (OOP) healthcare expenditures for non-elderly
adults (Age 18-64) with private health insurance coverage from official AHRQ MEPS tables/microdata.

STRICT FAIL-CLOSED RULES:
- NO hardcoded numeric fallback values ($1,420 / $1,550).
- If source observation cannot be parsed or verified, status = UNAVAILABLE with None values.
- Population Filter: Adults age 18-64 with INSCOV23=1 (ANY PRIVATE).
- Metric: Population-weighted mean out-of-pocket medical expenditure (TOTSLF23).

2024 Full Year Consolidated is scheduled by AHRQ for AUGUST 2026. Do not claim it exists
until it appears in the official MEPS PUF listing. HC-251 (2023) remains the latest listed
full-year file as of 2026-08-14.
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import io
import json
import logging
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source, record_unretrieved
from foundation.sources.http import download_file

logger = logging.getLogger(__name__)

MEPS_LISTING_URL = "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files.jsp"
MEPS_SCHEDULE_URL = "https://meps.ahrq.gov/mepsweb/about_meps/releaseschedule.jsp"
MEPS_HC251_LANDING = (
    "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files_detail.jsp?cboPufNumber=HC-251"
)
MEPS_HC251_ASCII_ZIP = "https://meps.ahrq.gov/mepsweb/data_files/pufs/h251/h251dat.zip"
MEPS_HC251_SAS_STATEMENTS = (
    "https://meps.ahrq.gov/mepsweb/data_stats/download_data/pufs/h251/h251su.txt"
)
MEPS_HC251_CODEBOOK = (
    "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files_codebook.jsp?PUFId=H251"
)
MEPS_DATA_YEAR = 2023
MEPS_PUF_ID = "HC-251"
MEPS_OOP_REPORT = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "metadata"
    / "living_cost_meps_oop_derivation.json"
)

# Official HC-251 codebook / SAS INPUT start-end columns (1-indexed inclusive).
# Source: MEPS HC-251 codebook 2025-08-12 and official h251su.txt @start statements.
HC251_LAYOUT: dict[str, tuple[int, int]] = {
    "AGELAST": (194, 195),
    "INSCOV23": (2090, 2090),
    "TOTSLF23": (2483, 2488),
    "PERWT23F": (3847, 3859),
}
INSCOV_ANY_PRIVATE = 1
_SAS_INPUT_RE = re.compile(r"@(?P<start>\d+)\s+(?P<name>[A-Z0-9]+)\s+(?P<width>\d+(?:\.\d+)?)")
MEPS_2024_FY_SCHEDULE = "AUGUST 2026"
MEPS_NOTE = (
    "Newest official Full Year Consolidated PUF actually listed is HC-251 (2023). "
    "AHRQ official 2026 release schedule lists the 2024 Full Year Consolidated Data File "
    f"for {MEPS_2024_FY_SCHEDULE}. Do not claim the 2024 file exists until it appears "
    "in the official MEPS PUF listing."
)

# Known 2024 event-file PUF numbers are NOT the Full Year Consolidated file.
# 2024 FY Consolidated PUF number is unknown until AHRQ lists it.
_FY_CONSOLIDATED_RE = re.compile(
    r"2024\s+Full\s+Year\s+Consolidated",
    re.IGNORECASE,
)
_PUF_NUMBER_RE = re.compile(r"cboPufNumber=(HC-\d+[A-Z]?)", re.IGNORECASE)
_H_DAT_ZIP_RE = re.compile(
    r"https://meps\.ahrq\.gov/mepsweb/data_files/pufs/h(\d+)/h\1dat\.zip",
    re.IGNORECASE,
)


def check_meps_2024_full_year_listing(
    listing_html: str | None = None,
    *,
    timeout: tuple[float, float] = (15.0, 60.0),
) -> dict[str, Any]:
    """Inspect the official MEPS PUF listing for a 2024 Full Year Consolidated file.

    Returns a structured refresh result. Does not invent a PUF number.
    """
    html = listing_html
    fetched_url = MEPS_LISTING_URL
    if html is None:
        try:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                download_file(url=MEPS_LISTING_URL, destination=tmp_path, timeout=timeout)
                html = tmp_path.read_text(encoding="utf-8", errors="replace")
            finally:
                tmp_path.unlink(missing_ok=True)
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            logger.warning("MEPS 2024 FY listing refresh failed: %s", exc)
            return {
                "checked_at_source": MEPS_LISTING_URL,
                "schedule_url": MEPS_SCHEDULE_URL,
                "schedule_states_2024_fy": MEPS_2024_FY_SCHEDULE,
                "released": False,
                "listed_puf_id": None,
                "ascii_zip_url": None,
                "notes": (
                    "Could not retrieve official MEPS PUF listing. "
                    f"Continue using {MEPS_PUF_ID} with true source year = {MEPS_DATA_YEAR}. "
                    f"Error: {exc}"
                ),
            }

    has_fy_label = bool(_FY_CONSOLIDATED_RE.search(html))
    # Only treat as released if the 2024 FY Consolidated label is present AND a
    # PUF number other than known 2023/2022 FY files is associated nearby.
    puf_ids = {m.group(1).upper() for m in _PUF_NUMBER_RE.finditer(html)}
    zip_hits = list(_H_DAT_ZIP_RE.finditer(html))
    listed_puf_id = None
    ascii_zip_url = None
    if has_fy_label:
        # Prefer a PUF number that is not HC-251 / HC-243 (prior FY files).
        for puf_id in sorted(puf_ids):
            if puf_id not in {"HC-251", "HC-243"}:
                listed_puf_id = puf_id
                break
        if listed_puf_id:
            digits = listed_puf_id.split("-", 1)[1].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            ascii_zip_url = (
                f"https://meps.ahrq.gov/mepsweb/data_files/pufs/h{digits.lower()}/"
                f"h{digits.lower()}dat.zip"
            )
        elif zip_hits:
            ascii_zip_url = zip_hits[0].group(0)

    released = bool(has_fy_label and listed_puf_id)
    if released:
        notes = (
            f"Official MEPS listing now includes 2024 Full Year Consolidated "
            f"as {listed_puf_id}. Prefer this file over HC-251."
        )
    else:
        notes = (
            "2024 Full Year Consolidated is NOT in the official MEPS PUF listing. "
            f"AHRQ schedule still lists it for {MEPS_2024_FY_SCHEDULE}. "
            f"Continue using {MEPS_PUF_ID} with true source year = {MEPS_DATA_YEAR}."
        )
    return {
        "checked_at_source": fetched_url,
        "schedule_url": MEPS_SCHEDULE_URL,
        "schedule_states_2024_fy": MEPS_2024_FY_SCHEDULE,
        "released": released,
        "listed_puf_id": listed_puf_id,
        "ascii_zip_url": ascii_zip_url,
        "notes": notes,
    }


def download_meps_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Retrieve latest listed official MEPS Full Year Consolidated, or HC-251."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported MEPS project cost year: {year}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    refresh = check_meps_2024_full_year_listing()
    if refresh["released"] and refresh["ascii_zip_url"] and refresh["listed_puf_id"]:
        puf_id = str(refresh["listed_puf_id"])
        digits = puf_id.split("-", 1)[1].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ").lower()
        artifact = acquire_source(
            source_id=f"meps_table1_{year}",
            url=str(refresh["ascii_zip_url"]),
            cache_dir=cache_dir,
            expected_filename=f"h{digits}dat.zip",
            force_download=force_download,
            refresh_if_unprovenanced=True,
        )
        if artifact is None:
            return record_unretrieved(
                f"meps_table1_{year}",
                status="UNAVAILABLE",
                resolved_url=MEPS_LISTING_URL,
                notes=(
                    f"Official MEPS {puf_id} (2024 Full Year Consolidated) was listed "
                    "but could not be retrieved."
                ),
            )
        return dataclasses.replace(
            artifact,
            notes=(
                f"MEPS {puf_id} data year 2024 used as OOP source vintage "
                f"for project cost year {year}. Refresh check found the 2024 FY file "
                f"on the official listing. {refresh['notes']}"
            ),
        )

    artifact = acquire_source(
        source_id=f"meps_table1_{year}",
        url=MEPS_HC251_ASCII_ZIP,
        cache_dir=cache_dir,
        expected_filename="h251dat.zip",
        force_download=force_download,
        refresh_if_unprovenanced=True,
    )
    if artifact is None:
        return record_unretrieved(
            f"meps_table1_{year}",
            status="UNAVAILABLE",
            resolved_url=MEPS_HC251_LANDING,
            notes=(
                f"Official MEPS {MEPS_PUF_ID} ({MEPS_DATA_YEAR} data year) could not be retrieved. "
                "No fabricated meps_fy_{year}.csv URL is used. "
                f"{MEPS_NOTE}"
            ),
        )
    return dataclasses.replace(
        artifact,
        notes=(
            f"MEPS {MEPS_PUF_ID} data year {MEPS_DATA_YEAR} used as OOP source vintage "
            f"for project cost year {year}. This is not a {year} MEPS file. "
            f"{refresh['notes']}"
        ),
    )


def parse_meps_oop_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> LivingCostComponentObservation:
    """Parse MEPS expected OOP healthcare expenditure table for adults 18-64 with INSCOV23=1 (ANY PRIVATE)."""
    file_path = cache_dir if cache_dir.is_file() else cache_dir / "h251dat.zip"

    if not file_path.exists():
        logger.warning(f"MEPS CSV not found: {file_path}")
        return LivingCostComponentObservation(
            component_id="healthcare_oop_meps",
            category="healthcare",
            geography_type="national",
            geography_id="US",
            geography_name="United States Baseline",
            state="US",
            reference_year=reference_year,
            value_annual=None,
            value_monthly=None,
            unit="USD",
            status=ComponentStatus.UNAVAILABLE,
            source_id=f"meps_fyc_{reference_year}",
            source_variable="TOTSLFX_mean_adult_18_64_priv_ins",
            source_url=MEPS_HC251_LANDING,
            source_release=f"AHRQ MEPS {MEPS_PUF_ID} ({MEPS_DATA_YEAR} data year)",
            source_reference_period=str(MEPS_DATA_YEAR),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes="UNAVAILABLE: MEPS out-of-pocket medical expenditure CSV could not be found.",
        )

    expected_oop_annual: float | None = None
    sample_size: int = 0
    represented_pop: int = 0

    try:
        with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                age_group = str(row.get("age_group") or row.get("Age") or "").strip()
                ins_status = (
                    str(
                        row.get("insurance_status")
                        or row.get("Insurance")
                        or row.get("insurance")
                        or ""
                    )
                    .strip()
                    .lower()
                )

                # Enforce strict population filter: Adults 18-64 + Private Insurance
                is_adult = (
                    "18-64" in age_group or "adult" in age_group.lower() or age_group == "18 to 64"
                )
                is_private = (
                    "priv" in ins_status or "any private" in ins_status or ins_status == "private"
                )

                if is_adult and is_private:
                    oop_str = (
                        row.get("mean_oop_expenditure")
                        or row.get("oop_annual")
                        or row.get("TOTSLFX_mean")
                    )
                    if oop_str is not None and str(oop_str).strip() != "":
                        try:
                            val = float(str(oop_str).replace("$", "").replace(",", "").strip())
                            if val > 0:
                                expected_oop_annual = val
                                sample_size = int(
                                    float(row.get("sample_count") or row.get("n_unweighted") or 0)
                                )
                                represented_pop = int(
                                    float(
                                        row.get("represented_population")
                                        or row.get("n_weighted")
                                        or 0
                                    )
                                )
                                break
                        except ValueError:
                            continue
    except (OSError, ValueError, csv.Error, UnicodeError) as e:
        logger.error(f"Failed to parse MEPS CSV: {e}")

    if expected_oop_annual is None or expected_oop_annual <= 0:
        # FAIL-CLOSED: No numeric substitution allowed
        return LivingCostComponentObservation(
            component_id="healthcare_oop_meps",
            category="healthcare",
            geography_type="national",
            geography_id="US",
            geography_name="United States Baseline",
            state="US",
            reference_year=reference_year,
            value_annual=None,
            value_monthly=None,
            unit="USD",
            status=ComponentStatus.UNAVAILABLE,
            source_id=f"meps_fyc_{reference_year}",
            source_variable="TOTSLFX_mean_adult_18_64_priv_ins",
            source_url=MEPS_HC251_LANDING,
            source_release=f"AHRQ MEPS {MEPS_PUF_ID} ({MEPS_DATA_YEAR} data year)",
            source_reference_period=str(MEPS_DATA_YEAR),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes="UNAVAILABLE: MEPS out-of-pocket medical expenditure could not be parsed from source dataset.",
        )

    return LivingCostComponentObservation(
        component_id="healthcare_oop_meps",
        category="healthcare",
        geography_type="national",
        geography_id="US",
        geography_name="United States Baseline",
        state="US",
        reference_year=reference_year,
        value_annual=round(expected_oop_annual, 2),
        value_monthly=round(expected_oop_annual / 12.0, 2),
        unit="USD",
        status=ComponentStatus.MEASURED,
        source_id=f"meps_table1_{reference_year}",
        source_variable="TOTSLFX_mean_adult_18_64_priv_ins",
        source_url=MEPS_HC251_LANDING,
        source_release=f"AHRQ MEPS {MEPS_PUF_ID} ({MEPS_DATA_YEAR} data year)",
        source_reference_period=str(MEPS_DATA_YEAR),
        retrieved_at=retrieved_at,
        source_artifact_sha256=file_sha256,
        methodology_version="0.2.0-draft",
        notes=(
            f"AHRQ MEPS weighted mean OOP medical spending for adults age 18-64 with INSCOV23=1 (ANY PRIVATE) "
            f"(Sample: {sample_size:,}, Represented: {represented_pop:,}). {MEPS_NOTE}"
        ),
    )


def parse_hc251_sas_layout(sas_text: str) -> dict[str, tuple[int, int]]:
    """Parse official SAS INPUT @start NAME width statements for HC-251 fields."""
    found: dict[str, tuple[int, int]] = {}
    for match in _SAS_INPUT_RE.finditer(sas_text):
        name = match.group("name")
        if name not in HC251_LAYOUT:
            continue
        start = int(match.group("start"))
        width_token = match.group("width")
        width = int(width_token.split(".", 1)[0])
        found[name] = (start, start + width - 1)
    missing = sorted(set(HC251_LAYOUT) - set(found))
    if missing:
        raise ValueError(f"Official SAS statements missing HC-251 fields: {missing}")
    for name, expected in HC251_LAYOUT.items():
        if found[name] != expected:
            raise ValueError(
                f"SAS layout {name}={found[name]} disagrees with official codebook {expected}"
            )
    return found


def _field(line: bytes, start: int, end: int) -> str:
    return line[start - 1 : end].decode("ascii", errors="replace")


def _split_hc251_records(raw: bytes) -> list[bytes]:
    if b"\r\n" in raw[:8000]:
        lines = raw.split(b"\r\n")
    else:
        lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    return lines


def weighted_percentile(values: list[float], weights: list[float], q: float) -> float | None:
    if not values or not weights or q <= 0 or q > 1:
        return None
    pairs = sorted(zip(values, weights, strict=True), key=lambda item: item[0])
    total = sum(weights)
    if total <= 0:
        return None
    acc = 0.0
    target = total * q
    for value, weight in pairs:
        acc += weight
        if acc >= target:
            return value
    return pairs[-1][0]


def derive_od002_oop(
    records: list[bytes],
    *,
    layout: dict[str, tuple[int, int]] | None = None,
) -> dict[str, Any]:
    """OD-002 weighted mean / median / P75 from official HC-251 fixed-width records.

    Filter: AGELAST 18-64, INSCOV23=1 (ANY PRIVATE), PERWT23F>0, TOTSLF23>=0.
    Zeros are included. Download is not derivation.
    """
    spec = layout or HC251_LAYOUT
    ages: list[int] = []
    oops: list[float] = []
    weights: list[float] = []
    rejected = 0
    for line in records:
        try:
            age = int(_field(line, *spec["AGELAST"]).strip() or "999")
            ins = int(_field(line, *spec["INSCOV23"]).strip() or "9")
            oop = float(_field(line, *spec["TOTSLF23"]).strip() or "nan")
            weight = float(_field(line, *spec["PERWT23F"]).strip() or "0")
        except ValueError:
            rejected += 1
            continue
        if 18 <= age <= 64 and ins == INSCOV_ANY_PRIVATE and weight > 0 and oop >= 0:
            ages.append(age)
            oops.append(oop)
            weights.append(weight)
    if not oops:
        raise ValueError("HC-251 derivation produced no in-universe persons")
    wsum = sum(weights)
    mean = sum(value * weight for value, weight in zip(oops, weights, strict=True)) / wsum
    return {
        "source_data_year": MEPS_DATA_YEAR,
        "puf_id": MEPS_PUF_ID,
        "source_variable": "TOTSLF23",
        "weight_variable": "PERWT23F",
        "age_variable": "AGELAST",
        "insurance_variable": "INSCOV23",
        "insurance_code": INSCOV_ANY_PRIVATE,
        "insurance_code_label": "ANY PRIVATE",
        "age_low": 18,
        "age_high": 64,
        "includes_zero_oop": True,
        "row_count": len(records),
        "rejected_parse_count": rejected,
        "in_universe_n": len(oops),
        "weighted_population": wsum,
        "weighted_mean": round(mean, 2),
        "weighted_median": weighted_percentile(oops, weights, 0.50),
        "weighted_p75": weighted_percentile(oops, weights, 0.75),
        "unweighted_mean": round(sum(oops) / len(oops), 2),
        "layout": {name: [start, end] for name, (start, end) in spec.items()},
    }


def derive_od002_from_zip(
    zip_path: Path,
    *,
    sas_path: Path | None = None,
) -> dict[str, Any]:
    """Read official h251dat.zip and derive OD-002. Does not calculate an MSLC."""
    raw_zip = zip_path.read_bytes()
    zip_sha = hashlib.sha256(raw_zip).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".dat")]
        if not names:
            raise ValueError(f"{zip_path.name} has no .dat member")
        dat = archive.read(names[0])
    layout = HC251_LAYOUT
    sas_sha = None
    if sas_path is not None and sas_path.exists():
        sas_text = sas_path.read_text(encoding="utf-8", errors="replace")
        layout = parse_hc251_sas_layout(sas_text)
        sas_sha = hashlib.sha256(sas_text.encode("utf-8")).hexdigest()
    stats = derive_od002_oop(_split_hc251_records(dat), layout=layout)
    stats.update(
        {
            "report_type": "living_cost_meps_oop_derivation",
            "generated_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "publisher": "AHRQ MEPS",
            "landing_url": MEPS_HC251_LANDING,
            "codebook_url": MEPS_HC251_CODEBOOK,
            "sas_statements_url": MEPS_HC251_SAS_STATEMENTS,
            "artifact_url": MEPS_HC251_ASCII_ZIP,
            "artifact_filename": zip_path.name,
            "dat_member": names[0],
            "sha256": zip_sha,
            "byte_size": len(raw_zip),
            "sas_sha256": sas_sha,
            "download_is_not_derivation": True,
            "calculates_mslc": False,
            "evidence_status": "MODELED_FROM_MEASURED_INPUTS",
            "notes": (
                "OD-002 canonical statistic is the person-weighted mean of TOTSLF23 among "
                "AGELAST 18-64 with INSCOV23=1 (ANY PRIVATE). Weighted median and P75 are "
                "required sensitivities. source_data_year remains 2023. "
                f"{MEPS_NOTE}"
            ),
        }
    )
    return stats


def write_meps_oop_derivation(
    zip_path: Path,
    dest: Path | None = None,
    *,
    sas_path: Path | None = None,
) -> dict[str, Any]:
    payload = derive_od002_from_zip(zip_path, sas_path=sas_path)
    target = dest or MEPS_OOP_REPORT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_meps_oop_derivation(path: Path | None = None) -> dict[str, Any] | None:
    target = path or MEPS_OOP_REPORT
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("report_type") != "living_cost_meps_oop_derivation":
        return None
    if payload.get("source_data_year") != MEPS_DATA_YEAR:
        return None
    mean = payload.get("weighted_mean")
    if not isinstance(mean, (int, float)) or mean < 0:
        return None
    return payload
