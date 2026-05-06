const dashboardState = {
    config: null,
    activeWorkspace: "bond-workspace",
    loaded: {
        "bond-workspace": false,
        "curve-workspace": false,
        "portfolio-workspace": false,
    },
    timers: {
        bond: null,
        curve: null,
        portfolio: null,
    },
};

const curveTenorOptions = ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "30Y"];
const currencyFormatter = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
});
const numberFormatter = new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 6,
});
const percentFormatter = new Intl.NumberFormat("en-US", {
    style: "percent",
    maximumFractionDigits: 3,
});

document.addEventListener("DOMContentLoaded", async () => {
    try {
        bindWorkspaceNavigation();
        closeDetailPanelsOnMobile();
        dashboardState.config = await fetchJson("/dashboard/config");
        populateSharedOptions();
        renderAssumptions();
        bindSampleButtons();
        bindRowActions();
        bindUploadAndExport();
        bindSessionActions();
        bindLiveInputs();
        hydrateFormsFromSamples();
        restoreSessionFromStorageOrHash();
        await ensureActiveWorkspaceLoaded();
    } catch (error) {
        handleDashboardError(error);
    }
});

function bindWorkspaceNavigation() {
    const defaultWorkspace = workspaceFromPath(window.location.pathname);
    for (const trigger of document.querySelectorAll("[data-target]")) {
        const tagName = trigger.tagName.toLowerCase();
        if (tagName === "a") {
            const targetId = trigger.dataset.target;
            const isActive = targetId === defaultWorkspace;
            trigger.classList.toggle("is-primary", isActive);
            if (isActive) {
                trigger.setAttribute("aria-current", "page");
            } else {
                trigger.removeAttribute("aria-current");
            }
            continue;
        }
        trigger.addEventListener("click", safeRun((event) => {
            event.preventDefault();
            event.stopPropagation();
            return activateWorkspace(trigger.dataset.target);
        }));
    }
    activateWorkspace(defaultWorkspace);
}

function activateWorkspace(targetId) {
    const target = document.getElementById(targetId);
    if (!target) {
        throw new Error(`Unknown workspace: ${targetId}`);
    }
    for (const section of document.querySelectorAll(".workspace")) {
        const isActive = section.id === targetId;
        section.classList.toggle("is-active", isActive);
        section.hidden = !isActive;
        section.setAttribute("aria-hidden", String(!isActive));
        section.style.display = isActive ? "block" : "none";
    }
    dashboardState.activeWorkspace = targetId;
    for (const trigger of document.querySelectorAll(".nav-link")) {
        const isActive = trigger.dataset.target === targetId;
        trigger.classList.toggle("is-primary", isActive);
        if (isActive) {
            trigger.setAttribute("aria-current", "page");
        } else {
            trigger.removeAttribute("aria-current");
        }
    }
    target.scrollIntoView({ behavior: "smooth", block: "start" });
}

function workspaceFromPath(pathname) {
    const pageParam = new URLSearchParams(window.location.search).get("page");
    if (pageParam === "curve") {
        return "curve-workspace";
    }
    if (pageParam === "portfolio") {
        return "portfolio-workspace";
    }
    if (pageParam === "bond") {
        return "bond-workspace";
    }
    const normalized = pathname.replace(/\/+$/, "") || "/";
    if (normalized === "/curve") {
        return "curve-workspace";
    }
    if (normalized === "/portfolio") {
        return "portfolio-workspace";
    }
    return "bond-workspace";
}

function closeDetailPanelsOnMobile() {
    if (window.matchMedia("(max-width: 720px)").matches) {
        for (const panel of document.querySelectorAll(".detail-panel")) {
            panel.open = false;
        }
    }
}

function populateSharedOptions() {
    const { frequency_options: frequencies, day_count_options: dayCounts } = dashboardState.config;
    for (const select of document.querySelectorAll('select[name="frequency"], #compare-frequency, #hedge-frequency')) {
        select.innerHTML = frequencies.map((value) => `<option value="${value}">${value}</option>`).join("");
    }
    for (const select of document.querySelectorAll('select[name="day_count"], #compare-day-count, #hedge-day-count')) {
        select.innerHTML = dayCounts.map((value) => `<option value="${value}">${value}</option>`).join("");
    }
}

function renderAssumptions() {
    const list = document.getElementById("assumptions-list");
    list.innerHTML = dashboardState.config.assumptions.map((assumption) => `<li>${assumption}</li>`).join("");
}

function bindSampleButtons() {
    document.getElementById("bond-sample").addEventListener("click", safeRun(() => {
        fillBondForm(dashboardState.config.sample_bond_request);
        return requestBondWorkspace();
    }));
    document.getElementById("curve-sample").addEventListener("click", safeRun(() => {
        fillCurveForm(dashboardState.config.sample_curve_request);
        return requestCurveWorkspace();
    }));
    document.getElementById("portfolio-sample").addEventListener("click", safeRun(() => {
        fillPortfolioForm(dashboardState.config.sample_portfolio_request);
        return requestPortfolioWorkspace();
    }));
}

