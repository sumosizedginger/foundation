# Product Requirements Document — The Foundation V0.1

## 1. Product

**The Foundation** is a public, source-linked, reproducible economic dashboard designed to judge economic health from the position of the bottom 30% of Americans.

The central question is not "Did GDP rise?" or "Did the stock market rise?"

It is:

> Can people near the economic foundation obtain work, afford necessary life, withstand shocks, and build a path upward?

## 2. Product principle

The bottom 30% is the **reference population** used to decide what deserves attention and how broad economic changes are judged.

The project is not a poverty counter and is not intended to imply that everyone inside the bottom 30% has the same life circumstances.

## 3. V0.1 goals

V0.1 must:

- calculate a defensible national Bottom-30 per-person household-income cutoff from CPS ASEC public-use data;
- expose the definition and calculation publicly;
- maintain a registry of approved economic indicators;
- ingest a limited set of high-quality free sources;
- preserve release dates, reference periods, units, and provenance;
- distinguish measured observations from estimates;
- show freshness and missing-data state;
- provide a static public website suitable for GitHub Pages;
- preserve historical snapshots and revisions;
- allow an agent to run the update workflow without manual coding;
- fail closed when an input meaning changes.

## 4. Explicit non-goals for V0.1

Do not build yet:

- the daily show;
- accounts or authentication;
- comments;
- newsletters;
- payments;
- a mobile app;
- state or county indices;
- personal financial calculators;
- AI-generated economic conclusions presented as measured data;
- an LLM chatbot;
- automated policy scoring;
- partisan scorecards;
- predictive trading tools;
- a 50-state map;
- a giant historical reconstruction before the modern pipeline works.

## 5. Core public pages

### Home

Must answer, in order:

1. What is The Foundation?
2. Who is the Bottom 30% under this methodology?
3. What is the latest measured cutoff?
4. What major economic pressures are improving or worsening?
5. How fresh is the data?
6. What changed in the latest update?
7. Where did each number come from?

### Methodology

Must expose:

- population definition;
- ranking unit;
- income definition;
- survey weighting method;
- normalization/scoring method once approved;
- revision policy;
- missing-data policy;
- known limitations;
- methodology version.

### Sources

For every source:

- organization;
- dataset/series;
- exact use;
- update cadence;
- official URL;
- latest reference period;
- latest release;
- freshness;
- known caveats.

### History

Must preserve:

- published vintages;
- revisions;
- methodology version for each vintage;
- ability to distinguish "what was known then" from later revised history.

## 6. Status semantics

Every public metric must carry a state:

- `measured`
- `estimated`
- `stale`
- `unavailable`
- `experimental`

The frontend must never render these as equivalent.

## 7. Release gate

The public composite Foundation score remains disabled until:

- all core calculation tests pass;
- CPS ASEC cutoff reproduces independently;
- source metadata are verified;
- normalization is frozen for the first release;
- sensitivity analysis is completed;
- double-counting review is completed;
- methodology version `1.0.0` is explicitly approved by the owner.

Until then the site may publish source observations and the Bottom-30 cutoff as **prelaunch research**.

## 8. Zero-dollar constraint

V0.1 must be operable with:

- free/open-source local tools;
- publicly available data;
- public GitHub repository;
- GitHub Pages;
- GitHub Actions within public-repository allowances;
- no required paid database;
- no required paid API;
- no required commercial analytics service.

Optional paid services may never become required for core reproducibility.

## 9. Success criteria

V0.1 succeeds when a technically competent stranger can:

1. clone the repository;
2. run the tests;
3. obtain the same Bottom-30 cutoff from the same source vintage;
4. trace every displayed observation to its source;
5. understand exactly what is estimated versus measured;
6. challenge the assumptions without reverse-engineering hidden code;
7. rebuild the static site.

## 10. Product failure

The product has failed if:

- its conclusion can be changed invisibly through frontend code;
- it requires trust in an unpublished spreadsheet;
- data are silently substituted;
- a score changes without a traceable source or methodology change;
- economic direction is chosen before measurement;
- an agent can "fix" a surprising number by changing methodology;
- the site looks authoritative while uncertainty is hidden.
