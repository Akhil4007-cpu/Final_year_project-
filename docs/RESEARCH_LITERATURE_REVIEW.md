# RESEARCH_LITERATURE_REVIEW

Scope: geometry-driven curve risk, surrogate safety measures from telematics, uncertainty
quantification, and the leakage/evaluation pitfalls that apply to a synthetic-data
advisory. Full bibliographic URLs and access dates (all **2026-10-17**) are in
[REFERENCES_VERIFIED.md](REFERENCES_VERIFIED.md); this file does the per-source analysis.

> **Verification honesty.** The entries below were confirmed to exist and read at the
> abstract/summary level via web search on 2026-10-17. Quantitative "performance as
> reported" is taken from what the abstracts/metadata stated; where a full-text figure was
> not read, it is marked *abstract-level*. No number is asserted as this project's result.

## Per-source review

### 1. FHWA-HRT-13-077 (Bauer et al., 2014)
- **Question:** how do horizontal-curve + grade combinations affect crash experience on
  rural two-lane highways?
- **Method:** empirical crash-analysis report by FHWA (historical crash data, roadway
  inventory).
- **Data:** U.S. rural highway crash records + geometric inventory. **Not** Indian roads.
- **Findings (abstract-level):** curve/grade combinations materially affect crash rates.
- **Limitation:** historical-crash regression; jurisdiction-specific; needs crash records.
- **Relevance:** grounds the premise that curve geometry matters for safety experience.
- **Does NOT establish:** a real-time, sensor-free rider score, nor Indian transferability.
  RoadGuard uses none of its crash data (R2).

### 2. Nadimi et al. (2025), *Assessing safety in horizontal curves using surrogate measures*
- **Question:** can surrogate measures characterise horizontal-curve safety?
- **Method:** surrogate-measure analysis (behaviour proxies rather than crash counts).
- **Data:** traffic/surrogate observations (not crash tallies).
- **Findings (abstract-level):** surrogate metrics track curve-safety behaviour.
- **Limitation:** requires observations RoadGuard does not collect.
- **Relevance:** motivates the *advisory* (behavioural cue) framing over a crash claim.
- **Does NOT establish:** that a polyline-only geometry score equals a sensor surrogate.

### 3. Hossain & Lee (2026), harsh-braking telematics surrogate
- **Question:** do connected-vehicle harsh-braking events proxy crash risk?
- **Method:** telematics harsh-event analysis on New Jersey interstates.
- **Data:** connected-vehicle telemetry.
- **Findings (abstract-level):** harsh-braking frequency is a usable proactive surrogate.
- **Limitation:** needs onboard telemetry / CV infrastructure.
- **Relevance:** shows the active-research direction; RoadGuard intentionally ships a
  **lower-bar** geometry-only cue because it collects no telemetry (privacy).
- **Does NOT establish:** anything achievable without telematics data.

### 4. Ma et al. (2023), dynamic sharp-curve risk prediction
- **Question:** predict driving risk on sharp curves in a connected-vehicle environment.
- **Method:** dynamic risk model combining geometry and CV data.
- **Data:** connected-vehicle + curve data.
- **Findings (abstract-level):** geometry-informed risk models are feasible with CV input.
- **Limitation:** depends on real-time vehicle state the project does not have.
- **Relevance:** closest prior art to RoadGuard's *intent*; the gap is the data it assumes.
- **Does NOT establish:** that removing the CV/speed-input component keeps accuracy — RoadGuard
  compensates by (a) an assumed speed band flagged as an assumption and (b) explicit
  uncertainty, and never claims crash probability (R4).

### 5. Lei et al. (2018), distribution-free conformal regression
- **Question:** model-agnostic, distribution-free predictive intervals with coverage.
- **Method:** conformal inference (split / inductive variant).
- **Evaluation:** finite-sample coverage guarantee under exchangeability.
- **Relevance:** the exact method in `app/model.py` (split-conformal absolute residual,
  nominal 0.8, empirical 0.8403 at seed 42; mean ± 95% CI across 5 data seeds in
  `multi_seed_metrics.json` — measured).
- **Does NOT establish:** coverage when exchangeability fails — i.e. OOD curve types, where
  measured empirical coverage drops to 0.6786. Disclosed, not hidden.

### 6. Roberts et al. (2017), cross-validation under structure / leakage
- **Question:** how to CV data with spatial/temporal/hierarchical dependence.
- **Relevance:** justifies the **scenario-based** train/calibration/test/ood split (zero
  train–test scenario overlap, `eval_results.json.leakage_audit`).
- **Does NOT establish:** a real geographic autocorrelation range (data are synthetic).

### 7–11. Standards / docs (ODbL, Nominatim policy, OSRM, scikit-learn monotonic, MDN
Geolocation) — operational constraints, not research findings; summarised in
[REFERENCES_VERIFIED.md](REFERENCES_VERIFIED.md). These dictate attribution strings,
rate/User-Agent discipline, monotonic `monotonic_cst` support, and GPS API semantics.

## Comparative analysis table

| Paper / Source | Year | Method | Data | Performance as reported | Key limitation | Row relevance to RoadGuard |
|---|---|---|---|---|---|---|
| FHWA-HRT-13-077 | 2014 | crash regression | U.S. rural crashes | *abstract-level* | needs crash data, US | premise only |
| Nadimi et al. | 2025 | surrogate measures | traffic obs | *abstract-level* | needs observations | advisory framing |
| Hossain & Lee | 2026 | telematics harsh events | CV telemetry | *abstract-level* | needs telemetry | motivates privacy-first lower bar |
| Ma et al. | 2023 | dynamic CV risk | CV + geometry | *abstract-level* | needs real-time speed | closest prior art |
| Lei et al. | 2018 | conformal regression | theory/any | coverage guarantee (exchange.) | fails under shift | uncertainty method |
| Roberts et al. | 2017 | block CV | structured | avoids leakage | needs spatial ranges | split design |
| **Proposed (RoadGuard GACE)** | — | geometry + conformal + baseline fallback | **synthetic only** | **"to be evaluated" against real data** | no real-road validation; not a crash model | this project |

The Proposed row deliberately reports **"to be evaluated"** for real-world performance —
RoadGuard makes **no** accuracy claim on Indian roads (R1, R4). Its measured numbers are
agreement-with-physics-label on synthetic data only (see
[GEOMETRY_ML_LIMITATIONS.md](GEOMETRY_ML_LIMITATIONS.md)).
