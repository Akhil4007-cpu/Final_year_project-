import { ApiError, getJson, postJson } from "./api.js";
import {
  $,
  $$,
  categoryLabel,
  clearElement,
  createElement,
  setBusy,
  setMessage,
  showToast,
} from "./ui.js";

const ADMIN = "/api/v1/admin";
const TABS = ["overview", "hazards", "users", "audit", "system"];

const dom = {
  loginView: $("#login-view"),
  loginForm: $("#login-form"),
  loginEmail: $("#login-email"),
  loginPassword: $("#login-password"),
  loginSubmit: $("#login-submit"),
  loginMessage: $("#login-message"),
  deniedView: $("#denied-view"),
  deniedCopy: $("#denied-copy"),
  deniedLogout: $("#denied-logout"),
  consoleView: $("#console-view"),
  navButtons: $$(".admin-nav button"),
  sections: {
    overview: $("#tab-overview"),
    hazards: $("#tab-hazards"),
    users: $("#tab-users"),
    audit: $("#tab-audit"),
    system: $("#tab-system"),
  },
  overviewStats: $("#overview-stats"),
  overviewRecent: $("#overview-recent"),
  overviewModel: $("#overview-model"),
  hazardsContent: $("#hazards-content"),
  hazardStatus: $("#hazard-status"),
  hazardLimit: $("#hazard-limit"),
  usersContent: $("#users-content"),
  auditContent: $("#audit-content"),
  auditLimit: $("#audit-limit"),
  systemContent: $("#system-content"),
  userChip: $("#admin-user-chip"),
  refreshButton: $("#refresh-button"),
  logoutButton: $("#logout-button"),
  moderateDialog: $("#moderate-dialog"),
  moderateForm: $("#moderate-form"),
  moderateTitle: $("#moderate-title"),
  moderateSummary: $("#moderate-summary"),
  moderateNote: $("#moderate-note"),
  moderateMessage: $("#moderate-message"),
  moderateSubmit: $("#moderate-submit"),
  moderateCancel: $("#moderate-cancel"),
  moderateClose: $("#moderate-close"),
};

const state = {
  user: null,
  tab: "overview",
  hazardsStatus: "",
  hazardsLimit: 200,
  auditLimit: 100,
  moderation: null,
  requestId: 0,
};

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function describeError(error) {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Try again.";
}

function isAuthError(error) {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return dateFormatter.format(date);
}

function formatNumber(value, digits = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return number.toFixed(digits);
}

function formatUptime(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${total % 60}s`;
  return `${total}s`;
}

function formatValue(value) {
  if (value === undefined || value === null || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function renderMessage(container, message) {
  clearElement(container);
  container.append(createElement("p", { className: "admin-message", text: message }));
}

function renderError(container, message, retry) {
  clearElement(container);
  container.append(createElement("p", { className: "admin-message", text: message }));
  if (retry) {
    const row = createElement("div", { className: "admin-actions" });
    const button = createElement("button", {
      className: "secondary",
      text: "Try again",
      attrs: { type: "button" },
    });
    button.addEventListener("click", retry);
    row.append(button);
    container.append(row);
  }
}

function statCard(label, value, note) {
  const card = createElement("div", { className: "stat-card" });
  card.append(createElement("p", { className: "stat-label", text: label }));
  card.append(createElement("p", { className: "stat-value", text: formatValue(value) }));
  if (note) card.append(createElement("p", { className: "stat-note", text: note }));
  return card;
}

function kvList(entries) {
  const list = createElement("dl", { className: "kv" });
  for (const [label, value] of entries) {
    if (value === undefined || value === null || value === "") continue;
    list.append(createElement("dt", { text: label }));
    const detail = createElement("dd");
    if (value instanceof Node) detail.append(value);
    else detail.textContent = formatValue(value);
    list.append(detail);
  }
  return list;
}

function buildTable(headers, rows) {
  const wrapper = createElement("div", { className: "table-scroll" });
  const table = createElement("table", { className: "data-table" });
  const head = createElement("thead");
  const headRow = createElement("tr");
  for (const header of headers) {
    const cell = createElement("th", { text: header, attrs: { scope: "col" } });
    headRow.append(cell);
  }
  head.append(headRow);
  const body = createElement("tbody");
  for (const row of rows) {
    const tableRow = createElement("tr");
    for (const value of row) {
      const cell = createElement("td");
      if (value instanceof Node) cell.append(value);
      else cell.textContent = formatValue(value);
      tableRow.append(cell);
    }
    body.append(tableRow);
  }
  table.append(head, body);
  wrapper.append(table);
  return wrapper;
}

function statusTag(status) {
  const labels = {
    unverified: "Unverified",
    verified: "Verified",
    rejected: "Rejected",
    expired: "Expired",
  };
  return createElement("span", {
    className: `tag tag-${status}`,
    text: labels[status] || status,
  });
}

function actionButton(label, className, onClick, { disabled = false, title = "" } = {}) {
  const button = createElement("button", {
    className,
    text: label,
    attrs: { type: "button" },
  });
  if (disabled) button.disabled = true;
  if (title) button.title = title;
  button.addEventListener("click", onClick);
  return button;
}

function auditDetails(details) {
  const serialized = JSON.stringify(details || {});
  const element = createElement("span", {
    className: "mono admin-details",
    text: serialized,
  });
  element.title = serialized;
  return element;
}

function buildAuditTable(events) {
  const rows = events.map((event) => [
    String(event.id),
    formatDateTime(event.created_at),
    event.actor_user_id === null || event.actor_user_id === undefined
      ? "system"
      : `#${event.actor_user_id}`,
    event.action,
    `${event.target_type}${event.target_id ? ` #${event.target_id}` : ""}`,
    auditDetails(event.details),
  ]);
  return buildTable(["ID", "Time", "Actor", "Action", "Target", "Details"], rows);
}

