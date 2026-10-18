import { api, ApiError, deleteJson, getJson, postJson } from "./api.js";
import {
  cumulativeDistances,
  formatDistance,
  formatDuration,
  formatTimeAgo,
  haversine,
  nearestOnPolyline,
  pointAtDistance,
} from "./geo.js";
import {
  $,
  bandClass,
  bandColor,
  bandLabel,
  categoryColor,
  categoryLabel,
  clearElement,
  closeSheet,
  createElement,
  openSheet,
  setMessage,
  showToast,
} from "./ui.js";
import { alertStage, detectCapabilities, planAlert, speedAwareness } from "./alerts.js";
import { DEFAULT_SETTINGS, loadSettings, normalizeSettings, saveSettings } from "./settings.js";

const GPS_TEXT = {
  off: "Location off",
  locating: "Locating…",
  gps_unavailable: "Location blocked",
  gps_uncertain: "GPS uncertain",
  ready: "GPS ready",
  navigating: "Navigating",
  advisory_active: "Advisory active",
  route_deviation: "Off route",
};

const dom = {
  gpsChip: $("#gps-chip"),
  gpsChipText: $("#gps-chip-text"),
  accountButton: $("#account-button"),
  searchPanel: $("#search-panel"),
  searchForm: $("#search-form"),
  searchInput: $("#search-input"),
  searchSubmit: $("#search-submit"),
  searchResults: $("#search-results"),
  locateButton: $("#locate-button"),
  reportButton: $("#report-button"),
  routePanel: $("#route-panel"),
  routeEyebrow: $("#route-eyebrow"),
  routeTitle: $("#route-title"),
  routeClose: $("#route-close"),
  routeDistance: $("#route-distance"),
  routeEta: $("#route-eta"),
  routeScoreValue: $("#route-score-value"),
  routeBand: $("#route-band"),
  coverageFill: $("#coverage-fill"),
  coverageText: $("#coverage-text"),
  comparisonNote: $("#comparison-note"),
  speedSelect: $("#speed-select"),
  startNav: $("#start-nav"),
  alternativesButton: $("#alternatives-button"),
  detailButton: $("#detail-button"),
  advisoryBanner: $("#advisory-banner"),
  advisoryTitle: $("#advisory-title"),
  advisoryText: $("#advisory-text"),
  advisorySpeed: $("#advisory-speed"),
  advisoryDismiss: $("#advisory-dismiss"),
  navHud: $("#nav-hud"),
  navInstruction: $("#nav-instruction"),
  navMeta: $("#nav-meta"),
  navEnd: $("#nav-end"),
  routerNote: $("#router-note"),
  routerNoteText: $("#router-note-text"),
  routerRetry: $("#router-retry"),
  alternativesSheet: $("#alternatives-sheet"),
  alternativesClose: $("#alternatives-close"),
  alternativesNote: $("#alternatives-note"),
  alternativesList: $("#alternatives-list"),
  detailSheet: $("#detail-sheet"),
  detailClose: $("#detail-close"),
  detailContent: $("#detail-content"),
  reportSheet: $("#report-sheet"),
  reportClose: $("#report-close"),
  reportForm: $("#report-form"),
  reportCategory: $("#report-category"),
  reportDescription: $("#report-description"),
  reportCoords: $("#report-coords"),
  reportMessage: $("#report-message"),
  reportSubmit: $("#report-submit"),
  reportCancel: $("#report-cancel"),
  reportPick: $("#report-pick"),
  accountSheet: $("#account-sheet"),
  accountClose: $("#account-close"),
  accountEmail: $("#account-email"),
  accountRole: $("#account-role"),
  accountAdminLink: $("#account-admin-link"),
  logoutButton: $("#logout-button"),
  deleteAccountButton: $("#delete-account-button"),
  tripSheet: $("#trip-sheet"),
  tripClose: $("#trip-close"),
  tripContent: $("#trip-content"),
  authDialog: $("#auth-dialog"),
  authForm: $("#auth-form"),
  authTitle: $("#auth-title"),
  authCancel: $("#auth-cancel"),
  authModeNote: $("#auth-mode-note"),
  authEmail: $("#auth-email"),
  authPassword: $("#auth-password"),
  authError: $("#auth-error"),
  authSubmit: $("#auth-submit"),
  authSwitch: $("#auth-switch"),
  connectionBanner: $("#connection-banner"),
  alertAnnounce: $("#alert-announce"),
  settingsButton: $("#settings-button"),
  settingsSheet: $("#settings-sheet"),
  settingsClose: $("#settings-close"),
  settingVisual: $("#setting-visual"),
  settingAudio: $("#setting-audio"),
  settingHaptic: $("#setting-haptic"),
  testAudioButton: $("#test-audio-button"),
  settingsNote: $("#settings-note"),
};

const state = {
  user: null,
  gps: {
    watchId: null,
    status: "off",
    lastFix: null,
    rejections: 0,
    lastErrorAt: 0,
  },
  destination: null,
  pendingRoute: false,
  pendingNav: false,
  pendingReport: false,
  routeData: null,
  selectedRouteId: null,
  routeController: null,
  routeToken: 0,
  routeError: false,
  authMode: "login",
  follow: true,
  pinMode: false,
  reportPin: null,
  nav: null,
  advisoryActive: false,
  alertSettings: { ...DEFAULT_SETTINGS },
  alertCapabilities: { visual: true, audio: false, haptic: false, notify: false },
  reducedMotion: false,
  audioUnlocked: false,
};

let audioContext = null;

/* ---------------------------------------------------------------- map */

const map = L.map("map", {
  zoomControl: false,
  preferCanvas: true,
  worldCopyJump: true,
}).setView([22.9734, 78.6569], 5);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  subdomains: "abc",
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

L.control.zoom({ position: "bottomright" }).addTo(map);

const routeLayer = L.layerGroup().addTo(map);
const hazardLayer = L.layerGroup().addTo(map);

let userMarker = null;
let accuracyCircle = null;
let destinationMarker = null;
let reportMarker = null;
let hazardAbort = null;
let hazardsTimer = null;
let searchAbort = null;
let mapMoveTimer = null;

/* ---------------------------------------------------------------- helpers */

function usableFix() {
  const fix = state.gps.lastFix;
  if (!fix) return null;
  if (Date.now() - fix.timestamp > 30000) return null;
  if (fix.accuracy > 100) return null;
  return fix;
}

function selectedRoute() {
  if (!state.routeData) return null;
  return state.routeData.routes.find((route) => route.id === state.selectedRouteId) || null;
}

function shortName(name) {
  if (!name) return "Destination";
  const parts = name.split(",").map((part) => part.trim()).filter(Boolean);
  return parts.slice(0, 2).join(", ");
}

function toFixed(value, digits = 1) {
  return Number.isFinite(value) ? value.toFixed(digits) : "—";
}

function percent(value) {
  return Number.isFinite(value) ? `${Math.round(value * 100)}%` : "—";
}

function refreshGpsChip() {
  let chipState = state.gps.status;
  if (state.nav && state.nav.active) {
    if (state.nav.deviated) chipState = "route_deviation";
    else if (state.advisoryActive) chipState = "advisory_active";
    else if (state.gps.status === "gps_uncertain") chipState = "gps_uncertain";
    else chipState = "navigating";
  }
  dom.gpsChip.dataset.state = chipState;
  dom.gpsChipText.textContent = GPS_TEXT[chipState] || "Location";
  const fix = state.gps.lastFix;
  dom.gpsChip.title = fix
    ? `Location accuracy ±${Math.round(fix.accuracy)} m. Click to centre the map.`
    : "Location status. Click to request a GPS fix.";
}

function setGpsStatus(status) {
  state.gps.status = status;
  refreshGpsChip();
}

