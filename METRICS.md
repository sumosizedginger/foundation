# Metrics Registry — Human-Readable Draft

Status: **CANDIDATE SET / NOT YET AUTHORIZED AS A PUBLIC COMPOSITE**

Machine-readable candidates live in `config/indicators.yml`.

## Design rule

A metric earns a place because it answers a distinct question about the economic position of the reference population.

It does not earn a place because it is easy to download.

## Candidate V0.1 metrics

### Population anchor

#### Bottom-30 annual cutoff
**Question:** What annual household money income per person marks the weighted 30th percentile?

Source: CPS ASEC.

This is a population-definition output, not itself a pillar score.

---

## Work

### U-6 labor underutilization
Question: How much visible labor underutilization exists beyond headline unemployment?

Population match: broad national labor force, not Bottom-30 specific.

Role: context/proxy.

### Want-a-job population
Question: How many people outside the labor force report wanting a job?

Population match: broad.

Role: corrects the misleading impression created by headline unemployment alone.

### Employment-population ratio / participation
Question: How much of the eligible population is actually attached to paid work?

Role: structural labor context.

### Bottom wage-quartile wage growth
Question: Are wages near the bottom of the wage distribution improving in real terms?

Preferred source: Atlanta Fed Wage Growth Tracker plus inflation comparison.

Population caveat: lowest wage quartile is not identical to the Bottom 30% by household per-person resources.

---

## Cost of Life

### Low-income inflation / distributional inflation
Question: Are prices faced by low-resource households rising faster or slower than their incomes?

Preferred source: New York Fed heterogeneity work/data when methodologically usable.

### Fuel/transport pressure
Question: Are transportation energy costs creating a new short-run burden?

Preferred source: EIA.

Role: Daily Pressure first; composite inclusion requires double-counting review.

### Essential-cost basket
Future candidate combining housing, food, transport, healthcare and utilities using explicit weights.

Do not invent this basket before expenditure-weight methodology is approved.

---

## Housing

### Rent burden
Question: What share of lower-resource households is paying >30% or >50% of income toward housing?

Preferred public sources: Census/HUD.

### Entry-home affordability
Question: How far is ownership entry from the resources available to the reference population?

Requires a transparent construction.

Do not simply use median home price.

### Housing insecurity
Candidate measures: eviction risk, missed rent/mortgage, survey-reported housing instability.

---

## Resilience

### $400 emergency capacity
Question: Can households absorb a modest unexpected expense without borrowing/selling something?

Source: Federal Reserve SHED.

Frequency caveat: annual.

### Difficulty paying normal expenses
Question: Are households reporting that ordinary bills exceed available resources?

Candidate Census survey source.

### Delinquency pressure
Question: Are debt payments beginning to fail?

Preferred source: New York Fed/Federal Reserve.

---

## Ownership

### Liquid financial assets among lower-resource households
Question: Is a buffer accumulating?

### Bottom-group net worth
Question: Is wealth ownership broadening or concentrating?

Preferred source: Federal Reserve Distributional Financial Accounts.

### Retirement asset participation
Question: Are households building long-horizon ownership claims?

---

## Mobility

Mobility is the least mature V0.1 pillar and should not be forced into the first public score simply to fill a box.

Candidates:

- first-time homeownership accessibility;
- wage progression;
- business formation among lower-resource households if credible data exist;
- movement across income/wealth positions in longitudinal data;
- educational debt burden versus earnings outcomes.

If no robust metric exists, publish "Mobility: experimental/unavailable" rather than bullshit.

---

## Daily Pressure versus structural indicators

A high-frequency series is not automatically more important.

Use these roles:

- `structural` — eligible for future Foundation composite;
- `pressure` — directional current signal;
- `context` — useful explanatory measure;
- `anchor` — defines/reference population;
- `experimental` — visible research, excluded from official score.

## Metric acceptance test

Before an indicator becomes official, answer:

1. What distinct human question does it answer?
2. What population does it actually measure?
3. How close is that population to our Bottom 30%?
4. What is the source?
5. What is the cadence?
6. What is the revision risk?
7. What is the unit?
8. Is higher better or worse?
9. What other indicators is it likely to duplicate?
10. What would make us remove it?