function bindRowActions() {
    document.getElementById("curve-add-row").addEventListener("click", safeRun(() => {
        appendCurveRow();
        return requestCurveWorkspace();
    }));
    document.getElementById("portfolio-add-row").addEventListener("click", safeRun(() => {
        appendPortfolioRow();
        return requestPortfolioWorkspace();
    }));
    document.getElementById("compare-enable").addEventListener("change", safeRun((event) => {
        document.getElementById("compare-grid").classList.toggle("is-enabled", event.target.checked);
        return requestBondWorkspace();
    }));
}

function bindUploadAndExport() {
    document.getElementById("curve-upload").addEventListener("change", async (event) => {
        const rows = await parseCsvUpload(event.target.files[0]);
        if (!rows.length) {
            return;
        }
        document.getElementById("curve-rows").innerHTML = "";
        rows.forEach((row) =>
            appendCurveRow({
                type: row.type || "deposit",
                tenor: row.tenor || "1Y",
                rate: Number(row.rate || 0.05),
                settlement_days: Number(row.settlement_days || 2),
            }),
        );
        await requestCurveWorkspace();
    });
    document.getElementById("portfolio-upload").addEventListener("change", async (event) => {
        const rows = await parseCsvUpload(event.target.files[0]);
        if (!rows.length) {
            return;
        }
        document.getElementById("portfolio-rows").innerHTML = "";
        rows.forEach((row) =>
            appendPortfolioRow({
                bond_spec: {
                    face: Number(row.face || 1000),
                    coupon_rate: Number(row.coupon_rate || 0.05),
                    issue_date: row.issue_date || "2025-01-01",
                    maturity: row.maturity || "2035-01-01",
                    frequency: Number(row.frequency || 2),
                    day_count: row.day_count || "ACT/ACT",
                },
                notional: Number(row.notional || 1000000),
                direction: Number(row.direction || 1),
            }),
        );
        await requestPortfolioWorkspace();
    });
    document.getElementById("bond-export-cashflows").addEventListener("click", safeRun(() => exportTableToCsv("bond-cashflow-table", "bond_cashflows.csv")));
    document.getElementById("curve-export-nodes").addEventListener("click", safeRun(() => exportTableToCsv("curve-nodes-table", "curve_nodes.csv")));
    document.getElementById("portfolio-export-risk").addEventListener("click", safeRun(() => exportTableToCsv("portfolio-risk-table", "portfolio_risk_report.csv")));
}

function bindSessionActions() {
    document.getElementById("save-session").addEventListener("click", safeRun(() => {
        const payload = captureSessionPayload();
        localStorage.setItem("curvecraft_dashboard_session", JSON.stringify(payload));
        showToast("Session saved locally.");
    }));
    document.getElementById("share-session").addEventListener("click", safeRun(async () => {
        const payload = captureSessionPayload();
        const encoded = btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
        const link = `${window.location.origin}${window.location.pathname}#scenario=${encoded}`;
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(link);
            showToast("Share link copied.");
            return;
        }
        window.prompt("Copy this scenario link:", link);
    }));
}

function bindLiveInputs() {
    document.getElementById("bond-form").addEventListener("input", debounce(requestBondWorkspace, "bond", 300));
    document.getElementById("curve-form").addEventListener("input", debounce(requestCurveWorkspace, "curve", 300));
    document.getElementById("portfolio-form").addEventListener("input", debounce(requestPortfolioWorkspace, "portfolio", 350));
}

function hydrateFormsFromSamples() {
    fillBondForm(dashboardState.config.sample_bond_request);
    fillCurveForm(dashboardState.config.sample_curve_request);
    fillPortfolioForm(dashboardState.config.sample_portfolio_request);
}

function restoreSessionFromStorageOrHash() {
    const hash = window.location.hash;
    if (hash.startsWith("#scenario=")) {
        try {
            const encoded = hash.replace("#scenario=", "");
            const payload = JSON.parse(decodeURIComponent(escape(atob(encoded))));
            hydrateSessionPayload(payload);
            return;
        } catch (error) {
            console.warn(error);
        }
    }
    const saved = localStorage.getItem("curvecraft_dashboard_session");
    if (!saved) {
        return;
    }
    try {
        hydrateSessionPayload(JSON.parse(saved));
    } catch (error) {
        console.warn(error);
    }
}

function captureSessionPayload() {
    const bondForm = document.getElementById("bond-form");
    const curveForm = document.getElementById("curve-form");
    const portfolioForm = document.getElementById("portfolio-form");
    return {
        bondForm: Object.fromEntries(new FormData(bondForm).entries()),
        curveForm: Object.fromEntries(new FormData(curveForm).entries()),
        portfolioForm: Object.fromEntries(new FormData(portfolioForm).entries()),
        curveRows: collectCurveRows(),
        portfolioRows: collectPortfolioRows(),
    };
}

