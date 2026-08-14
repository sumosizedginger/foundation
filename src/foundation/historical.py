from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Official BLS CPI-U Annual Averages (Series: CUUR0000SA0 / CUSR0000SA0)
# Base reference year for constant dollar translations: 2024
CPI_U_ANNUAL_AVERAGES: dict[int, float] = {
    2020: 258.811,
    2021: 270.970,
    2022: 292.655,
    2023: 304.702,
    2024: 314.072,
}


@dataclass(frozen=True)
class HistoricalAnchorVintage:
    survey_year: int
    income_year: int
    nominal_cutoff: float
    constant_2024_dollars: float
    cpi_u_index: float
    cpi_base_year: int
    represented_population: float
    quantiles_nominal: dict[str, float]
    quantiles_constant_2024: dict[str, float]
    source_archive: str
    archive_sha256: str
    methodology_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def adjust_to_constant_dollars(
    nominal_value: float,
    from_year: int,
    to_year: int = 2024,
) -> float:
    """Adjust a nominal dollar amount to constant dollars using official CPI-U averages."""
    if from_year not in CPI_U_ANNUAL_AVERAGES:
        raise ValueError(f"No CPI-U annual average available for year {from_year}")
    if to_year not in CPI_U_ANNUAL_AVERAGES:
        raise ValueError(f"No CPI-U annual average available for target year {to_year}")

    from_cpi = CPI_U_ANNUAL_AVERAGES[from_year]
    to_cpi = CPI_U_ANNUAL_AVERAGES[to_year]
    return round(nominal_value * (to_cpi / from_cpi), 2)


def get_historical_vintages_summary() -> list[HistoricalAnchorVintage]:
    """Return historical verified Population Anchor vintages with nominal and constant dollar values."""
    raw_vintages = [
        {
            "survey_year": 2023,
            "income_year": 2022,
            "nominal_cutoff": 19304.60,
            "represented_population": 330631702.0,
            "source_archive": "asecpub23csv.zip",
            "archive_sha256": "d2e000250782adfb0f10c6fb0cffca5a3a776ee46f73111c1d8157e84a282f16",
            "quantiles_nominal": {
                "P10": 8513.75,
                "P20": 14000.00,
                "P30": 19304.60,
                "P40": 24655.75,
                "P50": 30634.00,
                "P75": 53045.50,
                "P90": 87690.67,
            },
        },
        {
            "survey_year": 2024,
            "income_year": 2023,
            "nominal_cutoff": 20688.00,
            "represented_population": 332382485.0,
            "source_archive": "asecpub24csv.zip",
            "archive_sha256": "cdb39cdac34bef991206d738ffae2bb0e6fc8daec02c8e31a1e0c326d9c6be4b",
            "quantiles_nominal": {
                "P10": 9133.60,
                "P20": 15000.00,
                "P30": 20688.00,
                "P40": 26377.00,
                "P50": 32851.80,
                "P75": 57548.00,
                "P90": 94500.00,
            },
        },
        {
            "survey_year": 2025,
            "income_year": 2024,
            "nominal_cutoff": 21800.00,
            "represented_population": 337689642.0,
            "source_archive": "asecpub25csv.zip",
            "archive_sha256": "318845a2b5e0034eb2973898de1738f4df0025727de38499e7669cb9c0deef0b",
            "quantiles_nominal": {
                "P10": 10000.00,
                "P20": 15896.00,
                "P30": 21800.00,
                "P40": 28000.00,
                "P50": 35036.50,
                "P75": 61640.00,
                "P90": 100100.00,
            },
        },
    ]

    vintages: list[HistoricalAnchorVintage] = []
    base_year = 2024
    for r in raw_vintages:
        iy = int(r["income_year"])
        nom_cutoff = float(r["nominal_cutoff"])
        real_cutoff = adjust_to_constant_dollars(nom_cutoff, iy, base_year)

        quant_real = {
            k: adjust_to_constant_dollars(float(v), iy, base_year)
            for k, v in r["quantiles_nominal"].items()  # type: ignore
        }

        vintages.append(
            HistoricalAnchorVintage(
                survey_year=int(r["survey_year"]),
                income_year=iy,
                nominal_cutoff=nom_cutoff,
                constant_2024_dollars=real_cutoff,
                cpi_u_index=CPI_U_ANNUAL_AVERAGES[iy],
                cpi_base_year=base_year,
                represented_population=float(r["represented_population"]),
                quantiles_nominal=r["quantiles_nominal"],  # type: ignore
                quantiles_constant_2024=quant_real,
                source_archive=str(r["source_archive"]),
                archive_sha256=str(r["archive_sha256"]),
                methodology_version="0.1.0-draft",
            )
        )
    return vintages
