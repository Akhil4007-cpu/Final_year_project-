# REFERENCES_VERIFIED

Every entry below was located and opened via web search on **2026-10-17**. The access
date, URL, and a one-line "verified fact" are given for each so the viva panel can
re-check them. No citation here is invented, and no DOI is asserted unless it appeared on
the page itself. Rule R1 governs this file: nothing is fabricated to look scholarly.

## Peer-reviewed / official research

1. **Bauer, K.M., et al. (2014).** *Safety Effects of Horizontal Curve and Grade
   Combinations on Rural Two-Lane Highways.* Report **FHWA-HRT-13-077**, U.S. Federal
   Highway Administration.
   URL: https://rosap.ntl.bts.gov/view/dot/35716 · list: https://www.fhwa.dot.gov/publications/lists/021.cfm
   Verified: real FHWA report; quantifies safety effects of horizontal/vertical alignment
   combinations. **Used for:** the premise that curve geometry relates to crash *experience*
   on rural highways. **Does NOT establish:** a rider-facing real-time geometry score, nor
   transferability to Indian mixed-traffic roads.

2. **Nadimi, N., et al. (2025).** *Assessing safety in horizontal curves using surrogate
   measures.* Scientific Reports.
   URL: https://www.nature.com/articles/s41598-025-97384-7
   Verified: exists, 2025, ~11 citations. **Used for:** surrogate-measure framing (behaviour
   proxies, not raw crash counts). **Does NOT establish:** that a polyline-only score without
   onboard sensors predicts crashes.

3. **Hossain, M.T., & Lee, et al. (2026).** *Evaluating Harsh Braking Events as a Surrogate
   Measure of Crash Risk Using Connected-Vehicle Telematics.* Safety (MDPI) 8(3):68.
   URL: https://www.mdpi.com/2624-8921/8/3/68
   Verified: 2026, New Jersey interstate telematics study. **Used for:** evidence that
   harsh-event telematics is an active research line. **Does NOT establish:** anything
   obtainable without connected-vehicle telemetry, which RoadGuard deliberately does not
   collect.

4. **Ma, Y., et al. (2023).** *A dynamic method to predict driving risk on sharp curves.*
   Accident Analysis & Prevention.
   URL: https://www.sciencedirect.com/science/article/abs/pii/S0001457523002750
   Verified: 2023, ~37 citations, connected-vehicle sharp-curve risk. **Used for:** the
   gap this project narrows (curve risk without a V2X/telematics stack). **Does NOT
   establish:** that the geometry-only advisory matches sensor-based risk accuracy.

5. **Lei, J., G'Sell, M., Foygel Barber, R., & Tibshirani, R. (2018).** *Distribution-Free
   Predictive Inference for Regression.* JASA.
   URL (author PDF): https://www.stat.cmu.edu/~ryantibs/papers/conformal.pdf
   Verified: the conformal-regression foundation (~2216 citations). **Used for:** the
   split-conformal interval method in `app/model.py`. **Does NOT establish:** coverage under
   the distribution shift present in out-of-distribution curve types — which is why the OOD
   empirical-coverage drop (0.5929) is disclosed rather than hidden.

6. **Roberts, D.R., et al. (2017).** *Cross-validation strategies for data with temporal,
   spatial, hierarchical, or phylogenetic structure.* Ecography.
   URL: https://www.researchgate.net/publication/311523792_Cross-validation_strategies_for_data_with_temporal_spatial_hierarchical_or_phylogenetic_structure
   Verified: canonical block-CV / leakage reference. **Used for:** justifying the scenario-
   based (not row-random) split and the zero-leakage audit. **Does NOT establish:** a real
   spatial autocorrelation range for Indian roads (data are synthetic).

## Official documentation / standards

7. **OpenStreetMap Foundation — ODbL Licence/Attribution Guidelines.**
   URL: https://osmfoundation.org/wiki/Licence/Attribution_Guidelines ·
   https://wiki.openstreetmap.org/wiki/Open_Database_License
   Verified: ODbL requires visible attribution ("© OpenStreetMap contributors"). **Used
   for:** the attribution strings in `app/providers.py`.

8. **Nominatim Usage Policy (Geocoding Policy).**
   URL: https://operations.osmfoundation.org/policies/nominatim/ · https://nominatim.org/
   Verified: single request thread, identify with a contact User-Agent, no distributed bulk
   use. **Used for:** the rate/User-Agent design; **constrains** public launch (self-host
   before scale).

9. **OSRM routing engine (project).** URL: http://project-osrm.org/ (demo at
   router.project-osrm.org). Verified as the routing provider referenced in config.
   **Constrains:** demo instance has usage limits; self-host/commercial plan required
   pre-launch (see KNOWN_ISSUES #7).

10. **scikit-learn — `HistGradientBoostingRegressor` and monotonic constraints.**
    URL: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html ·
    https://scikit-learn.org/stable/auto_examples/ensemble/plot_monotonic_constraints.html
    Verified: `monotonic_cst` support in the histogram gradient-boosting estimator. **Used
    for:** the physics-informed monotonic guardrails in `features.py` / `model.py`.

11. **MDN Web Docs — Geolocation API.**
    URL: https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API ·
    https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/watchPosition
    Verified: `watchPosition` semantics, accuracy field, `enableHighAccuracy`. **Used for:**
    the client GPS FSM (accuracy/staleness/plausibility gates).

## Plan-named source NOT independently verified

The master plan also named a **"Nadimi 2025" telematics surrogate/harsh-event paper**
distinct from #2. I could **not** independently confirm a second Nadimi telematics/harsh-
event work under that exact framing; #2 (Nadimi 2025, horizontal curves) and #3 (Hossain
& Lee 2026, harsh-braking telematics) are the verified works that cover those two topics.
Stated plainly rather than citing an unverifiable item (R1).

## Tooling (versioned, in `requirements.txt`)

FastAPI 0.141.1 · Pydantic 2.13.5 · Uvicorn 0.52.4 · httpx 0.28.1 · NumPy 1.26.4 ·
scikit-learn 1.7.2 · joblib 1.5.3 · PyYAML 6.0.3 · Leaflet 1.9.4 (vendored, BSD-2) ·
SQLite (WAL). Python 3.10.10.