function hydrateSessionPayload(payload) {
    Object.entries(payload.bondForm || {}).forEach(([key, value]) => {
        const field = document.querySelector(`#bond-form [name="${key}"]`);
        if (field) {
            field.value = value;
        }
    });
    Object.entries(payload.curveForm || {}).forEach(([key, value]) => {
        const field = document.querySelector(`#curve-form [name="${key}"]`);
        if (field) {
            field.value = value;
        }
    });
    Object.entries(payload.portfolioForm || {}).forEach(([key, value]) => {
        const field = document.querySelector(`#portfolio-form [name="${key}"]`);
        if (field) {
            field.value = value;
        }
    });
    if (payload.curveRows?.length) {
        document.getElementById("curve-rows").innerHTML = "";
        payload.curveRows.forEach((row) => appendCurveRow(row));
    }
    if (payload.portfolioRows?.length) {
        document.getElementById("portfolio-rows").innerHTML = "";
        payload.portfolioRows.forEach((row) => appendPortfolioRow(row));
    }
    dashboardState.loaded["bond-workspace"] = false;
    dashboardState.loaded["curve-workspace"] = false;
    dashboardState.loaded["portfolio-workspace"] = false;
}

async function ensureActiveWorkspaceLoaded() {
    const workspace = dashboardState.activeWorkspace;
    if (dashboardState.loaded[workspace]) {
        return;
    }
    if (workspace === "bond-workspace") {
        await requestBondWorkspace();
    } else if (workspace === "curve-workspace") {
        await requestCurveWorkspace();
    } else if (workspace === "portfolio-workspace") {
        await requestPortfolioWorkspace();
    }
    dashboardState.loaded[workspace] = true;
}

function fillBondForm(sample) {
    const form = document.getElementById("bond-form");
    const bond = sample.bond_spec;
    form.face.value = bond.face;
    form.coupon_rate.value = bond.coupon_rate;
    form.issue_date.value = bond.issue_date;
    form.maturity.value = bond.maturity;
    form.frequency.value = bond.frequency;
    form.day_count.value = bond.day_count;
    form.yield.value = sample.yield;
    form.settlement_date.value = sample.settlement_date;
    form.yield_range_min.value = sample.yield_range_min;
    form.yield_range_max.value = sample.yield_range_max;
    form.scenario_bump_bps.value = sample.scenario_bump_bps;
    form.price_yield_points.value = sample.price_yield_points;

    document.getElementById("compare-enable").checked = false;
    document.getElementById("compare-grid").classList.remove("is-enabled");
    document.getElementById("compare-label").value = "Bond B";
    document.getElementById("compare-face").value = bond.face;
    document.getElementById("compare-coupon").value = bond.coupon_rate - 0.01;
    document.getElementById("compare-issue").value = bond.issue_date;
    document.getElementById("compare-maturity").value = "2040-01-01";
    document.getElementById("compare-frequency").value = bond.frequency;
    document.getElementById("compare-day-count").value = bond.day_count;
    document.getElementById("key-rate-bump").value = "1";
}

function fillCurveForm(sample) {
    const form = document.getElementById("curve-form");
    form.max_maturity.value = sample.max_maturity;
    form.grid_points.value = sample.grid_points;
    form.scenario_parallel_shift_bps.value = sample.scenario_parallel_shift_bps;
    const tbody = document.getElementById("curve-rows");
    tbody.innerHTML = "";
    sample.instruments.forEach((instrument) => appendCurveRow(instrument));
}

function fillPortfolioForm(sample) {
    const form = document.getElementById("portfolio-form");
    form.settlement_date.value = sample.settlement_date;
    form.scenario_parallel_shift_bps.value = sample.scenario_parallel_shift_bps;
    const tbody = document.getElementById("portfolio-rows");
    tbody.innerHTML = "";
    sample.positions.forEach((position) => appendPortfolioRow(position));

    const hedgeBond = sample.positions[0].bond_spec;
    document.getElementById("hedge-target-dv01").value = "0";
    document.getElementById("hedge-face").value = hedgeBond.face;
    document.getElementById("hedge-coupon").value = 0.06;
    document.getElementById("hedge-issue").value = hedgeBond.issue_date;
    document.getElementById("hedge-maturity").value = "2038-01-01";
    document.getElementById("hedge-frequency").value = hedgeBond.frequency;
    document.getElementById("hedge-day-count").value = hedgeBond.day_count;
}

function appendCurveRow(instrument = null) {
    const tbody = document.getElementById("curve-rows");
    const row = document.createElement("tr");
    row.innerHTML = `
        <td><select data-key="type"><option value="deposit">deposit</option><option value="swap">swap</option></select></td>
        <td><select data-key="tenor">${curveTenorOptions.map((tenor) => `<option value="${tenor}">${tenor}</option>`).join("")}</select></td>
        <td><input type="number" data-key="rate" min="-0.99" max="2" step="0.0001"></td>
        <td class="slider-cell"><input type="range" data-key="rate-slider" min="-1" max="15" step="0.01"></td>
        <td><input type="number" data-key="settlement_days" min="0" max="10" step="1"></td>
        <td><button type="button" class="remove-row" aria-label="Remove instrument">x</button></td>
    `;
    row.querySelector('[data-key="type"]').value = instrument?.type || "deposit";
    row.querySelector('[data-key="tenor"]').value = instrument?.tenor || "1Y";
    row.querySelector('[data-key="rate"]').value = instrument?.rate ?? 0.05;
    row.querySelector('[data-key="rate-slider"]').value = (instrument?.rate ?? 0.05) * 100;
    row.querySelector('[data-key="settlement_days"]').value = instrument?.settlement_days ?? 2;

    row.querySelector('[data-key="rate"]').addEventListener("input", (event) => {
        row.querySelector('[data-key="rate-slider"]').value = Number(event.target.value) * 100;
    });
    row.querySelector('[data-key="rate-slider"]').addEventListener("input", (event) => {
        row.querySelector('[data-key="rate"]').value = (Number(event.target.value) / 100).toFixed(4);
        requestCurveWorkspace();
    });
    row.addEventListener("input", debounce(requestCurveWorkspace, "curve", 250));
    row.querySelector(".remove-row").addEventListener("click", () => {
        row.remove();
        requestCurveWorkspace();
    });
    tbody.appendChild(row);
}

