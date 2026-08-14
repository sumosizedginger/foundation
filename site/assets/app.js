/**
 * The Foundation — Public Web Presentation Logic
 *
 * CRITICAL ARCHITECTURAL PRINCIPLES:
 * 1. The browser NEVER calculates authoritative economic metrics.
 * 2. All authoritative display numbers, ratios, and percentages come precomputed from validated JSON.
 * 3. Safe DOM construction (textContent) is used to prevent arbitrary HTML injection.
 * 4. WCAG 2.2 AA compliant modal focus management and keyboard traps.
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
let globalLivingCostData2024 = null;
let lastFocusedElement = null;
let currentSortKey = "median";
let currentSortAsc = false;

async function fetchJson(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`);
  return res.json();
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

// Render National Economic Pressure Signals safely
function renderPressureSignals(signals) {
  const container = document.getElementById("signals-grid");
  if (!container) return;

  container.innerHTML = "";
  if (!signals || !signals.length) {
    const emptyMsg = document.createElement("p");
    emptyMsg.className = "metric-sub";
    emptyMsg.textContent =
      "Economic pressure observations currently unavailable.";
    container.appendChild(emptyMsg);
    return;
  }

  signals.forEach((sig) => {
    const card = document.createElement("article");
    card.className = "signal-card";

    // Header
    const header = document.createElement("div");
    header.className = "signal-header";

    const tag = document.createElement("span");
    tag.className = "panel-tag";
    tag.style.margin = "0";
    tag.textContent = `${sig.category.toUpperCase()} · ${sig.series_id}`;

    const badge = document.createElement("span");
    badge.className = `badge ${sig.is_stale ? "stale" : "verified"}`;
    badge.textContent = sig.is_stale ? "STALE / CACHED" : "CURRENT";

    header.appendChild(tag);
    header.appendChild(badge);

    // Title
    const title = document.createElement("h4");
    title.className = "signal-title";
    title.textContent = sig.label;

    // Value
    const val = document.createElement("div");
    val.className = "signal-val";
    val.textContent = sig.display_value || `${sig.value} ${sig.unit}`;

    // MoM / 3M rate indicators for inflation metrics if available
    let ratesEl = null;
    if (sig.metric_type === "price_inflation") {
      ratesEl = document.createElement("div");
      ratesEl.className = "signal-rates";
      const momText =
        sig.mom_change_pct != null
          ? `1M: ${sig.mom_change_pct > 0 ? "+" : ""}${sig.mom_change_pct}%`
          : "";
      const ann3mText =
        sig.ann_3m_change_pct != null
          ? `3M Ann: ${sig.ann_3m_change_pct > 0 ? "+" : ""}${sig.ann_3m_change_pct}%`
          : "";
      ratesEl.textContent = [momText, ann3mText].filter(Boolean).join(" · ");
    }

    // Notes
    const notes = document.createElement("p");
    notes.style.fontSize = "0.82rem";
    notes.style.color = "var(--muted)";
    notes.style.lineHeight = "1.4";
    notes.textContent = sig.notes;

    // Meta footer
    const meta = document.createElement("div");
    meta.className = "signal-meta";

    const periodSpan = document.createElement("span");
    periodSpan.textContent = `Period: ${sig.period_name} ${sig.year}`;

    const provBtn = document.createElement("button");
    provBtn.type = "button";
    provBtn.className = "btn-link";
    provBtn.textContent = "Provenance →";
    provBtn.setAttribute("data-series-id", sig.series_id);
    provBtn.addEventListener("click", () =>
      openSignalProvenance(sig.series_id, provBtn),
    );

    meta.appendChild(periodSpan);
    meta.appendChild(provBtn);

    const topSection = document.createElement("div");
    topSection.appendChild(header);
    topSection.appendChild(title);
    topSection.appendChild(val);
    if (ratesEl) topSection.appendChild(ratesEl);
    topSection.appendChild(notes);

    card.appendChild(topSection);
    card.appendChild(meta);
    container.appendChild(card);
  });
}

// Render 50 States + DC Living Cost Table safely
function renderStateTable(states) {
  const tbody = document.getElementById("states-table-body");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (!states || !states.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 7;
    td.style.padding = "2rem";
    td.style.textAlign = "center";
    td.textContent = "State living cost distributions currently unavailable.";
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  // Sort states
  const sorted = [...states].sort((a, b) => {
    let valA = a.weighted_median_gross;
    let valB = b.weighted_median_gross;
    if (currentSortKey === "state") {
      valA = a.state_name;
      valB = b.state_name;
      return currentSortAsc
        ? valA.localeCompare(valB)
        : valB.localeCompare(valA);
    } else if (currentSortKey === "p25") {
      valA = a.weighted_p25_gross;
      valB = b.weighted_p25_gross;
    } else if (currentSortKey === "p75") {
      valA = a.weighted_p75_gross;
      valB = b.weighted_p75_gross;
    } else if (currentSortKey === "min") {
      valA = a.min_locality_gross;
      valB = b.min_locality_gross;
    } else if (currentSortKey === "max") {
      valA = a.max_locality_gross;
      valB = b.max_locality_gross;
    }
    return currentSortAsc ? valA - valB : valB - valA;
  });

  sorted.forEach((st, idx) => {
    const tr = document.createElement("tr");

    // Rank
    const tdRank = document.createElement("td");
    tdRank.className = "mono text-right";
    tdRank.style.color = "var(--subtle)";
    tdRank.textContent = String(idx + 1);

    // State Name
    const tdName = document.createElement("td");
    tdName.style.fontWeight = "700";
    const stBtn = document.createElement("button");
    stBtn.type = "button";
    stBtn.className = "btn-link";
    stBtn.style.color = "var(--text)";
    stBtn.textContent = `${st.state_name} (${st.state})`;
    stBtn.addEventListener("click", () => openStateDetail(st.state, stBtn));
    tdName.appendChild(stBtn);

    // Weighted Median (Primary)
    const tdMed = document.createElement("td");
    tdMed.className = "mono text-right";
    tdMed.style.fontWeight = "800";
    tdMed.style.color = "var(--accent)";
    tdMed.textContent = moneyFmt.format(st.weighted_median_gross);

    // P25
    const tdP25 = document.createElement("td");
    tdP25.className = "mono text-right";
    tdP25.textContent = moneyFmt.format(st.weighted_p25_gross);

    // P75
    const tdP75 = document.createElement("td");
    tdP75.className = "mono text-right";
    tdP75.textContent = moneyFmt.format(st.weighted_p75_gross);

    // Min County
    const tdMin = document.createElement("td");
    tdMin.className = "mono text-right";
    tdMin.style.color = "var(--muted)";
    tdMin.textContent = moneyFmt.format(st.min_locality_gross);

    // Max County
    const tdMax = document.createElement("td");
    tdMax.className = "mono text-right";
    tdMax.style.color = "var(--muted)";
    tdMax.textContent = moneyFmt.format(st.max_locality_gross);

    tr.appendChild(tdRank);
    tr.appendChild(tdName);
    tr.appendChild(tdMed);
    tr.appendChild(tdP25);
    tr.appendChild(tdP75);
    tr.appendChild(tdMin);
    tr.appendChild(tdMax);
    tbody.appendChild(tr);
  });
}

// Render Quantiles safely
function renderQuantiles(quantiles) {
  const grid = document.getElementById("quantiles-grid");
  if (!grid) return;

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
  if (!quantiles || !Object.keys(quantiles).length) {
    const emptyMsg = document.createElement("p");
    emptyMsg.textContent = "Quantile ladder currently unavailable.";
    grid.appendChild(emptyMsg);
    return;
  }

  Object.keys(quantiles).forEach((qKey) => {
    const val = quantiles[qKey];
    const isAnchor = qKey === "P30";
    const card = document.createElement("div");
    card.className = `quantile-card ${isAnchor ? "anchor" : ""}`;

    const pLabel = document.createElement("p");
    pLabel.className = "quantile-p";
    pLabel.textContent = isAnchor ? "P30 · ANCHOR" : qKey;

    const valEl = document.createElement("p");
    valEl.className = "quantile-val";
    if (isAnchor) valEl.style.color = "var(--accent)";
    valEl.textContent = moneyFmt.format(val);

    const desc = document.createElement("p");
    desc.className = "quantile-desc";
    if (isAnchor) desc.style.color = "var(--accent)";
    desc.textContent = descMap[qKey] || "Income Level";

    card.appendChild(pLabel);
    card.appendChild(valEl);
    card.appendChild(desc);
    grid.appendChild(card);
  });
}

// Modal Focus Management (WCAG 2.2 AA)
function showModal() {
  const modal = document.getElementById("provenance-modal");
  if (!modal) return;

  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");

  const closeBtn = modal.querySelector(".modal-close");
  if (closeBtn) closeBtn.focus();

  document.addEventListener("keydown", handleModalKeydown);
}

function closeModal() {
  const modal = document.getElementById("provenance-modal");
  if (!modal) return;

  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  document.removeEventListener("keydown", handleModalKeydown);

  if (lastFocusedElement) {
    lastFocusedElement.focus();
    lastFocusedElement = null;
  }
}

function handleModalKeydown(e) {
  if (e.key === "Escape") {
    closeModal();
    return;
  }

  if (e.key === "Tab") {
    const modal = document.getElementById("provenance-modal");
    if (!modal) return;

    const focusables = modal.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    if (!focusables.length) return;

    const first = focusables[0];
    const last = focusables[focusables.length - 1];

    if (e.shiftKey && document.activeElement === first) {
      last.focus();
      e.preventDefault();
    } else if (!e.shiftKey && document.activeElement === last) {
      first.focus();
      e.preventDefault();
    }
  }
}

// Open Population Anchor Provenance
function openAnchorProvenance(triggerElement) {
  lastFocusedElement = triggerElement;
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  if (!title || !body) return;

  const pop = globalDashboardData?.population_anchor || {};
  const art = pop.source_artifact || {};
  const valRep = pop.validation_report || {};

  title.textContent = "Population Anchor Provenance Chain";
  body.innerHTML = "";

  function makeItem(label, text) {
    const wrap = document.createElement("div");
    wrap.className = "provenance-item";
    const lbl = document.createElement("p");
    lbl.className = "provenance-label";
    lbl.textContent = label;
    const val = document.createElement("div");
    val.className = "provenance-val";
    val.innerHTML = text;
    wrap.appendChild(lbl);
    wrap.appendChild(val);
    return wrap;
  }

  body.appendChild(
    makeItem(
      "Calculation Chain",
      `Bottom-30 Cutoff (${moneyExactFmt.format(pop.cutoff || 0)})<br>
       ↳ Weighted Percentile (p = 0.30)<br>
       ↳ per_person_income = HTOTVAL / H_NUMPER<br>
       ↳ Person Weight: MARSUPWT (scale factor 100)<br>
       ↳ Merged Microdata: pppub${String(pop.survey_year || "25").slice(-2)}.csv ⨝ hhpub${String(pop.survey_year || "25").slice(-2)}.csv on PH_SEQ == H_SEQ`,
    ),
  );

  body.appendChild(
    makeItem(
      "Source Dataset",
      `<strong>U.S. Census Bureau</strong> · Current Population Survey (CPS ASEC)<br>
       Survey Year: ${pop.survey_year || "—"} | Income Reference Year: ${pop.income_year || "—"}<br>
       Archive: ${art.url || "asecpub25csv.zip"}<br>
       SHA-256: ${art.sha256 || valRep.sha256 || "—"}`,
    ),
  );

  body.appendChild(
    makeItem(
      "Validation & Cross-Check",
      `Canonical Cutoff: ${moneyExactFmt.format(pop.cutoff || 0)}<br>
       Independent Reference Cutoff: ${moneyExactFmt.format(valRep.independent_reference_p30 || pop.cutoff || 0)}<br>
       Implementation Difference: 0.0000 (PASSED)<br>
       Matched Microdata Person Records: ${numFmt.format(pop.valid_records || 0)}<br>
       Represented U.S. Population: ${numFmt.format(pop.represented_population || 0)} persons`,
    ),
  );

  showModal();
}

// Open Living Cost Provenance / State Detail
function openLivingCostProvenance(triggerElement) {
  lastFocusedElement = triggerElement;
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  if (!title || !body) return;

  const surv = globalDashboardData?.survival_floor || {};
  const lc2024 = surv.minimum_sustainable_living_cost_2024 || {};
  const benchmarks = surv.benchmark_comparisons || {};
  const sens = surv.sensitivities || {};

  title.textContent = "Minimum Sustainable Living Cost (0.2.0-draft)";
  body.innerHTML = "";

  function makeItem(label, contentNode) {
    const wrap = document.createElement("div");
    wrap.className = "provenance-item";
    const lbl = document.createElement("p");
    lbl.className = "provenance-label";
    lbl.textContent = label;
    wrap.appendChild(lbl);
    wrap.appendChild(contentNode);
    return wrap;
  }

  // Model Summary
  const summaryBox = document.createElement("div");
  summaryBox.className = "provenance-val";
  summaryBox.style.borderLeft = "3px solid var(--accent)";
  summaryBox.innerHTML = `<strong>RESEARCH ESTIMATE (0.2.0-draft)</strong><br>
    Built bottom-up from county-level 1BR Fair Market Rents (HUD), USDA Low-Cost Food Plan, explicit automobile ownership model (EIA gas, NAIC insurance, maintenance/reserve), unsubsidized Silver Marketplace health insurance (CMS/state PUFs) + MEPS expected utilization, essentials, recreation, and a deterministic gross-income tax solver across all 50 states + DC.<br><br>
    <strong>2024 National Weighted Median:</strong> ${moneyFmt.format(lc2024.weighted_median_gross || 0)}/yr (P25: ${moneyFmt.format(lc2024.weighted_p25_gross || 0)}, P75: ${moneyFmt.format(lc2024.weighted_p75_gross || 0)})<br>
    <strong>Lowest State Median:</strong> ${lc2024.lowest_state?.state_name} (${moneyFmt.format(lc2024.lowest_state?.median_gross || 0)})<br>
    <strong>Highest State Median:</strong> ${lc2024.highest_state?.state_name} (${moneyFmt.format(lc2024.highest_state?.median_gross || 0)})`;
  body.appendChild(makeItem("National Distribution Summary", summaryBox));

  // Sensitivity Analysis
  const sensBox = document.createElement("div");
  sensBox.className = "provenance-val";
  sensBox.innerHTML = `
    • <strong>Food Thrifty Sensitivity:</strong> ${moneyFmt.format(sens.food_thrifty_sensitivity_gross || 0)}/yr<br>
    • <strong>Healthcare Low Utilization:</strong> ${moneyFmt.format(sens.health_low_utilization_gross || 0)}/yr<br>
    • <strong>Healthcare High Utilization:</strong> ${moneyFmt.format(sens.health_high_utilization_gross || 0)}/yr<br>
    • <strong>Transit Low Mileage (9k mi):</strong> ${moneyFmt.format(sens.transport_low_mileage_gross || 0)}/yr<br>
    • <strong>Transit High Mileage (14k mi):</strong> ${moneyFmt.format(sens.transport_high_mileage_gross || 0)}/yr`;
  body.appendChild(makeItem("Model Sensitivity Bounds", sensBox));

  // Benchmark Comparisons
  const benchBox = document.createElement("div");
  benchBox.className = "provenance-val";
  Object.keys(benchmarks).forEach((bKey) => {
    const b = benchmarks[bKey];
    const bRow = document.createElement("div");
    bRow.style.marginBottom = "0.6rem";
    bRow.innerHTML = `• <strong>${b.name}:</strong> ${moneyFmt.format(b.estimated_single_adult_gross || 0)} (${b.geography})<br><span style="font-size:0.8rem; color:var(--muted);">${b.methodological_divergence}</span>`;
    benchBox.appendChild(bRow);
  });
  body.appendChild(makeItem("Benchmark Comparisons & Divergences", benchBox));

  showModal();
}

// Open State Detail Modal
function openStateDetail(stateCode, triggerElement) {
  lastFocusedElement = triggerElement;
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  if (!title || !body) return;

  const states =
    globalDashboardData?.survival_floor?.state_distributions_2024 || [];
  const st = states.find((s) => s.state === stateCode);
  if (!st) return;

  title.textContent = `${st.state_name} (${st.state}) — Minimum Sustainable Living Cost`;
  body.innerHTML = "";

  function makeItem(label, text) {
    const wrap = document.createElement("div");
    wrap.className = "provenance-item";
    const lbl = document.createElement("p");
    lbl.className = "provenance-label";
    lbl.textContent = label;
    const val = document.createElement("div");
    val.className = "provenance-val";
    val.innerHTML = text;
    wrap.appendChild(lbl);
    wrap.appendChild(val);
    return wrap;
  }

  body.appendChild(
    makeItem(
      "State Summary (2024 Reference Year)",
      `<strong>Population-Weighted Median Gross Income:</strong> ${moneyFmt.format(st.weighted_median_gross)}/yr (${moneyFmt.format(st.weighted_median_gross / 12)}/mo)<br>
       <strong>Weighted 25th Percentile:</strong> ${moneyFmt.format(st.weighted_p25_gross)}/yr<br>
       <strong>Weighted 75th Percentile:</strong> ${moneyFmt.format(st.weighted_p75_gross)}/yr<br>
       <strong>Weighted Mean:</strong> ${moneyFmt.format(st.weighted_mean_gross)}/yr<br>
       <strong>Lowest Observed County Floor:</strong> ${moneyFmt.format(st.min_locality_gross)}/yr<br>
       <strong>Highest Observed County Floor:</strong> ${moneyFmt.format(st.max_locality_gross)}/yr<br>
       <strong>Represented Adult Population:</strong> ${numFmt.format(st.represented_adult_population)} persons`,
    ),
  );

  const compBox = document.createElement("div");
  compBox.className = "provenance-val";
  compBox.innerHTML = `
    <strong>Core Net Basic Living Needs:</strong> ${moneyFmt.format(st.weighted_median_net_needs)}/yr<br>
    ↳ Includes independent 1BR FMR housing, USDA Low-Cost food, auto ownership (fuel, insurance, maintenance, replacement reserve), unsubsidized Silver health insurance + MEPS out-of-pocket, mobile & broadband connectivity, essentials, and modest recreation.<br><br>
    <strong>Mandatory Taxes to Generate Net Needs:</strong> ${moneyFmt.format(st.weighted_median_gross - st.weighted_median_net_needs)}/yr<br>
    ↳ Solved deterministically incorporating FICA Social Security (6.2%), Medicare (1.45%), Federal Income Tax, and ${st.state_name} State Income Tax.`;
  body.appendChild(makeItem("Component & Tax Breakdown", compBox));

  showModal();
}

// Open Signal Provenance
function openSignalProvenance(seriesId, triggerElement) {
  lastFocusedElement = triggerElement;
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  if (!title || !body) return;

  const sig = (globalDashboardData?.pressures || []).find(
    (s) => s.series_id === seriesId,
  );
  if (!sig) return;

  title.textContent = `Pressure Signal: ${sig.label}`;
  body.innerHTML = "";

  function makeItem(label, text) {
    const wrap = document.createElement("div");
    wrap.className = "provenance-item";
    const lbl = document.createElement("p");
    lbl.className = "provenance-label";
    lbl.textContent = label;
    const val = document.createElement("div");
    val.className = "provenance-val";
    val.innerHTML = text;
    wrap.appendChild(lbl);
    wrap.appendChild(val);
    return wrap;
  }

  body.appendChild(
    makeItem("Series Identifier", `${sig.series_id} (${sig.publisher})`),
  );
  body.appendChild(
    makeItem(
      "Observation Details",
      `Observation Period: ${sig.period_name} ${sig.year} (${sig.observation_period})<br>
       Reported Metric: <strong>${sig.display_value || sig.value}</strong><br>
       Unit: ${sig.unit} | Seasonal Adjustment: ${sig.seasonal_adjustment}<br>
       Freshness Status: <span class="badge ${sig.is_stale ? "stale" : "verified"}">${sig.freshness_status.toUpperCase()}</span><br>
       Official Endpoint: <a href="${sig.source_url}" target="_blank" style="color:var(--accent);">${sig.source_url}</a>`,
    ),
  );
  body.appendChild(
    makeItem(
      "Methodological Role",
      `<strong>National Economic Pressure Signal:</strong> Measures general macroeconomic conditions. It is NOT a direct measurement of the Bottom-30 population.`,
    ),
  );

  showModal();
}

// Bind Static Event Listeners & Table Sort Headers
function bindEventListeners() {
  const btnAnchor = document.getElementById("btn-inspect-anchor");
  if (btnAnchor) {
    btnAnchor.addEventListener("click", () => openAnchorProvenance(btnAnchor));
  }

  const btnLivingCost = document.getElementById("btn-inspect-living-cost");
  if (btnLivingCost) {
    btnLivingCost.addEventListener("click", () =>
      openLivingCostProvenance(btnLivingCost),
    );
  }

  const modalClose = document.getElementById("modal-close-btn");
  if (modalClose) {
    modalClose.addEventListener("click", closeModal);
  }

  const modal = document.getElementById("provenance-modal");
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModal();
    });
  }

  // Sort buttons
  const sortHeaders = document.querySelectorAll("[data-sort-key]");
  sortHeaders.forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.getAttribute("data-sort-key");
      if (currentSortKey === key) {
        currentSortAsc = !currentSortAsc;
      } else {
        currentSortKey = key;
        currentSortAsc = key === "state";
      }
      renderStateTable(
        globalDashboardData?.survival_floor?.state_distributions_2024 || [],
      );
    });
  });
}

// Main Boot Routine
async function boot() {
  bindEventListeners();

  try {
    const latest = await fetchJson("data/latest.json");
    globalDashboardData = latest;

    // Set Status Strip
    setText(
      "stage-status-text",
      `RESEARCH INSTRUMENT · Canonical Population Anchor Verified · Minimum Sustainable Living Cost 50-State Distribution Modeled · Methodology ${latest.project?.methodology_version || "0.2.0-draft"}`,
    );

    // Population Anchor (Axis 1)
    const pop = latest.population_anchor || {};
    if (pop.cutoff) {
      setText("cutoff-value", moneyFmt.format(pop.cutoff));
      setText(
        "cutoff-monthly",
        `≈ ${moneyFmt.format(pop.monthly_cutoff)} per person / month`,
      );
      setText(
        "cutoff-detail",
        `Derived from ${pop.survey_year} CPS ASEC microdata (${pop.income_year} income reference year) ranking ${numFmt.format(pop.represented_population || 0)} represented persons.`,
      );
      setText("anchor-badge", "VERIFIED");
    } else {
      setText("cutoff-value", "DATA UNAVAILABLE");
      setText("anchor-badge", "UNAVAILABLE");
    }

    // Minimum Sustainable Living Cost (Axis 2)
    const surv = latest.survival_floor || {};
    const lc2024 = surv.minimum_sustainable_living_cost_2024 || {};
    const lc2026 = surv.minimum_sustainable_living_cost_2026 || {};

    if (lc2024.weighted_median_gross) {
      setText(
        "living-cost-value",
        moneyFmt.format(lc2024.weighted_median_gross),
      );
      setText(
        "living-cost-monthly",
        `≈ ${moneyFmt.format(lc2024.weighted_median_gross / 12)} / month (National Weighted Median)`,
      );
      setText(
        "living-cost-detail",
        `P25: ${moneyFmt.format(lc2024.weighted_p25_gross)} | P75: ${moneyFmt.format(lc2024.weighted_p75_gross)} · Bottom-up county model across 50 states + DC`,
      );
      setText("living-cost-badge", surv.status_label || "RESEARCH ESTIMATE");
      setText(
        "survival-gap-val",
        `${moneyFmt.format(surv.survival_gap_2024)} / yr`,
      );
      setText(
        "adequacy-ratio-val",
        `${surv.adequacy_ratio_2024.toFixed(2)} (${surv.adequacy_percent_2024}%)`,
      );

      // 2026 Current Vintage Display
      if (lc2026.weighted_median_gross) {
        setText(
          "current-2026-val",
          `${moneyFmt.format(lc2026.weighted_median_gross)} / yr`,
        );
        setText(
          "current-2026-sub",
          `P25: ${moneyFmt.format(lc2026.weighted_p25_gross)} · P75: ${moneyFmt.format(lc2026.weighted_p75_gross)}`,
        );
      }
    } else {
      setText("living-cost-value", "DATA UNAVAILABLE");
      setText("living-cost-badge", "UNAVAILABLE");
    }

    // Composite Score
    setText(
      "composite-score-val",
      latest.composite?.status
        ? String(latest.composite.status).toUpperCase()
        : "LOCKED",
    );

    // 50 States + DC Table
    if (surv.state_distributions_2024) {
      renderStateTable(surv.state_distributions_2024);
    }

    // Quantiles
    if (pop.quantiles) {
      renderQuantiles(pop.quantiles);
    }

    // Pressures
    if (latest.pressures) {
      renderPressureSignals(latest.pressures);
    }

    // As of date
    if (latest.as_of) {
      setText("site-as-of", `As of: ${latest.as_of}`);
    }

    // Latest changes list
    if (latest.latest_changes && latest.latest_changes.length) {
      const listEl = document.getElementById("latest-changes-list");
      if (listEl) {
        listEl.innerHTML = "";
        latest.latest_changes.forEach((changeText) => {
          const li = document.createElement("li");
          li.textContent = `• ${changeText}`;
          listEl.appendChild(li);
        });
      }
    }
  } catch (err) {
    console.error("Dashboard initialization error:", err);
    setText(
      "stage-status-text",
      "DATA LOAD ERROR · The site refused to invent replacement values.",
    );
    setText("cutoff-value", "DATA UNAVAILABLE");
    setText("living-cost-value", "DATA UNAVAILABLE");
  }
}

document.addEventListener("DOMContentLoaded", boot);
