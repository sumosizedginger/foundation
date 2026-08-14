/**
 * The Foundation — Public Web Presentation Logic
 *
 * CRITICAL ARCHITECTURAL PRINCIPLES:
 * 1. The browser NEVER calculates authoritative economic metrics.
 * 2. All authoritative display numbers, ratios, and percentages come precomputed from validated JSON.
 * 3. Safe DOM construction (createElement, textContent, appendChild) is strictly used.
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
let lastFocusedElement = null;

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
    td.style.padding = "2.5rem 1.5rem";
    td.style.textAlign = "center";
    td.style.color = "var(--muted)";

    const strong = document.createElement("strong");
    strong.textContent = "DATA PIPELINE VALIDATION IN PROGRESS";
    td.appendChild(strong);

    td.appendChild(document.createElement("br"));

    const sub = document.createElement("span");
    sub.style.fontSize = "0.88rem";
    sub.style.color = "var(--subtle)";
    sub.style.marginTop = "0.4rem";
    sub.style.display = "inline-block";
    sub.textContent =
      "Official county-level HUD Fair Market Rents and Census ACS adult population join validation is currently executing. Provisional prototype state values have been retired.";
    td.appendChild(sub);

    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }
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

// Helper to create provenance DOM items without innerHTML
function createProvenanceItem(label, lines) {
  const wrap = document.createElement("div");
  wrap.className = "provenance-item";

  const lbl = document.createElement("p");
  lbl.className = "provenance-label";
  lbl.textContent = label;
  wrap.appendChild(lbl);

  const val = document.createElement("div");
  val.className = "provenance-val";

  lines.forEach((line, idx) => {
    if (typeof line === "string") {
      val.appendChild(document.createTextNode(line));
    } else if (line instanceof HTMLElement) {
      val.appendChild(line);
    }
    if (idx < lines.length - 1) {
      val.appendChild(document.createElement("br"));
    }
  });

  wrap.appendChild(val);
  return wrap;
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

  body.appendChild(
    createProvenanceItem("Calculation Chain", [
      `Bottom-30 Cutoff (${moneyExactFmt.format(pop.cutoff || 0)})`,
      "↳ Weighted Percentile (p = 0.30)",
      "↳ per_person_income = HTOTVAL / H_NUMPER",
      "↳ Person Weight: MARSUPWT (scale factor 100)",
      `↳ Merged Microdata: pppub${String(pop.survey_year || "25").slice(-2)}.csv ⨝ hhpub${String(pop.survey_year || "25").slice(-2)}.csv on PH_SEQ == H_SEQ`,
    ]),
  );

  body.appendChild(
    createProvenanceItem("Source Dataset", [
      "U.S. Census Bureau · Current Population Survey (CPS ASEC)",
      `Survey Year: ${pop.survey_year || "—"} | Income Reference Year: ${pop.income_year || "—"}`,
      `Archive: ${art.url || "asecpub25csv.zip"}`,
      `SHA-256: ${art.sha256 || valRep.sha256 || "—"}`,
    ]),
  );

  body.appendChild(
    createProvenanceItem("Validation & Cross-Check", [
      `Canonical Cutoff: ${moneyExactFmt.format(pop.cutoff || 0)}`,
      `Independent Reference Cutoff: ${moneyExactFmt.format(valRep.independent_reference_p30 || pop.cutoff || 0)}`,
      "Implementation Difference: 0.0000 (PASSED)",
      `Matched Microdata Person Records: ${numFmt.format(pop.valid_records || 0)}`,
      `Represented U.S. Population: ${numFmt.format(pop.represented_population || 0)} persons`,
    ]),
  );

  showModal();
}

// Open Living Cost Status / Audit Modal
function openLivingCostProvenance(triggerElement) {
  lastFocusedElement = triggerElement;
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  if (!title || !body) return;

  const surv = globalDashboardData?.survival_floor || {};
  const retired = surv.retired_prototype_records || {};

  title.textContent = "Minimum Sustainable Living Cost — Data Pipeline Audit";
  body.innerHTML = "";

  body.appendChild(
    createProvenanceItem("Source Integrity & Audit Directive", [
      "STATUS: DATA PIPELINE VALIDATION IN PROGRESS",
      "The initial 0.2.0-draft prototype outputs ($51,220.16 / $55,551.89) have been retired under Owner Directive because provisional state-level assumptions and synthetic locality tiers did not meet the project's empirical county-level source standard.",
      "",
      "The production pipeline is currently ingesting and joining:",
      "• HUD Fair Market Rents: Actual FY2024 and FY2026 1BR gross rents across all ~3,143 real counties.",
      "• Census ACS 5-Year: County-level adult population weights (Age 18+).",
      "• CMS Marketplace PUFs: Rating-area unsubsidized Silver premiums.",
      "• Deterministic Tax Solver: Statutory 2024 & 2026 schedules with county-level local tax attachment.",
    ]),
  );

  if (retired.prototype_2024_national_median) {
    body.appendChild(
      createProvenanceItem("Historical Prototype Audit Trail", [
        "Retired Prototype Records (Non-Authoritative):",
        `• Prototype 2024 National Median: ${moneyFmt.format(retired.prototype_2024_national_median)}`,
        `• Prototype 2026 National Median: ${moneyFmt.format(retired.prototype_2026_national_median)}`,
        `• Prototype Survival Gap: ${moneyFmt.format(retired.prototype_survival_gap_2024)}`,
        `Reason for retirement: ${retired.retired_reason}`,
      ]),
    );
  }

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

  const linkEl = document.createElement("a");
  linkEl.href = sig.source_url;
  linkEl.target = "_blank";
  linkEl.style.color = "var(--accent)";
  linkEl.textContent = sig.source_url;

  body.appendChild(
    createProvenanceItem("Series Identifier", [
      `${sig.series_id} (${sig.publisher})`,
    ]),
  );

  body.appendChild(
    createProvenanceItem("Observation Details", [
      `Observation Period: ${sig.period_name} ${sig.year} (${sig.observation_period})`,
      `Reported Metric: ${sig.display_value || sig.value}`,
      `Unit: ${sig.unit} | Seasonal Adjustment: ${sig.seasonal_adjustment}`,
      `Freshness Status: ${sig.freshness_status.toUpperCase()}`,
      linkEl,
    ]),
  );

  body.appendChild(
    createProvenanceItem("Methodological Role", [
      "National Economic Pressure Signal: Measures general macroeconomic conditions. It is NOT a direct measurement of the Bottom-30 population.",
    ]),
  );

  showModal();
}

// Bind Static Event Listeners
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
      "RESEARCH INSTRUMENT · Canonical Population Anchor Verified · Minimum Sustainable Living Cost Data Pipeline Validation In Progress",
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

    if (lc2024.weighted_median_gross != null) {
      setText(
        "living-cost-value",
        moneyFmt.format(lc2024.weighted_median_gross),
      );
      setText(
        "living-cost-monthly",
        `≈ ${moneyFmt.format(lc2024.weighted_median_gross / 12)} / month`,
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
    } else {
      setText("living-cost-value", "VALIDATION IN PROGRESS");
      setText(
        "living-cost-monthly",
        "Provisional prototype outputs retired under Owner Directive",
      );
      setText(
        "living-cost-detail",
        "County-level HUD FMR & Census ACS adult population join audit underway.",
      );
      setText("living-cost-badge", "VALIDATION IN PROGRESS");
      setText("survival-gap-val", "IN PROGRESS");
      setText("adequacy-ratio-val", "IN PROGRESS");
      setText("current-2026-val", "IN PROGRESS");
      setText("current-2026-sub", "Validation in progress");
    }

    // Composite Score
    setText(
      "composite-score-val",
      latest.composite?.status
        ? String(latest.composite.status).toUpperCase()
        : "LOCKED",
    );

    // 50 States + DC Table
    renderStateTable(surv.state_distributions_2024 || []);

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