function updateUserMarker(fix) {
  const latlng = [fix.lat, fix.lon];
  if (!userMarker) {
    userMarker = L.circleMarker(latlng, {
      radius: 8,
      color: "#ffffff",
      weight: 3,
      fillColor: "#0b57d0",
      fillOpacity: 1,
    }).addTo(map);
  } else {
    userMarker.setLatLng(latlng);
  }
  if (!accuracyCircle) {
    accuracyCircle = L.circle(latlng, {
      radius: fix.accuracy,
      color: "#0b57d0",
      weight: 1,
      opacity: 0.4,
      fillColor: "#0b57d0",
      fillOpacity: 0.08,
      interactive: false,
    }).addTo(map);
  } else {
    accuracyCircle.setLatLng(latlng);
    accuracyCircle.setRadius(fix.accuracy);
  }
  if (state.follow) {
    map.setView(latlng, Math.max(map.getZoom(), 15));
  }
}

function notifyGps(message) {
  const now = Date.now();
  if (now - state.gps.lastErrorAt < 20000) return;
  state.gps.lastErrorAt = now;
  showToast(message);
}

/* ---------------------------------------------------------------- location */

function startWatch() {
  if (state.gps.watchId !== null) return;
  if (!("geolocation" in navigator)) {
    setGpsStatus("gps_unavailable");
    showToast("This browser does not provide location.");
    return;
  }
  setGpsStatus("locating");
  state.gps.watchId = navigator.geolocation.watchPosition(onFix, onGeoError, {
    enableHighAccuracy: true,
    maximumAge: 3000,
    timeout: 20000,
  });
}

function onFix(position) {
  const coords = position.coords || {};
  const lat = Number(coords.latitude);
  const lon = Number(coords.longitude);
  if (
    !Number.isFinite(lat) ||
    !Number.isFinite(lon) ||
    lat < -90 ||
    lat > 90 ||
    lon < -180 ||
    lon > 180
  ) {
    return;
  }
  const accuracy = Number.isFinite(coords.accuracy) ? Math.max(0, coords.accuracy) : 9999;
  const timestamp = Number.isFinite(position.timestamp) ? position.timestamp : Date.now();
  if (Date.now() - timestamp > 30000) {
    setGpsStatus("gps_uncertain");
    return;
  }
  const previous = state.gps.lastFix;
  if (previous && timestamp > previous.timestamp) {
    const seconds = (timestamp - previous.timestamp) / 1000;
    const jump = haversine([previous.lat, previous.lon], [lat, lon]);
    if (seconds > 0 && jump / seconds > 75) {
      state.gps.rejections += 1;
      setGpsStatus("gps_uncertain");
      if (state.gps.rejections === 2) {
        showToast("Implausible location jumps detected. Waiting for a stable GPS fix.");
      }
      return;
    }
  }
  state.gps.rejections = 0;
  // `coords.speed` is m/s above ground when the device reports it; most browsers
  // report null on desktop and many phones. Number(null) is 0, so test for the
  // absent value first — an unreported speed must never look like 0 km/h.
  const rawSpeed = coords.speed === null || coords.speed === undefined ? Number.NaN : Number(coords.speed);
  const speedKmh = Number.isFinite(rawSpeed) && rawSpeed >= 0 ? rawSpeed * 3.6 : null;
  const fix = { lat, lon, accuracy, timestamp, speed_kmh: speedKmh };
  state.gps.lastFix = fix;
  setGpsStatus(accuracy > 100 ? "gps_uncertain" : "ready");
  updateUserMarker(fix);

  if (state.pendingRoute && state.destination && !state.routeData) {
    state.pendingRoute = false;
    analyzeRoute();
  }
  if (state.pendingNav) {
    state.pendingNav = false;
    beginNavigation();
  }
  if (state.nav && state.nav.active) {
    updateNavigation();
  }
  if (!dom.reportSheet.hidden) {
    updateReportCoords();
  }
}

function onGeoError(error) {
  if (error.code === 1) {
    setGpsStatus("gps_unavailable");
    notifyGps("Location permission is blocked. Enable it in browser settings.");
    if (state.gps.watchId !== null) {
      navigator.geolocation.clearWatch(state.gps.watchId);
      state.gps.watchId = null;
    }
    return;
  }
  if (error.code === 2) {
    setGpsStatus("gps_unavailable");
    notifyGps("GPS position is unavailable. Move to an open area and try again.");
    return;
  }
  setGpsStatus("gps_uncertain");
  notifyGps("GPS timed out. Still trying…");
}

function ensureLocation() {
  if (!window.isSecureContext && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
    showToast("Location requires HTTPS. Use a secure deployment.");
    return;
  }
  startWatch();
  const fix = usableFix();
  if (fix) {
    state.follow = true;
    map.setView([fix.lat, fix.lon], Math.max(map.getZoom(), 16));
  } else if (state.gps.status === "gps_unavailable") {
    showToast("Location is unavailable. Check browser permissions and HTTPS.");
  } else {
    showToast("Requesting your location…");
  }
}

/* ---------------------------------------------------------------- search */

async function runSearch(event) {
  event.preventDefault();
  const query = dom.searchInput.value.trim();
  if (query.length < 2) {
    showToast("Enter at least two characters.");
    return;
  }
  if (searchAbort) searchAbort.abort();
  const controller = new AbortController();
  searchAbort = controller;
  clearElement(dom.searchResults);
  dom.searchResults.hidden = false;
  const loading = createElement("li", { className: "results-empty", text: "Searching…" });
  dom.searchResults.append(loading);
  dom.searchSubmit.disabled = true;
  try {
    const data = await getJson(
      `/api/v1/geocode?q=${encodeURIComponent(query)}&limit=5`,
      controller.signal,
    );
    renderSearchResults(data.results);
  } catch (error) {
    if (error.name === "AbortError") return;
    clearElement(dom.searchResults);
    const message =
      error instanceof ApiError && error.code === "insufficient_evidence"
        ? "No matching place was found."
        : error.message;
    dom.searchResults.append(
      createElement("li", { className: "results-empty", text: message }),
    );
  } finally {
    dom.searchSubmit.disabled = false;
  }
}

function renderSearchResults(results) {
  clearElement(dom.searchResults);
  dom.searchResults.hidden = false;
  if (!results.length) {
    dom.searchResults.append(
      createElement("li", { className: "results-empty", text: "No matching place was found." }),
    );
    return;
  }
  results.forEach((result) => {
    const item = document.createElement("li");
    const button = createElement("button", {
      className: "result-button",
      attrs: { type: "button" },
    });
    button.append(
      createElement("span", { className: "result-name", text: shortName(result.display_name) }),
      createElement("span", { className: "result-meta", text: result.display_name }),
    );
    button.addEventListener("click", () => selectDestination(result));
    item.append(button);
    dom.searchResults.append(item);
  });
}

function selectDestination(result) {
  if (state.nav && state.nav.active) {
    endNavigation({ silent: true });
  }
  state.destination = {
    lat: Number(result.lat),
    lon: Number(result.lon),
    display_name: result.display_name,
  };
  dom.searchInput.value = shortName(result.display_name);
  dom.searchResults.hidden = true;
  if (destinationMarker) {
    destinationMarker.setLatLng([state.destination.lat, state.destination.lon]);
  } else {
    destinationMarker = L.marker([state.destination.lat, state.destination.lon]).addTo(map);
  }
  destinationMarker.bindTooltip(shortName(result.display_name));
  map.setView([state.destination.lat, state.destination.lon], 14);
  state.follow = false;
  const fix = usableFix();
  if (fix) {
    analyzeRoute();
  } else {
    state.pendingRoute = true;
    startWatch();
    showToast("Enable location to analyse the route from your position.");
  }
}

/* ---------------------------------------------------------------- route analysis */

function routeRequestBody() {
  return {
    origin: { lat: state.gps.lastFix.lat, lon: state.gps.lastFix.lon },
    destination: { lat: state.destination.lat, lon: state.destination.lon },
    alternatives: true,
    speed_kmh: dom.speedSelect.value ? Number(dom.speedSelect.value) : null,
  };
}

