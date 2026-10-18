# Reproduce

From the project root, with pinned dependencies installed:

```powershell
python -m ml.train --seed 42 --per-type 140
python -m ml.evaluate_seeds
python -m pytest
```

Training is offline-only. The runtime loads `ml/artifacts/model.joblib` once at startup
and never imports `ml/` modules.

`ml.evaluate_seeds` retrains + re-evaluates over 5 data seeds (42–46) and writes
`multi_seed_metrics.json` with headline metrics as mean ± 95% CI — the cross-seed numbers
quoted in the Model Card and `GEOMETRY_ML_DESIGN.md` come from that file, not from a single
seed.

Dataset hash: `5e92447a370b2646c8929a434a577f9decf5694afb28e3c2d76ce93415d5db9d`