function modelMetricSummary(metrics) {
  if (!metrics) return null;
  const delta = Number(metrics.ml_minus_baseline_mae);
  let comparison = "baseline comparison unavailable";
  if (Number.isFinite(delta)) {
    comparison =
      delta > 0
        ? `${formatNumber(delta, 2)} points worse than baseline`
        : `${formatNumber(Math.abs(delta), 2)} points better than baseline`;
  }
  return `ML ${formatNumber(metrics.mae, 2)} · baseline ${formatNumber(
    metrics.baseline_mae,
    2,
  )} · ${comparison}`;
}

function renderModelDetails(container, model, { showOod = false } = {}) {
  container.append(createElement("h2", { text: "Geometry model" }));
  if (!model.available) {
    container.append(
      createElement("p", {
        className: "callout callout-danger",
        text: `Model unavailable: ${model.reason || "no reason reported"}. Sections fall back to the physics baseline where possible.`,
      }),
    );
  } else {
    container.append(
      createElement("p", {
        className: "callout",
        text: "Synthetic training only. This model is not trained on, or validated against, real-world crash or rider observations.",
      }),
    );
  }

  const metrics = model.metrics || {};
  const entries = [
    ["Name", model.model_name],
    ["Artifact version", model.artifact_version ? `v${model.artifact_version}` : "—"],
    ["Label version", model.label_version],
    ["Baseline version", model.baseline_version],
    ["Generator version", model.generator_version],
    ["Uncertainty", model.uncertainty_method],
    [
      "Nominal interval coverage",
      model.nominal_coverage !== null && model.nominal_coverage !== undefined
        ? `${formatNumber(Number(model.nominal_coverage) * 100, 1)}%`
        : null,
    ],
    ["Clean-geometry accuracy", modelMetricSummary(metrics.clean)],
    ["Degraded-geometry accuracy", modelMetricSummary(metrics.degraded)],
    [
      "Uncertainty coverage",
      metrics.uncertainty_coverage
        ? `empirical ${formatNumber(
            Number(metrics.uncertainty_coverage.empirical_coverage) * 100,
            1,
          )}% at nominal ${formatNumber(
            Number(metrics.uncertainty_coverage.nominal_coverage) * 100,
            0,
          )}%`
        : null,
    ],
    ["Feature count", model.feature_count],
    ["Required at startup", model.require_model],
  ];
  if (showOod) {
    entries.splice(9, 0, [
      "Unseen radius-band accuracy",
      modelMetricSummary(metrics.ood_radius),
    ]);
  }
  container.append(kvList(entries));
  container.append(
    createElement("p", {
      className: "hint admin-note",
      text: "Fallback rule: when model and physics-baseline scores disagree by more than 20 points, the displayed score uses the baseline and the section is marked as a fallback.",
    }),
  );
}

