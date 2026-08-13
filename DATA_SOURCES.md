# Approved Data Sources — V0.1

This document defines source priority and intended use. Machine-readable entries live in `config/sources.yml`.

## Source policy

Prefer original publishers.

Aggregators may be used to discover a series or cross-check a value, but the production pipeline should fetch from the original publisher whenever practical.

A source may not be silently replaced.

If a source becomes unavailable or materially changes its methodology, the affected metric must fail closed until reviewed.

---

## 1. U.S. Census Bureau — CPS ASEC

**Role:** Canonical Bottom-30 population definition and annual household money-income distribution.

**Primary dataset:** Current Population Survey Annual Social and Economic Supplement public-use microdata.

**Official dataset page:**
https://www.census.gov/data/datasets/time-series/demo/cps/cps-asec.html

**2025 CSV archive:**
https://www2.census.gov/programs-surveys/cps/datasets/2025/march/asecpub25csv.zip

The 2025 CSV includes replicate weights.

**V0.1 fields of interest:**

- `HTOTVAL` — household income amount
- `H_NUMPER` — number of persons in household
- `MARSUPWT` — March supplement person weight
- `H_SEQ` — household sequence identifier

**Cadence:** Annual.

**Critical warning:** Survey year and income reference year differ. Do not label prior-year annual money income as current-year measured income.

**Production rule:** Download official archive, record SHA-256, process locally, preserve download metadata. The large raw archive does not need to be committed to Git.

---

## 2. Bureau of Labor Statistics

**Role:** Labor-market conditions, underutilization, participation, employment, earnings, CPI and related official series.

**API:**
https://www.bls.gov/developers/

**Data API overview:**
https://www.bls.gov/bls/api_features.htm

**Important API note:** BLS documents both unregistered and registered modes with different capabilities/limits. The pipeline must not require a registration key for core V0.1 operation unless a specific required feature forces it.

**Candidate measures:**

- U-6 labor underutilization
- labor-force participation
- employment-population ratio
- people not in labor force who want a job
- involuntary part-time work
- CPI components relevant to lower-resource households

**Cadence:** Mostly monthly; some releases more frequent.

**Rule:** Series IDs must be verified against official BLS documentation before being added to `config/indicators.yml`.

---

## 3. Federal Reserve Board

**Role:** Household financial well-being, distributional financial accounts, debt-service and wealth measures.

**Candidate sources:**

- Distributional Financial Accounts
- Survey of Household Economics and Decisionmaking
- Financial Accounts of the United States

**Main site:**
https://www.federalreserve.gov/data.htm

**Cadence:** Varies from quarterly to annual.

**Use cases:**

- bottom-group wealth;
- liquid asset distribution;
- retirement position;
- emergency-expense resilience;
- household debt-service burden.

---

## 4. Federal Reserve Bank of New York

**Role:** Household debt/credit and heterogeneity research/data.

**Candidate sources:**

- Household Debt and Credit
- Economic Heterogeneity Indicators

**Main research/data site:**
https://www.newyorkfed.org/research

**Cadence:** Varies.

**Rule:** Prefer downloadable first-party data over copying values from narrative articles.

---

## 5. Federal Reserve Bank of Atlanta

**Role:** Wage distribution and labor-market distribution.

**Candidate source:**
Wage Growth Tracker.

**Official page:**
https://www.atlantafed.org/research-and-data/data/wage-growth-tracker

**Use:** Bottom wage-quartile growth and related distributional wage signals.

**Rule:** Record exactly which population slice the source publishes. Do not relabel a bottom quartile as "our Bottom 30%."

---

## 6. Bureau of Economic Analysis

**Role:** Regional price parity and national/regional income context.

**Official site:**
https://www.bea.gov/data

**Use in V0.1:** Context only unless a metric is explicitly approved.

**Future use:** State/local Foundation versions and cost-of-living adjustment.

---

## 7. U.S. Energy Information Administration

**Role:** High-frequency energy/fuel price pressure.

**Open data:**
https://www.eia.gov/opendata/

**Use:** Daily/weekly pressure signals when directly relevant to household transportation or utility costs.

**Rule:** Energy movement may affect Daily Pressure but must not dominate a slow-moving structural Foundation score merely because it updates more often.

---

## 8. Housing sources

Housing is methodologically dangerous because many useful datasets are private-sector products with differing reuse terms.

### Preferred first-party/public candidates

- Census housing data
- HUD
- Federal Reserve
- FHFA
- Freddie Mac/Fannie Mae public datasets where appropriate

### Redfin

Redfin publishes a public Data Center with downloadable housing-market information.

Official data center:
https://www.redfin.com/news/data-center/

Before production ingestion:

1. review current reuse/automation terms;
2. record allowed use;
3. do not redistribute restricted raw data;
4. prefer derived observations with source attribution when permitted.

No scraper may be introduced merely because a download endpoint is inconvenient.

---

## 9. Census Household Trends and Outlook Pulse / related household surveys

**Role:** More current household stress signals such as difficulty paying expenses, food sufficiency and housing pressure.

**Rule:** Survey redesigns must be treated as possible structural breaks. Do not splice incompatible designs into a time series without documentation.

---

## 10. Source metadata requirements

Every production observation must store at least:

```yaml
source_id:
publisher:
dataset:
series_or_variable:
source_url:
reference_period:
release_date:
retrieved_at:
unit:
population:
geography:
status:
methodology_version:
```

Where possible also store:

```yaml
raw_file_sha256:
source_revision:
seasonal_adjustment:
notes:
```

---

## 11. Forbidden production sources

Do not use as canonical inputs:

- unsourced social-media posts;
- AI-generated summaries;
- SEO statistics pages;
- scraped chart pixels;
- secondary news articles when the original release is available;
- a different dataset substituted merely because its number looks plausible.

News can explain events.

News does not replace the underlying measurement source.
