// Mock-provider harness for the rider E2E suite. Everything intercepted here is
// labelled `mock`: it never reaches OSRM/Nominatim and never runs the model. These
// tests exercise the FRONTEND (nav state machine, layout, alert cue playback); the
// analyze *contract* itself is covered offline by tests/test_api_routes.py.

const PNG_1PX = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);

const R = 6371000;
const toRad = (d) => (d * Math.PI) / 180;

export function haversine(a, b) {
  const dLat = toRad(b[0] - a[0]);
  const dLon = toRad(b[1] - a[1]);
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

// A straight south-bound polyline; each 0.002° lat step is ~222 m.
export function buildGeometry(n = 8) {
  const pts = [];
  let lat = 17.42;
  const lon = 78.45;
  for (let i = 0; i < n; i += 1) {
    pts.push([lat, lon]);
    lat -= 0.002;
  }
  return pts;
}

export function geomLength(pts) {
  let total = 0;
  for (let i = 1; i < pts.length; i += 1) total += haversine(pts[i - 1], pts[i]);
  return total;
}

export function progressAt(pts, index) {
  return geomLength(pts.slice(0, index + 1));
}

function summary(band) {
  return {
    state: "scored",
    coverage: 0.99,
    scored_length_m: 1540,
    total_length_m: 1556,
    missing_length_m: 16,
    score: band === "high" ? 61.5 : 33.1,
    band,
    baseline_score: 30.2,
    uncertainty: { low: 28.0, high: 40.0 },
    uncertainty_coverage: 0.84,
    model_available: true,
    model_used_sections: 4,
    fallback_sections: 0,
    ood_sections: 0,
    provenance: ["mock"],
    reason: null,
  };
}

function geometryQuality() {
  return {
    status: "usable",
    point_count: 8,
    duplicate_points_removed: 0,
    median_spacing_m: 222.4,
    max_gap_m: 222.6,
    coarse: false,
    long_gap_count: 0,
    score: 0.97,
    issues: [],
  };
}

function section(i, band) {
  return {
    index: i,
    kind: i === 3 ? "curve" : "straight",
    start_index: i,
    end_index: i + 1,
    length_m: 222,
    start_distance_m: i * 222,
    radius_m: i === 3 ? 40 : null,
    min_radius_m: i === 3 ? 38 : null,
    p10_radius_m: i === 3 ? 45 : null,
    heading_change_deg: i === 3 ? 34 : 0,
    curve_length_m: i === 3 ? 220 : 0,
    curvature_std: 0,
    max_turn_deg: i === 3 ? 34 : 0,
    transition_abruptness: 0,
    spiral_like: false,
    gap_before_m: null,
    sequence_index: i,
    evidence: "scored",
    provenance: ["mock"],
    baseline_score: 30,
    model_score: band === "high" ? 61 : 33,
    display_score: band === "high" ? 61 : 33,
    band,
    uncertainty: { low: 28, high: 40 },
    disagreement: false,
    ood: false,
    model_status: "model_estimate",
    geometry_quality: { median_spacing_m: 222.4, max_gap_m: 222.6, coarse: false, long_gap: false },
  };
}

export function analyzePayload({ pts, advisoryBand = null }) {
  const len = geomLength(pts);
  const band = advisoryBand || "low";
  const advisories = [];
  if (advisoryBand) {
    const at = progressAt(pts, 3);
    advisories.push({
      id: "adv-1",
      section_index: 3,
      start_distance_m: at,
      end_distance_m: at + 80,
      lead_m: 200,
      clear_after_m: 100,
      cooldown_s: 30,
      band: advisoryBand,
      score: advisoryBand === "high" ? 61.5 : 33.1,
      uncertainty: { low: 28, high: 40 },
      message: "Sharp curve ahead. Slow down.",
      provenance: "computed_geometry",
    });
  }
  return {
    state: "scored",
    generated_at: new Date().toISOString(),
    provider: { name: "osrm", attribution: "mock", fetched_at: new Date().toISOString(), cached: false },
    model: {
      available: true,
      reason: null,
      model_name: "hist_gradient_boosting",
      label_version: "label_v1",
      baseline_version: "physics_v2r_v1",
      generator_version: null,
      artifact_version: 1,
      synthetic_training: true,
      uncertainty_method: "split_conformal_residual",
      nominal_coverage: 0.8,
      metrics: null,
      feature_count: 22,
      monotonic_constraints: {},
      require_model: false,
    },
    inputs: {
      speed_kmh: 45,
      speed_source: "default",
      speed_is_advisory: true,
      road_class_supplied: false,
      grade_supplied: false,
      scoring_distance_basis: "mapped route geometry length",
    },
    routes: [
      {
        id: "r1",
        state: "scored",
        distance_m: len,
        duration_s: 130,
        geometry_length_m: len,
        geometry_quality: geometryQuality(),
        geometry: pts,
        summary: summary(band),
        sections: [section(0, band), section(1, band), section(2, band), section(3, band)],
        advisories,
        provider_route_index: 0,
        error: null,
      },
    ],
    comparison: null,
    assumptions: ["mock harness assumption"],
    disclaimer:
      "Geometry challenge indicator — not an accident probability. Advisory based on mapped road shape; real conditions may differ.",
  };
}

const GEOCODE = {
  results: [
    {
      display_name: "Charminar, Hyderabad, Telangana, India",
      lat: 17.3616,
      lon: 78.4747,
      category: "tourism",
      type: "attraction",
      importance: 0.7,
    },
  ],
  provider: { name: "nominatim", attribution: "mock", fetched_at: new Date().toISOString(), cached: false },
};

// Install all browser-level mocks on a context. Returns a `seen` recorder for asserts.
export async function installMocks(context, { analyze = "scored", authed = false } = {}) {
  const seen = { analyzeClientHeader: null, analyzeBody: null, analyzeMethod: null };

  await context.route("**/tile.openstreetmap.org/**", (route) =>
    route.fulfill({ status: 200, contentType: "image/png", body: PNG_1PX }),
  );

  await context.route("**/api/v1/auth/me", (route) =>
    authed
      ? route.fulfill({ json: { user: { email: "rider@example.test", role: "rider", id: 1 } } })
      : route.fulfill({ status: 401, json: { error: { code: "auth_failure", message: "Authentication required" } } }),
  );

  await context.route("**/api/v1/geocode**", (route) => route.fulfill({ json: GEOCODE }));

  await context.route("**/api/v1/routes/analyze", async (route) => {
    const req = route.request();
    seen.analyzeClientHeader = req.headers()["x-roadguard-client"] ?? null;
    seen.analyzeMethod = req.method();
    try {
      seen.analyzeBody = await req.postDataJSON();
    } catch {
      seen.analyzeBody = null;
    }
    if (analyze === "insufficient") {
      return route.fulfill({
        status: 422,
        json: { error: { code: "insufficient_evidence", message: "No usable route geometry evidence." } },
      });
    }
    if (analyze === "provider") {
      return route.fulfill({
        status: 503,
        json: { error: { code: "provider_unavailable", message: "Routing provider is temporarily unavailable." } },
      });
    }
    return route.fulfill({ json: analyze });
  });

  await context.route("**/api/v1/hazards**", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        json: { id: "h1", verification_state: "unverified", category: "pothole", lat: 17.42, lon: 78.45 },
      });
    }
    return route.fulfill({ json: { hazards: [] } });
  });

  return seen;
}

