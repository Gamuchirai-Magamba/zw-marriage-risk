"""
Step 2D, part 1: freeze the model output into files the app can serve.

    python export_app_data.py

Why this exists
---------------
The deployed service must NOT need the microdata. Two reasons:

1. **Licence.** DHS and MICS data cannot be redistributed. A container
   with survey microdata inside it is redistribution.
2. **Engineering.** Fitting a model on every request, or on every cold
   start, is slow and pointless when the inputs never change.

So the pipeline splits cleanly:

    microdata  ->  fit_model.py  ->  app_data/*.json  ->  API + map
    (private)      (your laptop)     (derived, safe)      (deployed)

Everything in ``app_data/`` is a derived aggregate at district level.
Nothing in it can be traced to a respondent.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import geopandas as gpd

import paths
from zw_marriage_risk import data, explain, model

warnings.filterwarnings("ignore")

APP = Path("app_data")
APP.mkdir(exist_ok=True)

#: Douglas-Peucker tolerance in degrees. The full boundary file is 6 MB;
#: simplified it is well under 1 MB, which matters for a web map on a
#: Zimbabwean mobile connection.
SIMPLIFY_TOLERANCE = 0.005


print("fitting...")
df = data.build_analysis_table(
    paths.DHS_WOMEN, paths.DHS_GPS,
    paths.MICS_WOMEN, paths.MICS_GPS, paths.DISTRICTS,
)
cov = data.district_covariates(paths.DHS_GEOCOV, paths.DHS_GPS, paths.DISTRICTS)
fitted = model.fit(df, cov)

est = model.district_estimates(fitted)
direct = data.direct_estimates(df)
drivers = explain.district_drivers(fitted, top=3)
fair = explain.fairness_audit(fitted)
cal = explain.calibration(fitted)
cv = model.crossval_districts(df, cov)

# ---------------------------------------------------------------- estimates
table = (
    est.join(direct[["direct", "n_married"]])
    .join(drivers[["summary", "district_effect"]])
    .reset_index()
)
table.to_json(APP / "districts.json", orient="records", indent=2)
print(f"  {APP / 'districts.json'}  ({len(table)} districts)")

# ---------------------------------------------------------------- geometry
poly = geo_src = gpd.read_file(paths.DISTRICTS)[["GEONAMES", "GEONAME", "geometry"]]
poly = poly.rename(columns={"GEONAMES": "district", "GEONAME": "province"})
poly["district"] = poly.district.str.lower().str.strip()

before = poly.geometry.to_json().__len__()
poly["geometry"] = poly.geometry.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
poly = poly.merge(table[["district", "estimate", "lo", "hi", "width", "n"]],
                  on="district", how="left")

missing = int(poly.estimate.isna().sum())
if missing:
    raise ValueError(f"{missing} polygons have no estimate - check the name join")

poly.to_file(APP / "districts.geojson", driver="GeoJSON")
after = (APP / "districts.geojson").stat().st_size
print(f"  {APP / 'districts.geojson'}  ({after / 1024:.0f} KB, "
      f"simplified from ~{before / 1024:.0f} KB)")

# ---------------------------------------------------------------- metadata
def _brier(q: int) -> float:
    """Brier score for one wealth quintile."""
    sel = fair[(fair.group == "wealth") & (fair.level == q)]
    return float(sel.brier.iloc[0])


meta = {
    "generated_from": {
        "surveys": ["Zimbabwe DHS 2015", "Zimbabwe MICS 2019 (MICS6)"],
        "women": int(len(df)),
        "clusters": int(df.cluster.nunique()),
        "districts": int(df.district.nunique()),
    },
    "model": {
        "type": "multilevel logistic regression, random intercept by district",
        "fitted_with": "statsmodels BinomialBayesMixedGLM (variational Bayes)",
        "formula": fitted["formula"],
        "coefficients": {
            name: float(v)
            for name, v in zip(
                fitted["result"].model.exog_names,
                fitted["result"].fe_mean,
                strict=True,
            )
        },
    },
    "validation": {
        "cv_model_mae": round(cv["model_mae"], 2),
        "cv_baseline_mae": round(cv["baseline_mae"], 2),
        "calibration_mean_abs_gap": round(float(cal.gap.abs().mean()), 2),
    },
    "fairness_by_wealth": (
        fair[fair.group == "wealth"][["level", "n", "actual", "predicted", "brier"]]
        .round(3)
        .to_dict(orient="records")
    ),
    "caveats": [
        "Estimates describe places, never individuals.",
        "Data is from 2015 and 2019; the 2023-24 DHS microdata is not yet public.",
        "The model is least accurate for the poorest wealth quintile "
        f"(Brier {_brier(1):.3f} vs {_brier(5):.3f} for the richest).",
        "Variational Bayes understates uncertainty; treat intervals as a floor.",
    ],
}
(APP / "meta.json").write_text(json.dumps(meta, indent=2))
print(f"  {APP / 'meta.json'}")

print("\nDone. app_data/ contains no microdata - only district aggregates.")