function appendPortfolioRow(position = null) {
    const tbody = document.getElementById("portfolio-rows");
    const row = document.createElement("tr");
    row.innerHTML = `
        <td><input type="number" data-key="face" min="0.01" step="0.01"></td>
        <td><input type="number" data-key="coupon_rate" min="0" max="1" step="0.0001"></td>
        <td><input type="date" data-key="issue_date"></td>
        <td><input type="date" data-key="maturity"></td>
        <td><select data-key="frequency">${dashboardState.config.frequency_options.map((value) => `<option value="${value}">${value}</option>`).join("")}</select></td>
        <td><select data-key="day_count">${dashboardState.config.day_count_options.map((value) => `<option value="${value}">${value}</option>`).join("")}</select></td>
        <td><input type="number" data-key="notional" min="0.01" step="0.01"></td>
        <td><select data-key="direction"><option value="1">Long</option><option value="-1">Short</option></select></td>
        <td><button type="button" class="remove-row" aria-label="Remove position">x</button></td>
    `;
    const bond = position?.bond_spec || dashboardState.config.sample_portfolio_request.positions[0].bond_spec;
    row.querySelector('[data-key="face"]').value = bond.face;
    row.querySelector('[data-key="coupon_rate"]').value = bond.coupon_rate;
    row.querySelector('[data-key="issue_date"]').value = bond.issue_date;
    row.querySelector('[data-key="maturity"]').value = bond.maturity;
    row.querySelector('[data-key="frequency"]').value = bond.frequency;
    row.querySelector('[data-key="day_count"]').value = bond.day_count;
    row.querySelector('[data-key="notional"]').value = position?.notional ?? 1000000;
    row.querySelector('[data-key="direction"]').value = position?.direction ?? 1;

    row.addEventListener("input", debounce(requestPortfolioWorkspace, "portfolio", 350));
    row.querySelector(".remove-row").addEventListener("click", () => {
        row.remove();
        requestPortfolioWorkspace();
    });
    tbody.appendChild(row);
}

async function requestBondWorkspace() {
    const form = document.getElementById("bond-form");
    if (!validateBondForm(form)) {
        return;
    }
    const bondPayload = {
        bond_spec: extractBondSpecFromForm(form),
        yield: Number(form.yield.value),
        settlement_date: form.settlement_date.value,
        scenario_bump_bps: Number(form.scenario_bump_bps.value),
        yield_range_min: Number(form.yield_range_min.value),
        yield_range_max: Number(form.yield_range_max.value),
        price_yield_points: Number(form.price_yield_points.value),
    };
    const curveRows = collectCurveRows();
    const bondResponse = await fetchJson("/dashboard/bond", bondPayload);

    if (!curveRows.length) {
        renderBondDashboard(bondResponse, { metrics: [] }, { key_rate_dv01: {}, bump_bps: 0 });
        setHint("curve-table-hint", "Add curve instruments to enable curve pricing and key-rate analytics.", true);
        return;
    }

    const curvePayload = buildCurvePricePayload(form);
    const keyRatePayload = {
        bond_spec: extractBondSpecFromForm(form),
        settlement_date: form.settlement_date.value,
        curve_instruments: curveRows,
        bump_bps: Number(document.getElementById("key-rate-bump").value),
    };
    const [curveResponse, keyRateResponse] = await Promise.all([
        fetchJson("/dashboard/bond-curve-price", curvePayload),
        fetchJson("/dashboard/key-rate", keyRatePayload),
    ]);
    renderBondDashboard(bondResponse, curveResponse, keyRateResponse);
    dashboardState.loaded["bond-workspace"] = true;
}

async function requestCurveWorkspace() {
    const form = document.getElementById("curve-form");
    const instruments = collectCurveRows();
    if (!instruments.length) {
        setHint("curve-table-hint", "Add at least one market instrument to build the curve.", true);
        return;
    }
    setHint("curve-table-hint", "Deposit and swap rows feed the live curve bootstrap and scenario overlays.", false);
    const payload = {
        instruments,
        max_maturity: Number(form.max_maturity.value),
        grid_points: Number(form.grid_points.value),
        scenario_parallel_shift_bps: Number(form.scenario_parallel_shift_bps.value),
    };
    const response = await fetchJson("/dashboard/curve", payload);
    renderCurveDashboard(response);
    dashboardState.loaded["curve-workspace"] = true;
}

