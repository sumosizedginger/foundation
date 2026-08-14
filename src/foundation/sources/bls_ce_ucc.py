"""Documented BLS CE Interview vehicle-maintenance allowlist.

Official sources used to build this list (not guessed FMLI column names):

1. BLS CE PUMD Getting Started Guide §3.3.1 names the detailed Interview
   file VEQ / VQB as "Vehicle maintenance and repair" with type code
   (VOPSERVY / VQBCODE) and amount (VOPEXPX / VQBEXPX).
   https://www.bls.gov/cex/pumd-getting-started-guide.htm

2. Official CEQ instrument, April 2024–March 2025, Section 11B
   (VQB_ITEM / VQBCODE / VQBEXPX). Item text:
   1 driver's licenses; 2 inspection; 3 registration/personal property tax;
   4 extended warranties / repair service policies; 5 service clubs (AAA /
   OnStar / LoJack); 6 towing; 7 cleaning / detailing / car washes;
   8 tire purchases or mounting; 9 vehicle maintenance, parts, or services
   including oil changes and other filter and fluid replacements;
   10 vehicle accident or damage repair; 11 customization;
   12 accessories (recreation or safety); 13 tolls; 14 parking;
   15 docking/landing fees; 16 RV liquid fuels.
   https://www.bls.gov/cex/research_papers/pdf/2024-2025-ceqquestionnaire.pdf

3. Official 2024 Interview PUMD (intrvw24.zip) MTBI rows with
   EXPNAME=VQBEXPX. Exact NEWID+amount joins map VQBCODE → UCC:

   140 → 480110
   190 → 490100 (majority) / 480100
   200 → 490900
   210 → 620114
   220 → 520550
   230 → 490100 / 480100
   240 → 490100 / 480100
   250 → 520541
   260 → 520531
   270 → 520901
   280 → 250213
   320 → 490100 / 480100
   367 → 490100
   400 → 520310
   410 → 520410
   420 → 510115
   900 → $0 parent / combined overwrite (no unique UCC)

4. Historical Interview type codes that survive in VQBCODE:
   VOPSERVY 140 = tire purchases / mounting (BLS 2005 Interview
   documentation). CAPI 2017/2020 lists 190 = oil change, lubrication,
   or oil filter.

5. Pre-2023 Interview MTBI UCCs 470211 (tires) and 470220 (maintenance
   / repair) are ABSENT from the 2024 Interview MTBI. Their absence is
   not measured zero spending. UCC 470212 in 2024 MTBI is EXPNAME
   GASOILX / TOTYUPDX / TRNONCUX — a fuel/oil allocation residual,
   not parts — and is excluded.

Dictionary / stub URLs remain the official BLS documents. Automated
retrieval of those xlsx/zip files currently returns HTTP 403 from this
client; the codes above are taken from the official CEQ questionnaire
and from the official 2024 PUMD files themselves.
"""

from __future__ import annotations

from typing import Any

UCC_DICTIONARY_URL = "https://www.bls.gov/cex/pumd/ce-pumd-interview-diary-dictionary.xlsx"
UCC_STUBS_URL = "https://www.bls.gov/cex/pumd/stubs.zip"
UCC_GETTING_STARTED = "https://www.bls.gov/cex/pumd-getting-started-guide.htm"
CEQ_2024_2025_QUESTIONNAIRE = (
    "https://www.bls.gov/cex/research_papers/pdf/2024-2025-ceqquestionnaire.pdf"
)

