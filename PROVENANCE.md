# Provenance Contract

Every number on the public site should eventually answer six questions:

1. Who published the source?
2. What exact variable/series/file produced the observation?
3. What time period does it describe?
4. When was it released/retrieved?
5. What transformation did The Foundation apply?
6. Which methodology version governed the transformation?

## Raw file provenance

For downloaded files record:

- canonical URL;
- retrieval timestamp;
- SHA-256;
- byte size;
- content type if available;
- survey/reference year;
- extraction member used.

## API provenance

For APIs record:

- endpoint;
- series/variable IDs;
- request period;
- response/retrieval timestamp;
- relevant response metadata.

Do not store secrets or sensitive headers.

## Derived value provenance

A derived value must list its parents.

Example:

```text
Bottom-30 cutoff
  <- weighted percentile 0.30
  <- household_income_per_person
  <- HTOTVAL / H_NUMPER
  <- MARSUPWT
  <- CPS ASEC 2025 public-use CSV
```

## Human-readable expectation

The public site does not need to expose every internal field on the first screen.

It must make the provenance path discoverable without requiring a reader to inspect source code.