function setRouteLoading() {
  dom.routePanel.hidden = false;
  dom.routeEyebrow.textContent = "Analysing route";
  dom.routeTitle.textContent = "Reading mapped road geometry…";
  dom.routeDistance.textContent = "—";
  dom.routeEta.textContent = "—";
  dom.routeScoreValue.textContent = "—";
  dom.routeBand.textContent = "";
  dom.routeBand.className = "band-pill";
  dom.coverageFill.style.width = "0%";
  dom.coverageText.textContent = "Fetching route geometry and computing sections.";
  dom.comparisonNote.hidden = true;
  dom.startNav.disabled = true;
  dom.startNav.textContent = "Analysing…";
  dom.alternativesButton.disabled = true;
  dom.detailButton.disabled = true;
}

function renderRouteError(error) {
  state.routeError = true;
  state.routeData = null;
  state.selectedRouteId = null;
  routeLayer.clearLayers();
  dom.routePanel.hidden = false;
  dom.routeEyebrow.textContent = "Route unavailable";
  let title = "Route could not be analysed";
  if (error.code === "provider_unavailable") title = "Routing provider unavailable";
  if (error.code === "insufficient_evidence") title = "No drivable route found";
  dom.routeTitle.textContent = title;
  dom.routeDistance.textContent = "—";
  dom.routeEta.textContent = "—";
  dom.routeScoreValue.textContent = "Not scored";
  dom.routeBand.textContent = "Unavailable";
  dom.routeBand.className = "band-pill band-unavailable";
  dom.coverageFill.style.width = "0%";
  dom.coverageText.textContent = "No fallback route is invented.";
  dom.comparisonNote.textContent = error.message;
  dom.comparisonNote.hidden = false;
  dom.startNav.disabled = false;
  dom.startNav.textContent = "Retry";
  dom.alternativesButton.disabled = true;
  dom.detailButton.disabled = true;
  showToast(error.message);
}

async function analyzeRoute({ forNavigation = false } = {}) {
  const fix = usableFix();
  if (!fix) {
    if (state.destination) state.pendingRoute = true;
    startWatch();
    showToast("A recent GPS fix with ±100 m accuracy or better is required.");
    return false;
  }
  if (!state.destination) {
    showToast("Choose a destination first.");
    return false;
  }
  if (state.routeController) state.routeController.abort();
  const controller = new AbortController();
  state.routeController = controller;
  const token = ++state.routeToken;
  if (!forNavigation) {
    setRouteLoading();
    closeSheet(dom.alternativesSheet);
    closeSheet(dom.detailSheet);
  }
  try {
    const data = await postJson(
      "/api/v1/routes/analyze",
      routeRequestBody(),
      controller.signal,
    );
    if (token !== state.routeToken) return false;
    state.routeData = data;
    const previous = data.routes.find((route) => route.id === state.selectedRouteId);
    state.selectedRouteId = previous ? previous.id : data.routes[0]?.id || null;
    state.routeError = false;
    renderRoute();
    if (state.nav && state.nav.active && forNavigation) {
      const route = selectedRoute();
      if (!route || route.state !== "scored") {
        showToast("Recalculated route has insufficient geometry evidence.");
        return false;
      }
      state.nav.route = route;
      state.nav.progressM = 0;
      state.nav.deviated = false;
      state.nav.deviations = 0;
      state.nav.currentAdvisoryId = null;
      state.nav.dismissed.clear();
      hideRouterNote();
      dom.routePanel.hidden = true;
      updateNavigation();
      showToast("Route recalculated.");
    }
    return true;
  } catch (error) {
    if (error.name === "AbortError") return false;
    if (token !== state.routeToken) return false;
    renderRouteError(error);
    return false;
  }
}

function comparisonMessage() {
  const comparison = state.routeData?.comparison;
  if (!comparison) return "";
  if (comparison.state === "comparable") {
    return "Alternatives are within a comparable geometry-challenge range. No recommendation is made.";
  }
  if (comparison.state === "ranked") {
    const routes = state.routeData.routes;
    const index = routes.findIndex(
      (route) => route.id === comparison.lowest_geometry_challenge_route_id,
    );
    return `Route ${index + 1} has the lowest geometry-challenge estimate. This is not a safety ranking.`;
  }
  return comparison.reason || "Routes could not be compared.";
}

function renderRoutePanel() {
  const route = selectedRoute();
  const data = state.routeData;
  if (!route || !data) return;
  const summary = route.summary;
  const index = data.routes.indexOf(route);
  dom.routePanel.hidden = Boolean(state.nav && state.nav.active);
  dom.routeEyebrow.textContent = `Route ${index + 1} of ${data.routes.length} · ${data.provider.name.toUpperCase()}`;
  dom.routeTitle.textContent = state.destination
    ? shortName(state.destination.display_name)
    : "Analysed route";
  dom.routeDistance.textContent = formatDistance(route.distance_m);
  dom.routeEta.textContent = formatDuration(route.duration_s);

  if (summary.state === "scored") {
    dom.routeScoreValue.textContent =
      summary.score === null ? bandLabel(summary.band) : toFixed(summary.score, 1);
    dom.routeBand.textContent = bandLabel(summary.band);
    dom.routeBand.className = `band-pill ${bandClass(summary.band)}`;
    dom.routeScoreValue.title =
      "Weighted geometry challenge score from 0 to 100 across scored sections.";
  } else {
    dom.routeScoreValue.textContent = "Not scored";
    dom.routeBand.textContent = "Insufficient evidence";
    dom.routeBand.className = "band-pill band-unavailable";
    dom.routeScoreValue.title = summary.reason || "";
  }

  const coverage = Math.max(0, Math.min(1, summary.coverage || 0));
  dom.coverageFill.style.width = `${Math.round(coverage * 100)}%`;
  const coverageParts = [
    `${percent(coverage)} of ${formatDistance(summary.total_length_m)} scored`,
    `${formatDistance(summary.missing_length_m)} without usable geometry`,
  ];
  if (summary.reason) coverageParts.push(summary.reason);
  dom.coverageText.textContent = coverageParts.join(" · ");

  const message = comparisonMessage();
  dom.comparisonNote.textContent = message;
  dom.comparisonNote.hidden = !message;

  dom.speedSelect.value =
    data.inputs.speed_source === "caller_supplied" ? String(Math.round(data.inputs.speed_kmh)) : "";
  dom.speedSelect.disabled = Boolean(state.nav && state.nav.active);

  const scored = summary.state === "scored";
  dom.startNav.disabled = !scored;
  dom.startNav.textContent = scored
    ? route.advisories.length
      ? "Start advisories"
      : "Start navigation"
    : "No scored route";
  dom.alternativesButton.disabled = data.routes.length < 2;
  dom.detailButton.disabled = false;
  state.routeError = false;
}

function drawRoute() {
  const route = selectedRoute();
  const data = state.routeData;
  routeLayer.clearLayers();
  if (!route || !data) return;

  data.routes.forEach((other) => {
    if (other.id === route.id || other.geometry.length < 2) return;
    L.polyline(other.geometry, {
      color: "#6b7280",
      weight: 4,
      opacity: 0.45,
      dashArray: "6 8",
      interactive: false,
    }).addTo(routeLayer);
  });

  if (!route.sections.length) {
    L.polyline(route.geometry, {
      color: "#6b7280",
      weight: 6,
      opacity: 0.8,
      dashArray: "4 6",
      interactive: false,
    }).addTo(routeLayer);
  } else {
    route.sections.forEach((section) => {
      const slice = route.geometry.slice(section.start_index, section.end_index + 1);
      if (slice.length < 2) return;
      const usable = section.evidence === "scored";
      L.polyline(slice, {
        color: usable ? bandColor(section.band) : "#6b7280",
        weight: 7,
        opacity: usable ? 0.92 : 0.7,
        dashArray: usable ? null : "4 6",
        lineCap: "round",
        interactive: false,
      }).addTo(routeLayer);
    });
  }

  const cumulative = cumulativeDistances(route.geometry);
  route._cumulative = cumulative;
  route.advisories.forEach((advisory) => {
    const point = pointAtDistance(route.geometry, cumulative, advisory.start_distance_m);
    if (!point) return;
    L.circleMarker(point, {
      radius: 6,
      color: "#ffffff",
      weight: 2,
      fillColor: bandColor(advisory.band),
      fillOpacity: 1,
    })
      .bindTooltip(`${bandLabel(advisory.band)} challenge curve`, { direction: "top" })
      .addTo(routeLayer);
  });

  const bounds = L.latLngBounds(route.geometry.map((point) => L.latLng(point[0], point[1])));
  if (bounds.isValid() && !(state.nav && state.nav.active)) {
    const mobile = window.innerWidth < 900;
    map.fitBounds(bounds, {
      paddingTopLeft: [36, 96],
      paddingBottomRight: [36, mobile ? 300 : 70],
      maxZoom: 16,
    });
    state.follow = false;
  }
}

