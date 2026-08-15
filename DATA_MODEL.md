# Data Model Specification

**Version:** `0.2.0-draft`  
**Purpose:** Strict typed schemas for all raw observations, component models, local calculations, state aggregations, and national distributions.

---

## 1. Living Cost Component Observation

Every individual cost element (e.g., housing, food, auto insurance, health premium) stores complete provenance and geographic context:

```json
{
  "component_id": "housing_1br",
  "category": "housing",
  "geography_type": "county",
  "geography_id": "06075",
  "geography_name": "San Francisco County, CA",
  "state": "CA",
  "reference_year": 2024,
  "value_annual": 28680.0,
  "value_monthly": 2390.0,
  "unit": "USD",
  "status": "measured",
  "source_id": "hud_fmr_2024",
  "source_variable": "fmr_1br",
  "source_url": "https://www.huduser.gov/portal/datasets/fmr/fmr2024/FY24_FMRs_revised.xlsx",
  "source_release": "FY 2024 Fair Market Rents",
  "source_reference_period": "2024",
  "retrieved_at": "2026-08-13T16:00:00Z",
  "source_artifact_sha256": "3a8b...7f",
  "methodology_version": "0.2.0-draft",
  "notes": "40th percentile 1BR gross rent including tenant utilities"
}
```

---

## 2. Local Living Cost (County / FMR Area)

Represents the complete bottom-up calculation for a specific locality:

```json
{
  "geography_id": "06075",
  "geography_name": "San Francisco County, CA",
  "state": "CA",
  "reference_year": 2024,
  "profile_id": "single_adult_independent",
  "adult_population": 732000,
  "components": {
    "housing": 28680.0,
    "food": 4820.0,
    "transportation": 9400.0,
    "healthcare_insurance": 5640.0,
    "healthcare_out_of_pocket": 1680.0,
    "connectivity": 1440.0,
    "essentials": 2400.0,
    "social_recreation": 2800.0,
    "resilience": 1200.0
  },
  "net_needs_annual": 58060.0,
  "net_needs_monthly": 4838.33,
  "gross_required_income": 74850.0,
  "gross_required_monthly": 6237.5,
  "taxes": {
    "fica_social_security": 4640.7,
    "fica_medicare": 1085.33,
    "federal_income_tax": 7120.0,
    "state_income_tax": 3943.97,
    "local_income_tax": 0.0,
    "total_taxes": 16790.0
  },
  "status": "research_estimate",
  "methodology_version": "0.2.0-draft",
  "calculated_at": "2026-08-13T16:00:00Z"
}
```

---

## 3. State Living Cost Distribution

Represents the population-weighted aggregation across all counties in a state:

```json
{
  "state": "CA",
  "state_name": "California",
  "reference_year": 2024,
  "profile_id": "single_adult_independent",
  "represented_adult_population": 30500000,
  "locality_count": 58,
  "weighted_p25_gross": 58200.0,
  "weighted_median_gross": 66800.0,
  "weighted_p75_gross": 78400.0,
  "weighted_mean_gross": 68450.0,
  "min_locality_gross": 46200.0,
  "max_locality_gross": 89400.0,
  "weighted_median_net_needs": 52100.0,
  "methodology_version": "0.2.0-draft",
  "calculated_at": "2026-08-13T16:00:00Z"
}
```

---

## 4. National Living Cost Distribution

Represents the population-weighted aggregation across all localities in the 50 states + DC:

```json
{
  "geography": "United States",
  "reference_year": 2024,
  "profile_id": "single_adult_independent",
  "represented_adult_population": 262000000,
  "locality_count": 3143,
  "weighted_p25_gross": 48500.0,
  "weighted_median_gross": 56400.0,
  "weighted_p75_gross": 67800.0,
  "weighted_mean_gross": 58100.0,
  "lowest_state_median": {
    "state": "MS",
    "median_gross": 43200.0
  },
  "highest_state_median": {
    "state": "HI",
    "median_gross": 79600.0
  },
  "status": "research_estimate",
  "methodology_version": "0.2.0-draft",
  "calculated_at": "2026-08-13T16:00:00Z"
}
```

---

## 5. Time-Comparable Survival Gap & Adequacy Object (2024)

```json
{
  "reference_year": 2024,
  "population_anchor_annual": 21800.0,
  "population_anchor_status": "measured",
  "living_cost_national_median_gross": 56400.0,
  "living_cost_status": "research_estimate",
  "survival_gap_annual": -34600.0,
  "adequacy_ratio": 0.386,
  "adequacy_percent": 39,
  "time_comparability_verified": true,
  "methodology_version": "0.2.0-draft"
}
```

---

## 6. Owner-freeze / translation fields

Every living-cost component that later enters a candidate calculation must carry:

- `project_cost_year`
- `source_data_year`
- `translation_method` (`LATEST_AVAILABLE` | `RULE_YEAR` | `YTD` | `TARGET_YEAR_OBSERVATION` | `CPI_UPDATED` | `NONE_ALREADY_LOCAL` | `SOURCE_GAP` | `FORMULA_PENDING_INPUTS`)
- `price_index_series`
- `translation_factor`
- `original_value`
- `translated_value`

Methodology status (`FROZEN`) is stored separately from evidence status (`VALIDATED`, `INCOMPLETE_PROVENANCE`, `SOURCE_GAP`, `RETRIEVED_UNVALIDATED`, `FORMULA_FROZEN_INPUTS_PENDING`, …).

Owner-decision records live at `data/metadata/living_cost_owner_decisions_frozen.json`.

## 7. Status Enum

- `measured` — Derived directly from official microdata using deterministic formulas.
- `research_estimate` — Transparent multi-component model undergoing active validation.
- `in_development` — Methodology rebuild in progress.
- `stale` — Upstream source not refreshed beyond threshold; cached data shown with explicit warning.
- `unavailable` — Source data missing or failed validation; fails closed.
- `prelaunch` — Feature locked prior to formal public activation.