function renderOverview(data) {
  clearElement(dom.overviewStats);
  const users = data.users || {};
  const hazards = data.hazards || {};
  const database = data.database || {};
  const model = data.model || {};
  const openHazards = (hazards.unverified || 0) + (hazards.verified || 0);

  dom.overviewStats.append(
    statCard(
      "Users",
      users.total,
      `${users.active || 0} active · ${users.riders || 0} riders · ${users.admins || 0} admins`,
    ),
    statCard(
      "Open hazards",
      openHazards,
      `${hazards.unverified || 0} unverified · ${hazards.verified || 0} verified · ${hazards.rejected || 0} rejected · ${hazards.expired || 0} expired`,
    ),
    statCard(
      "Geometry model",
      model.available ? "Loaded" : "Unavailable",
      model.available
        ? `${model.model_name} · synthetic training only`
        : model.reason || "No model artifact loaded",
    ),
    statCard(
      "Database",
      database.ok ? `Schema v${database.schema_version}` : "Error",
      database.ok
        ? `${database.users} users · ${database.hazards} hazards stored`
        : database.error || "Database check failed",
    ),
    statCard(
      "Process uptime",
      formatUptime(data.uptime_s),
      `Started ${formatDateTime(data.started_at)}`,
    ),
  );

  clearElement(dom.overviewRecent);
  const recent = Array.isArray(data.recent_audit) ? data.recent_audit : [];
  if (!recent.length) {
    renderMessage(dom.overviewRecent, "No audit events recorded yet.");
  } else {
    dom.overviewRecent.append(buildAuditTable(recent));
  }

  clearElement(dom.overviewModel);
  renderModelDetails(dom.overviewModel, model);
}

function renderHazards(data) {
  clearElement(dom.hazardsContent);
  const hazards = Array.isArray(data.hazards) ? data.hazards : [];
  if (!hazards.length) {
    renderMessage(dom.hazardsContent, "No hazard reports match this filter.");
    return;
  }
  dom.hazardsContent.append(
    createElement("p", {
      className: "hint admin-note",
      text: `Showing ${data.count} report${data.count === 1 ? "" : "s"}. Confirmations are rider votes, not independent inspections.`,
    }),
  );
  const rows = hazards.map((hazard) => {
    const category = createElement("div");
    category.append(createElement("div", { text: categoryLabel(hazard.category) }));
    if (hazard.description) {
      category.append(
        createElement("div", { className: "hint", text: hazard.description }),
      );
    }

    const location = createElement("div");
    location.append(
      createElement("div", { text: `${formatNumber(hazard.lat, 5)}, ${formatNumber(hazard.lon, 5)}` }),
      createElement("div", {
        className: "hint",
        text: hazard.source === "map_pin" ? "Map pin" : "Current location",
      }),
    );

    const actions = createElement("div", { className: "admin-actions" });
    if (hazard.status === "unverified" || hazard.status === "verified") {
      actions.append(
        actionButton("Verify", "secondary", () => openModeration(hazard, "verify")),
        actionButton("Reject", "danger-outline", () => openModeration(hazard, "reject")),
      );
    } else {
      actions.append(createElement("span", { className: "hint", text: "Closed" }));
    }

    return [
      String(hazard.id),
      category,
      statusTag(hazard.status),
      location,
      String(hazard.confirmations),
      formatDateTime(hazard.created_at),
      formatDateTime(hazard.expires_at),
      actions,
    ];
  });
  dom.hazardsContent.append(
    buildTable(
      ["ID", "Report", "Status", "Location", "Votes", "Created", "Expires", "Actions"],
      rows,
    ),
  );
}

