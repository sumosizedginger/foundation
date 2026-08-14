# The Foundation

> **How are the bottom 30% of Americans actually doing?**

The Foundation is an open, deterministic, auditable economic research instrument focused on Americans with the least financial room to absorb mistakes, price shocks, job loss, illness, housing pressure, and structural costs.

The site is built as a static public instrument where **the browser never calculates authoritative economic metrics** — all public metrics are precomputed, validated, and published via an auditable deterministic pipeline.

---

## 1. The Dual-Axis Economic Framework

The dashboard separates the population definition from baseline survival adequacy:

- **Axis 1 · Population Anchor ($21,800 / year / person)**: The weighted 30th percentile of per-person household income (`HTOTVAL / H_NUMPER`) calculated from official Census CPS ASEC microdata (2024 income reference year / 2025 survey year). Represents 337.7M represented Americans.
- **Axis 2 · Minimum Sustainable Living Cost**: `DATA PIPELINE VALIDATION IN PROGRESS`. The retired $27,960 Survival Floor and the retired $51,220.16 / $55,551.89 prototype headlines are not current results.
- **Survival Gap**: `Population Anchor - Survival Floor = -$6,160/year` (Negative indicates the cutoff falls below the modeled single-adult floor).
- **Adequacy Ratio**: `Population Anchor / Survival Floor = 0.78` (78% of modeled floor).

### Household Composition Matrix

Axis 2 household living-cost figures are unpublished. The retired single-adult Survival Floor of $27,960 and derived Gap/Adequacy cells are historical only.

---

## 2. Complete Income Quantile Ladder (2024 Income Year)

- **P10**: $10,000.00 (Deep Foundation)
- **P20**: $15,896.00 (Lower Tier)
- **P30**: **$21,800.00 (Bottom-30 Population Anchor)**
- **P40**: $28,000.00 (Near Foundation)
- **P50**: $35,036.50 (National Median)
- **P75**: $61,640.00 (Upper Middle)
- **P90**: $100,100.00 (Top 10% Cutoff)

---

## 3. Quickstart & Pipeline Execution

```bash
# 1. Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS / Linux

# 2. Run full deterministic pipeline (processes CPS ASEC vintages, models survival, fetches BLS signals)
python -m foundation.cli update

# 3. Run full automated test suite (28 passing tests)
pytest -v

# 4. Build static site data artifacts into site/data/
python scripts/build_site.py

# 5. Verify repository structure, schemas, and release gates
python scripts/verify_repo.py
```

---

## 4. Historical Constant-Dollar Translation

Historical Population Anchor values are tracked in both **nominal dollars** and **inflation-adjusted constant 2024 dollars** using the official BLS Consumer Price Index (CPI-U):

| Survey Year | Income Year | Nominal Cutoff | Constant 2024 Dollars | CPI-U Index |       Real Change       |
| :---------: | :---------: | :------------: | :-------------------: | :---------: | :---------------------: |
|    2023     |    2022     |   $19,304.60   |      $20,717.34       |   292.655   |        Baseline         |
|    2024     |    2023     |   $20,688.00   |      $21,324.78       |   304.702   |          +2.9%          |
|    2025     |    2024     |   $21,800.00   |      $21,800.00       |   314.072   | +2.2% (+5.2% over 2022) |

---

## 5. Provenance & Fail-Closed Integrity

Every published vintage produces a machine-readable validation report (`data/metadata/validation_report_{year}.json`) verifying:

- Archive filename & SHA-256 hash
- Record counts & matched keys
- MARSUPWT sum & represented population
- Exact 0.00 difference between canonical and independent cross-check algorithms

If source schemas break or validations fail, the pipeline fails closed.

---

## 6. Open-Source Licensing

- **Software Code**: [Apache License 2.0](LICENSE.md)
- **Methodology & Original Documentation**: [Creative Commons Attribution 4.0 (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
- **Derived Data**: CC BY 4.0 where legally authorized. External source terms and attribution preserved.
- **Brand Identity & Marks**: The Foundation name, logos, and brand identity are explicitly reserved. See [LICENSE.md](LICENSE.md).
