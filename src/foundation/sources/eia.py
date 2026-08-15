"""Energy Information Administration (EIA) Retail Gasoline Source Adapter.

Ingests state and PADD regional regular retail gasoline prices ($/gallon) from EIA.
Outputs measured price_per_gallon ONLY (status = MEASURED).
Economic consumption modeling (miles/MPG/gallons) is strictly separated into living_cost/transportation.py.
"""

from __future__ import annotations

import csv
import logging
from datetime import date
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

logger = logging.getLogger(__name__)

EIA_GAS_URL = "https://www.eia.gov/petroleum/gasdiesel/"


EIA_GAS_XLS_URL = "https://www.eia.gov/petroleum/gasdiesel/xls/pswrgvwall.xls"


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
    try:
        import xlrd
    except ImportError:
        logger.error("xlrd is required to parse EIA .xls workbooks")
        return []

    try:
        book = xlrd.open_workbook(file_path)
    except (OSError, xlrd.XLRDError, ValueError) as exc:
        logger.error("Failed to open EIA gasoline workbook: %s", exc)
        return []

    observations: list[LivingCostComponentObservation] = []
    # The first data sheet is typically the weekly U.S. series; later sheets
    # are PADD/state. We walk every sheet and keep only calendar-year means.
    for sheet in book.sheets():
        header_row = None
        geo_name = str(sheet.name).strip()
        dates: list[float] = []
        values: list[float] = []
        for r in range(min(sheet.nrows, 4000)):
            row = [sheet.cell_value(r, c) for c in range(min(sheet.ncols, 4))]
            blob = " ".join(str(x) for x in row).lower()
            if header_row is None and ("date" in blob or "week" in blob):
                header_row = r
                continue
            if header_row is None:
                continue
            raw_date, raw_val = row[0], row[1] if len(row) > 1 else None
            year = _eia_cell_year(raw_date, book.datemode)
            if year != reference_year:
                continue
            try:
                price = float(raw_val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            dates.append(price)
            values.append(price)
        if not values:
            continue
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
                source_release=f"EIA Weekly Retail Gasoline ({sheet.name})",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=(
                    f"EIA workbook sheet '{sheet.name}' calendar-year mean of "
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


def _eia_cell_year(raw_date: object, datemode: int) -> int | None:
    if isinstance(raw_date, (int, float)) and raw_date > 200:
        try:
            import xlrd

            parts = xlrd.xldate_as_tuple(float(raw_date), datemode)
            return int(parts[0])
        except (ValueError, TypeError, OverflowError):
            return None
    text = str(raw_date)
    for token in text.replace("/", "-").split("-"):
        if token.isdigit() and len(token) == 4:
            return int(token)
    return None