function renderUsers(users) {
  clearElement(dom.usersContent);
  if (!Array.isArray(users) || !users.length) {
    renderMessage(dom.usersContent, "No user accounts found.");
    return;
  }
  const rows = users.map((user) => {
    const isSelf = state.user && user.id === state.user.id;
    const active = createElement("span", {
      className: `tag ${user.is_active ? "tag-verified" : "tag-expired"}`,
      text: user.is_active ? "Active" : "Deactivated",
    });
    const actions = createElement("div", { className: "admin-actions" });
    const label = user.is_active ? "Deactivate" : "Activate";
    const button = actionButton(
      label,
      user.is_active ? "danger-outline" : "secondary",
      () => toggleUserActive(user, button),
      {
        disabled: Boolean(isSelf),
        title: isSelf ? "You cannot deactivate your own account." : "",
      },
    );
    actions.append(button);
    if (isSelf) actions.append(createElement("span", { className: "hint", text: "You" }));
    return [
      String(user.id),
      user.email,
      createElement("span", { className: "tag", text: user.role }),
      active,
      formatDateTime(user.created_at),
      actions,
    ];
  });
  dom.usersContent.append(
    buildTable(["ID", "Email", "Role", "Status", "Created", "Actions"], rows),
  );
}

function renderAudit(data) {
  clearElement(dom.auditContent);
  const events = Array.isArray(data.events) ? data.events : [];
  if (!events.length) {
    renderMessage(dom.auditContent, "No audit events recorded yet.");
    return;
  }
  dom.auditContent.append(
    createElement("p", {
      className: "hint admin-note",
      text: `Showing ${data.count} event${data.count === 1 ? "" : "s"}, newest first.`,
    }),
  );
  dom.auditContent.append(buildAuditTable(events));
}

function renderSystem(data) {
  clearElement(dom.systemContent);

  const runtimeCard = createElement("div", { className: "admin-card" });
  runtimeCard.append(
    createElement("h2", { text: "Runtime" }),
    kvList([
      ["Application", `${data.app} ${data.version}`],
      ["Environment", data.env],
      ["Python", data.python],
      ["Platform", data.platform],
      ["Process ID", data.process_id],
      ["Started", formatDateTime(data.started_at)],
      ["Uptime", formatUptime(data.uptime_s)],
    ]),
  );

  const databaseCard = createElement("div", { className: "admin-card" });
  databaseCard.append(createElement("h2", { text: "Database" }));
  if (data.database && data.database.ok) {
    databaseCard.append(
      kvList([
        ["Status", "ok"],
        ["Schema version", data.database.schema_version],
        ["Path exists", data.database.path_exists],
        ["Users", data.database.users],
        ["Hazards", data.database.hazards],
      ]),
    );
  } else {
    databaseCard.append(
      createElement("p", {
        className: "callout callout-danger",
        text: `Database check failed: ${(data.database && data.database.error) || "unknown error"}.`,
      }),
    );
  }

  const providerCard = createElement("div", { className: "admin-card" });
  const endpoints = data.provider_endpoints || {};
  providerCard.append(
    createElement("h2", { text: "Map providers" }),
    kvList([
      ["Geocoding endpoint", endpoints.nominatim],
      ["Routing endpoint", endpoints.osrm],
      ["Cached responses", data.provider_cache_entries],
    ]),
    createElement("p", {
      className: "hint admin-note",
      text: "Public Nominatim and OSRM demo endpoints are throttled and cached. Provider results are mapped data, not live road or traffic conditions.",
    }),
  );

  const limitsCard = createElement("div", { className: "admin-card" });
  const limits = data.rate_limits || {};
  limitsCard.append(
    createElement("h2", { text: "Rate limits" }),
    kvList([
      ["Route analyses per minute", limits.route_per_minute],
      ["Hazard reports per hour", limits.hazard_per_hour],
      ["Login attempts per minute", limits.login_per_minute],
    ]),
    createElement("p", {
      className: "hint admin-note",
      text: "Limits are enforced per process with an in-memory sliding window. A multi-process deployment needs a shared limiter.",
    }),
  );

  const modelCard = createElement("div", { className: "admin-card" });
  renderModelDetails(modelCard, data.model || {}, { showOod: true });

  dom.systemContent.append(runtimeCard, databaseCard, providerCard, limitsCard, modelCard);
}

function overviewTargets() {
  return [dom.overviewStats, dom.overviewRecent, dom.overviewModel];
}

function currentTargets(tab) {
  switch (tab) {
    case "overview":
      return overviewTargets();
    case "hazards":
      return [dom.hazardsContent];
    case "users":
      return [dom.usersContent];
    case "audit":
      return [dom.auditContent];
    case "system":
      return [dom.systemContent];
    default:
      return [];
  }
}

