# Validation and Release Gates

The project's most dangerous failure is a confident wrong number.

Validation therefore outranks uptime.

## 1. Core principle

**Fail closed.**

A missing update is embarrassing.

Publishing plausible garbage is fatal.

## 2. Bottom-30 calculation tests

Required:

### Equal household assignment
Every person in the same household receives the same per-person household income.

### Household-size arithmetic
Examples:

```text
$36,000 / 1 = $36,000
$60,000 / 2 = $30,000
$45,000 / 3 = $15,000
$100,000 / 5 = $20,000
```

### Ranking
Lower per-person household income must rank below higher values regardless of raw household income.

### Person weighting
The weighted percentile must respond correctly when person survey weights differ.

### Boundary convention
The exact `>= 30% cumulative weight` rule must have a regression test.

### Invalid records
Reject/handle explicitly:

- person count <= 0;
- weight <= 0;
- nonnumeric income;
- nonnumeric weight;
- missing household count;
- infinite values.

### Negative income
Must remain supported unless official source documentation requires special decoding.

## 3. CPS ASEC source validation

Before calculation:

- required fields exist;
- row count is plausible;
- numeric conversion failure rate is reported;
- household person count falls in documented plausible range;
- survey weight distribution is nonzero;
- archive/source metadata are stored;
- raw archive hash is stored.

Before reporting population totals from `MARSUPWT`, confirm scale/implied decimals from current official documentation. Percentile ranking is scale-invariant; totals are not.

## 4. Published-value sanity checks

The project should compute independent checks that are not used to force the answer.

Examples:

- weighted household-income summaries versus published Census summary statistics where definitions align;
- number of household records / people against source documentation;
- known quantiles against independent calculations.

A mismatch triggers investigation.

It does not automatically mean The Foundation is wrong, because definitions may differ.

The explanation must be documented.

## 5. Source-schema drift

Every connector maintains expected fields/structure.

If required meaning changes:

```text
STOP -> research -> document -> test -> owner review if material
```

Do not rename-and-pray.

## 6. Units

Every observation stores an explicit unit.

Forbidden ambiguity examples:

- `0.034` without knowing whether it means 3.4% or 0.034%;
- dollars without nominal/real year;
- index values without base;
- seasonally adjusted and unadjusted values mixed silently.

## 7. Time semantics

Every observation distinguishes:

- reference period;
- release date;
- retrieval date.

Never sort "latest" by retrieval date when the economic reference period is what matters.

## 8. Revisions

When a publisher revises data:

- keep the original vintage;
- ingest the revised value;
- calculate the effect;
- create revision metadata;
- update current history only under an explicit revision policy.

## 9. Double-counting review

Before composite release:

1. map each metric to a primary concept;
2. compute historical correlations where data overlap;
3. identify metrics that are downstream of the same shock;
4. test score sensitivity to removal of each metric;
5. document retained redundancy and why.

## 10. Weight sensitivity

Before composite release, compare at minimum:

- proposed weights;
- equal pillar weights;
- equal metric weights;
- labor-heavy plausible variant;
- housing-heavy plausible variant.

If reasonable alternatives produce radically different qualitative conclusions, the composite is not mature enough to publish.

## 11. Missing-data tests

A missing metric must never automatically become:

- zero;
- previous value with no stale flag;
- average;
- interpolated value.

Policy must be explicit per metric.

## 12. Freshness

Each source defines:

- expected cadence;
- warning age;
- stale age.

Staleness changes data-health state.

It does not necessarily erase the last valid observation.

## 13. Static-site validation

Before deploy:

- JSON files parse;
- required fields exist;
- no `NaN` or `Infinity`;
- site loads with JavaScript enabled;
- site still communicates prelaunch/data status if a chart fails;
- methodology/source links resolve within artifact;
- no secrets are present;
- no frontend calculation mutates official values.

## 14. Release gate checklist

The composite Foundation score may not be labeled official until all are true:

- [ ] Bottom-30 weighted percentile independently reproduced
- [ ] CPS ASEC variable meanings re-verified from current source docs
- [ ] Current source vintage archived with SHA-256 metadata
- [ ] Candidate metrics accepted/rejected explicitly
- [ ] Normalization frozen
- [ ] Weighting frozen
- [ ] Double-counting analysis completed
- [ ] Sensitivity analysis completed
- [ ] Revision policy tested
- [ ] Freshness policy tested
- [ ] Historical sanity checks reviewed
- [ ] Site provenance drill-down working
- [ ] Methodology version set to `1.0.0`
- [ ] Owner explicitly authorizes public composite score

Until then: publish prelaunch research, not fake certainty.