async function requestPortfolioWorkspace() {
    const form = document.getElementById("portfolio-form");
    const positions = collectPortfolioRows();
    if (!positions.length) {
        setHint("portfolio-table-hint", "Add at least one position to calculate portfolio risk.", true);
        return;
    }
    setHint("portfolio-table-hint", "Edit rows inline, import CSV, and use the hedge panel for DV01 neutralization.", false);
    const curveInstruments = collectCurveRows();
    const payload = {
        positions,
        settlement_date: form.settlement_date.value,
        scenario_parallel_shift_bps: Number(form.scenario_parallel_shift_bps.value),
        curve_instruments: curveInstruments.length ? curveInstruments : null,
    };
    const hedgePayload = {
        positions,
        settlement_date: form.settlement_date.value,
        target_dv01: Number(document.getElementById("hedge-target-dv01").value),
        hedge_bond_spec: {
            face: Number(document.getElementById("hedge-face").value),
            coupon_rate: Number(document.getElementById("hedge-coupon").value),
            issue_date: document.getElementById("hedge-issue").value,
            maturity: document.getElementById("hedge-maturity").value,
            frequency: Number(document.getElementById("hedge-frequency").value),
            day_count: document.getElementById("hedge-day-count").value,
        },
        curve_instruments: curveInstruments.length ? curveInstruments : null,
    };
    const [response, hedgeResponse] = await Promise.all([
        fetchJson("/dashboard/portfolio", payload),
        fetchJson("/dashboard/hedge", hedgePayload),
    ]);
    renderPortfolioDashboard(response, hedgeResponse);
    dashboardState.loaded["portfolio-workspace"] = true;
}

function extractBondSpecFromForm(form) {
    return {
        face: Number(form.face.value),
        coupon_rate: Number(form.coupon_rate.value),
        issue_date: form.issue_date.value,
        maturity: form.maturity.value,
        frequency: Number(form.frequency.value),
        day_count: form.day_count.value,
    };
}

function buildCurvePricePayload(form) {
    const payload = {
        bond_spec: extractBondSpecFromForm(form),
        settlement_date: form.settlement_date.value,
        curve_instruments: collectCurveRows(),
    };
    if (document.getElementById("compare-enable").checked) {
        payload.compare_label = document.getElementById("compare-label").value || "Bond B";
        payload.compare_bond_spec = {
            face: Number(document.getElementById("compare-face").value),
            coupon_rate: Number(document.getElementById("compare-coupon").value),
            issue_date: document.getElementById("compare-issue").value,
            maturity: document.getElementById("compare-maturity").value,
            frequency: Number(document.getElementById("compare-frequency").value),
            day_count: document.getElementById("compare-day-count").value,
        };
    }
    return payload;
}

function collectCurveRows() {
    return Array.from(document.querySelectorAll("#curve-rows tr"))
        .map((row) => ({
            type: row.querySelector('[data-key="type"]').value,
            tenor: row.querySelector('[data-key="tenor"]').value,
            rate: Number(row.querySelector('[data-key="rate"]').value),
            settlement_days: Number(row.querySelector('[data-key="settlement_days"]').value),
        }))
        .filter((row) => Number.isFinite(row.rate));
}

function collectPortfolioRows() {
    return Array.from(document.querySelectorAll("#portfolio-rows tr"))
        .map((row) => ({
            bond_spec: {
                face: Number(row.querySelector('[data-key="face"]').value),
                coupon_rate: Number(row.querySelector('[data-key="coupon_rate"]').value),
                issue_date: row.querySelector('[data-key="issue_date"]').value,
                maturity: row.querySelector('[data-key="maturity"]').value,
                frequency: Number(row.querySelector('[data-key="frequency"]').value),
                day_count: row.querySelector('[data-key="day_count"]').value,
            },
            notional: Number(row.querySelector('[data-key="notional"]').value),
            direction: Number(row.querySelector('[data-key="direction"]').value),
        }))
        .filter((position) => Number.isFinite(position.notional));
}

function validateBondForm(form) {
    let valid = true;
    valid = validateDateOrder(form.issue_date, form.maturity, "Maturity must be later than issue date.") && valid;
    valid = validateDateOrder(form.issue_date, form.settlement_date, "Settlement should be on or after issue date.", false) && valid;
    valid = validateBounds(form.yield_range_min, form.yield_range_max, "Yield range max must exceed min.") && valid;
    return valid;
}

function validateDateOrder(startField, endField, message, requireEndAfterStart = true) {
    const hint = endField.parentElement.querySelector(".field-hint");
    if (!startField.value || !endField.value) {
        setFieldHint(hint, "");
        return true;
    }
    const startDate = new Date(startField.value);
    const endDate = new Date(endField.value);
    const passes = requireEndAfterStart ? endDate > startDate : endDate >= startDate;
    setFieldHint(hint, passes ? "" : message, !passes);
    return passes;
}

function validateBounds(minField, maxField, message) {
    const hint = maxField.parentElement.querySelector(".field-hint");
    const passes = Number(maxField.value) > Number(minField.value);
    setFieldHint(hint, passes ? "" : message, !passes);
    return passes;
}

