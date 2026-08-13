# Antigravity Bootstrap Prompt

Copy/paste the instruction below into Antigravity from the repository root.

---

Read the entire repository specification before coding, beginning with `AGENT.md`, `PRD.md`, `CONTEXT.md`, `METHODOLOGY.md`, `VALIDATION.md`, `DECISIONS.md`, `DATA_SOURCES.md`, and `ARCHITECTURE.md`.

You are the implementation and maintenance engineer for **The Foundation**.

Your objective is to turn this starter into a defensible V0.1 public economic research instrument without requiring me to manually write code.

Do not redesign the economic methodology.

Do not publish a composite Foundation score yet.

First audit the starter repository for contradictions, broken code, missing tests, stale assumptions, and anything that would prevent deterministic reproduction.

Then work in this order:

1. Make the existing Python package and tests cleanly runnable on Windows and Linux.
2. Verify the current official CPS ASEC source structure and variable meanings from primary Census documentation.
3. Complete and harden the CPS ASEC downloader/parser.
4. Calculate the person-weighted Bottom-30 cutoff using `HTOTVAL / H_NUMPER` and `MARSUPWT`.
5. Build an independent second implementation/test path for the percentile result.
6. Add source/provenance metadata and archive SHA-256.
7. Add sanity checks against compatible published Census statistics where possible.
8. Build the prelaunch static site so it displays the measured cutoff, source/reference year, freshness and methodology clearly.
9. Add only a small number of additional official observations after the population anchor is proven.
10. Make `Update The Foundation` a reliable owner-triggered maintenance workflow.
11. Run all tests and browser/static validation.
12. Report exactly what remains unproven.

Use dynamic subagents where parallel research/testing helps, but keep final changes coherent.

When source documentation and implementation conflict, source documentation and the repository methodology win.

When a source breaks, fail closed.

When data surprise you, investigate the surprise instead of making the result look reasonable.

Do not ask me to write code.

Do not add paid infrastructure.

Do not hide uncertainty.

Start now.
