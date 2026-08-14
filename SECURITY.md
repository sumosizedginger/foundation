# Security and Operational Boundaries

## Core principle

The Foundation should need almost no secrets.

Public data should remain public-data plumbing.

## Secrets

Never commit:

- API keys;
- GitHub tokens;
- cookies;
- passwords;
- private MCP credentials.

Use environment variables or GitHub encrypted secrets when optional credentials are required.

Optional living-cost retrieve secrets (never committed):

- `CENSUS_API_KEY` — Census API national queries. Official ACS B01001 county weights can also be retrieved from the public summary file without a key.
- `EIA_API_KEY` — EIA Open Data v2 if bulk workbook is insufficient.
- `HUD_API_TOKEN` — HUD User API if direct XLSX retrieve is blocked.

## Network

Approved production connectors should use HTTPS.

Use explicit domains from `config/sources.yml`.

Do not build a general web scraper into the economic pipeline.

## Downloads

For raw archives:

- verify HTTP status;
- impose sensible timeout;
- record content length when available;
- hash downloaded bytes;
- inspect archive members before extraction;
- prevent zip-slip/path traversal;
- extract only expected file types.

## Microdata

CPS ASEC is public-use anonymized microdata.

Do not attempt re-identification.

Do not add tooling designed to join public-use files to identify named individuals.

## Git

Before automated commit/push:

- confirm repository;
- confirm branch;
- inspect diff;
- exclude raw giant archives;
- exclude secrets;
- never force-push without explicit owner instruction.

## Dependencies

Pin reasonable minimum versions.

Avoid dependencies whose only value is replacing a few lines of standard-library code.

Run dependency/security checks when practical, but do not add a paid scanner requirement.

## Agent permissions

Recommended autonomous permissions:

- read/write project files;
- run Python/pytest;
- download from approved source domains;
- build static site;
- Git status/diff/add/commit/push when the owner has configured authentication.

Require owner judgment for:

- new source domains;
- methodology changes;
- secrets/credential configuration;
- destructive Git operations;
- deleting historical/revision data;
- introducing paid services.