function renderBondDashboard(response, curveResponse, keyRateResponse) {
    renderMetricStrip("bond-metrics", [
        metricCard("Dirty Price", currencyFormatter.format(response.dirty_price)),
        metricCard("Clean Price", currencyFormatter.format(response.clean_price)),
        metricCard("Accrued", currencyFormatter.format(response.accrued_interest)),
        metricCard("YTM", percentFormatter.format(response.ytm)),
        metricCard("DV01", numberFormatter.format(response.dv01)),
        metricCard("Duration", numberFormatter.format(response.modified)),
        metricCard("Convexity", numberFormatter.format(response.convexity)),
    ]);
    renderScenarioStrip("bond-scenario", [
        scenarioCard(`+${response.scenario.bump_bps.toFixed(0)} bps`, currencyFormatter.format(response.scenario.clean_price_up), response.scenario.delta_up),
        scenarioCard(`-${response.scenario.bump_bps.toFixed(0)} bps`, currencyFormatter.format(response.scenario.clean_price_down), response.scenario.delta_down),
    ]);
    renderBondPriceChart(response);
    renderBondCashFlowChart(response.cash_flows);
    renderKeyRateChart(keyRateResponse);

    document.getElementById("bond-cashflow-table").innerHTML = response.cash_flows
        .map((row) => `<tr><td>${row.date}</td><td>${currencyFormatter.format(row.coupon)}</td><td>${currencyFormatter.format(row.principal)}</td><td>${currencyFormatter.format(row.total_cf)}</td></tr>`)
        .join("");
    document.getElementById("bond-compare-table").innerHTML = (curveResponse.metrics || [])
        .map((metric) => `<tr><td>${metric.label}</td><td>${currencyFormatter.format(metric.dirty_price_from_curve)}</td><td>${currencyFormatter.format(metric.clean_price_from_curve)}</td><td>${numberFormatter.format(metric.effective_duration)}</td><td>${numberFormatter.format(metric.effective_convexity)}</td><td>${numberFormatter.format(metric.dv01_from_curve)}</td></tr>`)
        .join("");
    if (!curveResponse.metrics?.length) {
        document.getElementById("bond-compare-table").innerHTML =
            '<tr><td colspan="6">Provide curve instruments in the Curve workspace to populate curve-based compare analytics.</td></tr>';
    }
}

function renderCurveDashboard(response) {
    renderMetricStrip("curve-metrics", [
        metricCard("Curve Nodes", String(response.nodes.length)),
        metricCard("Front Spot", percentFormatter.format(response.nodes[1]?.spot_rate ?? 0)),
        metricCard("Long Spot", percentFormatter.format(response.nodes[response.nodes.length - 1]?.spot_rate ?? 0)),
        metricCard("Shift Overlay", `${response.scenario_parallel_shift_bps.toFixed(0)} bps`),
    ]);
    renderCurveChart(response);
    document.getElementById("curve-nodes-table").innerHTML = response.nodes
        .map((row) => `<tr><td>${numberFormatter.format(row.tenor_years)}</td><td>${numberFormatter.format(row.discount_factor)}</td><td>${percentFormatter.format(row.spot_rate)}</td></tr>`)
        .join("");
}

function renderPortfolioDashboard(response, hedgeResponse) {
    renderMetricStrip("portfolio-metrics", [
        metricCard("Total MV", currencyFormatter.format(response.total_mv)),
        metricCard("Total DV01", numberFormatter.format(response.total_dv01)),
        metricCard("Weighted Duration", numberFormatter.format(response.weighted_duration)),
        metricCard("Curve Source", response.curve_source),
    ]);
    renderScenarioStrip("portfolio-scenario", [
        scenarioCard(`${response.scenario_parallel_shift_bps.toFixed(0)} bps Shift`, currencyFormatter.format(response.shifted_total_mv), response.scenario_pnl),
    ]);
    renderPortfolioChart(response.key_rate_profile);
    renderKeyRateTable(response.key_rate_profile);

    document.getElementById("portfolio-risk-table").innerHTML = response.risk_report
        .map((row) => `<tr><td>${row["CUSIP/name"] ?? row.cusip_name}</td><td>${currencyFormatter.format(row.notional)}</td><td>${currencyFormatter.format(row.MV ?? row.mv)}</td><td>${numberFormatter.format(row.DV01 ?? row.dv01)}</td><td>${numberFormatter.format(row.duration)}</td><td>${numberFormatter.format(row.convexity)}</td></tr>`)
        .join("");
    document.getElementById("portfolio-scenario-table").innerHTML = Object.entries(response.scenario_results)
        .map(([scenario, pnl]) => `<tr><td>${scenario}</td><td>${currencyFormatter.format(pnl)}</td></tr>`)
        .join("");
    document.getElementById("portfolio-hedge-table").innerHTML = `<tr><td>${numberFormatter.format(hedgeResponse.current_portfolio_dv01)}</td><td>${numberFormatter.format(hedgeResponse.target_dv01)}</td><td>${numberFormatter.format(hedgeResponse.hedge_bond_unit_dv01)}</td><td>${currencyFormatter.format(hedgeResponse.required_hedge_notional)}</td><td>${numberFormatter.format(hedgeResponse.projected_post_hedge_dv01)}</td></tr>`;
}

function renderMetricStrip(containerId, cards) {
    document.getElementById(containerId).innerHTML = cards.join("");
}

function renderScenarioStrip(containerId, cards) {
    document.getElementById(containerId).innerHTML = cards.join("");
}