function renderRoute() {
  drawRoute();
  renderRoutePanel();
}

/* ---------------------------------------------------------------- navigation */

function beginNavigation() {
  const route = selectedRoute();
  if (!route || route.state !== "scored") {
    showToast("This route has insufficient geometry evidence to start advisories.");
    return;
  }
  const fix = usableFix();
  if (!fix) {
    state.pendingNav = true;
    startWatch();
    showToast("Waiting for a GPS fix before starting advisories.");
    return;
  }
  state.nav = {
    active: true,
    route,
    progressM: 0,
    deviations: 0,
    deviated: false,
    startedAt: Date.now(),
    advisoryStartedAt: null,
    advisoriesShown: new Set(),
    currentAdvisoryId: null,
    cueStageKey: null,
    dismissed: new Map(),
  };
  state.follow = true;
  state.advisoryActive = false;
  dom.routePanel.hidden = true;
  dom.searchPanel.hidden = true;
  dom.navHud.hidden = false;
  dom.speedSelect.disabled = true;
  hideRouterNote();
  hideAdvisory();
  map.setView([fix.lat, fix.lon], 17);
  refreshGpsChip();
  updateNavigation();
  if (!route.advisories.length) {
    showToast("No advisory-threshold curves on this route. Progress is still shown.");
  }
}

function updateNavigation() {
  const nav = state.nav;
  if (!nav || !nav.active) return;
  const fix = usableFix();
  if (!fix) {
    dom.navInstruction.textContent = "Waiting for a usable GPS fix";
    dom.navMeta.textContent = "Advisories need ±100 m accuracy or better.";
    hideAdvisory();
    return;
  }
  const route = nav.route;
  const cumulative =
    route._cumulative || (route._cumulative = cumulativeDistances(route.geometry));
  const nearest = nearestOnPolyline([fix.lat, fix.lon], route.geometry, cumulative);
  nav.progressM = nearest.progressM;
  const threshold = Math.max(55, Math.min(120, fix.accuracy * 1.6));
  if (nearest.distanceM > threshold) {
    nav.deviations += 1;
    if (nav.deviations >= 2 && !nav.deviated) {
      nav.deviated = true;
      hideAdvisory();
      showRouterNote("Off the analysed route. Advisories are paused.");
    }
  } else {
    nav.deviations = 0;
    if (nav.deviated) {
      nav.deviated = false;
      hideRouterNote();
    }
  }
  if (nav.deviated) {
    dom.navInstruction.textContent = "Off the analysed route";
    dom.navMeta.textContent = `${formatDistance(nearest.distanceM)} from the analysed route. Advisories paused.`;
    refreshGpsChip();
    return;
  }

  const remaining = Math.max(0, route.geometry_length_m - nav.progressM);
  const remainingSeconds =
    route.geometry_length_m > 0
      ? (route.duration_s * remaining) / route.geometry_length_m
      : 0;
  if (remaining <= 25) {
    dom.navInstruction.textContent = "Destination reached";
    dom.navMeta.textContent = "The analysed route has ended. Tap End for a summary.";
  } else if (fix.accuracy > 60) {
    dom.navInstruction.textContent = "Continue on route";
    dom.navMeta.textContent = `${formatDistance(remaining)} remaining · GPS ±${Math.round(fix.accuracy)} m · advisories paused`;
  } else {
    dom.navInstruction.textContent = "Continue on route";
    dom.navMeta.textContent = `${formatDistance(remaining)} remaining · ~${formatDuration(remainingSeconds)} at provider pace · GPS ±${Math.round(fix.accuracy)} m`;
  }

  if (fix.accuracy <= 60 && remaining > 25) {
    updateAdvisory(route, nav.progressM);
  } else {
    hideAdvisory();
  }
  refreshGpsChip();
}

function updateAdvisory(route, progress) {
  const nav = state.nav;
  if (!nav) return;
  const candidate = route.advisories.find(
    (advisory) =>
      progress >= advisory.start_distance_m - advisory.lead_m &&
      progress <= advisory.end_distance_m + advisory.clear_after_m,
  );
  if (!candidate) {
    hideAdvisory();
    return;
  }
  const dismissedUntil = nav.dismissed.get(candidate.id) || 0;
  if (dismissedUntil > Date.now()) {
    hideAdvisory();
    return;
  }
  const ahead = progress < candidate.start_distance_m;
  dom.advisoryBanner.dataset.band = candidate.band;
  dom.advisoryBanner.hidden = false;
  dom.advisoryTitle.textContent = ahead
    ? `${bandLabel(candidate.band)} challenge curve ahead`
    : `${bandLabel(candidate.band)} challenge curve`;
  dom.advisoryText.textContent = ahead
    ? `About ${formatDistance(candidate.start_distance_m - progress)} ahead. Advisory only; based on mapped road shape.`
    : "You are in this curve. Advisory only; based on mapped road shape.";
  renderSpeedNote(route, candidate);
  const stage = alertStage(ahead);
  const key = `${candidate.id}:${stage}`;
  const isNewAdvisory = nav.currentAdvisoryId !== candidate.id;
  if (isNewAdvisory) {
    nav.currentAdvisoryId = candidate.id;
    nav.advisoriesShown.add(candidate.id);
    nav.advisoryStartedAt = Date.now();
  }
  if (nav.cueStageKey !== key) {
    nav.cueStageKey = key;
    fireAlertCue(candidate, ahead);
  }
  state.advisoryActive = true;
  dom.navInstruction.textContent = ahead
    ? `Curve in ${formatDistance(candidate.start_distance_m - progress)}`
    : "Curve in progress";
}

// Fire the staged audio/haptic/visual cues for an advisory crossing, honouring the
// rider's per-channel settings, this device's capabilities, and reduced-motion.
function fireAlertCue(advisory, ahead) {
  const plan = planAlert({
    band: advisory.band,
    ahead,
    settings: state.alertSettings,
    capabilities: state.alertCapabilities,
    reducedMotion: state.reducedMotion,
  });
  dom.advisoryBanner.dataset.intensity = plan.intensity;
  if (plan.fired.haptic && typeof navigator.vibrate === "function") {
    try {
      navigator.vibrate(plan.pattern.vibrate);
    } catch (error) {
      /* vibration can throw if the page is backgrounded; banner already informs */
    }
  }
  if (plan.fired.audio) playToneSequence(plan.pattern.tones);
  // The banner itself is a polite live region, so approaching advisories are already
  // announced. Only the high-band "in the curve now" event escalates to assertive.
  if (plan.assertive) announceAlert(`${bandLabel(advisory.band)} challenge curve now.`);
}

function announceAlert(text) {
  if (!dom.alertAnnounce) return;
  // Clearing then setting forces screen readers to re-announce identical text.
  dom.alertAnnounce.textContent = "";
  window.setTimeout(() => {
    dom.alertAnnounce.textContent = text;
  }, 60);
}

function playToneSequence(tones) {
  if (!audioContext) return;
  try {
    let start = audioContext.currentTime;
    for (const tone of tones) {
      const osc = audioContext.createOscillator();
      const gain = audioContext.createGain();
      osc.type = "sine";
      osc.frequency.value = tone.freq;
      const dur = tone.dur / 1000;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.08, start + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + dur);
      osc.connect(gain).connect(audioContext.destination);
      osc.start(start);
      osc.stop(start + dur);
      start += dur + 0.02;
    }
  } catch (error) {
    /* audio cue is best-effort; the visual banner is the guaranteed channel */
  }
}

