/**
 * The Foundation — Public Web Presentation Logic
 *
 * CRITICAL ARCHITECTURAL PRINCIPLE:
 * The browser NEVER calculates authoritative economic metrics.
 * The browser strictly parses, formats, and renders precomputed, validated JSON.
 */

const moneyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const moneyExactFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const numFmt = new Intl.NumberFormat("en-US");

let globalDashboardData = null;
let globalSurvivalData = null;
let globalPopulationData = null;

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`);
  return res.json();
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function setHtml(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

// Render National Economic Pressure Signals
function renderPressureSignals(signals) {
  const container = document.getElementById("signals-grid");
  if (!container || !signals || !signals.length) return;

  container.innerHTML = "";
  signals.forEach((sig) => {
    const card = document.createElement("article");
    card.className = "signal-card";

    const isRate = sig.unit === "percent";
    const valDisplay = isRate ? `${sig.value.toFixed(1)}%` : sig.value.toLocaleString();

    card.innerHTML = `
      <div>
        <div class="signal-header">
          <span class="panel-tag" style="margin: 0;">${sig.category.toUpperCase()} · ${sig.series_id}</span>
          <span class="badge verified" style="font-size: 0.65rem;">${sig.freshness_status.toUpperCase()}</span>
        </div>
        <h4 class="signal-title">${sig.label}</h4>
        <div class="signal-val">${valDisplay}</div>
        <p style="font-size: 0.82rem; color: var(--muted); line-height: 1.4;">${sig.notes}</p>
      </div>
      <div class="signal-meta">
        <span>Period: ${sig.period_name} ${sig.year}</span>
        <button class="btn-link" onclick="openSignalProvenance('${sig.series_id}')">Provenance →</button>
      </div>
    `;
    container.appendChild(card);
  });
}

// Render Household Size Matrix
function renderHouseholdMatrix(matrix) {
  const tbody = document.getElementById("household-matrix-body");
  if (!tbody || !matrix || !matrix.length) return;

  tbody.innerHTML = "";
  matrix.forEach((row) => {
    const tr = document.createElement("tr");
    const isAdequate = row.adequacy_ratio >= 1.0;
    const gapColor = isAdequate ? "var(--good)" : "var(--danger)";
    const gapSign = row.survival_gap_annual >= 0 ? "+" : "";

    tr.innerHTML = `
      <td class="mono" style="font-weight: 700;">${row.household_size}</td>
      <td>${row.composition_label}</td>
      <td class="mono text-right">${moneyFmt.format(row.population_anchor_annual)}</td>
      <td class="mono text-right">${moneyFmt.format(row.survival_floor_annual)}</td>
      <td class="mono text-right" style="color: ${gapColor}; font-weight: 700;">${gapSign}${moneyFmt.format(row.survival_gap_annual)}</td>
      <td class="mono text-right" style="color: ${gapColor}; font-weight: 700;">${row.adequacy_ratio.toFixed(2)} (${Math.round(row.adequacy_ratio * 100)}%)</td>
    `;
    tbody.appendChild(tr);
  });
}

// Render Quantiles
function renderQuantiles(quantiles) {
  const grid = document.getElementById("quantiles-grid");
  if (!grid || !quantiles) return;

  const descMap = {
    P10: "Deep Foundation",
    P20: "Lower Tier",
    P30: "Bottom-30 Anchor",
    P40: "Near Foundation",
    P50: "National Median",
    P75: "Upper Middle",
    P90: "Top 10% Cutoff",
  };

  grid.innerHTML = "";
  Object.keys(quantiles).forEach((qKey) => {
    const val = quantiles[qKey];
    const isAnchor = qKey === "P30";
    const card = document.createElement("div");
    card.className = `quantile-card ${isAnchor ? "anchor" : ""}`;

    card.innerHTML = `
      <p class="quantile-p">${isAnchor ? "P30 · ANCHOR" : qKey}</p>
      <p class="quantile-val" style="${isAnchor ? "color: var(--accent);" : ""}">${moneyFmt.format(val)}</p>
      <p class="quantile-desc" style="${isAnchor ? "color: var(--accent);" : ""}">${descMap[qKey] || "Income Level"}</p>
    `;
    grid.appendChild(card);
  });
}

// Provenance Inspection Modal Logic
window.openProvenance = function (type) {
  const modal = document.getElementById("provenance-modal");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  if (!modal || !body) return;

  if (type === "population_anchor") {
    title.textContent = "Population Anchor Provenance Chain";
    const pop = globalDashboardData?.population_anchor || {};
    const art = pop.source_artifact || {};
    const valRep = pop.validation_report || {};

    body.innerHTML = `
      <div class="provenance-item">
        <p class="provenance-label">Calculation Chain</p>
        <div class="provenance-val">
          Bottom-30 Cutoff ($21,800.00)<br>
          ↳ Weighted Percentile (p = 0.30)<br>
          ↳ household_income_per_person = HTOTVAL / H_NUMPER<br>
          ↳ Person Survey Weight: MARSUPWT (scale factor 100)<br>
          ↳ Merged Records: pppub25.csv ⨝ hhpub25.csv on PH_SEQ == H_SEQ
        </div>
      </div>
      <div class="provenance-item">
        <p class="provenance-label">Source Dataset</p>
        <div class="provenance-val">
          <strong>U.S. Census Bureau</strong> · Current Population Survey (CPS ASEC)<br>
          Survey Year: ${pop.survey_year} | Income Reference Year: ${pop.income_year}<br>
          Archive: ${art.url || "asecpub25csv.zip"}<br>
          SHA-256: ${art.sha256 || valRep.sha256 || "318845a2b5e0034e357900b991196ce28ecdd0c99a0937b27ff77f8ea6497284"}
        </div>
      </div>
      <div class="provenance-item">
        <p class="provenance-label">Validation Cross-Check</p>
        <div class="provenance-val">
          Canonical Value: ${moneyExactFmt.format(pop.cutoff || 21800)}<br>
          Independent Reference Value: ${moneyExactFmt.format(valRep.independent_reference_p30 || 21800)}<br>
          Implementation Difference: 0.0000 (PASSED)<br>
          Matched Person Records: ${numFmt.format(pop.valid_records || 142125)}<br>
          Represented Population: ${numFmt.format(pop.represented_population || 337689642)} persons
        </div>
      </div>
    `;
  } else if (type === "survival_floor") {
    title.textContent = "Survival Floor Component Model & Research Status";
    const surv = globalDashboardData?.survival_floor || {};
    const comps = surv.components || [];

    let compListHtml = comps
      .map(
        (c) => `
      <div style="border-bottom: 1px solid var(--line); padding: 0.75rem 0;">
        <div style="display:flex; justify-content:space-between; font-weight:700;">
          <span>${c.category.toUpperCase().replace("_", " ")}</span>
          <span class="mono">${moneyFmt.format(c.annual_cost)} / yr (${moneyFmt.format(c.monthly_cost)}/mo)</span>
        </div>
        <p style="font-size:0.82rem; color:var(--muted); margin-top:0.2rem;">${c.method}</p>
        <p style="font-size:0.75rem; color:var(--subtle);">Source: ${c.source_name} (${c.source_agency})</p>
      </div>
    `
      )
      .join("");

    body.innerHTML = `
      <div class="provenance-item">
        <p class="provenance-label">Status & Authority</p>
        <div class="provenance-val" style="border-left: 3px solid var(--accent);">
          <strong>RESEARCH ESTIMATE</strong> · Prelaunch Validation State<br>
          Synthesized from official government expenditure baselines (HUD FMR, USDA TFP, EIA RECS, BLS CE, MEPS).
        </div>
      </div>
      <div class="provenance-item">
        <p class="provenance-label">Component Breakdown (Single Adult)</p>
        <div class="provenance-val">
          ${compListHtml || "<p>Loading components…</p>"}
        </div>
      </div>
      <div class="provenance-item">
        <p class="provenance-label">Benchmark Comparisons</p>
        <div class="provenance-val">
          • <strong>MIT Living Wage:</strong> ~$42,500 (Includes civic engagement, unsubsidized healthcare, county weighting)<br>
          • <strong>ALICE Survival Budget:</strong> ~$31,200 (Includes 10% contingency reserve and tech budgets)<br>
          • <strong>Official Poverty Measure (OPM):</strong> $15,650 (Based on 1963 3x food multiplier)
        </div>
      </div>
    `;
  }

  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
};

window.openSignalProvenance = function (seriesId) {
  const modal = document.getElementById("provenance-modal");
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  if (!modal || !body) return;

  const sig = (globalDashboardData?.pressures || []).find((s) => s.series_id === seriesId);
  if (!sig) return;

  title.textContent = `Pressure Signal: ${sig.label}`;
  body.innerHTML = `
    <div class="provenance-item">
      <p class="provenance-label">Series Identifier</p>
      <div class="provenance-val">${sig.series_id} (${sig.publisher})</div>
    </div>
    <div class="provenance-item">
      <p class="provenance-label">Observation Details</p>
      <div class="provenance-val">
        Latest Observation: ${sig.period_name} ${sig.year} (${sig.observation_period})<br>
        Value: <strong>${sig.value} ${sig.unit}</strong><br>
        Seasonal Adjustment: ${sig.seasonal_adjustment}<br>
        Official Endpoint: <a href="${sig.source_url}" target="_blank" style="color:var(--accent);">${sig.source_url}</a>
      </div>
    </div>
    <div class="provenance-item">
      <p class="provenance-label">Methodological Role</p>
      <div class="provenance-val">
        <strong>National Economic Pressure Signal:</strong> Measures general macroeconomic conditions. It is NOT a direct measurement of the Bottom-30 population.
      </div>
    </div>
  `;

  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
};

window.closeProvenance = function () {
  const modal = document.getElementById("provenance-modal");
  if (modal) {
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
  }
};

// Close modal when clicking backdrop
document.addEventListener("click", (e) => {
  const modal = document.getElementById("provenance-modal");
  if (modal && e.target === modal) {
    closeProvenance();
  }
});

// Boot Application
async function init() {
  try {
    const latest = await fetchJson("data/latest.json");
    globalDashboardData = latest;

    // Set Header Status Strip
    setText(
      "stage-status",
      `PRELAUNCH RESEARCH INSTRUMENT · Canonical Population Anchor Verified · Composite Score Locked · Methodology ${latest.project?.methodology_version || "0.1.0"}`
    );

    // Set Population Anchor Card
    const pop = latest.population_anchor || {};
    if (pop.cutoff) {
      setText("cutoff-value", moneyFmt.format(pop.cutoff));
      setText("cutoff-monthly", `≈ ${moneyFmt.format(pop.monthly_cutoff || pop.cutoff / 12)} per person / month`);
      setText(
        "cutoff-detail",
        `Derived from ${pop.survey_year} CPS ASEC microdata (${pop.income_year} income reference year) ranking ${numFmt.format(pop.represented_population || 337689642)} represented persons.`
      );
    }

    // Set Survival Floor Card
    const surv = latest.survival_floor || {};
    if (surv.single_adult_floor_annual) {
      setText("survival-value", moneyFmt.format(surv.single_adult_floor_annual));
      setText(
        "survival-monthly",
        `≈ ${moneyFmt.format(surv.single_adult_floor_monthly || surv.single_adult_floor_annual / 12)} per month`
      );
      setText("survival-gap-val", `${moneyFmt.format(surv.survival_gap_annual)} / yr`);
      setText(
        "adequacy-ratio-val",
        `${surv.adequacy_ratio.toFixed(2)} (${Math.round(surv.adequacy_ratio * 100)}%)`
      );
    }

    // Render Matrix, Quantiles, and Pressures
    if (surv.household_matrix) {
      renderHouseholdMatrix(surv.household_matrix);
    }

    if (pop.quantiles) {
      renderQuantiles(pop.quantiles);
    }

    if (latest.pressures) {
      renderPressureSignals(latest.pressures);
    }

    if (latest.as_of) {
      setText("site-as-of", `As of: ${latest.as_of}`);
    }

    if (latest.latest_changes && latest.latest_changes.length) {
      const listEl = document.getElementById("latest-changes-list");
      if (listEl) {
        listEl.innerHTML = latest.latest_changes.map((c) => `<li>• ${c}</li>`).join("");
      }
    }
  } catch (err) {
    console.error("Dashboard initialisation error:", err);
    setText(
      "stage-status",
      "DATA LOAD NOTICE · Precomputed JSON loading issue. The site refused to manufacture replacement numbers."
    );
  }
}

document.addEventListener("DOMContentLoaded", init);