function metricCard(label, value) {
    return `<article class="metric-card"><h3>${label}</h3><p>${value}</p></article>`;
}

function scenarioCard(label, value, delta) {
    const deltaClass = delta >= 0 ? "delta-positive" : "delta-negative";
    const deltaLabel = `${delta >= 0 ? "+" : ""}${currencyFormatter.format(delta)}`;
    return `<article class="scenario-card"><h3>${label}</h3><p>${value}</p><small class="${deltaClass}">d ${deltaLabel}</small></article>`;
}

function renderBondPriceChart(response) {
    Plotly.react(
        "bond-price-chart",
        [
            {
                x: response.price_yield_yields.map((value) => value * 100),
                y: response.price_yield_clean_prices,
                mode: "lines",
                name: "Clean Price",
                line: { color: "#f3b861", width: 3 },
            },
        ],
        chartLayout("Price-Yield Relationship", "Yield (%)", "Clean Price"),
        chartConfig(),
    );
}

function renderKeyRateChart(response) {
    const entries = Object.entries(response.key_rate_dv01);
    if (!entries.length) {
        Plotly.react(
            "bond-key-rate-chart",
            [{ x: [], y: [], type: "bar", name: "Key Rate DV01" }],
            chartLayout("Key Rate DV01", "Tenor", "DV01"),
            chartConfig(),
        );
        return;
    }
    Plotly.react(
        "bond-key-rate-chart",
        [
            {
                x: entries.map(([tenor]) => tenor),
                y: entries.map(([, value]) => value),
                type: "bar",
                name: "Key Rate DV01",
                marker: { color: "#73cdff" },
            },
        ],
        chartLayout(`Key Rate DV01 (${response.bump_bps.toFixed(1)} bps)`, "Tenor", "DV01"),
        chartConfig(),
    );
}

function renderBondCashFlowChart(cashFlows) {
    Plotly.react(
        "bond-cashflow-chart",
        [
            { x: cashFlows.map((row) => row.date), y: cashFlows.map((row) => row.coupon), type: "bar", name: "Coupon", marker: { color: "#f3b861" } },
            { x: cashFlows.map((row) => row.date), y: cashFlows.map((row) => row.principal), type: "bar", name: "Principal", marker: { color: "#73cdff" } },
        ],
        { ...chartLayout("Cash Flow Ladder", "Date", "Cash Flow"), barmode: "stack" },
        chartConfig(),
    );
}

function renderCurveChart(response) {
    const traces = [
        { x: response.curve_maturities, y: response.spot_rates.map((value) => value * 100), mode: "lines", name: "Spot Rate", line: { color: "#f3b861", width: 3 } },
        { x: response.curve_maturities, y: response.forward_rates.map((value) => value * 100), mode: "lines", name: "Forward Rate", line: { color: "#73cdff", width: 2 } },
        { x: response.par_maturities, y: response.par_rates.map((value) => value * 100), mode: "lines", name: "Par Rate", line: { color: "#79d3a6", width: 2 } },
        { x: response.curve_maturities, y: response.shifted_spot_rates.map((value) => value * 100), mode: "lines", name: `Parallel (${response.scenario_parallel_shift_bps.toFixed(0)} bps)`, line: { color: "#ff8f8f", dash: "dot", width: 2 } },
    ];
    Object.entries(response.scenario_rates).forEach(([name, rates]) => {
        traces.push({
            x: response.curve_maturities,
            y: rates.map((value) => value * 100),
            mode: "lines",
            name,
            line: { width: 1.4, dash: "dash" },
        });
    });
    Plotly.react("curve-chart", traces, chartLayout("Yield Curve and Scenario Overlays", "Maturity (Years)", "Rate (%)", { denseLegend: true }), chartConfig());
}

function renderPortfolioChart(rows) {
    const positionRows = rows.filter((row) => row.name !== "Total");
    if (!positionRows.length) {
        return;
    }
    const tenors = Object.keys(positionRows[0].buckets);
    const traces = positionRows.map((row, index) => ({
        x: tenors,
        y: tenors.map((tenor) => row.buckets[tenor]),
        type: "bar",
        name: row.name,
        marker: { color: ["#f3b861", "#73cdff", "#79d3a6", "#ff8f8f", "#b2a4ff"][index % 5] },
    }));
    Plotly.react("portfolio-chart", traces, { ...chartLayout("Portfolio Key Rate DV01", "Tenor Bucket", "DV01 Contribution"), barmode: "stack" }, chartConfig());
}

function renderKeyRateTable(rows) {
    const head = document.getElementById("portfolio-key-rate-head");
    const body = document.getElementById("portfolio-key-rate-table");
    if (!rows.length) {
        head.innerHTML = "";
        body.innerHTML = "";
        return;
    }
    const columns = Object.keys(rows[0].buckets);
    head.innerHTML = `<tr><th>Name</th>${columns.map((column) => `<th>${column}</th>`).join("")}</tr>`;
    body.innerHTML = rows
        .map((row) => `<tr><td>${row.name}</td>${columns.map((column) => `<td>${numberFormatter.format(row.buckets[column])}</td>`).join("")}</tr>`)
        .join("");
}