// Web Audio must be created/resumed inside a user gesture on iOS Safari.
function unlockAudio() {
  if (state.alertSettings.audio === false) return;
  const Ctor = window.AudioContext || window.webkitAudioContext;
  if (!Ctor) return;
  if (!audioContext) audioContext = new Ctor();
  if (audioContext.state === "suspended") audioContext.resume().catch(() => {});
  state.audioUnlocked = true;
}

function liveSpeedText() {
  const fix = usableFix();
  if (!fix || fix.speed_kmh === null || fix.speed_kmh === undefined) {
    return "Not reported by this device — advisories use the assumed band and say so";
  }
  return `~${Math.round(fix.speed_kmh)} km/h reported by the device (advisory comparison only)`;
}

// Compare the rider's measured GPS speed with the speed band the advisory was// scored at, using the same a = v²/R physics as the baseline. When the device does
// not report a speed this falls back to an explicit disclosure — never a silent
// reuse of the assumed band. The note never tells the rider what speed to ride at
// (master plan R4).
function renderSpeedNote(route, advisory) {
  if (!dom.advisorySpeed) return;
  const fix = usableFix();
  const section = (route.sections || []).find((item) => item.index === advisory.section_index);
  const radius = section ? section.min_radius_m || section.radius_m : null;
  const inputs = state.routeData ? state.routeData.inputs : null;
  const note = speedAwareness({
    speed_kmh: fix ? fix.speed_kmh : null,
    radius_m: radius,
    scored_speed_kmh: inputs ? inputs.speed_kmh : null,
  });
  dom.advisorySpeed.textContent = note.message;
  dom.advisorySpeed.dataset.status = note.status;
  dom.advisorySpeed.hidden = false;
}

function hideAdvisory() {
  dom.advisoryBanner.hidden = true;
  dom.advisoryBanner.dataset.intensity = "";
  if (dom.advisorySpeed) {
    dom.advisorySpeed.hidden = true;
    dom.advisorySpeed.textContent = "";
    dom.advisorySpeed.dataset.status = "";
  }
  state.advisoryActive = false;
  if (state.nav) {
    state.nav.currentAdvisoryId = null;
    state.nav.cueStageKey = null;
  }
  refreshGpsChip();
}

function dismissAdvisory() {
  const nav = state.nav;
  if (!nav || !nav.currentAdvisoryId) return;
  const advisory = nav.route.advisories.find((item) => item.id === nav.currentAdvisoryId);
  const cooldown = advisory ? advisory.cooldown_s : 30;
  nav.dismissed.set(nav.currentAdvisoryId, Date.now() + cooldown * 1000);
  hideAdvisory();
  showToast(`Advisory dismissed for ${Math.round(cooldown)} seconds.`);
}

function showRouterNote(text) {
  dom.routerNoteText.textContent = text;
  dom.routerNote.hidden = false;
  dom.navHud.hidden = true;
  refreshGpsChip();
}

function hideRouterNote() {
  dom.routerNote.hidden = true;
  if (state.nav && state.nav.active) dom.navHud.hidden = false;
}

function endNavigation({ silent = false } = {}) {
  const nav = state.nav;
  if (!nav || !nav.active) return;
  const summary = {
    distanceM: nav.progressM,
    seconds: (Date.now() - nav.startedAt) / 1000,
    advisories: nav.advisoriesShown.size,
    startedAt: nav.startedAt,
    endedAt: Date.now(),
    route: nav.route,
  };
  state.nav = null;
  state.advisoryActive = false;
  dom.advisoryBanner.hidden = true;
  dom.navHud.hidden = true;
  dom.routerNote.hidden = true;
  dom.searchPanel.hidden = false;
  dom.routePanel.hidden = !state.routeData;
  dom.speedSelect.disabled = false;
  refreshGpsChip();
  if (state.routeData) renderRoutePanel();
  if (!silent) renderTripSummary(summary);
}

function renderTripSummary(summary) {
  const content = dom.tripContent;
  clearElement(content);
  const entries = [
    ["Started", new Date(summary.startedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })],
    ["Ended", new Date(summary.endedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })],
    ["Distance navigated", formatDistance(summary.distanceM)],
    ["Duration", formatDuration(summary.seconds)],
    ["Curve advisories shown", String(summary.advisories)],
    ["Route challenge band", bandLabel(summary.route.summary.band)],
  ];
  content.append(detailBlock("Session", [createKv(entries)]));
  content.append(
    detailBlock(
      "Privacy",
      [createElement("p", {
        className: "hint",
        text: "The server does not store a precise movement trail for this session.",
      })],
    ),
  );
  openSheet(dom.tripSheet);
}

/* ---------------------------------------------------------------- detail sheet */

function createKv(entries) {
  const dl = createElement("dl", { className: "kv" });
  entries.forEach(([label, value]) => {
    dl.append(
      createElement("dt", { text: label }),
      createElement("dd", { text: value === undefined || value === null || value === "" ? "—" : String(value) }),
    );
  });
  return dl;
}

function detailBlock(title, nodes) {
  const block = createElement("div", { className: "detail-block" });
  block.append(createElement("h3", { text: title }));
  nodes.forEach((node) => block.append(node));
  return block;
}

function renderDetail() {
  const route = selectedRoute();
  const data = state.routeData;
  if (!route || !data) return;
  const summary = route.summary;
  const model = data.model;
  const content = dom.detailContent;
  clearElement(content);

  const uncertainty = summary.uncertainty
    ? `${toFixed(summary.uncertainty.low, 1)} – ${toFixed(summary.uncertainty.high, 1)} points`
    : "Unavailable";
  content.append(
    detailBlock("Route evidence", [
      createKv([
        ["State", summary.state],
        ["Weighted challenge score", summary.score === null ? "Not scored" : `${toFixed(summary.score, 1)} / 100`],
        ["Challenge band", bandLabel(summary.band)],
        ["Baseline score", summary.baseline_score === null ? "—" : `${toFixed(summary.baseline_score, 1)} / 100`],
        ["Coverage", `${percent(summary.coverage)} (${formatDistance(summary.scored_length_m)} of ${formatDistance(summary.total_length_m)})`],
        ["Unscored length", formatDistance(summary.missing_length_m)],
        ["Uncertainty interval", uncertainty],
        ["Uncertainty coverage", percent(summary.uncertainty_coverage)],
        ["Model-scored sections", String(summary.model_used_sections)],
        ["Baseline fallback sections", String(summary.fallback_sections)],
        ["Outside calibrated radius band", String(summary.ood_sections)],
        ["Provider distance", formatDistance(route.distance_m)],
        ["Provider duration", formatDuration(route.duration_s)],
        ["Provider attribution", data.provider.attribution],
      ]),
    ]),
  );

  const coverage = model.metrics?.uncertainty_coverage;
  const clean = model.metrics?.clean;
  const degraded = model.metrics?.degraded;
  const oodRadius = model.metrics?.ood_radius;
  content.append(
    detailBlock("Model and provenance", [
      createKv([
        ["Model available", model.available ? "Yes" : "No"],
        ["Model", model.model_name],
        ["Label version", model.label_version],
        ["Generator version", model.generator_version || "—"],
        ["Training data", "Synthetic only (generator_v1)"],
        ["Uncertainty method", model.uncertainty_method || "—"],
        ["Nominal interval", percent(model.nominal_coverage)],
        ["Empirical interval coverage", coverage ? percent(coverage.empirical_coverage) : "—"],
        ["Clean holdout MAE", clean ? `${toFixed(clean.mae, 2)} (baseline ${toFixed(clean.baseline_mae, 2)})` : "—"],
        ["Degraded holdout MAE", degraded ? `${toFixed(degraded.mae, 2)} (baseline ${toFixed(degraded.baseline_mae, 2)})` : "—"],
        ["Held-out radius-band MAE", oodRadius ? `${toFixed(oodRadius.mae, 2)} (baseline ${toFixed(oodRadius.baseline_mae, 2)})` : "—"],
      ]),
      createElement("p", {
        className: "hint",
        text: "The physics baseline is the label reference, so clean MAE favours the baseline by construction. The model's measured advantage is on degraded and noisy geometry. No real-ride or crash validation is claimed.",
      }),
    ]),
  );

  content.append(
    detailBlock("Inputs and assumptions", [
      createKv([
        ["Speed band", `${toFixed(data.inputs.speed_kmh, 0)} km/h (${data.inputs.speed_source})`],
        ["Speed is advisory", data.inputs.speed_is_advisory ? "Yes — not a measured rider speed" : "Caller-supplied"],
        ["Road class", data.inputs.road_class_supplied ? "Supplied" : "Unavailable; class code marked missing"],
        ["Grade", data.inputs.grade_supplied ? "Supplied" : "Unavailable; never inferred from a polyline"],
        ["Scoring distance", data.inputs.scoring_distance_basis],
        [
          "Live GPS speed",
          liveSpeedText(),
        ],
      ]),
      assumptionList(data.assumptions),
      createElement("p", { className: "hint", text: data.disclaimer }),
    ]),
  );

  content.append(
    detailBlock("Section-level evidence", [
      createElement("p", {
        className: "hint",
        text: "OOD means the estimated radius lies in the held-out calibration band; uncertainty is widened. Fallback means the model disagreed with the baseline by more than 20 points, so the baseline is displayed.",
      }),
      buildSectionTable(route.sections),
    ]),
  );

  if (data.comparison) {
    const comparison = data.comparison;
    content.append(
      detailBlock("Route comparison", [
        createKv([
          ["State", comparison.state],
          ["Reason", comparison.reason || "—"],
          ["Score gap", comparison.score_gap === null || comparison.score_gap === undefined ? "—" : `${toFixed(comparison.score_gap, 2)} points`],
          ["Coverage spread", comparison.coverage_spread === undefined ? "—" : percent(comparison.coverage_spread)],
          ["Ranking basis", comparison.ranking_basis || "—"],
        ]),
      ]),
    );
  }

  openSheet(dom.detailSheet);
}

