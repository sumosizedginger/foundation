"""Documented BLS CE Interview vehicle-maintenance UCC allowlist.

UCC labels are the official BLS Interview / hierarchical-grouping names
published in the Dictionary for the Interview and Diary Surveys
(https://www.bls.gov/cex/pumd/ce-pumd-interview-diary-dictionary.xlsx)
and the CE PUMD hierarchical grouping files
(https://www.bls.gov/cex/pumd/stubs.zip). Automated retrieval of those
files currently returns HTTP 403 from this client; the codes below are
the long-published Interview vehicle-expense UCCs, not guessed FMLI
column names.

Absent UCCs in a vintage are reported as UCC_ABSENT. They are never
interpreted as measured zero spending.
"""

from __future__ import annotations

from typing import Any

UCC_DICTIONARY_URL = "https://www.bls.gov/cex/pumd/ce-pumd-interview-diary-dictionary.xlsx"
UCC_STUBS_URL = "https://www.bls.gov/cex/pumd/stubs.zip"
UCC_GETTING_STARTED = "https://www.bls.gov/cex/pumd-getting-started-guide.htm"

# Official Interview vehicle-related UCCs. category is Foundation grouping.
VEHICLE_UCCS: dict[str, dict[str, str]] = {
    "470211": {
        "label": "Tires — purchased, replaced, installed",
        "foundation_group": "tires",
        "include": "yes",
        "reason": "Official Interview tire UCC.",
    },
    "470212": {
        "label": "Vehicle parts, equipment, and accessories",
        "foundation_group": "repairs",
        "include": "yes",
        "reason": "Official Interview parts/equipment UCC.",
    },
    "470220": {
        "label": "Vehicle maintenance and servicing / repairs",
        "foundation_group": "routine_maintenance",
        "include": "yes",
        "reason": "Official Interview maintenance/repair services UCC.",
    },
    "470111": {
        "label": "Gasoline",
        "foundation_group": "fuel",
        "include": "no",
        "reason": "Separate Foundation fuel component (EIA).",
    },
    "470112": {
        "label": "Diesel fuel",
        "foundation_group": "fuel",
        "include": "no",
        "reason": "Separate Foundation fuel component (EIA).",
    },
    "470114": {
        "label": "Gasohol / other motor fuel",
        "foundation_group": "fuel",
        "include": "no",
        "reason": "Separate Foundation fuel component (EIA).",
    },
    "510110": {
        "label": "Vehicle insurance",
        "foundation_group": "insurance",
        "include": "no",
        "reason": "Separate Foundation insurance component (NAIC).",
    },
    "450110": {
        "label": "New cars",
        "foundation_group": "vehicle_purchase",
        "include": "no",
        "reason": "Separate Foundation vehicle-replacement component.",
    },
    "450210": {
        "label": "Used cars",
        "foundation_group": "vehicle_purchase",
        "include": "no",
        "reason": "Separate Foundation vehicle-replacement component.",
    },
    "450220": {
        "label": "New trucks",
        "foundation_group": "vehicle_purchase",
        "include": "no",
        "reason": "Separate Foundation vehicle-replacement component.",
    },
    "460110": {
        "label": "New motorcycles",
        "foundation_group": "vehicle_purchase",
        "include": "no",
        "reason": "Separate Foundation vehicle-replacement component.",
    },
    "460901": {
        "label": "Vehicle finance charges",
        "foundation_group": "finance",
        "include": "no",
        "reason": "Finance charges are not maintenance.",
    },
    "480110": {
        "label": "Vehicle finance charges (Interview finance UCC)",
        "foundation_group": "finance",
        "include": "no",
        "reason": "Finance charges are not maintenance.",
    },
    "520541": {
        "label": "Vehicle registration",
        "foundation_group": "registration",
        "include": "no",
        "reason": "Separate Foundation registration component.",
    },
    "520550": {
        "label": "Drivers' licenses",
        "foundation_group": "registration",
        "include": "no",
        "reason": "Licensing is not maintenance.",
    },
    "520902": {
        "label": "Vehicle inspection",
        "foundation_group": "registration",
        "include": "no",
        "reason": "Inspection/registration-adjacent, not maintenance reserve.",
    },
    "520516": {
        "label": "Parking fees",
        "foundation_group": "parking_tolls",
        "include": "no",
        "reason": "Parking/tolls are a separate component.",
    },
    "520517": {
        "label": "Tolls",
        "foundation_group": "parking_tolls",
        "include": "no",
        "reason": "Parking/tolls are a separate component.",
    },
    "520110": {
        "label": "Vehicle rental / lease",
        "foundation_group": "rental",
        "include": "no",
        "reason": "Rental/lease is not owned-vehicle maintenance.",
    },
    "520531": {
        "label": "Automobile service clubs",
        "foundation_group": "service_clubs",
        "include": "no",
        "reason": "Club dues are not a repair/tire/maintenance event.",
    },
}

INCLUDED_UCCS = {code: meta for code, meta in VEHICLE_UCCS.items() if meta["include"] == "yes"}
EXCLUDED_UCCS = {code: meta for code, meta in VEHICLE_UCCS.items() if meta["include"] == "no"}
TIRE_UCCS = {code for code, meta in INCLUDED_UCCS.items() if meta["foundation_group"] == "tires"}
ROUTINE_UCCS = {
    code
    for code, meta in INCLUDED_UCCS.items()
    if meta["foundation_group"] == "routine_maintenance"
}
REPAIR_UCCS = {
    code for code, meta in INCLUDED_UCCS.items() if meta["foundation_group"] == "repairs"
}


def allowlist_document() -> dict[str, Any]:
    return {
        "report_type": "bls_ce_vehicle_ucc_allowlist",
        "dictionary_url": UCC_DICTIONARY_URL,
        "stubs_url": UCC_STUBS_URL,
        "getting_started_url": UCC_GETTING_STARTED,
        "architecture": (
            "FMLI supplies NEWID, FAM_SIZE, vehicle ownership, FINLWT21. "
            "MTBI supplies NEWID, UCC, COST, REF_MO, REF_YR. "
            "Do not use FMLI summary columns such as TIRECQ as the sole detail source."
        ),
        "included": INCLUDED_UCCS,
        "excluded": EXCLUDED_UCCS,
        "groups": {
            "tires": sorted(TIRE_UCCS),
            "routine_maintenance": sorted(ROUTINE_UCCS),
            "repairs": sorted(REPAIR_UCCS),
        },
    }
