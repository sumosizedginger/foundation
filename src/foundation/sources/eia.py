"""Energy Information Administration (EIA) Retail Gasoline Source Adapter.

Ingests state and PADD regional regular retail gasoline prices ($/gallon) from EIA.
Outputs measured price_per_gallon ONLY (status = MEASURED).
Economic consumption modeling (miles/MPG/gallons) is strictly separated into living_cost/transportation.py.
"""

from __future__ import annotations

import csv
import hashlib
import logging
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

logger = logging.getLogger(__name__)

EIA_GAS_URL = "https://www.eia.gov/petroleum/gasdiesel/"


EIA_GAS_XLS_URL = "https://www.eia.gov/petroleum/gasdiesel/xls/pswrgvwall.xls"
EIA_WORKBOOK_FILENAME = "pswrgvwall.xls"


def selected_eia_workbook_sha256(file_path: Path) -> str | None:
    """SHA-256 of the selected EIA workbook bytes.

    The provenance sidecar is not identity. Missing workbook => None.
    """
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_eia_gas_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Official EIA weekly retail gasoline workbook (national + PADD + selected states)."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported EIA reference year: {year}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    from foundation.sources.acquisition import acquire_source

    return acquire_source(
        source_id=f"eia_gas_price_{year}",
        url=EIA_GAS_XLS_URL,
        cache_dir=cache_dir,
        expected_filename="pswrgvwall.xls",
        force_download=force_download,
    )


def parse_eia_gas_prices_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse EIA state retail regular gasoline price dataset."""
    if cache_dir.is_file():
        file_path = cache_dir
    else:
        xls = cache_dir / "pswrgvwall.xls"
        csv_path = cache_dir / f"eia_gas_{reference_year}.csv"
        file_path = xls if xls.exists() else csv_path

    if file_path.suffix.lower() == ".xls":
        return parse_eia_gas_prices_xls(
            file_path,
            reference_year=reference_year,
            retrieved_at=retrieved_at,
            file_sha256=file_sha256,
        )

    if not file_path.exists():
        logger.warning(f"EIA gas CSV not found: {file_path}")
        return []

    observations: list[LivingCostComponentObservation] = []

    try:
        with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                state_alpha = str(row.get("state") or row.get("State") or "").strip().upper()
                if not state_alpha:
                    continue

                gas_price_str = (
                    row.get("regular_gas_price")
                    or row.get("price_per_gal")
                    or row.get("price")
                    or "0"
                )
                try:
                    price_per_gal = float(
                        str(gas_price_str).replace("$", "").replace(",", "").strip()
                    )
                except ValueError:
                    continue

                if price_per_gal <= 0:
                    continue

                obs = LivingCostComponentObservation(
                    component_id="eia_gas_price_per_gal",
                    category="transportation_input",
                    geography_type="state",
                    geography_id=state_alpha,
                    geography_name=f"{state_alpha} Regular Gasoline Price",
                    state=state_alpha,
                    reference_year=reference_year,
                    value_annual=round(price_per_gal, 3),  # Price per gallon
                    value_monthly=round(price_per_gal, 3),
                    unit="USD_PER_GALLON",
                    status=ComponentStatus.MEASURED,
                    source_id=f"eia_gas_price_{reference_year}",
                    source_variable="EMM_EPM0_PTE_R_DPG",
                    source_url=EIA_GAS_URL,
                    source_release=f"EIA Retail Gasoline Annual Average ({reference_year})",
                    source_reference_period=str(reference_year),
                    retrieved_at=retrieved_at,
                    source_artifact_sha256=file_sha256,
                    methodology_version="0.2.0-draft",
                    notes=f"EIA official measured average price for regular retail gasoline in {state_alpha}: ${price_per_gal:.3f}/gal.",
                )
                observations.append(obs)
    except (OSError, ValueError, csv.Error, UnicodeError) as e:
        logger.error(f"Failed to parse EIA Gas CSV: {e}")

    return observations


# Geography labels that are not state-measured retail prices.
EIA_NON_STATE_LABELS = {
    "U.S.",
    "US",
    "UNITED STATES",
    "EAST COAST",
    "NEW ENGLAND",
    "CENTRAL ATLANTIC",
    "LOWER ATLANTIC",
    "MIDWEST",
    "GULF COAST",
    "ROCKY MOUNTAIN",
    "WEST COAST",
    "PADD 1",
    "PADD 2",
    "PADD 3",
    "PADD 4",
    "PADD 5",
}


def _iter_eia_weekly_rows(file_path: Path) -> Iterator[tuple[str, date | None, int | None, float]]:
    """Yield (geo_name, observed_date, year, price) from the official workbook."""
    try:
        import xlrd
    except ImportError:
        logger.error("xlrd is required to parse EIA .xls workbooks")
        return

    try:
        book = xlrd.open_workbook(file_path)
    except (OSError, xlrd.XLRDError, ValueError) as exc:
        logger.error("Failed to open EIA gasoline workbook: %s", exc)
        return

    for sheet in book.sheets():
        header_row = None
        geo_name = str(sheet.name).strip()
        for r in range(min(sheet.nrows, 4000)):
            row = [sheet.cell_value(r, c) for c in range(min(sheet.ncols, 4))]
            blob = " ".join(str(x) for x in row).lower()
            if header_row is None and ("date" in blob or "week" in blob):
                header_row = r
                continue
            if header_row is None:
                continue
            raw_date, raw_val = row[0], row[1] if len(row) > 1 else None
            observed = _eia_cell_date(raw_date, book.datemode)
            year = (
                observed.year if observed is not None else _eia_cell_year(raw_date, book.datemode)
            )
            try:
                price = float(raw_val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            yield geo_name, observed, year, price


def parse_eia_gas_prices_xls(
    file_path: Path,
    *,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse official EIA weekly regular retail gasoline workbook.

    The workbook is national + PADD + selected states. Observations that are
    PADD/regional are labeled as such and are not called state-measured.
    """
    values_by_geo: dict[str, list[float]] = {}
    for geo_name, _observed, year, price in _iter_eia_weekly_rows(file_path):
        if year != reference_year:
            continue
        values_by_geo.setdefault(geo_name, []).append(price)

    observations: list[LivingCostComponentObservation] = []
    for geo_name, values in values_by_geo.items():
        mean_price = round(sum(values) / len(values), 3)
        geo_upper = geo_name.upper()
        is_state = (
            len(geo_name) == 2 and geo_name.isalpha() and geo_upper not in EIA_NON_STATE_LABELS
        )
        geography_type = "state" if is_state else "region"
        observations.append(
            LivingCostComponentObservation(
                component_id="eia_gas_price_per_gal",
                category="transportation_input",
                geography_type=geography_type,
                geography_id=geo_name if is_state else geo_upper.replace(" ", "_")[:32],
                geography_name=geo_name,
                state=geo_name if is_state else "US",
                reference_year=reference_year,
                value_annual=mean_price,
                value_monthly=mean_price,
                unit="USD_PER_GALLON",
                status=ComponentStatus.MEASURED,
                source_id=f"eia_gas_price_{reference_year}",
                source_variable="weekly_regular_retail_mean",
                source_url=EIA_GAS_XLS_URL,
                source_release=f"EIA Weekly Retail Gasoline ({geo_name})",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=(
                    f"EIA workbook sheet '{geo_name}' calendar-year mean of "
                    f"{len(values)} weekly regular retail observations in {reference_year}: "
                    f"${mean_price:.3f}/gal. "
                    + (
                        "State-measured."
                        if is_state
                        else "Regional/PADD/national — not a state-measured price."
                    )
                ),
            )
        )
    return observations