function assumptionList(assumptions) {
  const list = createElement("ul");
  assumptions.forEach((text) => list.append(createElement("li", { text })));
  return list;
}

function buildSectionTable(sections) {
  const wrap = createElement("div", { className: "table-wrap" });
  const table = createElement("table", {
    className: "section-table",
    attrs: { "aria-label": "Section-level geometry and model evidence" },
  });
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["#", "Type", "Length", "Radius", "Base", "Model", "Display", "Band", "Status", "Interval"].forEach(
    (label) => {
      const th = createElement("th", { text: label, attrs: { scope: "col" } });
      headRow.append(th);
    },
  );
  head.append(headRow);
  table.append(head);

  const body = document.createElement("tbody");
  sections.forEach((section) => {
    const row = document.createElement("tr");
    if (section.evidence !== "scored") row.className = "row-unavailable";
    let status = "No data";
    if (section.evidence === "scored") {
      if (section.model_status === "model_estimate") status = "ML";
      else if (section.model_status === "baseline_fallback") status = "Fallback";
      else status = "Baseline";
      if (section.ood) status += " · OOD";
    }
    const cells = [
      String(section.index + 1),
      section.kind === "curve" ? "Curve" : "Straight",
      formatDistance(section.length_m),
      section.min_radius_m || section.radius_m
        ? `${Math.round(section.min_radius_m || section.radius_m)} m`
        : "—",
      section.baseline_score === null ? "—" : toFixed(section.baseline_score, 1),
      section.model_score === null ? "—" : toFixed(section.model_score, 1),
      section.display_score === null ? "—" : toFixed(section.display_score, 1),
      bandLabel(section.band),
      status,
      section.uncertainty
        ? `${toFixed(section.uncertainty.low, 0)}–${toFixed(section.uncertainty.high, 0)}`
        : "—",
    ];
    cells.forEach((value, index) => {
      const cell = createElement("td", {
        text: value,
        className: index >= 2 ? "num" : "",
      });
      row.append(cell);
    });
    body.append(row);
  });
  table.append(body);
  wrap.append(table);
  return wrap;
}

/* ---------------------------------------------------------------- alternatives */

function renderAlternatives() {
  const data = state.routeData;
  if (!data) return;
  clearElement(dom.alternativesList);
  dom.alternativesNote.textContent =
    comparisonMessage() || "Route scores describe mapped geometry only; they are not safety rankings.";
  data.routes.forEach((route, index) => {
    const card = createElement("li", {
      className: "route-card",
      attrs: { "data-selected": String(route.id === state.selectedRouteId) },
    });
    const head = createElement("div", { className: "route-card-head" });
    const titleBox = document.createElement("div");
    titleBox.append(
      createElement("p", { className: "route-card-title", text: `Route ${index + 1}` }),
      createElement("p", {
        className: "route-card-meta",
        text:
          route.state === "scored"
            ? `${bandLabel(route.summary.band)} geometry challenge`
            : "Insufficient geometry evidence",
      }),
    );
    const pill = createElement("span", {
      className: `band-pill ${bandClass(route.summary.band)}`,
      text: route.state === "scored" ? bandLabel(route.summary.band) : "Not scored",
    });
    head.append(titleBox, pill);
    const metrics = createElement("div", { className: "route-card-metrics" });
    metrics.append(
      createElement("span", { text: formatDistance(route.distance_m) }),
      createElement("span", { text: formatDuration(route.duration_s) }),
      createElement("span", { text: `${percent(route.summary.coverage)} scored` }),
    );
    const actions = createElement("div", { className: "route-card-actions" });
    const view = createElement("button", {
      className: "secondary",
      text: route.id === state.selectedRouteId ? "Selected" : "View route",
      attrs: { type: "button" },
    });
    view.disabled = route.id === state.selectedRouteId;
    view.addEventListener("click", () => {
      state.selectedRouteId = route.id;
      renderRoute();
      renderAlternatives();
      closeSheet(dom.alternativesSheet);
    });
    actions.append(view);
    card.append(head, metrics, actions);
    dom.alternativesList.append(card);
  });
  openSheet(dom.alternativesSheet);
}

/* ---------------------------------------------------------------- hazards */

function scheduleHazardLoad() {
  if (mapMoveTimer) clearTimeout(mapMoveTimer);
  mapMoveTimer = setTimeout(loadHazards, 500);
}

async function loadHazards() {
  if (map.getZoom() < 10) {
    hazardLayer.clearLayers();
    return;
  }
  if (hazardAbort) hazardAbort.abort();
  const controller = new AbortController();
  hazardAbort = controller;
  const bounds = map.getBounds();
  const params = new URLSearchParams({
    min_lat: bounds.getSouth().toFixed(6),
    min_lon: bounds.getWest().toFixed(6),
    max_lat: bounds.getNorth().toFixed(6),
    max_lon: bounds.getEast().toFixed(6),
    limit: "200",
  });
  try {
    const data = await getJson(`/api/v1/hazards?${params.toString()}`, controller.signal);
    renderHazards(data.hazards);
  } catch (error) {
    if (error.name === "AbortError") return;
    // Community reports are supplementary; failures never alter route scoring.
  }
}

function renderHazards(hazards) {
  hazardLayer.clearLayers();
  hazards.forEach((hazard) => {
    const marker = L.circleMarker([hazard.lat, hazard.lon], {
      radius: 8,
      color: hazard.status === "verified" ? "#0f6b4f" : "#8a5a12",
      weight: 2,
      dashArray: hazard.status === "unverified" ? "3 3" : null,
      fillColor: categoryColor(hazard.category),
      fillOpacity: hazard.status === "verified" ? 0.8 : 0.55,
    });
    marker.bindPopup(buildHazardPopup(hazard));
    marker.addTo(hazardLayer);
  });
}

