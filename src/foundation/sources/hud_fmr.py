"""HUD Fair Market Rent source connector.

Ingests county and FMR-area 1-Bedroom 40th percentile gross rents from official HUD datasets.
"""

from __future__ import annotations
from typing import Any
import requests

HUD_FMR_BASE_URL = "https://www.huduser.gov/portal/datasets/fmr.html"


def get_hud_fmr_download_url(year: int = 2024) -> str:
    """Return official HUD dataset download URL for given fiscal year."""
    yy = str(year)[-2:]
    return f"https://www.huduser.gov/portal/datasets/fmr/fmr{year}/FY{yy}_FMRs_revised.xlsx"
