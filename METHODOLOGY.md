# Methodology — V0.1

Status: **CANONICAL POPULATION ANCHOR VERIFIED · SURVIVAL AXIS RESEARCH ESTIMATE · COMPOSITE-SCORE LOCKED**

The Foundation is a public, deterministic, auditable economic research instrument designed to evaluate economic health from the vantage point of the bottom 30% of Americans.

---

## 1. Dual-Axis Economic Framework

The dashboard evaluates the economic condition of the foundation along two distinct axes:

```text
+------------------------------------------------------------------------------------+
|  AXIS 1: POPULATION ANCHOR (Who are the Bottom 30%?)                                |
|  Defines the reference population via person-ranked per-person household income.   |
|  2024 Income Reference Value: $21,800 per person per year (VERIFIED).              |
+------------------------------------------------------------------------------------+
                                      vs.
+------------------------------------------------------------------------------------+
|  AXIS 2: SURVIVAL FLOOR (Can they afford basic life?)                               |
|  Models the resources required to cover unavoidable baseline living necessities.   |
|  Single-Adult Baseline Value: $27,960 per year (RESEARCH ESTIMATE).                |
+------------------------------------------------------------------------------------+
                                       ||
                                       vv
+------------------------------------------------------------------------------------+
|  SURVIVAL GAP: Population Anchor - Survival Floor = -$6,160/year                   |
|  ADEQUACY RATIO: Population Anchor / Survival Floor = 0.78 (78% of basic needs)     |
+------------------------------------------------------------------------------------+
```

### What the Population Anchor Is NOT:
* It is **NOT** a poverty threshold;
* It is **NOT** a living-wage threshold;
* It is **NOT** a survival threshold;
* It is **NOT** a statement that $21,800 is sufficient;
* It is **NOT** the Foundation composite score.

---

## 2. Canonical Bottom-30 Population Anchor

### The Core Formula

The Bottom 30% is the lowest weighted 30% of **persons** when each person is assigned their household's annual money income divided by the number of people in that household:

$$\text{per\_person\_household\_income}_i = \frac{\text{HTOTVAL}_h}{\text{H\_NUMPER}_h}$$

Where:
- $\text{HTOTVAL}_h$ = Total annual household money income for household $h$.
- $\text{H\_NUMPER}_h$ = Total number of people living in and supported by household $h$.
- Every person $i$ in household $h$ receives the identical per-person income value.

### Person-Weighted Percentile Ranking

Persons are sorted in ascending order by their per-person household income and evaluated using the official March supplement person survey weight ($\text{MARSUPWT}$).

The weighted inverse empirical cumulative distribution determines the cutoff:

$$\text{Target Weight} = 0.30 \times \sum_{i} \text{MARSUPWT}_i$$

The canonical Population Anchor is the first observation at which cumulative survey weight is greater than or equal to the target weight.

### Why Persons are Ranked Rather Than Households

A household with five people represents five human beings experiencing the economic reality of those shared resources. Ranking households equally would treat a single-person household with $60,000 as equivalent in population weight to a family of six with $60,000. The Foundation measures humans.

### Why No Equivalence Scale

Standard equivalence scales (such as the OECD or square-root scales) adjust household resources by treating children or additional adults as fractional persons.

The Foundation deliberately rejects equivalence scales in V0.1:
- One supported human counts as one supported human.
- $80,000 supporting 4 people ($20,000/person) is not treated as equivalent to $80,000 supporting 1 person ($80,000/person).
- This is a normative design decision that maintains complete transparency.

---

## 3. The Second Economic Axis: Survival Floor

The Survival Floor estimates the minimum annual resources required for an independent household to cover basic unavoidable living necessities without government cash assistance or debt.

### Single-Adult Research Baseline ($27,960 / year)

Status: `RESEARCH ESTIMATE` (Prelaunch validation state).

| Component | Annual Cost | Monthly Cost | Primary Public Source | Methodology & Standards |
| :--- | :---: | :---: | :--- | :--- |
| **Housing** | $13,200 | $1,100 | HUD Fair Market Rents / ACS Median Rent | 40th percentile efficiency/1BR rental baseline including essential utilities. |
| **Food** | $3,600 | $300 | USDA Thrifty Food Plan (FNS/CNPP) | Monthly cost of food for single adult (age 19–50) with official +20% 1-person adjustment. |
| **Utilities & Telecom** | $2,640 | $220 | EIA RECS & BLS Consumer Expenditure | Residential electric, heating/cooling, water/sewer, and basic broadband. |
| **Transportation** | $3,840 | $320 | BLS Consumer Expenditure Survey | Operating costs for reliable used commuting vehicle (gas, liability insurance, basic maintenance) or transit. |
| **Healthcare** | $1,680 | $140 | MEPS / AHRQ & ACA Benchmark Subsidies | Out-of-pocket medical expenses plus subsidized ACA Silver benchmark health insurance premium. |
| **Taxes & Basics** | $3,000 | $250 | IRS Statutory FICA & BLS Supplies | Mandatory FICA payroll taxes (7.65% = $2,139) plus state/local sales taxes and essential hygiene supplies. |
| **Total Floor** | **$27,960** | **$2,330** | **Synthesized Government Baseline** | **Bare-minimum survival floor for independent single adult.** |

---

## 4. Household-Size Matrix