function buildHazardPopup(hazard) {
  const container = document.createElement("div");
  container.append(
    createElement("div", { className: "popup-title", text: categoryLabel(hazard.category) }),
    createElement("div", {
      className: "popup-meta",
      text: `${hazard.confirmations} confirmation${hazard.confirmations === 1 ? "" : "s"} · ${formatTimeAgo(hazard.created_at)}`,
    }),
  );
  if (hazard.description) {
    container.append(createElement("p", { text: hazard.description }));
  }
  container.append(createElement("p", { className: "popup-note", text: hazard.label }));
  const actions = createElement("div", { className: "popup-actions" });
  if (hazard.status === "verified") {
    container.append(
      createElement("p", { className: "popup-note", text: "Reviewed by an administrator." }),
    );
  } else if (hazard.is_mine) {
    container.append(
      createElement("p", { className: "popup-note", text: "Your report — awaiting review." }),
    );
  } else {
    const confirm = createElement("button", {
      className: "primary",
      text: state.user ? "Confirm sighting" : "Sign in to confirm",
      attrs: { type: "button" },
    });
    confirm.addEventListener("click", () => confirmHazard(hazard, confirm));
    actions.append(confirm);
    container.append(actions);
  }
  return container;
}

async function confirmHazard(hazard, button) {
  if (!state.user) {
    openAuth("login");
    return;
  }
  button.disabled = true;
  button.textContent = "Confirming…";
  try {
    await postJson(`/api/v1/hazards/${hazard.id}/votes`, { action: "confirm" });
    showToast("Confirmation recorded.");
    map.closePopup();
    await loadHazards();
  } catch (error) {
    if (error.status === 401) {
      state.user = null;
      renderAccount();
      openAuth("login");
    } else {
      showToast(error.message);
    }
    button.disabled = false;
    button.textContent = "Confirm sighting";
  }
}

/* ---------------------------------------------------------------- report */

function reportMode() {
  const checked = document.querySelector('input[name="report-location"]:checked');
  return checked ? checked.value : "current_location";
}

function reportCoords() {
  if (reportMode() === "current_location") {
    const fix = usableFix();
    if (!fix) return null;
    return { lat: fix.lat, lon: fix.lon, source: "current_location", accuracy: fix.accuracy };
  }
  const pin = state.reportPin || { lat: map.getCenter().lat, lon: map.getCenter().lng };
  return { lat: pin.lat, lon: pin.lon, source: "map_pin" };
}

function updateReportCoords() {
  if (dom.reportSheet.hidden) return;
  const coords = reportCoords();
  if (!coords) {
    dom.reportCoords.textContent =
      "No recent GPS fix with ±100 m accuracy. Choose the map-pin option.";
    return;
  }
  const label =
    coords.source === "current_location"
      ? `current GPS (±${Math.round(coords.accuracy)} m)`
      : "map pin";
  dom.reportCoords.textContent = `${coords.lat.toFixed(5)}, ${coords.lon.toFixed(5)} · ${label}`;
}

function openReport() {
  if (state.nav && state.nav.active) {
    showToast("End navigation before reporting a hazard.");
    return;
  }
  if (!state.user) {
    state.pendingReport = true;
    openAuth("login");
    return;
  }
  state.pendingReport = false;
  setMessage(dom.reportMessage, "");
  const fix = usableFix();
  const radio = document.querySelector(
    `input[name="report-location"][value="${fix ? "current_location" : "map_pin"}"]`,
  );
  if (radio) radio.checked = true;
  updateReportCoords();
  openSheet(dom.reportSheet);
}

function closeReport() {
  closeSheet(dom.reportSheet);
  setMessage(dom.reportMessage, "");
}

async function submitReport(event) {
  event.preventDefault();
  if (!state.user) {
    state.pendingReport = true;
    openAuth("login");
    return;
  }
  const coords = reportCoords();
  if (!coords) {
    setMessage(dom.reportMessage, "A valid location is required. Enable GPS or pick a map pin.");
    return;
  }
  const description = dom.reportDescription.value.trim();
  dom.reportSubmit.disabled = true;
  dom.reportSubmit.textContent = "Submitting…";
  setMessage(dom.reportMessage, "");
  try {
    await postJson("/api/v1/hazards", {
      category: dom.reportCategory.value,
      description,
      lat: coords.lat,
      lon: coords.lon,
      source: coords.source,
    });
    closeReport();
    dom.reportDescription.value = "";
    state.reportPin = null;
    if (reportMarker) {
      map.removeLayer(reportMarker);
      reportMarker = null;
    }
    showToast("Report submitted — unverified until an administrator reviews it.");
    await loadHazards();
  } catch (error) {
    if (error.status === 401) {
      state.user = null;
      renderAccount();
      state.pendingReport = true;
      openAuth("login");
    } else {
      setMessage(dom.reportMessage, error.message);
    }
  } finally {
    dom.reportSubmit.disabled = false;
    dom.reportSubmit.textContent = "Submit report";
  }
}

function startPinMode() {
  closeSheet(dom.reportSheet);
  state.pinMode = true;
  map.getContainer().style.cursor = "crosshair";
  showToast("Tap the map to place the hazard pin.");
}

map.on("click", (event) => {
  if (!state.pinMode) return;
  state.pinMode = false;
  map.getContainer().style.cursor = "";
  state.reportPin = { lat: event.latlng.lat, lon: event.latlng.lng };
  if (reportMarker) {
    reportMarker.setLatLng(event.latlng);
  } else {
    reportMarker = L.marker(event.latlng).addTo(map);
  }
  reportMarker.bindTooltip("Hazard report pin");
  const radio = document.querySelector('input[name="report-location"][value="map_pin"]');
  if (radio) radio.checked = true;
  openReport();
});

document.querySelectorAll('input[name="report-location"]').forEach((radio) => {
  radio.addEventListener("change", updateReportCoords);
});

/* ---------------------------------------------------------------- auth */

function renderAccount() {
  const user = state.user;
  dom.accountEmail.textContent = user ? user.email : "Not signed in";
  dom.accountRole.textContent = user
    ? user.role === "admin"
      ? "Administrator account"
      : "Rider account"
    : "Sign in to report hazards and confirm community reports.";
  dom.accountAdminLink.hidden = !user || user.role !== "admin";
  dom.logoutButton.hidden = !user;
  dom.deleteAccountButton.hidden = !user;
}

function initAlertRuntime() {
  state.alertCapabilities = detectCapabilities({
    hasVibrate: typeof navigator.vibrate === "function",
    AudioContext: window.AudioContext,
    webkitAudioContext: window.webkitAudioContext,
    Notification: window.Notification,
  });
  const loaded = loadSettings(window.localStorage);
  state.alertSettings = loaded.settings;
  if (window.matchMedia) {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    state.reducedMotion = mq.matches;
    const onChange = (event) => {
      state.reducedMotion = event.matches;
    };
    if (typeof mq.addEventListener === "function") mq.addEventListener("change", onChange);
    else if (typeof mq.addListener === "function") mq.addListener(onChange);
  }
}

function renderSettings() {
  const s = state.alertSettings;
  const caps = state.alertCapabilities;
  dom.settingVisual.checked = s.visual;
  dom.settingAudio.checked = s.audio;
  dom.settingHaptic.checked = s.haptic;
  // Reflect device reality, not just the stored preference.
  dom.settingHaptic.disabled = !caps.haptic;
  dom.settingAudio.disabled = false;
  dom.testAudioButton.hidden = !caps.audio;
  const notes = [];
  if (!caps.haptic) notes.push("This browser has no vibration support; haptic cues fall back to visual/audible.");
  if (!caps.audio) notes.push("This browser cannot play an audio cue; alerts stay visual.");
  if (state.reducedMotion) notes.push("Reduced-motion is on, so alerts do not flash.");
  dom.settingsNote.textContent = notes.join(" ");
}

function updateSetting(key, checked) {
  state.alertSettings = normalizeSettings({ ...state.alertSettings, [key]: checked });
  const persisted = saveSettings(window.localStorage, state.alertSettings);
  if (!persisted && key === "visual") {
    showToast("Settings apply this session only (storage unavailable).");
  }
  if (key === "audio" && checked) unlockAudio();
}

