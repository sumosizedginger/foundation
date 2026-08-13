# UI / UX Specification

## Objective

The site should feel like a public instrument, not a campaign page and not a finance casino.

The first screen must answer:

> What does the evidence say about the economic foundation right now?

## Design principles

- dark, high-contrast presentation is acceptable;
- typography must be legible before decorative;
- status must never depend on color alone;
- source/provenance must be one click away;
- uncertainty must be visible;
- no fake precision;
- no animated number theater;
- no market-ticker visual language unless the data truly update that way;
- responsive from phone to desktop.

## V0.1 home hierarchy

### 1. Identity

`THE FOUNDATION`

Short explanation:

"An open economic dashboard centered on the bottom 30% of Americans."

### 2. Population anchor

Display:

- latest measured Bottom-30 cutoff;
- reference income year;
- survey year;
- whether value is measured or inflation-adjusted estimate;
- definition link.

If composite score is not released, say so plainly.

### 3. Current evidence

Cards/rows for accepted candidate observations with:

- value;
- direction;
- population;
- reference period;
- release date;
- freshness;
- status.

### 4. What changed

Latest source releases and material observation changes.

### 5. Data health

Show:

- current;
- aging;
- stale;
- unavailable;
- experimental.

### 6. Methodology/source path

Persistent access to methodology, sources and history.

## Pages

### `/`
Current state.

### `/methodology.html`
Human-readable methodology.

### `/sources.html`
Source registry and freshness.

### `/history.html`
Published/research vintages and revisions.

## Provenance interaction

Eventually every displayed metric should expose:

```text
metric
  -> exact observation
  -> transformation
  -> source variable/series
  -> release/reference date
  -> source link
  -> methodology version
```

If full drill-down is not implemented in V0.1, source metadata must still be visible.

## Language

Do not use:

- "the economy is good";
- "the economy is bad";
- "Americans are thriving";
- "Americans are doomed";

unless a specific defined metric supports exactly that claim.

Prefer:

- improved;
- worsened;
- unchanged;
- mixed;
- stale;
- unavailable;
- measured;
- estimated.

## Composite score

Until release gate approval, render:

`Composite Foundation score: PRELAUNCH — methodology under validation`

Do not show `0`, `N/A` without explanation, or a placeholder number that could be mistaken as real.

## Accessibility

Minimum:

- semantic headings;
- keyboard navigation;
- visible focus;
- sufficient contrast;
- screen-reader labels for status;
- charts accompanied by text summaries;
- reduced-motion support.

## Performance

Static site target.

No framework required.

A framework may be adopted only if it materially improves maintainability without compromising zero-dollar static deployment.