// Replace navigator.geolocation with a scripted source and expose __feedFix(lat,lon,acc,advanceMs).
export async function installGeolocation(context) {
  await context.addInitScript(() => {
    const watchers = [];
    let id = 0;
    const sim = { t: Date.now() };
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      enumerable: true,
      get() {
        return {
          watchPosition(success) {
            watchers.push(success);
            id += 1;
            return id;
          },
          clearWatch() {},
          getCurrentPosition() {},
        };
      },
    });
    window.__feedFix = (lat, lon, accuracy = 10, advanceMs = 0, speedKmh = null) => {
      sim.t += advanceMs;
      const position = {
        coords: {
          latitude: lat,
          longitude: lon,
          accuracy,
          altitude: null,
          altitudeAccuracy: null,
          heading: null,
          // GeolocationCoordinates.speed is m/s above ground; null = not measured.
          speed: Number.isFinite(speedKmh) ? speedKmh / 3.6 : null,
        },
        timestamp: sim.t,
      };
      watchers.slice().forEach((cb) => cb(position));
    };
  });
}

export async function seedSettings(context, settings) {
  await context.addInitScript(
    (payload) => {
      window.localStorage.setItem("roadguard.alertSettings.v1", JSON.stringify(payload));
    },
    settings,
  );
}

/* ---------------------------------------------------------------- admin console */

const ADMIN_MODEL = {
  available: true,
  reason: null,
  model_name: "hist_gradient_boosting",
  label_version: "label_v1",
  baseline_version: "physics_v2r_v1",
  generator_version: "gen_v1",
  uncertainty_method: "split_conformal_residual",
  nominal_coverage: 0.8,
  feature_count: 22,
  require_model: false,
  artifact_version: 1,
  metrics: {
    clean: { mae: 0.573, baseline_mae: 27.826, ml_minus_baseline_mae: -27.253 },
    degraded: { mae: 14.142, baseline_mae: 27.826 },
    uncertainty_coverage: { empirical_coverage: 0.84, nominal_coverage: 0.8 },
    ood_radius: { model_mae: 20.307, baseline_mae: 12.647 },
  },
};