function openSettings() {
  renderSettings();
  openSheet(dom.settingsSheet);
}

function testAudioCue() {
  unlockAudio();
  if (!state.alertCapabilities.audio) {
    showToast("Audio cues are not supported on this device.");
    return;
  }
  if (!audioContext) {
    showToast("Tap the button once more to allow sound, then it will play.");
    return;
  }
  playToneSequence([{ freq: 740, dur: 140 }, { freq: 880, dur: 160 }]);
}

async function refreshAuth() {
  try {
    const data = await getJson("/api/v1/auth/me");
    state.user = data.user;
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) {
      // Network failure leaves the user signed out locally; the cookie is untouched.
    }
    state.user = null;
  }
  renderAccount();
}

function openAuth(mode = "login") {
  state.authMode = mode;
  const login = mode === "login";
  dom.authTitle.textContent = login ? "Sign in" : "Create an account";
  dom.authModeNote.textContent = login
    ? "Sign in to report hazards and confirm community reports."
    : "Create a rider account. Passwords must be at least 10 characters.";
  dom.authSubmit.textContent = login ? "Sign in" : "Create account";
  dom.authSwitch.textContent = login ? "Create an account" : "Back to sign in";
  dom.authPassword.autocomplete = login ? "current-password" : "new-password";
  setMessage(dom.authError, "");
  if (!dom.authDialog.open) dom.authDialog.showModal();
  dom.authEmail.focus();
}

function switchAuthMode() {
  openAuth(state.authMode === "login" ? "register" : "login");
}

async function submitAuth(event) {
  event.preventDefault();
  const email = dom.authEmail.value.trim();
  const password = dom.authPassword.value;
  if (state.authMode === "register" && password.length < 10) {
    setMessage(dom.authError, "Password must be at least 10 characters.");
    return;
  }
  dom.authSubmit.disabled = true;
  dom.authSubmit.textContent = "Working…";
  setMessage(dom.authError, "");
  try {
    const path = state.authMode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
    const data = await postJson(path, { email, password });
    state.user = data.user;
    renderAccount();
    dom.authDialog.close();
    dom.authForm.reset();
    showToast(`Signed in as ${data.user.email}.`);
    await loadHazards();
    if (state.pendingReport) {
      state.pendingReport = false;
      openReport();
    }
  } catch (error) {
    setMessage(dom.authError, error.message);
  } finally {
    dom.authSubmit.disabled = false;
    dom.authSubmit.textContent = state.authMode === "login" ? "Sign in" : "Create account";
  }
}

async function logout() {
  try {
    await api("/api/v1/auth/logout", { method: "POST" });
  } catch (error) {
    // Clear the local view regardless; the server expires sessions.
  }
  state.user = null;
  renderAccount();
  closeSheet(dom.accountSheet);
  showToast("Signed out.");
  await loadHazards();
}

async function deleteAccount() {
  if (!window.confirm("Delete your account? Verified reports are anonymised. This cannot be undone.")) {
    return;
  }
  try {
    await deleteJson("/api/v1/auth/account");
    state.user = null;
    renderAccount();
    closeSheet(dom.accountSheet);
    showToast("Account deleted.");
    await loadHazards();
  } catch (error) {
    showToast(error.message);
  }
}

/* ---------------------------------------------------------------- route reset */

function closeRoute() {
  if (state.nav && state.nav.active) endNavigation({ silent: true });
  if (state.routeController) state.routeController.abort();
  state.routeData = null;
  state.selectedRouteId = null;
  state.routeError = false;
  routeLayer.clearLayers();
  dom.routePanel.hidden = true;
  dom.searchPanel.hidden = false;
  dom.searchInput.value = "";
  state.destination = null;
  if (destinationMarker) {
    map.removeLayer(destinationMarker);
    destinationMarker = null;
  }
  closeSheet(dom.alternativesSheet);
  closeSheet(dom.detailSheet);
}

/* ---------------------------------------------------------------- events */

function bindEvents() {
  dom.searchForm.addEventListener("submit", runSearch);
  dom.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") dom.searchResults.hidden = true;
  });
  dom.locateButton.addEventListener("click", ensureLocation);
  dom.gpsChip.addEventListener("click", ensureLocation);
  dom.reportButton.addEventListener("click", () => {
    if (state.pinMode) {
      state.pinMode = false;
      map.getContainer().style.cursor = "";
      openReport();
      return;
    }
    openReport();
  });
  dom.accountButton.addEventListener("click", () => {
    if (state.user) openSheet(dom.accountSheet);
    else openAuth("login");
  });
  dom.settingsButton.addEventListener("click", () => {
    unlockAudio();
    openSettings();
  });
  dom.settingsClose.addEventListener("click", () => closeSheet(dom.settingsSheet));
  dom.settingVisual.addEventListener("change", (event) => updateSetting("visual", event.target.checked));
  dom.settingAudio.addEventListener("change", (event) => updateSetting("audio", event.target.checked));
  dom.settingHaptic.addEventListener("change", (event) => updateSetting("haptic", event.target.checked));
  dom.testAudioButton.addEventListener("click", testAudioCue);
  dom.routeClose.addEventListener("click", closeRoute);
  dom.startNav.addEventListener("click", () => {
    unlockAudio();
    if (state.routeError) {
      analyzeRoute();
      return;
    }
    beginNavigation();
  });
  dom.alternativesButton.addEventListener("click", () => {
    if (!state.routeData) return;
    renderAlternatives();
  });
  dom.detailButton.addEventListener("click", renderDetail);
  dom.speedSelect.addEventListener("change", () => {
    if (state.routeData && !(state.nav && state.nav.active)) analyzeRoute();
  });
  dom.advisoryDismiss.addEventListener("click", dismissAdvisory);
  dom.navEnd.addEventListener("click", () => endNavigation());
  dom.routerRetry.addEventListener("click", () => {
    if (!state.nav || !state.nav.active) return;
    showToast("Recalculating route…");
    analyzeRoute({ forNavigation: true });
  });
  dom.alternativesClose.addEventListener("click", () => closeSheet(dom.alternativesSheet));
  dom.detailClose.addEventListener("click", () => closeSheet(dom.detailSheet));
  dom.tripClose.addEventListener("click", () => closeSheet(dom.tripSheet));
  dom.accountClose.addEventListener("click", () => closeSheet(dom.accountSheet));
  dom.logoutButton.addEventListener("click", logout);
  dom.deleteAccountButton.addEventListener("click", deleteAccount);
  dom.reportClose.addEventListener("click", closeReport);
  dom.reportCancel.addEventListener("click", closeReport);
  dom.reportForm.addEventListener("submit", submitReport);
  dom.reportPick.addEventListener("click", startPinMode);
  dom.authForm.addEventListener("submit", submitAuth);
  dom.authCancel.addEventListener("click", () => dom.authDialog.close());
  dom.authSwitch.addEventListener("click", switchAuthMode);
  map.on("moveend", () => {
    scheduleHazardLoad();
    updateReportCoords();
  });
  map.on("dragstart", () => {
    state.follow = false;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (state.pinMode) {
      state.pinMode = false;
      map.getContainer().style.cursor = "";
      openReport();
      return;
    }
    if (dom.authDialog.open) return;
    if (!dom.reportSheet.hidden) {
      closeReport();
      return;
    }
    [
      dom.alternativesSheet,
      dom.detailSheet,
      dom.accountSheet,
      dom.tripSheet,
      dom.settingsSheet,
    ].forEach((sheet) => {
      if (!sheet.hidden) closeSheet(sheet);
    });
  });
  window.addEventListener("offline", () => {
    dom.connectionBanner.hidden = false;
    showToast("Offline: search, routing, and hazard updates are unavailable.");
  });
  window.addEventListener("online", () => {
    dom.connectionBanner.hidden = true;
    showToast("Back online.");
    loadHazards();
  });
}

async function boot() {
  initAlertRuntime();
  bindEvents();
  refreshGpsChip();
  if (!navigator.onLine) dom.connectionBanner.hidden = false;
  await refreshAuth();
}

boot();