function fetchTab(tab) {
  if (tab === "overview") return getJson(`${ADMIN}/overview`);
  if (tab === "hazards") {
    const params = new URLSearchParams({ limit: String(state.hazardsLimit) });
    if (state.hazardsStatus) params.set("status", state.hazardsStatus);
    return getJson(`${ADMIN}/hazards?${params.toString()}`);
  }
  if (tab === "users") return getJson(`${ADMIN}/users`);
  if (tab === "audit") {
    return getJson(`${ADMIN}/audit?limit=${encodeURIComponent(state.auditLimit)}`);
  }
  if (tab === "system") return getJson(`${ADMIN}/diagnostics`);
  throw new Error(`Unknown admin section: ${tab}`);
}

async function loadTab(tab = state.tab) {
  if (!state.user) return;
  const requestId = ++state.requestId;
  const isCurrent = () => requestId === state.requestId && state.tab === tab;

  dom.refreshButton.disabled = true;
  dom.refreshButton.setAttribute("aria-busy", "true");
  for (const target of currentTargets(tab)) renderMessage(target, "Loading…");

  try {
    const data = await fetchTab(tab);
    if (!isCurrent()) return;
    if (tab === "overview") renderOverview(data);
    else if (tab === "hazards") renderHazards(data);
    else if (tab === "users") renderUsers(data);
    else if (tab === "audit") renderAudit(data);
    else if (tab === "system") renderSystem(data);
  } catch (error) {
    if (!isCurrent()) return;
    if (isAuthError(error)) {
      showLogin({ message: "Your session ended. Sign in again." });
      return;
    }
    const targets = currentTargets(tab);
    targets.slice(1).forEach((target) => clearElement(target));
    renderError(targets[0], describeError(error), () => loadTab(tab));
  } finally {
    if (requestId === state.requestId) {
      dom.refreshButton.disabled = false;
      dom.refreshButton.removeAttribute("aria-busy");
    }
  }
}

function selectTab(tab) {
  if (!TABS.includes(tab)) return;
  state.tab = tab;
  for (const button of dom.navButtons) {
    if (button.dataset.tab === tab) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  for (const [name, section] of Object.entries(dom.sections)) {
    section.hidden = name !== tab;
  }
  loadTab(tab);
}

function showLogin({ message = "", tone = "error" } = {}) {
  state.user = null;
  dom.loginView.hidden = false;
  dom.deniedView.hidden = true;
  dom.consoleView.hidden = true;
  dom.userChip.hidden = true;
  dom.userChip.textContent = "";
  dom.refreshButton.hidden = true;
  dom.logoutButton.hidden = true;
  setMessage(dom.loginMessage, message, tone);
  if (!dom.loginEmail.value) dom.loginEmail.focus();
  else dom.loginPassword.focus();
}

function showDenied(user) {
  state.user = user;
  dom.loginView.hidden = true;
  dom.consoleView.hidden = true;
  dom.deniedView.hidden = false;
  dom.userChip.hidden = false;
  dom.userChip.textContent = user.email;
  dom.refreshButton.hidden = true;
  dom.logoutButton.hidden = false;
  dom.deniedCopy.textContent = `${user.email} is signed in with the ${user.role} role. This console requires an administrator account.`;
}

function showConsole() {
  dom.loginView.hidden = true;
  dom.deniedView.hidden = true;
  dom.consoleView.hidden = false;
  dom.userChip.hidden = false;
  dom.userChip.textContent = state.user.email;
  dom.refreshButton.hidden = false;
  dom.logoutButton.hidden = false;
  selectTab(state.tab);
}

async function signOut(message = "Signed out.") {
  try {
    await postJson("/api/v1/auth/logout");
  } catch {
    // The local UI still ends the session view; a failed server logout is surfaced on next request.
  }
  dom.loginEmail.value = "";
  dom.loginPassword.value = "";
  showLogin({ message, tone: "ok" });
}

function openModeration(hazard, action) {
  state.moderation = { hazard, action };
  const verifying = action === "verify";
  dom.moderateTitle.textContent = verifying
    ? "Verify hazard report"
    : "Reject hazard report";
  dom.moderateSummary.textContent = `Hazard #${hazard.id} · ${categoryLabel(
    hazard.category,
  )} · currently ${hazard.status}.`;
  dom.moderateNote.value = "";
  setMessage(dom.moderateMessage, "");
  dom.moderateSubmit.textContent = verifying ? "Verify" : "Reject";
  dom.moderateSubmit.className = verifying ? "primary" : "danger-button";
  dom.moderateDialog.showModal();
  dom.moderateNote.focus();
}

function closeModeration() {
  state.moderation = null;
  setMessage(dom.moderateMessage, "");
  if (dom.moderateDialog.open) dom.moderateDialog.close();
}

async function toggleUserActive(user, button) {
  const targetActive = !user.is_active;
  setBusy(button, true, targetActive ? "Activating…" : "Deactivating…");
  try {
    await postJson(`${ADMIN}/users/${user.id}/active`, { active: targetActive });
    showToast(
      targetActive
        ? `Account ${user.email} activated.`
        : `Account ${user.email} deactivated.`,
    );
    await loadTab("users");
  } catch (error) {
    if (isAuthError(error)) {
      showLogin({ message: "Your session ended. Sign in again." });
      return;
    }
    setBusy(button, false);
    showToast(describeError(error));
  }
}

dom.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = dom.loginEmail.value.trim();
  const password = dom.loginPassword.value;
  if (!email || !password) {
    setMessage(dom.loginMessage, "Enter both an email address and a password.");
    return;
  }
  setMessage(dom.loginMessage, "");
  setBusy(dom.loginSubmit, true, "Signing in…");
  try {
    const payload = await postJson("/api/v1/auth/login", { email, password });
    dom.loginPassword.value = "";
    if (payload.user.role !== "admin") {
      showDenied(payload.user);
      return;
    }
    state.user = payload.user;
    state.tab = "overview";
    showConsole();
  } catch (error) {
    setMessage(dom.loginMessage, describeError(error));
  } finally {
    setBusy(dom.loginSubmit, false);
  }
});

