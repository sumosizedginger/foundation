# THE FOUNDATION — FINAL CANDIDATE-GATE HARDENING STATUS

Implementation SHA: `733f9d46ef7cea338da1555314e32903167a8901`  
Started from audited HEAD: `32a6abf2bf0ecc8df29e1e53105258b831ed8b76`  
(plus the later docs commit `6c5b665`)

OD-001 through OD-013 remain **ACCEPTED / FROZEN**.

Authorization source of truth is only `config/definitions.yml`:

```yaml
living_cost:
  candidate_calculation_authorized: false
  release_authorized: false
  required_project_cost_years: [2024, 2026]
```

`states_modeled = 0`  
`ready_for_private_candidate = false`  
`candidate_inputs_bound = false`  
`translation_index_bound = false`  
`headline_calculated = false`

**NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.**

The private candidate assembler was not built.

---

## GitHub CI (implementation SHA `733f9d4`)

These are GitHub Actions results, not local pytest.

| Workflow | Run | Result |
|---|---|---|
| Tests & Code Quality | [31894205899](https://github.com/sumosizedginger/foundation/actions/runs/31894205899) | **success — 161 passed, 5 skipped, 1 warning** |
| Validate Living Cost Sources | [31894205780](https://github.com/sumosizedginger/foundation/actions/runs/31894205780) | **success** |
| Deploy Pages | [31894205831](https://github.com/sumosizedginger/foundation/actions/runs/31894205831) | **success** |

Dual independent verifiers: both `VERDICT: PASS`  
(`/tmp/goal-verifier-a9cbc4c02224-code-review.md`, `/tmp/goal-verifier-a9cbc4c02224-qa.md`).

---

## Completed this pass

1. **Public freshness-gate bypasses removed.**  
   `assert_candidate_freshness_ready(checks)` and `evaluate_freshness_readiness(checks)` accept only `checks`.  
   No `required_families`, `translation_index_bound`, `silent_source_year_relabel`, `candidate_inputs_bound`, or `project_cost_year` parameters.  
   The production gate always uses `REQUIRED_FRESHNESS_FAMILIES` and `is_translation_index_bound()`.  
   Silent year-relabel is derived from check metadata (`substituted_2024_for_2026` / `silent_relabel`).  
   Tests monkeypatch providers, not truth-value kwargs.

2. **Candidate year bundle is real.**  
   `required_project_cost_years = [2024, 2026]` lives in `config/definitions.yml`.  
   The gate refuses a family that does not cover a required year.  
   A 2024-only record cannot silently satisfy 2026.

3. **`candidate_inputs_bound` is part of the assertion gate.**  
   Canonical reader: `are_candidate_inputs_bound()` from  
   `data/metadata/living_cost_candidate_input_bindings.json`.  
   The file does not exist. The value is **false**.  
   The public assertion raises `REQUIRED_CANDIDATE_INPUTS_NOT_BOUND`.  
   No caller override. Assembler not built.

4. **Listing freshness is separate from artifact-byte freshness.**  
   New fields: `listing_freshness_status`, `artifact_currentness_status`,  
   `selected_artifact_matches_latest`.  
   A mutable source cannot be `VERIFIED_CURRENT` from a landing-page filename alone.

5. **USDA mutable workbook currentness.**  
   Official latest month is parsed from the FNS page and from official workbook bytes  
   downloaded to a temp file (cache is not overwritten).  
   Official latest = selected latest = **May 2026**. Hashes match. Family `VERIFIED_CURRENT`.  
   Cached May + official June => `NEWER_AVAILABLE`.  
   Same month + changed bytes => `NEWER_AVAILABLE`.  
   2024 remains 12 months. 2026 remains January–May.  
   `substituted_2024_for_2026 = false`.

6. **Mutable-artifact rule applied to other rolling sources.**  
   EIA `pswrgvwall.xls`: official max observation **2026-08-10** matches selected; hashes match; `VERIFIED_CURRENT`.  
   EPA `vehicles.csv.zip`: listing current, bytes not proven; family `CHECK_FAILED`.  
   BEA `SARPP.zip`: official zip hashed against selected; `VERIFIED_CURRENT` on this run.  
   CMS current plan-year PUF: dual federal+SBE listing still required; mutable current-year archives are not treated as byte-current; family `CHECK_FAILED`.  
   NAIC current report: vintage parsed, local PDF not proven to be that report; family `CHECK_FAILED`.

7. **NAIC vintage discovery.**  
   Latest identifier: **AUT-PB 2022-2023**.  
   Parser accepts `2022/2023`, `2022-2023`, `AUT-PB 2022-2023`.  
   Highest ending year is selected.  
   Generic title without a year range cannot be `VERIFIED_CURRENT`.  
   Evidence remains `RETRIEVED_UNVALIDATED`.

8. **Duplicate gate reasons counted once.**  
   `empirical_blocker_family_count = 12`  
   `gate_blocker_reason_count = 38` (unique strings)  
   Freshness still **FAIL**s. That is correct.

9. **Preserved good state.**  
   Frozen ODs, config-only authorization, both flags false, Oregon individual = federal PUF,  
   Oregon SBE = SHOP-only, local tax unresolved ≠ 0, unsupported tax years fail closed.

---

## Report values (committed artifact)

| Field | Value |
|---|---|
| `candidate_calculation_authorized` | false |
| `living_cost.release_authorized` | false |
| `candidate_inputs_bound` | false |
| `required_project_cost_years` | [2024, 2026] |
| USDA official latest month | May 2026 |
| USDA selected latest month | May 2026 |
| EIA latest observation | 2026-08-10 |
| NAIC discovered identifier | AUT-PB 2022-2023 |
| empirical blocker families | 12 |
| unique gate blocker reasons | 38 |

---

## NOT COMPLETED

These remain open. This pass did not paper over them.

- Private candidate engine (not authorized; do not build)
- Public MSLC / Gap / Adequacy / rankings / national median / Composite
- Binding file for candidate inputs (`candidate_inputs_bound` stays false)
- Bound OD-010 CPI/medical translation table
- Bound vehicle-replacement inputs
- Official BLS CE ZIP retrieve (HTTP 403 / `INCOMPLETE_PROVENANCE`)
- Successful NHTS listing discovery
- Successful FCC Urban Rate Survey retrieve
- Mobile phone price (`SOURCE_GAP`)
- Vehicle registration inventory (`SOURCE_GAP`)
- NAIC local PDF bound to AUT-PB 2022-2023 and state-table extraction validated
- EPA MPG cohort extraction (`RETRIEVED_UNVALIDATED`; listing is not byte proof)
- CMS current-year PUF byte currentness
- Federal tax inventory (`INVENTORY_NOT_VALIDATED`)
- State/local tax inventories
- MEPS health OOP derivation (`RETRIEVED_UNVALIDATED`; HC-251 / 2023)
- 12 empirical evidence blocker families

---

## Next

Do not calculate an MSLC.

A later owner may set `candidate_calculation_authorized: true` only after freshness can pass, candidate inputs are bound, and the year bundle is covered.

Publication still needs `release_authorized` and a built, approved release engine.

STOP.
