# Approved Data Sources

**Version:** `0.2.0-draft`  
**Purpose:** Official data source registry for The Foundation's Population Anchor and Minimum Sustainable Living Cost models.

---

## 1. Population Anchor Source

- **Publisher:** U.S. Census Bureau
- **Dataset:** Current Population Survey — Annual Social & Economic Supplement (CPS ASEC) Public Use Microdata
- **Variables:** `HTOTVAL`, `H_NUMPER`, `MARSUPWT`, `H_SEQ`, `PH_SEQ`, `A_LINENO`
- **Cadence:** Annual (March Supplement)
- **Official URL:** `https://www.census.gov/data/datasets/time-series/demo/cps/cps-asec.html`

---

## 2. Minimum Sustainable Living Cost — Production Sources

### 2.1 Housing (Shelter & Core Utilities)

- **Publisher:** U.S. Department of Housing and Urban Development (HUD)
- **Dataset:** Fair Market Rents (FMR) at the 40th percentile (1-Bedroom)
- **Geographic Resolution:** County / HUD FMR Area (All 50 states + DC)
- **Vintages:** FY 2024 (Time-Comparable), FY 2026 (Current)
- **Official URL:** `https://www.huduser.gov/portal/datasets/fmr.html`

### 2.2 Food

- **Publisher:** U.S. Department of Agriculture (USDA) Food and Nutrition Service / CNPP
- **Dataset:** USDA Low-Cost Food Plan (Primary Sustainable Baseline) & Thrifty Food Plan (Sensitivity Bound)
- **Profile:** Single adult age 19–50 (+20% 1-person size adjustment, adult gender midpoint)
- **Geographic Resolution:** National baseline with official Alaska/Hawaii regional supplements
- **Official URL:** `https://www.fns.usda.gov/cnpp/usda-food-plans-cost-food-monthly-reports`

### 2.3 Transportation (Automobile Baseline)

- **Publishers:** Federal Highway Administration (FHWA), Energy Information Administration (EIA), National Association of Insurance Commissioners (NAIC), Bureau of Labor Statistics (BLS)
- **Datasets:**
  - Annual Necessary Mileage: FHWA National Household Travel Survey (NHTS)
  - Retail Gasoline Prices: EIA Petroleum & Other Liquids Data (State/Regional weekly/monthly averages)
  - Automobile Insurance: NAIC Auto Insurance Database Report / State Insurance Commissioner filings
  - Maintenance, Repairs & Tires: BLS Consumer Expenditure Survey (Single-adult consumer units)
  - Vehicle Replacement Reserve: BLS CE / Federal Reserve used vehicle depreciation schedule

### 2.4 Healthcare (Unsubsidized Insurance & Expected Out-of-Pocket)

- **Publishers:** Centers for Medicare & Medicaid Services (CMS), State-Based Health Insurance Exchanges, Agency for Healthcare Research and Quality (AHRQ)
- **Datasets:**
  - Premium: CMS Marketplace Plan Public Use Files (PUF) / State Exchange PUFs (Age 40 single non-smoker, lowest-cost adequate Silver plan)
  - Expected Out-of-Pocket Utilization: Medical Expenditure Panel Survey (MEPS) Household Component (Expected annual OOP for non-elderly single adults)

### 2.5 Connectivity, Household Essentials & Clothing

- **Publishers:** BLS Consumer Expenditure Survey, Federal Communications Commission (FCC)
- **Datasets:**
  - Broadband & Mobile Phone: FCC Urban Broadband Rate Survey & BLS CE Telecommunications
  - Personal Hygiene, Cleaning Supplies & Basic Apparel: Restricted necessity sub-basket from BLS CE single-person consumer unit microdata

### 2.6 Social Participation & Recreation

- **Publishers:** Bureau of Labor Statistics (BLS), Bureau of Economic Analysis (BEA)
- **Datasets:**
  - Modest Recreation & Social Participation: BLS CE Survey P25 expenditure among single-adult positive spenders in basic recreation/social categories
  - Regional Cost Adjustment: BEA Regional Price Parities (RPP)

### 2.7 Population Weights

- **Publisher:** U.S. Census Bureau
- **Dataset:** American Community Survey (ACS) 1-Year / 5-Year Data
- **Variables:** Adult population (age 18+) by county / FMR area for all 3,143+ counties/equivalents

### 2.8 Statutory Tax Tables

- **Publishers:** Internal Revenue Service (IRS), Federation of Tax Administrators (FTA), State Departments of Revenue
- **Datasets:** Federal standard deduction, federal tax brackets, FICA statutory rates, state standard deductions, personal exemptions, state income tax rate schedules, and local income tax rules for 2024 and 2026.

---

## 3. High-Frequency Economic Pressure Signals

- **Publisher:** Bureau of Labor Statistics (BLS)
- **Series:** U-6 (`LNS13327709`), Participation (`LNS11300000`), Employment-Population (`LNS12300000`), Want a Job (`LNS15026639`), CPI All Items (`CUSR0000SA0`), CPI Shelter (`CUSR0000SAH1`), CPI Food at Home (`CUSR0000SAF11`), CPI Medical Care (`CUSR0000SAM`), CPI Gasoline (`CUSR0000SETB01`).
