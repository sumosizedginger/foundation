"""Deterministic Gross-Income Tax Engine for Minimum Sustainable Living Cost.

Solves for gross required income G such that:
    G - applicable_taxes(G, state, locality_fips, year) >= CoreNetNeeds

Calculates:
- Employee Social Security Tax (6.2% up to statutory cap)
- Employee Medicare Tax (1.45%)
- Federal Statutory Income Tax (incorporating single standard deduction & marginal brackets)
- State Statutory Income Tax (explicit year-specific 2024 and 2026 statutory configurations for all 50 states + DC)
- Local County/Municipal Income Tax attached to specific county FIPS
- Zero means-tested subsidies or refundable credits applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Statutory Federal Tax Rules by Reference Year (Single Filer)
FEDERAL_TAX_RULES = {
    2024: {
        "source": "IRS Rev. Proc. 2023-34 / SSA 2024 Fact Sheet",
        "standard_deduction": 14600.0,
        "ss_tax_rate": 0.062,
        "ss_wage_cap": 168600.0,
        "medicare_rate": 0.0145,
        "brackets": [
            (11600.0, 0.10),
            (47150.0, 0.12),
            (100525.0, 0.22),
            (191950.0, 0.24),
            (243725.0, 0.32),
            (609350.0, 0.35),
            (float("inf"), 0.37),
        ],
    },
    2026: {
        "source": "IRS Revenue Procedure 2025-32 / SSA 2026 Baseline",
        "standard_deduction": 16100.0,
        "ss_tax_rate": 0.062,
        "ss_wage_cap": 184500.0,
        "medicare_rate": 0.0145,
        "brackets": [
            (12400.0, 0.10),
            (50400.0, 0.12),
            (105700.0, 0.22),
            (201775.0, 0.24),
            (256225.0, 0.32),
            (640600.0, 0.35),
            (float("inf"), 0.37),
        ],
    },
}

# States with zero earned income tax
NO_INCOME_TAX_STATES = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}

# Year-Specific Statutory State Income Tax Schedules (Single Filer)
# Each entry contains primary statutory references and exact statutory brackets for 2024 and 2026.
STATE_STATUTORY_SCHEDULES: dict[int, dict[str, dict[str, Any]]] = {
    2024: {
        "AL": {
            "source": "Ala. Code § 40-18-5",
            "deduction": 3000.0,
            "brackets": [(500.0, 0.02), (3000.0, 0.04), (float("inf"), 0.05)],
        },
        "AZ": {
            "source": "Ariz. Rev. Stat. § 43-1011",
            "deduction": 14600.0,
            "brackets": [(float("inf"), 0.025)],
        },
        "AR": {
            "source": "Ark. Code Ann. § 26-51-201",
            "deduction": 2340.0,
            "brackets": [(4400.0, 0.02), (8800.0, 0.03), (float("inf"), 0.044)],
        },
        "CA": {
            "source": "Cal. Rev. & Tax Code § 17041",
            "deduction": 5540.0,
            "brackets": [
                (10412.0, 0.01),
                (24684.0, 0.02),
                (38959.0, 0.04),
                (54081.0, 0.06),
                (68350.0, 0.08),
                (float("inf"), 0.093),
            ],
        },
        "CO": {
            "source": "Colo. Rev. Stat. § 39-22-104",
            "deduction": 14600.0,
            "brackets": [(float("inf"), 0.044)],
        },
        "CT": {
            "source": "Conn. Gen. Stat. § 12-700",
            "deduction": 0.0,
            "brackets": [(10000.0, 0.03), (50000.0, 0.05), (100000.0, 0.055), (float("inf"), 0.06)],
        },
        "DC": {
            "source": "D.C. Code § 47-1806.03",
            "deduction": 14600.0,
            "brackets": [(10000.0, 0.04), (40000.0, 0.06), (60000.0, 0.065), (float("inf"), 0.085)],
        },
        "DE": {
            "source": "30 Del. C. § 1102",
            "deduction": 3250.0,
            "brackets": [
                (2000.0, 0.0),
                (5000.0, 0.022),
                (10000.0, 0.039),
                (20000.0, 0.048),
                (25000.0, 0.052),
                (60000.0, 0.0555),
                (float("inf"), 0.066),
            ],
        },
        "GA": {
            "source": "O.C.G.A. § 48-7-20",
            "deduction": 12000.0,
            "brackets": [(float("inf"), 0.0549)],
        },
        "HI": {
            "source": "Haw. Rev. Stat. § 235-51",
            "deduction": 2200.0,
            "brackets": [
                (2400.0, 0.014),
                (4800.0, 0.032),
                (9600.0, 0.055),
                (14400.0, 0.064),
                (19200.0, 0.068),
                (24000.0, 0.072),
                (36000.0, 0.076),
                (48000.0, 0.079),
                (float("inf"), 0.0825),
            ],
        },
        "IA": {
            "source": "Iowa Code § 422.5",
            "deduction": 0.0,
            "brackets": [(float("inf"), 0.038)],
        },
        "ID": {
            "source": "Idaho Code § 63-3024",
            "deduction": 14600.0,
            "brackets": [(float("inf"), 0.058)],
        },
        "IL": {
            "source": "35 ILCS 5/201",
            "deduction": 2775.0,
            "brackets": [(float("inf"), 0.0495)],
        },
        "IN": {
            "source": "Ind. Code § 6-3-2-1",
            "deduction": 1000.0,
            "brackets": [(float("inf"), 0.0305)],
        },
        "KS": {
            "source": "Kan. Stat. Ann. § 79-32,110",
            "deduction": 3500.0,
            "brackets": [(15000.0, 0.031), (30000.0, 0.0525), (float("inf"), 0.057)],
        },
        "KY": {
            "source": "Ky. Rev. Stat. § 141.020",
            "deduction": 3160.0,
            "brackets": [(float("inf"), 0.040)],
        },
        "LA": {
            "source": "La. Rev. Stat. § 47:32",
            "deduction": 4500.0,
            "brackets": [(12500.0, 0.0185), (50000.0, 0.035), (float("inf"), 0.0425)],
        },
        "MA": {
            "source": "Mass. Gen. Laws ch. 62 § 4",
            "deduction": 4400.0,
            "brackets": [(float("inf"), 0.050)],
        },
        "MD": {
            "source": "Md. Code Tax-Gen. § 10-105",
            "deduction": 2550.0,
            "brackets": [
                (1000.0, 0.02),
                (2000.0, 0.03),
                (3000.0, 0.04),
                (100000.0, 0.0475),
                (float("inf"), 0.05),
            ],
        },
        "ME": {
            "source": "36 M.R.S. § 5111",
            "deduction": 14600.0,
            "brackets": [(26050.0, 0.058), (61600.0, 0.0675), (float("inf"), 0.0715)],
        },
        "MI": {
            "source": "Mich. Comp. Laws § 206.51",
            "deduction": 5600.0,
            "brackets": [(float("inf"), 0.0425)],
        },
        "MN": {
            "source": "Minn. Stat. § 290.06",
            "deduction": 14575.0,
            "brackets": [(31690.0, 0.0535), (104090.0, 0.068), (float("inf"), 0.0785)],
        },
        "MO": {
            "source": "Mo. Rev. Stat. § 143.011",
            "deduction": 14600.0,
            "brackets": [
                (1273.0, 0.0),
                (2546.0, 0.02),
                (3819.0, 0.025),
                (5092.0, 0.03),
                (6365.0, 0.035),
                (7638.0, 0.04),
                (8911.0, 0.045),
                (float("inf"), 0.048),
            ],
        },
        "MS": {
            "source": "Miss. Code Ann. § 27-7-5",
            "deduction": 2300.0,
            "brackets": [(10000.0, 0.0), (float("inf"), 0.047)],
        },
        "MT": {
            "source": "Mont. Code Ann. § 15-30-2103",
            "deduction": 14600.0,
            "brackets": [(20500.0, 0.047), (float("inf"), 0.059)],
        },
        "NC": {
            "source": "N.C. Gen. Stat. § 105-153.7",
            "deduction": 12750.0,
            "brackets": [(float("inf"), 0.045)],
        },
        "ND": {
            "source": "N.D. Cent. Code § 57-38-30.3",
            "deduction": 14600.0,
            "brackets": [(44725.0, 0.0), (225975.0, 0.0195), (float("inf"), 0.025)],
        },
        "NE": {
            "source": "Neb. Rev. Stat. § 77-2715.03",
            "deduction": 7900.0,
            "brackets": [
                (3700.0, 0.0246),
                (22100.0, 0.0351),
                (35000.0, 0.0501),
                (float("inf"), 0.0584),
            ],
        },
        "NJ": {
            "source": "N.J. Stat. Ann. § 54A:2-1",
            "deduction": 1000.0,
            "brackets": [
                (20000.0, 0.014),
                (35000.0, 0.0175),
                (40000.0, 0.035),
                (75000.0, 0.05525),
                (float("inf"), 0.0637),
            ],
        },
        "NM": {
            "source": "N.M. Stat. Ann. § 7-2-7",
            "deduction": 14600.0,
            "brackets": [
                (5500.0, 0.017),
                (11000.0, 0.032),
                (16000.0, 0.047),
                (float("inf"), 0.049),
            ],
        },
        "NY": {
            "source": "N.Y. Tax Law § 601",
            "deduction": 8000.0,
            "brackets": [
                (8500.0, 0.04),
                (11700.0, 0.045),
                (13900.0, 0.0525),
                (80650.0, 0.055),
                (float("inf"), 0.06),
            ],
        },
        "OH": {
            "source": "Ohio Rev. Code § 5747.02",
            "deduction": 0.0,
            "brackets": [(26050.0, 0.0), (100000.0, 0.0275), (float("inf"), 0.035)],
        },
        "OK": {
            "source": "Okla. Stat. tit. 68 § 2355",
            "deduction": 6350.0,
            "brackets": [
                (1000.0, 0.0025),
                (2500.0, 0.0075),
                (3750.0, 0.0175),
                (4900.0, 0.0275),
                (7200.0, 0.0375),
                (float("inf"), 0.0475),
            ],
        },
        "OR": {
            "source": "Or. Rev. Stat. § 316.037",
            "deduction": 2745.0,
            "brackets": [
                (4050.0, 0.0475),
                (10200.0, 0.0675),
                (125000.0, 0.0875),
                (float("inf"), 0.099),
            ],
        },
        "PA": {
            "source": "72 Pa. Stat. § 7302",
            "deduction": 0.0,
            "brackets": [(float("inf"), 0.0307)],
        },
        "RI": {
            "source": "R.I. Gen. Laws § 44-30-2.6",
            "deduction": 10000.0,
            "brackets": [(73450.0, 0.0375), (166950.0, 0.0475), (float("inf"), 0.0599)],
        },
        "SC": {
            "source": "S.C. Code Ann. § 12-6-510",
            "deduction": 14600.0,
            "brackets": [(3460.0, 0.0), (17330.0, 0.03), (float("inf"), 0.064)],
        },
        "UT": {
            "source": "Utah Code § 59-10-104",
            "deduction": 0.0,
            "brackets": [(float("inf"), 0.0465)],
        },
        "VA": {
            "source": "Va. Code § 58.1-320",
            "deduction": 8500.0,
            "brackets": [(3000.0, 0.02), (5000.0, 0.03), (17000.0, 0.05), (float("inf"), 0.0575)],
        },
        "VT": {
            "source": "32 V.S.A. § 5822",
            "deduction": 7400.0,
            "brackets": [(45400.0, 0.0335), (110050.0, 0.066), (float("inf"), 0.076)],
        },
        "WI": {
            "source": "Wis. Stat. § 71.06",
            "deduction": 13810.0,
            "brackets": [
                (14320.0, 0.0354),
                (28640.0, 0.0465),
                (315310.0, 0.053),
                (float("inf"), 0.0765),
            ],
        },
        "WV": {
            "source": "W. Va. Code § 11-21-4e",
            "deduction": 0.0,
            "brackets": [
                (10000.0, 0.0236),
                (25000.0, 0.0315),
                (40000.0, 0.0354),
                (60000.0, 0.0472),
                (float("inf"), 0.0512),
            ],
        },
    },
    2026: {
        "AL": {
            "source": "Ala. Code § 40-18-5",
            "deduction": 3000.0,
            "brackets": [(500.0, 0.02), (3000.0, 0.04), (float("inf"), 0.05)],
        },
        "AZ": {
            "source": "Ariz. Rev. Stat. § 43-1011",
            "deduction": 16100.0,
            "brackets": [(float("inf"), 0.025)],
        },
        "AR": {
            "source": "Ark. Code Ann. § 26-51-201",
            "deduction": 2400.0,
            "brackets": [(4600.0, 0.02), (9200.0, 0.03), (float("inf"), 0.040)],
        },
        "CA": {
            "source": "Cal. Rev. & Tax Code § 17041",
            "deduction": 5800.0,
            "brackets": [
                (10900.0, 0.01),
                (25800.0, 0.02),
                (40700.0, 0.04),
                (56500.0, 0.06),
                (71400.0, 0.08),
                (float("inf"), 0.093),
            ],
        },
        "CO": {
            "source": "Colo. Rev. Stat. § 39-22-104",
            "deduction": 16100.0,
            "brackets": [(float("inf"), 0.044)],
        },
        "CT": {
            "source": "Conn. Gen. Stat. § 12-700",
            "deduction": 0.0,
            "brackets": [(10000.0, 0.03), (50000.0, 0.05), (100000.0, 0.055), (float("inf"), 0.06)],
        },
        "DC": {
            "source": "D.C. Code § 47-1806.03",
            "deduction": 16100.0,
            "brackets": [(10000.0, 0.04), (40000.0, 0.06), (60000.0, 0.065), (float("inf"), 0.085)],
        },
        "DE": {
            "source": "30 Del. C. § 1102",
            "deduction": 3250.0,
            "brackets": [
                (2000.0, 0.0),
                (5000.0, 0.022),
                (10000.0, 0.039),
                (20000.0, 0.048),
                (25000.0, 0.052),
                (60000.0, 0.0555),
                (float("inf"), 0.066),
            ],
        },
        "GA": {
            "source": "O.C.G.A. § 48-7-20",
            "deduction": 12000.0,
            "brackets": [(float("inf"), 0.050)],
        },
        "HI": {
            "source": "Haw. Rev. Stat. § 235-51",
            "deduction": 2200.0,
            "brackets": [
                (2400.0, 0.014),
                (4800.0, 0.032),
                (9600.0, 0.055),
                (14400.0, 0.064),
                (19200.0, 0.068),
                (24000.0, 0.072),
                (36000.0, 0.076),
                (48000.0, 0.079),
                (float("inf"), 0.0825),
            ],
        },
        "IA": {
            "source": "Iowa Code § 422.5",
            "deduction": 0.0,
            "brackets": [(float("inf"), 0.038)],
        },
        "ID": {
            "source": "Idaho Code § 63-3024",
            "deduction": 16100.0,
            "brackets": [(float("inf"), 0.05695)],
        },
        "IL": {
            "source": "35 ILCS 5/201",
            "deduction": 2850.0,
            "brackets": [(float("inf"), 0.0495)],
        },
        "IN": {
            "source": "Ind. Code § 6-3-2-1",
            "deduction": 1000.0,
            "brackets": [(float("inf"), 0.030)],
        },
        "KS": {
            "source": "Kan. Stat. Ann. § 79-32,110",
            "deduction": 3500.0,
            "brackets": [(15000.0, 0.031), (30000.0, 0.0525), (float("inf"), 0.0558)],
        },
        "KY": {
            "source": "Ky. Rev. Stat. § 141.020",
            "deduction": 3300.0,
            "brackets": [(float("inf"), 0.035)],
        },
        "LA": {
            "source": "La. Rev. Stat. § 47:32",
            "deduction": 4500.0,
            "brackets": [(12500.0, 0.0185), (50000.0, 0.035), (float("inf"), 0.0425)],
        },
        "MA": {
            "source": "Mass. Gen. Laws ch. 62 § 4",
            "deduction": 4400.0,
            "brackets": [(float("inf"), 0.050)],
        },
        "MD": {
            "source": "Md. Code Tax-Gen. § 10-105",
            "deduction": 2700.0,
            "brackets": [
                (1000.0, 0.02),
                (2000.0, 0.03),
                (3000.0, 0.04),
                (100000.0, 0.0475),
                (float("inf"), 0.05),
            ],
        },
        "ME": {
            "source": "36 M.R.S. § 5111",
            "deduction": 16100.0,
            "brackets": [(27300.0, 0.058), (64500.0, 0.0675), (float("inf"), 0.0715)],
        },
        "MI": {
            "source": "Mich. Comp. Laws § 206.51",
            "deduction": 5600.0,
            "brackets": [(float("inf"), 0.0425)],
        },
        "MN": {
            "source": "Minn. Stat. § 290.06",
            "deduction": 15200.0,
            "brackets": [(33100.0, 0.0535), (108700.0, 0.068), (float("inf"), 0.0785)],
        },
        "MO": {
            "source": "Mo. Rev. Stat. § 143.011",
            "deduction": 16100.0,
            "brackets": [
                (1350.0, 0.0),
                (2700.0, 0.02),
                (4050.0, 0.025),
                (5400.0, 0.03),
                (6750.0, 0.035),
                (8100.0, 0.04),
                (9450.0, 0.045),
                (float("inf"), 0.047),
            ],
        },
        "MS": {
            "source": "Miss. Code Ann. § 27-7-5",
            "deduction": 2300.0,
            "brackets": [(10000.0, 0.0), (float("inf"), 0.040)],
        },
        "MT": {
            "source": "Mont. Code Ann. § 15-30-2103",
            "deduction": 16100.0,
            "brackets": [(21500.0, 0.047), (float("inf"), 0.059)],
        },
        "NC": {
            "source": "N.C. Gen. Stat. § 105-153.7",
            "deduction": 12750.0,
            "brackets": [(float("inf"), 0.0425)],
        },
        "ND": {
            "source": "N.D. Cent. Code § 57-38-30.3",
            "deduction": 16100.0,
            "brackets": [(47000.0, 0.0), (237000.0, 0.0195), (float("inf"), 0.025)],
        },
        "NE": {
            "source": "Neb. Rev. Stat. § 77-2715.03",
            "deduction": 8500.0,
            "brackets": [
                (3900.0, 0.0246),
                (23300.0, 0.0351),
                (36900.0, 0.0501),
                (float("inf"), 0.0520),
            ],
        },
        "NJ": {
            "source": "N.J. Stat. Ann. § 54A:2-1",
            "deduction": 1000.0,
            "brackets": [
                (20000.0, 0.014),
                (35000.0, 0.0175),
                (40000.0, 0.035),
                (75000.0, 0.05525),
                (float("inf"), 0.0637),
            ],
        },
        "NM": {
            "source": "N.M. Stat. Ann. § 7-2-7",
            "deduction": 16100.0,
            "brackets": [
                (5500.0, 0.017),
                (11000.0, 0.032),
                (16000.0, 0.047),
                (float("inf"), 0.049),
            ],
        },
        "NY": {
            "source": "N.Y. Tax Law § 601",
            "deduction": 8000.0,
            "brackets": [
                (8500.0, 0.04),
                (11700.0, 0.045),
                (13900.0, 0.0525),
                (80650.0, 0.055),
                (float("inf"), 0.06),
            ],
        },
        "OH": {
            "source": "Ohio Rev. Code § 5747.02",
            "deduction": 0.0,
            "brackets": [(26050.0, 0.0), (100000.0, 0.0275), (float("inf"), 0.035)],
        },
        "OK": {
            "source": "Okla. Stat. tit. 68 § 2355",
            "deduction": 6350.0,
            "brackets": [
                (1000.0, 0.0025),
                (2500.0, 0.0075),
                (3750.0, 0.0175),
                (4900.0, 0.0275),
                (7200.0, 0.0375),
                (float("inf"), 0.0475),
            ],
        },
        "OR": {
            "source": "Or. Rev. Stat. § 316.037",
            "deduction": 2880.0,
            "brackets": [
                (4250.0, 0.0475),
                (10700.0, 0.0675),
                (125000.0, 0.0875),
                (float("inf"), 0.099),
            ],
        },
        "PA": {
            "source": "72 Pa. Stat. § 7302",
            "deduction": 0.0,
            "brackets": [(float("inf"), 0.0307)],
        },
        "RI": {
            "source": "R.I. Gen. Laws § 44-30-2.6",
            "deduction": 10500.0,
            "brackets": [(77000.0, 0.0375), (175000.0, 0.0475), (float("inf"), 0.0599)],
        },
        "SC": {
            "source": "S.C. Code Ann. § 12-6-510",
            "deduction": 16100.0,
            "brackets": [(3600.0, 0.0), (18000.0, 0.03), (float("inf"), 0.062)],
        },
        "UT": {
            "source": "Utah Code § 59-10-104",
            "deduction": 0.0,
            "brackets": [(float("inf"), 0.0455)],
        },
        "VA": {
            "source": "Va. Code § 58.1-320",
            "deduction": 8500.0,
            "brackets": [(3000.0, 0.02), (5000.0, 0.03), (17000.0, 0.05), (float("inf"), 0.0575)],
        },
        "VT": {
            "source": "32 V.S.A. § 5822",
            "deduction": 7800.0,
            "brackets": [(47500.0, 0.0335), (115000.0, 0.066), (float("inf"), 0.076)],
        },
        "WI": {
            "source": "Wis. Stat. § 71.06",
            "deduction": 14450.0,
            "brackets": [
                (15000.0, 0.0354),
                (30000.0, 0.0465),
                (330000.0, 0.053),
                (float("inf"), 0.0765),
            ],
        },
        "WV": {
            "source": "W. Va. Code § 11-21-4e",
            "deduction": 0.0,
            "brackets": [
                (10000.0, 0.0236),
                (25000.0, 0.0315),
                (40000.0, 0.0354),
                (60000.0, 0.0472),
                (float("inf"), 0.0512),
            ],
        },
    },
}

# OD-011 geography class:
#   A = coterminous municipality / county-equivalent
#   B = true county-level tax
#   C = municipality covering only part of modeled county (do NOT apply countywide)
#   D = unresolved
LOCAL_TAX_GEOGRAPHY: dict[str, str] = {
    # Maryland county income tax — true county-level (class B)
    **{
        fips: "B"
        for fips in (
            "24001",
            "24003",
            "24005",
            "24009",
            "24011",
            "24013",
            "24015",
            "24017",
            "24019",
            "24021",
            "24023",
            "24025",
            "24027",
            "24029",
            "24031",
            "24033",
            "24035",
            "24037",
            "24039",
            "24041",
            "24043",
            "24045",
            "24047",
            "24510",
        )
    },
    # NYC boroughs are coterminous county-equivalents (class A)
    "36005": "A",
    "36047": "A",
    "36061": "A",
    "36081": "A",
    "36085": "A",
    # Philadelphia city/county is coterminous (class A)
    "42101": "A",
}

# Specific county/city local income tax rates by 5-digit FIPS code
# Only attached to explicit geographies where statutory authority mandates county/city income tax
LOCAL_TAX_RATES_BY_FIPS: dict[str, float] = {
    # Maryland Counties (all 24 MD counties levy local income tax between 2.25% and 3.20%)
    "24001": 0.0305,
    "24003": 0.0281,
    "24005": 0.0320,
    "24009": 0.0300,
    "24011": 0.0320,
    "24013": 0.0303,
    "24015": 0.0310,
    "24017": 0.0303,
    "24019": 0.0320,
    "24021": 0.0296,
    "24023": 0.0265,
    "24025": 0.0306,
    "24027": 0.0320,
    "24029": 0.0320,
    "24031": 0.0320,
    "24033": 0.0320,
    "24035": 0.0300,
    "24037": 0.0320,
    "24039": 0.0320,
    "24041": 0.0320,
    "24043": 0.0320,
    "24045": 0.0320,
    "24047": 0.0320,
    "24510": 0.0320,
    # New York City Counties (Bronx, Kings, New York, Queens, Richmond - NYC Personal Income Tax)
    "36005": 0.03876,
    "36047": 0.03876,
    "36061": 0.03876,
    "36081": 0.03876,
    "36085": 0.03876,
    # Philadelphia County, PA
    "42101": 0.0375,
}


@dataclass(frozen=True)
class TaxCalculationResult:
    gross_income: float
    net_income: float
    fica_social_security: float
    fica_medicare: float
    federal_income_tax: float
    state_income_tax: float
    local_income_tax: float
    total_tax: float

    def to_dict(self) -> dict[str, float]:
        return {
            "gross_income": round(self.gross_income, 2),
            "net_income": round(self.net_income, 2),
            "fica_social_security": round(self.fica_social_security, 2),
            "fica_medicare": round(self.fica_medicare, 2),
            "federal_income_tax": round(self.federal_income_tax, 2),
            "state_income_tax": round(self.state_income_tax, 2),
            "local_income_tax": round(self.local_income_tax, 2),
            "total_tax": round(self.total_tax, 2),
        }


def calculate_federal_income_tax(gross: float, year: int = 2024) -> float:
    """Calculate statutory single federal income tax with standard deduction."""
    rules = FEDERAL_TAX_RULES.get(year, FEDERAL_TAX_RULES[2024])
    taxable = max(0.0, gross - rules["standard_deduction"])
    if taxable <= 0:
        return 0.0

    tax = 0.0
    prev_threshold = 0.0
    for threshold, rate in rules["brackets"]:
        if taxable > prev_threshold:
            chunk = min(taxable - prev_threshold, threshold - prev_threshold)
            tax += chunk * rate
            prev_threshold = threshold
        else:
            break
    return tax


def calculate_fica_taxes(gross: float, year: int = 2024) -> tuple[float, float]:
    """Calculate employee Social Security and Medicare FICA taxes."""
    rules = FEDERAL_TAX_RULES.get(year, FEDERAL_TAX_RULES[2024])
    ss_taxable = min(gross, rules["ss_wage_cap"])
    ss_tax = ss_taxable * rules["ss_tax_rate"]
    medicare_tax = gross * rules["medicare_rate"]
    return ss_tax, medicare_tax


def calculate_state_income_tax(gross: float, state: str, year: int = 2024) -> float:
    """Calculate statutory single state income tax for given state and year."""
    st = state.upper()
    if st in NO_INCOME_TAX_STATES or st == "US":
        return 0.0

    year_schedules = STATE_STATUTORY_SCHEDULES.get(year, STATE_STATUTORY_SCHEDULES[2024])
    sched = year_schedules.get(st)
    if not sched:
        raise ValueError(f"State income tax schedule UNAVAILABLE for state {st} in {year}")

    std_ded = sched["deduction"]
    taxable = max(0.0, gross - std_ded)
    if taxable <= 0:
        return 0.0

    tax = 0.0
    prev_threshold = 0.0
    for threshold, rate in sched["brackets"]:
        if taxable > prev_threshold:
            chunk = min(taxable - prev_threshold, threshold - prev_threshold)
            tax += chunk * rate
            prev_threshold = threshold
        else:
            break
    return tax


def calculate_local_income_tax(gross: float, fips_code: str = "") -> float:
    """Calculate statutory local income tax attached to specific county FIPS.

    OD-011: class C (partial-city) taxes cannot be applied automatically to an
    entire county. Unclassified / class D geographies do not silently invent a rate.
    """
    from foundation.living_cost.owner_freeze import local_tax_application_rule

    if not fips_code:
        return 0.0
    classification = LOCAL_TAX_GEOGRAPHY.get(fips_code, "D")
    rule = local_tax_application_rule(classification)  # type: ignore[arg-type]
    if classification == "C":
        raise ValueError(
            f"partial-city tax cannot be applied automatically to entire county {fips_code}"
        )
    if not rule["apply"]:
        return 0.0
    rate = LOCAL_TAX_RATES_BY_FIPS.get(fips_code, 0.0)
    return gross * rate


def evaluate_taxes_for_gross(
    gross: float,
    state: str,
    fips_code: str = "",
    year: int = 2024,
) -> TaxCalculationResult:
    """Compute all mandatory statutory taxes for a given gross income."""
    ss_tax, med_tax = calculate_fica_taxes(gross, year)
    fed_tax = calculate_federal_income_tax(gross, year)
    state_tax = calculate_state_income_tax(gross, state, year)
    local_tax = calculate_local_income_tax(gross, fips_code)
    total_tax = ss_tax + med_tax + fed_tax + state_tax + local_tax
    net = gross - total_tax

    return TaxCalculationResult(
        gross_income=gross,
        net_income=net,
        fica_social_security=ss_tax,
        fica_medicare=med_tax,
        federal_income_tax=fed_tax,
        state_income_tax=state_tax,
        local_income_tax=local_tax,
        total_tax=total_tax,
    )


def solve_gross_required_income(
    net_needs: float,
    state: str = "US",
    fips_code: str = "",
    year: int = 2024,
    tolerance: float = 0.01,
    max_iter: int = 100,
) -> TaxCalculationResult:
    """Solve for gross required income G using deterministic bisection."""
    if net_needs <= 0:
        return evaluate_taxes_for_gross(0.0, state, fips_code, year)

    low = net_needs
    high = net_needs * 3.0

    for _ in range(max_iter):
        mid = (low + high) / 2.0
        res = evaluate_taxes_for_gross(mid, state, fips_code, year)
        diff = res.net_income - net_needs

        if abs(diff) <= tolerance:
            return res
        elif diff < 0:
            low = mid
        else:
            high = mid

    return evaluate_taxes_for_gross((low + high) / 2.0, state, fips_code, year)