# 2024 Interview VQB type codes. foundation_group is the Foundation split.
VQB_CODES: dict[str, dict[str, str]] = {
    "140": {
        "label": "Tire purchases or mounting",
        "foundation_group": "tires",
        "include": "yes",
        "official_mtbi_ucc": "480110",
        "reason": (
            "Historical VOPSERVY 140 = tires; 2024 CEQ item 8; "
            "official 2024 MTBI maps VQBEXPX to UCC 480110."
        ),
    },
    "190": {
        "label": "Vehicle maintenance, parts, or services including oil changes",
        "foundation_group": "routine_maintenance",
        "include": "yes",
        "official_mtbi_ucc": "490100",
        "reason": (
            "2017/2020 CAPI code 190 = oil change / lubrication / oil filter; "
            "2024 CEQ item 9; official 2024 MTBI maps VQBEXPX to UCC 490100."
        ),
    },
    "367": {
        "label": "Vehicle maintenance (BLS UCC 490100; small/frequent VQB events)",
        "foundation_group": "routine_maintenance",
        "include": "yes",
        "official_mtbi_ucc": "490100",
        "reason": (
            "Official 2024 MTBI assigns VQBCODE 367 almost entirely to UCC 490100, "
            "the same maintenance family as code 190. Not mapped to fuel, "
            "insurance, registration, parking, or purchase UCCs."
        ),
    },
    "320": {
        "label": "Vehicle accident or damage repair",
        "foundation_group": "repairs",
        "include": "yes",
        "official_mtbi_ucc": "490100",
        "reason": (
            "2024 CEQ item 10 (accident or damage repair, including mechanic "
            "service); official 2024 MTBI maps VQBEXPX to UCC 490100/480100."
        ),
    },
    "200": {
        "label": "Other vehicle maintenance/repair (UCC 490900)",
        "foundation_group": "repairs",
        "include": "yes",
        "official_mtbi_ucc": "490900",
        "reason": (
            "Official 2024 MTBI maps VQBCODE 200 to UCC 490900 (VQBEXPX in the "
            "490xxx vehicle-maintenance family)."
        ),
    },
    "230": {
        "label": "Vehicle maintenance/repair (UCC 490100/480100)",
        "foundation_group": "repairs",
        "include": "yes",
        "official_mtbi_ucc": "490100",
        "reason": "Official 2024 MTBI maps VQBCODE 230 to UCC 490100/480100.",
    },
    "240": {
        "label": "Vehicle maintenance/repair (UCC 490100/480100)",
        "foundation_group": "repairs",
        "include": "yes",
        "official_mtbi_ucc": "490100",
        "reason": (
            "Official 2024 MTBI maps VQBCODE 240 to UCC 490100/480100. Included "
            "on that UCC assignment; the PUMD file does not print a separate "
            "item label for 240."
        ),
    },
    "220": {
        "label": "Driver's licenses",
        "foundation_group": "registration",
        "include": "no",
        "official_mtbi_ucc": "520550",
        "reason": "2024 CEQ item 1; official UCC 520550. Licensing is not maintenance.",
    },
    "250": {
        "label": "Vehicle registration or personal property taxes",
        "foundation_group": "registration",
        "include": "no",
        "official_mtbi_ucc": "520541",
        "reason": "2024 CEQ item 3; official UCC 520541. Separate registration component.",
    },
    "260": {
        "label": "Automobile service clubs (AAA, OnStar, LoJack)",
        "foundation_group": "service_clubs",
        "include": "no",
        "official_mtbi_ucc": "520531",
        "reason": "2024 CEQ item 5; official UCC 520531. Club dues are not a repair event.",
    },
    "270": {
        "label": "Other vehicle operating expense (UCC 520901)",
        "foundation_group": "other_vehicle",
        "include": "no",
        "official_mtbi_ucc": "520901",
        "reason": "Official 2024 MTBI maps VQBCODE 270 to UCC 520901, not 490xxx.",
    },
    "280": {
        "label": "Vehicle cleaning / detailing / car washes",
        "foundation_group": "cleaning",
        "include": "no",
        "official_mtbi_ucc": "250213",
        "reason": "2024 CEQ item 7; official UCC 250213. Cleaning is not the repair reserve.",
    },
    "210": {
        "label": "Non-maintenance VQB expense (UCC 620114)",
        "foundation_group": "other",
        "include": "no",
        "official_mtbi_ucc": "620114",
        "reason": "Official 2024 MTBI maps VQBCODE 210 to UCC 620114, not 490xxx.",
    },
    "400": {
        "label": "Other vehicle operating expense (UCC 520310)",
        "foundation_group": "parking_tolls",
        "include": "no",
        "official_mtbi_ucc": "520310",
        "reason": "Official 2024 MTBI maps VQBCODE 400 to UCC 520310 (52xxx, not 490xxx).",
    },
    "410": {
        "label": "Tolls or parking (UCC 520410)",
        "foundation_group": "parking_tolls",
        "include": "no",
        "official_mtbi_ucc": "520410",
        "reason": "2024 CEQ items 13–14; official UCC 520410. Parking/tolls are separate.",
    },
    "420": {
        "label": "Auto repair service policies / extended warranties",
        "foundation_group": "insurance",
        "include": "no",
        "official_mtbi_ucc": "510115",
        "reason": "2024 CEQ item 4; official UCC 510115 (51xxx insurance family).",
    },
    "900": {
        "label": "Parent / combined VQB overwrite ($0)",
        "foundation_group": "parent_record",
        "include": "no",
        "official_mtbi_ucc": "",
        "reason": "2024 VQBCODE 900 has VQBEXPX=0 (BLS parent overwrite). Not spending.",
    },
}

