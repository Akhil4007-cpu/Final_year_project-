# DATA_AND_PROVENANCE

RoadGuard keeps every number traceable to the channel that produced it. This is the
mechanism behind rule R1 (no fabricated data) and R7 (stated basis). The
`Provenance` enum in `app/provenance.py` defines the channels; nothing is merged or
silently promoted between them.

## The five evidence channels (+ an explicit absence state)

| Provenance tag | What it is | Source in code | Never conflated with |
|---|---|---|---|
| `provider` | Third-party geocoding / routing responses | `app/providers.py` (Nominatim, OSRM) | our own measurement |
| `computed_geometry` | Geometry we derive ourselves from a polyline (radius, heading, curvature) | `app/geo.py`, `app/baseline.py` | real-world observation |
| `model_estimate` | GACE learned score with its conformal interval | `app/model.py` | physics baseline or accident risk |
| `user_submitted` | Community hazard reports | `app/hazards.py` | verified fact (see R6) |
| `synthetic_experimental` | Training data / offline evaluation only | `ml/` | runtime observation (see R10) |
| `unavailable` | Explicit absence of evidence | `app/errors.py`, `EvidenceState` | a zero or "safe" score (R3/R5) |

`EvidenceState` ∈ {`scored`, `insufficient_evidence`, `unavailable`} — a section/route
that cannot be scored reports one of the latter two, never a fabricated value.

## How provenance is attached

- `analysis.py` tags each scored section `["computed_geometry", "model_estimate"]` when
  the model contributes, or `["computed_geometry"]` when it falls back to baseline, or
  `["unavailable"]` when geometry cannot be scored.
- `aggregation.py` accumulates the channel list on the route roll-up so the rider can see
  *which* channels support the route number.
- `advisory.py` stamps each advisory card with `model_estimate` provenance and the
  advisory-only wording.
- `hazards.py` tags reports `user_submitted`; the UI shows them as
  "Community report — unverified" until an admin verifies, so an unverified report is
  never presented as confirmed (R6).

## Attribution and licensing (ODbL)

- Geocoding and map tiles: **© OpenStreetMap contributors (ODbL)** —
  `OSM_ATTRIBUTION` in `app/providers.py`, surfaced on `/api/v1/hazards` and geocode
  responses.
- Routing: **"Routing by OSRM; map data © OpenStreetMap contributors (ODbL)"** —
  `OSRM_ATTRIBUTION`, surfaced on route-analysis responses (`app/api.py:376`).
- OSRM is the public demo (`router.project-osrm.org`); **before public launch** the plan
  requires a self-host or commercial routing plan because the demo has usage limits. Not
  yet done — recorded in [LOOP_STATE.md](LOOP_STATE.md).
- Leaflet 1.9.4 is vendored locally (BSD-2). No third-party JS is loaded at runtime.

## Synthetic training data provenance

- Versioned: `generator_v1` + `label_v1`, seed 42, 1,180 rows, 22 features (incl. the
  `physics_prior` the model corrects), SHA-256
  `5e92447a370b2646c8929a434a577f9decf5694afb28e3c2d76ce93415d5db9d`
  (`ml/artifacts/dataset_manifest.json`).
- Scenario types: straight, simple_arc, spiral, reverse_curve, compound, hairpin,
  urban_turn. OOD slices: type `hairpin`, radius band [300, 700] m.
- These rows are `synthetic_experimental`. They are **never** presented as real road
  observations, and the `ml/` package is never imported by the runtime server (enforced
  by `test_runtime_never_imports_ml_training`, R10).

## What is deliberately absent

No accident statistics, no historical crash CSV, no "blackspot" tables, no weather, no
live traffic, no vehicle telemetry. These are out of scope by rule, and their absence is
disclosed rather than filled with invented data (R2).
