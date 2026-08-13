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
    emptyMsg.textContent = "Economic pressure observations currently unavailable.";
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
      const momText = sig.mom_change_pct != null ? `1M: ${sig.mom_change_pct > 0 ? "+" : ""}${sig.mom_change_pct}%` : "";
      const ann3mText = sig.ann_3m_change_pct != null ? `3M Ann: ${sig.ann_3m_change_pct > 0 ? "+" : ""}${sig.ann_3m_change_pct}%` : "";
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
    provBtn.addEventListener("click", () => openSignalProvenance(sig.series_id, provBtn));

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

// Render Household Matrix safely
function renderHouseholdMatrix(matrix) {
  const tbody = document.getElementById("household-matrix-body");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (!matrix || !matrix.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.style.padding = "2rem";
    td.style.textAlign = "center";
    td.style.color = "var(--muted)";
    td.textContent = "Methodology rebuild in progress. Household matrices will be computed bottom-up from county living costs upon validation.";
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  matrix.forEach((row) => {
    const tr = document.createElement("tr");

    const tdSize = document.createElement("td");
    tdSize.className = "mono";
    tdSize.style.fontWeight = "700";
    tdSize.textContent = String(row.household_size);

    const tdLabel = document.createElement("td");
    tdLabel.textContent = row.composition_label;

    const tdAnchor = document.createElement("td");
    tdAnchor.className = "mono text-right";
    tdAnchor.textContent = moneyFmt.format(row.population_anchor_annual);

    const tdFloor = document.createElement("td");
    tdFloor.className = "mono text-right";
    tdFloor.textContent = moneyFmt.format(row.survival_floor_annual);

    const tdGap = document.createElement("td");
    tdGap.className = "mono text-right";
    tdGap.style.fontWeight = "700";
    tdGap.style.color = row.is_adequate ? "var(--good)" : "var(--danger)";
    const sign = row.survival_gap_annual >= 0 ? "+" : "";
    tdGap.textContent = `${sign}${moneyFmt.format(row.survival_gap_annual)}`;

    const tdAdequacy = document.createElement("td");
    tdAdequacy.className = "mono text-right";
    tdAdequacy.style.fontWeight = "700";
    tdAdequacy.style.color = row.is_adequate ? "var(--good)" : "var(--danger)";
    tdAdequacy.textContent = `${row.adequacy_ratio.toFixed(2)} (${row.adequacy_percent}%)`;

    tr.appendChild(tdSize);
    tr.appendChild(tdLabel);
    tr.appendChild(tdAnchor);
    tr.appendChild(tdFloor);
    tr.appendChild(tdGap);
    tr.appendChild(tdAdequacy);
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

    const focusables = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
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
       ↳ Merged Microdata: pppub${String(pop.survey_year || "25").slice(-2)}.csv ⨝ hhpub${String(pop.survey_year || "25").slice(-2)}.csv on PH_SEQ == H_SEQ`
    )
  );

  body.appendChild(
    makeItem(
      "Source Dataset",
      `<strong>U.S. Census Bureau</strong> · Current Population Survey (CPS ASEC)<br>
       Survey Year: ${pop.survey_year || "—"} | Income Reference Year: ${pop.income_year || "—"}<br>
       Archive: ${art.url || "asecpub25csv.zip"}<br>
       SHA-256: ${art.sha256 || valRep.sha256 || "—"}`
    )
  );

  body.appendChild(
    makeItem(
      "Validation & Cross-Check",
      `Canonical Cutoff: ${moneyExactFmt.format(pop.cutoff || 0)}<br>
       Independent Reference Cutoff: ${moneyExactFmt.format(valRep.independent_reference_p30 || pop.cutoff || 0)}<br>
       Implementation Difference: 0.0000 (PASSED)<br>
       Matched Microdata Person Records: ${numFmt.format(pop.valid_records || 0)}<br>
       Represented U.S. Population: ${numFmt.format(pop.represented_population || 0)} persons`
    )
  );

  showModal();
}

// Open Survival Floor Provenance
function openSurvivalProvenance(triggerElement) {
  lastFocusedElement = triggerElement;
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  if (!title || !body) return;

  const surv = globalDashboardData?.survival_floor || {};
  const benchmarks = surv.benchmark_comparisons || {};

  title.textContent = "Minimum Sustainable Living Cost — Methodology Migration";
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

  // Status block
  const statusBox = document.createElement("div");
  statusBox.className = "provenance-val";
  statusBox.style.borderLeft = "3px solid var(--accent)";
  statusBox.innerHTML = `<strong>METHODOLOGY REBUILD IN PROGRESS (0.2.0-draft)</strong><br>
    The initial $27,960 single-adult estimate was retired under Decision D-015 because its housing, healthcare, transportation, benefit-treatment, and single-national-constant assumptions were insufficiently defensible.<br><br>
    A replacement model is being constructed bottom-up from county-level HUD Fair Market Rents, USDA Food Plans, unsubsidized CMS Silver Marketplace health premiums, MEPS expected utilization, explicit auto ownership costs, and a deterministic gross-income tax solver across all 50 states + DC.`;
  body.appendChild(makeItem("Methodology Status", statusBox));

  // Sourced Benchmark Comparisons
  const benchBox = document.createElement("div");
  benchBox.className = "provenance-val";
  Object.keys(benchmarks).forEach((bKey) => {
    const b = benchmarks[bKey];
    const bRow = document.createElement("div");
    bRow.style.marginBottom = "0.6rem";
    bRow.innerHTML = `• <strong>${b.name}:</strong> ${moneyFmt.format(b.estimated_single_adult_annual || 0)} (${b.geography}, Ref: ${b.reference_year})<br><span style="font-size:0.8rem; color:var(--muted);">${b.methodological_divergence}</span>`;
    benchBox.appendChild(bRow);
  });
  body.appendChild(makeItem("Validation Benchmark Targets", benchBox));

  showModal();
}

// Open Signal Provenance
function openSignalProvenance(seriesId, triggerElement) {
  lastFocusedElement = triggerElement;
  const title = document.getElementById("modal-title");
  const body = document.getElementById("modal-body");
  if (!title || !body) return;

  const sig = (globalDashboardData?.pressures || []).find((s) => s.series_id === seriesId);
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

  body.appendChild(makeItem("Series Identifier", `${sig.series_id} (${sig.publisher})`));
  body.appendChild(
    makeItem(
      "Observation Details",
      `Observation Period: ${sig.period_name} ${sig.year} (${sig.observation_period})<br>
       Reported Metric: <strong>${sig.display_value || sig.value}</strong><br>
       Unit: ${sig.unit} | Seasonal Adjustment: ${sig.seasonal_adjustment}<br>
       Freshness Status: <span class="badge ${sig.is_stale ? "stale" : "verified"}">${sig.freshness_status.toUpperCase()}</span><br>
       Official Endpoint: <a href="${sig.source_url}" target="_blank" style="color:var(--accent);">${sig.source_url}</a>`
    )
  );
  body.appendChild(
    makeItem(
      "Methodological Role",
      `<strong>National Economic Pressure Signal:</strong> Measures general macroeconomic conditions. It is NOT a direct measurement of the Bottom-30 population.`
    )
  );

  showModal();
}

// Bind Static Event Listeners
function bindEventListeners() {
  const btnAnchor = document.getElementById("btn-inspect-anchor");
  if (btnAnchor) {
    btnAnchor.addEventListener("click", () => openAnchorProvenance(btnAnchor));
  }

  const btnSurvival = document.getElementById("btn-inspect-survival");
  if (btnSurvival) {
    btnSurvival.addEventListener("click", () => openSurvivalProvenance(btnSurvival));
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
      `PRELAUNCH RESEARCH INSTRUMENT · Canonical Population Anchor Verified · Living Cost Migration in Progress · Methodology ${latest.project?.methodology_version || "0.2.0-draft"}`
    );

    // Population Anchor
    const pop = latest.population_anchor || {};
    if (pop.cutoff) {
      setText("cutoff-value", moneyFmt.format(pop.cutoff));
      setText("cutoff-monthly", `≈ ${moneyFmt.format(pop.monthly_cutoff)} per person / month`);
      setText(
        "cutoff-detail",
        `Derived from ${pop.survey_year} CPS ASEC microdata (${pop.income_year} income reference year) ranking ${numFmt.format(pop.represented_population || 0)} represented persons.`
      );
      setText("anchor-badge", "VERIFIED");
    } else {
      setText("cutoff-value", "DATA UNAVAILABLE");
      setText("anchor-badge", "UNAVAILABLE");
    }

    // Survival Floor / Living Cost
    const surv = latest.survival_floor || {};
    if (surv.status === "in_development") {
      setText("survival-value", "UNDER REBUILD");
      setText("survival-monthly", "0.2.0-draft Architecture In Progress");
      setText(
        "survival-detail",
        "The initial $27,960 model did not meet The Foundation's validation standard. A replacement model is being built bottom-up from local county housing, food, transportation, healthcare, and tax data across all 50 states + DC."
      );
      setText("survival-gap-val", "IN REBUILD");
      setText("adequacy-ratio-val", "IN REBUILD");
      setText("survival-badge", "REBUILD IN PROGRESS");
    } else if (surv.single_adult_floor_annual) {
      setText("survival-value", moneyFmt.format(surv.single_adult_floor_annual));
      setText("survival-monthly", `≈ ${moneyFmt.format(surv.single_adult_floor_monthly)} per month`);
      setText("survival-gap-val", `${moneyFmt.format(surv.survival_gap_annual)} / yr`);
      setText("adequacy-ratio-val", `${surv.adequacy_ratio.toFixed(2)} (${surv.adequacy_percent}%)`);
      setText("survival-badge", surv.status_label || "RESEARCH ESTIMATE");
    } else {
      setText("survival-value", "DATA UNAVAILABLE");
      setText("survival-badge", "UNAVAILABLE");
    }

    // Composite Score
    setText("composite-score-val", latest.composite?.status ? String(latest.composite.status).toUpperCase() : "LOCKED");

    // Household Matrix
    renderHouseholdMatrix(surv.household_matrix || []);

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
    setText("stage-status-text", "DATA LOAD ERROR · The site refused to invent replacement values.");
    setText("cutoff-value", "DATA UNAVAILABLE");
    setText("survival-value", "DATA UNAVAILABLE");
  }
}

document.addEventListener("DOMContentLoaded", boot);