# Official 2024 Interview MTBI UCCs whose EXPNAME is VQBEXPX.
VEHICLE_UCCS: dict[str, dict[str, str]] = {
    "480110": {
        "label": "VQBEXPX tire purchases / mounting (VQBCODE 140)",
        "foundation_group": "tires",
        "include": "yes",
        "reason": "Official 2024 MTBI UCC for VQBCODE 140 tire events.",
    },
    "490100": {
        "label": "VQBEXPX vehicle maintenance and repair",
        "foundation_group": "routine_maintenance",
        "include": "yes",
        "reason": "Official 2024 MTBI UCC for VQBCODE 190/367/320/230/240.",
    },
    "480100": {
        "label": "VQBEXPX vehicle maintenance/repair allocation",
        "foundation_group": "repairs",
        "include": "yes",
        "reason": "Official 2024 MTBI companion UCC for a subset of 190/230/240/320.",
    },
    "490900": {
        "label": "VQBEXPX other vehicle maintenance/repair",
        "foundation_group": "repairs",
        "include": "yes",
        "reason": "Official 2024 MTBI UCC for VQBCODE 200.",
    },
    "470211": {
        "label": "Historical Interview tire UCC (pre-Section-11 redesign)",
        "foundation_group": "tires",
        "include": "no",
        "reason": (
            "Absent from 2024 Interview MTBI. Absence is not measured zero "
            "tire spending. 2024 tires are VQBCODE 140 / UCC 480110."
        ),
    },
    "470220": {
        "label": "Historical Interview maintenance/repair UCC (pre-redesign)",
        "foundation_group": "routine_maintenance",
        "include": "no",
        "reason": (
            "Absent from 2024 Interview MTBI. Absence is not measured zero "
            "maintenance. 2024 maintenance is VQB / UCC 490100."
        ),
    },
    "470212": {
        "label": "2024 MTBI GASOILX / TOTYUPDX / TRNONCUX residual",
        "foundation_group": "fuel",
        "include": "no",
        "reason": (
            "In official 2024 MTBI this UCC is a gasoline/oil allocation split, "
            "not vehicle parts. Excluded as fuel."
        ),
    },
    "470111": {
        "label": "Gasoline (JGASOXQV)",
        "foundation_group": "fuel",
        "include": "no",
        "reason": "Separate Foundation fuel component (EIA).",
    },
    "470112": {
        "label": "Diesel fuel (JDIESXQV)",
        "foundation_group": "fuel",
        "include": "no",
        "reason": "Separate Foundation fuel component (EIA).",
    },
    "470113": {
        "label": "Gasoline/oil allocation (GASOILX)",
        "foundation_group": "fuel",
        "include": "no",
        "reason": "Fuel/oil allocation. Separate Foundation fuel component.",
    },
    "510110": {
        "label": "Vehicle insurance",
        "foundation_group": "insurance",
        "include": "no",
        "reason": "Separate Foundation insurance component (NAIC).",
    },
    "510115": {
        "label": "VQBEXPX extended warranties / service policies (VQBCODE 420)",
        "foundation_group": "insurance",
        "include": "no",
        "reason": "Official 2024 MTBI UCC for VQBCODE 420. Insurance-like.",
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
        "label": "Vehicle finance / trade residual",
        "foundation_group": "finance",
        "include": "no",
        "reason": "Finance charges are not maintenance.",
    },
    "520541": {
        "label": "VQBEXPX vehicle registration (VQBCODE 250)",
        "foundation_group": "registration",
        "include": "no",
        "reason": "Separate Foundation registration component.",
    },
    "520550": {
        "label": "VQBEXPX driver's licenses (VQBCODE 220)",
        "foundation_group": "registration",
        "include": "no",
        "reason": "Licensing is not maintenance.",
    },
    "520902": {
        "label": "Vehicle inspection (pre-redesign UCC)",
        "foundation_group": "registration",
        "include": "no",
        "reason": "Inspection/registration-adjacent, not maintenance reserve.",
    },
    "520516": {
        "label": "Parking fees (QADRENTX / RTCARX)",
        "foundation_group": "parking_tolls",
        "include": "no",
        "reason": "Parking/tolls are a separate component.",
    },
    "520517": {
        "label": "Tolls (QADRENTX / RTCARX)",
        "foundation_group": "parking_tolls",
        "include": "no",
        "reason": "Parking/tolls are a separate component.",
    },
    "520310": {
        "label": "VQBEXPX other vehicle operating (VQBCODE 400)",
        "foundation_group": "parking_tolls",
        "include": "no",
        "reason": "Official 2024 MTBI UCC for VQBCODE 400. Not 490xxx.",
    },
    "520410": {
        "label": "VQBEXPX tolls/parking (VQBCODE 410)",
        "foundation_group": "parking_tolls",
        "include": "no",
        "reason": "Official 2024 MTBI UCC for VQBCODE 410.",
    },
    "520110": {
        "label": "VQBEXPX allocated companion of 510115/950024",
        "foundation_group": "rental",
        "include": "no",
        "reason": "2024 MTBI VQBEXPX allocation, not owned-vehicle maintenance.",
    },
    "520531": {
        "label": "VQBEXPX automobile service clubs (VQBCODE 260)",
        "foundation_group": "service_clubs",
        "include": "no",
        "reason": "Club dues are not a repair/tire/maintenance event.",
    },
    "250213": {
        "label": "VQBEXPX vehicle cleaning (VQBCODE 280)",
        "foundation_group": "cleaning",
        "include": "no",
        "reason": "Cleaning/detailing is not the maintenance/repair reserve.",
    },
    "620114": {
        "label": "VQBEXPX non-maintenance (VQBCODE 210)",
        "foundation_group": "other",
        "include": "no",
        "reason": "Official 2024 MTBI UCC 620114 is outside the 490xxx family.",
    },
    "520901": {
        "label": "VQBEXPX other vehicle operating (VQBCODE 270)",
        "foundation_group": "other_vehicle",
        "include": "no",
        "reason": "Official 2024 MTBI UCC 520901 is not maintenance.",
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

INCLUDED_VQB_CODES = {code: meta for code, meta in VQB_CODES.items() if meta["include"] == "yes"}
EXCLUDED_VQB_CODES = {code: meta for code, meta in VQB_CODES.items() if meta["include"] == "no"}
TIRE_VQB_CODES = {
    code for code, meta in INCLUDED_VQB_CODES.items() if meta["foundation_group"] == "tires"
}
ROUTINE_VQB_CODES = {
    code
    for code, meta in INCLUDED_VQB_CODES.items()
    if meta["foundation_group"] == "routine_maintenance"
}
REPAIR_VQB_CODES = {
    code for code, meta in INCLUDED_VQB_CODES.items() if meta["foundation_group"] == "repairs"
}

HISTORICAL_ABSENT_TIRE_UCCS = {"470211"}
HISTORICAL_ABSENT_MAINTENANCE_UCCS = {"470220"}


def allowlist_document() -> dict[str, Any]:
    return {
        "report_type": "bls_ce_vehicle_ucc_allowlist",
        "dictionary_url": UCC_DICTIONARY_URL,
        "stubs_url": UCC_STUBS_URL,
        "getting_started_url": UCC_GETTING_STARTED,
        "ceq_questionnaire_url": CEQ_2024_2025_QUESTIONNAIRE,
        "architecture": (
            "FMLI supplies NEWID, FAM_SIZE, vehicle ownership, FINLWT21. "
            "VQB (official detailed vehicle-maintenance/repair file) supplies "
            "NEWID, VQBCODE, VQBEXPX, VQBMO. MTBI supplies the official UCC "
            "assigned to each VQBEXPX row and is the fallback if VQB is absent. "
            "Do not use FMLI summary columns such as TIRECQ as the sole detail "
            "source. Do not treat UCC 470212 as parts."
        ),
        "included_vqb_codes": INCLUDED_VQB_CODES,
        "excluded_vqb_codes": EXCLUDED_VQB_CODES,
        "included_uccs": INCLUDED_UCCS,
        "excluded_uccs": EXCLUDED_UCCS,
        "groups": {
            "tires": {
                "vqb_codes": sorted(TIRE_VQB_CODES),
                "uccs": sorted(TIRE_UCCS),
            },
            "routine_maintenance": {
                "vqb_codes": sorted(ROUTINE_VQB_CODES),
                "uccs": sorted(ROUTINE_UCCS),
            },
            "repairs": {
                "vqb_codes": sorted(REPAIR_VQB_CODES),
                "uccs": sorted(REPAIR_UCCS),
            },
        },
        "historical_absent_not_measured_zero": {
            "tires": sorted(HISTORICAL_ABSENT_TIRE_UCCS),
            "routine_maintenance": sorted(HISTORICAL_ABSENT_MAINTENANCE_UCCS),
        },
    }