Household Survival Floors are **independently modeled by household composition** and reflect genuine economies of scale (e.g. shared housing and utilities).

> [!IMPORTANT]
> Household Survival Floors must **NEVER** be generated by simply multiplying the single-adult floor by household size.

### Matrix: Equivalent Boundary vs. Survival Floor (2024 Reference Year)

| Household Size | Composition Profile | Equivalent Household Income at Bottom-30 Boundary | Household Survival Floor (Research Estimate) | Survival Gap | Adequacy Ratio |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **1** | 1 Adult | $21,800 | $27,960 | **-$6,160** | **0.78 (78%)** |
| **2** | 2 Adults / 1 Adult + 1 Child | $43,600 | $39,800 | **+$3,800** | **1.10 (110%)** |
| **3** | 2 Adults + 1 Child / 1 Adult + 2 Kids | $65,400 | $53,200 | **+$12,200** | **1.23 (123%)** |
| **4** | 2 Adults + 2 Children | $87,200 | $68,300 | **+$18,900** | **1.28 (128%)** |
| **5** | 2 Adults + 3 Children | $109,000 | $81,500 | **+$27,500** | **1.34 (134%)** |

*Note: The equivalent household income column is explicitly labeled "Equivalent household income at the Bottom-30 boundary" and is NOT a poverty threshold.*

---

## 5. Benchmark Comparisons & Methodological Divergences

The Foundation Survival Floor is compared against leading external research benchmarks:

1. **MIT Living Wage Calculator (Dr. Amy Glasmeier)**
   - *Estimated National Single Adult*: ~$42,500/year.
   - *Methodological Divergence*: MIT includes civic engagement expenses, unsubsidized health insurance, and county-level cost aggregation, whereas The Foundation models bare-minimum survival assuming ACA subsidies and strict home meal preparation.
2. **United For ALICE Survival Budget (United Way)**
   - *Estimated National Single Adult*: ~$31,200/year.
   - *Methodological Divergence*: ALICE includes an explicit 10% miscellaneous contingency reserve and higher technology allowances. When the contingency buffer is removed, ALICE aligns closely with The Foundation's $27,960 baseline.
3. **Official Poverty Measure (OPM — Census/HHS)**
   - *2024 Single Adult Threshold*: $15,650/year.
   - *Methodological Divergence*: OPM relies on the 1963 food-to-income multiplier (3x food) and severely underestimates modern housing, transportation, utility, and healthcare requirements.

---

## 6. Complete Income Quantile Ladder

To contextualize the Bottom 30% relative to the rest of American society, the production pipeline computes weighted person-income quantiles from official CPS ASEC microdata:

| Quantile | Description | 2024 Income (Survey 2025) | 2023 Income (Survey 2024) | 2022 Income (Survey 2023) |
| :--- | :--- | :---: | :---: | :---: |
| **P10** | 10th Percentile (Extreme Foundation) | $10,000.00 | $9,133.60 | $8,513.75 |
| **P20** | 20th Percentile | $15,896.00 | $15,000.00 | $14,000.00 |
| **P30** | **Population Anchor (Bottom-30 Cutoff)** | **$21,800.00** | **$20,688.00** | **$19,304.60** |
| **P40** | 40th Percentile | $28,000.00 | $26,377.00 | $24,655.75 |
| **P50** | 50th Percentile (National Median) | $35,036.50 | $32,851.80 | $30,634.00 |
| **P75** | 75th Percentile (Upper Middle) | $61,640.00 | $57,548.00 | $53,045.50 |
| **P90** | 90th Percentile (Top 10% Boundary) | $100,100.00 | $94,500.00 | $87,690.67 |

---

## 7. Historical Constant Dollar Translation

When evaluating historical changes in the Population Anchor, values are presented in both **nominal dollars** and **inflation-adjusted constant dollars** (base year: 2024) using official BLS CPI-U series:

$$\text{Constant 2024 Dollars} = \text{Nominal Value}_t \times \left(\frac{\text{CPI-U}_{2024}}{\text{CPI-U}_t}\right)$$

| Survey Year | Income Year | Nominal Cutoff | Constant 2024 Dollars | CPI-U Index | Real Purchasing Power Change |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 2023 | 2022 | $19,304.60 | $20,717.34 | 292.655 | Baseline |
| 2024 | 2023 | $20,688.00 | $21,324.78 | 304.702 | +2.9% |
| 2025 | 2024 | $21,800.00 | $21,800.00 | 314.072 | +2.2% (+5.2% over 2022) |

> [!WARNING]
> Never imply that a rising nominal cutoff represents economic improvement. Real purchasing power must always be examined.

---

## 8. National Economic Pressure Signals

General economic series (such as BLS U-6, Labor Force Participation, Employment-Population Ratio, and CPI sub-indices) are explicitly designated as **National Economic Pressure Signals**.

They provide vital high-frequency macro context, but they are **not** Bottom-30 specific measures and are never misrepresented as such.

---

## 9. Composite Foundation Score: Locked in Prelaunch

The composite Foundation Score remains **locked in PRELAUNCH / RESEARCH**.

No provisional score or fake 0–100 number is generated or published. It will remain locked until all release gates in `VALIDATION.md` (normalization freezing, weight sensitivity analysis, double-counting review, and owner authorization) are fulfilled.