function chartLayout(title, xaxisTitle, yaxisTitle, options = {}) {
    const mobile = window.matchMedia("(max-width: 760px)").matches;
    const denseLegend = options.denseLegend === true;
    return {
        title: {
            text: title,
            x: 0,
            xanchor: "left",
            y: 0.98,
            yanchor: "top",
            font: { size: mobile ? 13 : 16 },
        },
        template: "plotly_dark",
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(8, 18, 33, 0.82)",
        font: { family: '"Avenir Next", "Segoe UI", sans-serif', color: "#edf3fb", size: mobile ? 11 : 12 },
        margin: {
            t: mobile ? (denseLegend ? 92 : 74) : (denseLegend ? 86 : 64),
            r: mobile ? 16 : 20,
            b: mobile ? 44 : 48,
            l: mobile ? 44 : 58,
        },
        xaxis: {
            title: { text: xaxisTitle, standoff: mobile ? 8 : 10 },
            gridcolor: "rgba(255,255,255,0.08)",
            zerolinecolor: "rgba(255,255,255,0.08)",
            tickfont: { size: mobile ? 10 : 11 },
            automargin: true,
        },
        yaxis: {
            title: { text: yaxisTitle, standoff: mobile ? 8 : 10 },
            gridcolor: "rgba(255,255,255,0.08)",
            zerolinecolor: "rgba(255,255,255,0.08)",
            tickfont: { size: mobile ? 10 : 11 },
            automargin: true,
        },
        legend: mobile
            ? {
                orientation: "h",
                yanchor: "bottom",
                y: 1.04,
                xanchor: "left",
                x: 0,
                font: { size: 10 },
                itemwidth: 64,
                tracegroupgap: 6,
            }
            : {
                orientation: denseLegend ? "h" : "v",
                yanchor: denseLegend ? "bottom" : "top",
                y: denseLegend ? 1.04 : 0.98,
                xanchor: denseLegend ? "left" : "right",
                x: denseLegend ? 0 : 1.01,
                font: { size: denseLegend ? 11 : 12 },
                itemwidth: denseLegend ? 80 : 110,
            },
    };
}

function chartConfig() {
    return { displayModeBar: false, responsive: true };
}

function setFieldHint(hintElement, text, isError = false) {
    hintElement.textContent = text;
    hintElement.classList.toggle("is-error", Boolean(isError && text));
}

function setHint(id, text, isError) {
    const node = document.getElementById(id);
    node.textContent = text;
    node.classList.toggle("is-error", Boolean(isError));
}

function debounce(callback, timerKey, delayMs) {
    return () => {
        window.clearTimeout(dashboardState.timers[timerKey]);
        dashboardState.timers[timerKey] = window.setTimeout(() => {
            callback().catch(handleDashboardError);
        }, delayMs);
    };
}

function handleDashboardError(error) {
    console.error(error);
    showToast(error?.message || "Dashboard request failed.");
}

async function fetchJson(url, payload = null) {
    const response = await fetch(url, {
        method: payload ? "POST" : "GET",
        headers: { "Content-Type": "application/json" },
        body: payload ? JSON.stringify(payload) : null,
    });
    if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({ detail: "Request failed." }));
        throw new Error(errorPayload.detail || "Request failed.");
    }
    return response.json();
}

async function parseCsvUpload(file) {
    if (!file) {
        return [];
    }
    const text = await file.text();
    const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
    if (lines.length < 2) {
        return [];
    }
    const headers = lines[0].split(",").map((value) => value.trim());
    return lines.slice(1).map((line) => {
        const cells = line.split(",").map((value) => value.trim());
        return headers.reduce((acc, header, index) => {
            acc[header] = cells[index] ?? "";
            return acc;
        }, {});
    });
}

function exportTableToCsv(tableBodyId, filename) {
    const body = document.getElementById(tableBodyId);
    if (!body) {
        throw new Error(`Missing table body: ${tableBodyId}`);
    }
    const table = body.closest("table");
    if (!table) {
        throw new Error(`Missing table wrapper for: ${tableBodyId}`);
    }
    const rows = Array.from(table.querySelectorAll("tr"));
    const csv = rows
        .map((row) =>
            Array.from(row.querySelectorAll("th,td"))
                .map((cell) => `"${cell.textContent.replaceAll('"', '""')}"`)
                .join(","),
        )
        .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
}

function safeRun(callback) {
    return (event) => {
        Promise.resolve(callback(event)).catch(handleDashboardError);
    };
}

function showToast(message) {
    let toast = document.getElementById("dashboard-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "dashboard-toast";
        toast.style.position = "fixed";
        toast.style.right = "16px";
        toast.style.bottom = "16px";
        toast.style.zIndex = "9999";
        toast.style.padding = "10px 12px";
        toast.style.borderRadius = "8px";
        toast.style.border = "1px solid rgba(223, 176, 111, 0.45)";
        toast.style.background = "rgba(8, 18, 33, 0.94)";
        toast.style.color = "#f6e4ca";
        toast.style.fontSize = "0.82rem";
        toast.style.maxWidth = "420px";
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.opacity = "1";
    window.clearTimeout(toast._timer);
    toast._timer = window.setTimeout(() => {
        toast.style.opacity = "0";
    }, 2400);
}