const OVERVIEW = {
  users: { total: 3, active: 3, riders: 2, admins: 1 },
  hazards: { unverified: 2, verified: 1, rejected: 0, expired: 0 },
  model: ADMIN_MODEL,
  database: { ok: true, schema_version: 1, users: 3, hazards: 3, error: null },
  uptime_s: 1234,
  started_at: new Date().toISOString(),
  recent_audit: [
    {
      id: "a1",
      created_at: new Date().toISOString(),
      actor_user_id: 1,
      action: "hazard_verified",
      target_type: "hazard",
      target_id: "h1",
      details: '{"note":"confirmed by admin"}',
    },
  ],
};

const HAZARDS = {
  hazards: [
    {
      id: "h1",
      category: "pothole",
      description: "Deep pothole near the junction.",
      lat: 17.42,
      lon: 78.45,
      source: "current_location",
      status: "unverified",
      confirmations: 0,
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 86400000).toISOString(),
    },
    {
      id: "h2",
      category: "waterlogging",
      description: "Flooded underpass.",
      lat: 17.36,
      lon: 78.47,
      source: "map_pin",
      status: "verified",
      confirmations: 3,
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + 86400000).toISOString(),
    },
  ],
  count: 2,
};

const USERS = [
  { id: 1, email: "admin@example.test", role: "admin", is_active: true, created_at: new Date().toISOString() },
  { id: 2, email: "rider@example.test", role: "rider", is_active: true, created_at: new Date().toISOString() },
];

const AUDIT = {
  events: OVERVIEW.recent_audit,
  count: 1,
};

const DIAGNOSTICS = {
  app: "RoadGuard AI",
  version: "0.1.0",
  env: "test",
  python: "3.12",
  platform: "linux",
  process_id: 42,
  started_at: new Date().toISOString(),
  uptime_s: 1234,
  database: { ok: true, schema_version: 1, path_exists: true, users: 3, hazards: 3, error: null },
  provider_endpoints: { nominatim: "https://nominatim.invalid", osrm: "https://osrm.invalid" },
  provider_cache_entries: 0,
  rate_limits: { route_per_minute: 20, hazard_per_hour: 10, login_per_minute: 5 },
  model: ADMIN_MODEL,
};

// Install admin-console mocks. `me` decides the initial gate; login always succeeds as admin.
export async function installAdminMocks(context, { me = "401" } = {}) {
  const seen = { loginClientHeader: null, moderateBody: null, moderateMethod: null };

  if (me === "401") {
    await context.route("**/api/v1/auth/me", (route) =>
      route.fulfill({ status: 401, json: { error: { code: "auth_failure", message: "Authentication required" } } }),
    );
  } else if (me === "rider") {
    await context.route("**/api/v1/auth/me", (route) =>
      route.fulfill({ json: { user: { id: 2, email: "rider@example.test", role: "rider" } } }),
    );
  } else {
    await context.route("**/api/v1/auth/me", (route) =>
      route.fulfill({ json: { user: { id: 1, email: "admin@example.test", role: "admin" } } }),
    );
  }

  await context.route("**/api/v1/auth/login", async (route) => {
    seen.loginClientHeader = route.request().headers()["x-roadguard-client"] ?? null;
    return route.fulfill({ json: { user: { id: 1, email: "admin@example.test", role: "admin" }, session_expires_in_s: 43200 } });
  });

  await context.route("**/api/v1/auth/logout", (route) => route.fulfill({ json: { ok: true } }));

  await context.route("**/api/v1/admin/overview", (route) => route.fulfill({ json: OVERVIEW }));
  await context.route("**/api/v1/admin/hazards**", (route) => route.fulfill({ json: HAZARDS }));
  await context.route("**/api/v1/admin/users", (route) => route.fulfill({ json: USERS }));
  await context.route("**/api/v1/admin/audit**", (route) => route.fulfill({ json: AUDIT }));
  await context.route("**/api/v1/admin/diagnostics", (route) => route.fulfill({ json: DIAGNOSTICS }));

  await context.route("**/api/v1/admin/hazards/*/moderate", async (route) => {
    seen.moderateMethod = route.request().method();
    try {
      seen.moderateBody = await route.request().postDataJSON();
    } catch {
      seen.moderateBody = null;
    }
    return route.fulfill({ json: { ok: true } });
  });

  await context.route("**/api/v1/admin/users/*/active", (route) => route.fulfill({ json: { ok: true } }));

  return seen;
}