def max_eia_observation_date(file_path: Path) -> date | None:
    """Newest calendar date present in the official weekly gasoline workbook."""
    try:
        import xlrd
    except ImportError:
        return None
    try:
        book = xlrd.open_workbook(file_path)
    except (OSError, xlrd.XLRDError, ValueError):
        return None
    latest: date | None = None
    for sheet in book.sheets():
        for row_idx in range(min(sheet.nrows, 4000)):
            raw = sheet.cell_value(row_idx, 0)
            if not isinstance(raw, (int, float)) or raw <= 200:
                continue
            try:
                parts = xlrd.xldate_as_tuple(float(raw), book.datemode)
                observed = date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, TypeError, OverflowError):
                continue
            if latest is None or observed > latest:
                latest = observed
    return latest


def eia_year_observation_dates(file_path: Path, reference_year: int) -> list[date]:
    """Unique weekly observation dates for one calendar year, sorted."""
    if not file_path.is_file():
        return []
    found: set[date] = set()
    for _geo, observed, year, _price in _iter_eia_weekly_rows(file_path):
        if year != reference_year or observed is None or observed.year != reference_year:
            continue
        found.add(observed)
    return sorted(found)


def summarize_eia_year(
    file_path: Path,
    *,
    reference_year: int,
    sha256: str | None = None,
) -> dict[str, Any]:
    """Year-specific EIA coverage from the official parser, not the global max date.

    A year is covered only when parse_eia_gas_prices_xls returns canonical
    evidence for that reference year. The last observation date is the last
    row in that year, never a later year's global maximum.
    """
    digest = sha256 if sha256 is not None else selected_eia_workbook_sha256(file_path)
    if not file_path.is_file():
        return {
            "covered": False,
            "source_data_year": reference_year,
            "first_observation_date": None,
            "last_observation_date": None,
            "observation_count": 0,
            "geographic_series_count": 0,
            "artifact": EIA_WORKBOOK_FILENAME,
            "sha256": None,
            "note": "selected workbook bytes are absent",
        }
    observations = parse_eia_gas_prices_xls(
        file_path,
        reference_year=reference_year,
        file_sha256=digest or "",
    )
    dates = eia_year_observation_dates(file_path, reference_year)
    covered = bool(observations)
    return {
        "covered": covered,
        "source_data_year": reference_year,
        "first_observation_date": None if not dates else dates[0].isoformat(),
        "last_observation_date": None if not dates else dates[-1].isoformat(),
        "observation_count": len(dates),
        "geographic_series_count": len(observations),
        "artifact": EIA_WORKBOOK_FILENAME,
        "sha256": digest,
        "note": (
            f"{reference_year} weekly observations"
            if covered
            else f"{reference_year} weekly observations missing"
        ),
    }


def _eia_cell_date(raw_date: object, datemode: int) -> date | None:
    if isinstance(raw_date, (int, float)) and raw_date > 200:
        try:
            import xlrd

            parts = xlrd.xldate_as_tuple(float(raw_date), datemode)
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, TypeError, OverflowError):
            return None
    text = str(raw_date).strip()
    if len(text) >= 10 and text[4:5] in {"-", "/"}:
        try:
            return date.fromisoformat(text[:10].replace("/", "-"))
        except ValueError:
            return None
    return None


def _eia_cell_year(raw_date: object, datemode: int) -> int | None:
    observed = _eia_cell_date(raw_date, datemode)
    if observed is not None:
        return observed.year
    text = str(raw_date)
    for token in text.replace("/", "-").split("-"):
        if token.isdigit() and len(token) == 4:
            return int(token)
    return None