for (const button of dom.navButtons) {
  button.addEventListener("click", () => selectTab(button.dataset.tab));
}

dom.refreshButton.addEventListener("click", () => loadTab(state.tab));
dom.logoutButton.addEventListener("click", () => signOut());
dom.deniedLogout.addEventListener("click", () => signOut());

dom.hazardStatus.addEventListener("change", () => {
  state.hazardsStatus = dom.hazardStatus.value;
  if (state.tab === "hazards") loadTab("hazards");
});

dom.hazardLimit.addEventListener("change", () => {
  state.hazardsLimit = Number(dom.hazardLimit.value) || 200;
  if (state.tab === "hazards") loadTab("hazards");
});

dom.auditLimit.addEventListener("change", () => {
  state.auditLimit = Number(dom.auditLimit.value) || 100;
  if (state.tab === "audit") loadTab("audit");
});

dom.moderateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const pending = state.moderation;
  if (!pending) return;
  setMessage(dom.moderateMessage, "");
  setBusy(dom.moderateSubmit, true, "Saving…");
  try {
    await postJson(`${ADMIN}/hazards/${pending.hazard.id}/moderate`, {
      action: pending.action,
      note: dom.moderateNote.value.trim(),
    });
    const verb = pending.action === "verify" ? "verified" : "rejected";
    showToast(`Hazard #${pending.hazard.id} ${verb}.`);
    closeModeration();
    await loadTab("hazards");
  } catch (error) {
    if (isAuthError(error)) {
      closeModeration();
      showLogin({ message: "Your session ended. Sign in again." });
      return;
    }
    setMessage(dom.moderateMessage, describeError(error));
  } finally {
    setBusy(dom.moderateSubmit, false);
  }
});

dom.moderateCancel.addEventListener("click", closeModeration);
dom.moderateClose.addEventListener("click", closeModeration);
dom.moderateDialog.addEventListener("close", () => {
  state.moderation = null;
});

async function boot() {
  try {
    const payload = await getJson("/api/v1/auth/me");
    if (payload.user.role === "admin") {
      state.user = payload.user;
      showConsole();
    } else {
      showDenied(payload.user);
    }
  } catch (error) {
    if (isAuthError(error)) {
      showLogin();
      return;
    }
    showLogin({ message: describeError(error) });
  }
}

void boot();
