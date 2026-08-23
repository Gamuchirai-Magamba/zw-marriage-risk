"""
Why is this district high? And who does the model fail?

Two jobs, both required before anyone should act on an estimate.

Drivers
-------
"Gokwe North is high" is not actionable. "Gokwe North is high mainly
because secondary completion is low, not because it is unusually poor" is
- because those imply different interventions.

For each district we decompose its estimate into the contribution of each
factor, relative to the national average.

**Why not SHAP.** SHAP approximates Shapley values for arbitrary models.
Our model is a GLM: its linear predictor is *already* additive, so the
exact contribution of each feature is available in closed form. The
decomposition below IS the Shapley value for this model, computed
exactly rather than sampled. Reaching for SHAP here would be slower and
less accurate.

Fairness
--------
A model that is accurate on average can still be systematically wrong for
one group. Here that matters more than usual: if the model performs worst
for the poorest women, it fails precisely the girls the tool exists to
help. So we measure it, and we publish it whichever way it comes out.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["district_drivers", "fairness_audit", "calibration"]


def _linear_predictor(fitted: dict) -> tuple[np.ndarray, pd.DataFrame]:
    """Fixed-effect linear predictor per woman, plus the design frame."""
    res = fitted["result"]
    d = fitted["frame"]
    preds = fitted["predictors"]
    exog = np.column_stack([np.ones(len(d))] + [d[p].to_numpy(float) for p in preds])
    return exog @ res.fe_mean, d


def district_drivers(fitted: dict, top: int = 4) -> pd.DataFrame:
    """Decompose each district's estimate into its causes.

    Every term is a deviation from the national average on the log-odds
    scale, so they add up:

        district log-odds = national log-odds
                          + sum of feature contributions
                          + district effect

    Parameters
    ----------
    top
        How many factors to name in the ``summary`` column.

    Returns
    -------
    DataFrame
        Indexed by district. One column per predictor holding its
        contribution, plus ``district_effect`` (the part no feature
        explains), ``total`` and a human-readable ``summary``.

    Notes
    -----
    ``district_effect`` is the interesting residual. A large positive
    value means this district is worse than its education, wealth and
    geography can account for - which is a prompt to go and ask why,
    not an answer.
    """
    res = fitted["result"]
    d = fitted["frame"]
    preds = fitted["predictors"]
    districts = fitted["districts"]

    coefs = dict(zip(res.model.exog_names, res.fe_mean, strict=True))
    national_mean = {p: float(d[p].mean()) for p in preds}
    re_mean = np.asarray(res.vc_mean, dtype=float)

    rows = []
    for i, name in enumerate(districts):
        g = d[d.district == name]
        row = {"district": name, "province": g.province.iloc[0], "n": len(g)}

        for p in preds:
            beta = coefs.get(p, 0.0)
            row[p] = (float(g[p].mean()) - national_mean[p]) * beta

        row["district_effect"] = float(re_mean[i])
        row["total"] = sum(row[p] for p in preds) + row["district_effect"]
        rows.append(row)

    out = pd.DataFrame(rows).set_index("district")

    factor_cols = [*preds, "district_effect"]

    # How each district's own value compares to the national average.
    # Needed because a contribution's sign alone is ambiguous: education
    # has a negative coefficient, so a POSITIVE contribution means the
    # district has LESS education than average. Saying "education raises
    # risk" would invert the meaning for a reader.
    level = {}
    for p in preds:
        by_district = d.groupby("district")[p].mean()
        level[p] = by_district - national_mean[p]

    def describe(r):
        ranked = r[factor_cols].abs().sort_values(ascending=False).index[:top]
        parts = []
        for f in ranked:
            v = r[f]
            if abs(v) < 0.02:
                continue

            if f == "district_effect":
                word = "higher" if v > 0 else "lower"
                parts.append(
                    f"unexplained district effect - {word} than its "
                    f"characteristics predict ({v:+.2f})"
                )
                continue

            direction = "below" if level[f].loc[r.name] < 0 else "above"
            effect = "raising" if v > 0 else "lowering"
            parts.append(
                f"{direction}-average {f.replace('_', ' ')}, {effect} risk ({v:+.2f})"
            )
        return "; ".join(parts) if parts else "close to the national average"

    out["summary"] = out.apply(describe, axis=1)
    return out.sort_values("total", ascending=False)


def fairness_audit(fitted: dict, groups: list[str] | None = None) -> pd.DataFrame:
    """How well does the model do for each subgroup?

    Reports, per group:

    * ``actual``    - the observed rate (weighted)
    * ``predicted`` - the model's mean prediction
    * ``bias``      - predicted minus actual, in points. Positive means
                      the model over-states risk for this group.
    * ``brier``     - mean squared error of the predicted probabilities

    Published as-is. If a group comes out badly, that is the finding.
    """
    groups = groups or ["wealth", "rural", "province", "survey"]
    fe, d = _linear_predictor(fitted)

    re_mean = np.asarray(fitted["result"].vc_mean, dtype=float)
    lookup = dict(zip(fitted["districts"], re_mean, strict=True))
    eta = fe + d.district.map(lookup).to_numpy(float)
    p = 1.0 / (1.0 + np.exp(-eta))

    d = d.assign(_p=p)

    rows = []
    for col in groups:
        for level, g in d.groupby(col):
            actual = 100 * float(np.average(g.y, weights=g.weight))
            pred = 100 * float(np.average(g._p, weights=g.weight))
            rows.append({
                "group": col,
                "level": level,
                "n": len(g),
                "actual": actual,
                "predicted": pred,
                "bias": pred - actual,
                "brier": float(np.average((g._p - g.y) ** 2, weights=g.weight)),
            })
    return pd.DataFrame(rows)


def calibration(fitted: dict, bins: int = 8) -> pd.DataFrame:
    """Do women predicted at 40% actually marry early 40% of the time?

    A model can rank correctly and still be badly calibrated. That matters
    here because a programme officer will read "38%" as a real
    probability, not as a rank.
    """
    fe, d = _linear_predictor(fitted)
    re_mean = np.asarray(fitted["result"].vc_mean, dtype=float)
    lookup = dict(zip(fitted["districts"], re_mean, strict=True))
    p = 1.0 / (1.0 + np.exp(-(fe + d.district.map(lookup).to_numpy(float))))

    d = d.assign(_p=p)
    d["_bin"] = pd.qcut(d._p, bins, duplicates="drop")

    rows = []
    for b, g in d.groupby("_bin", observed=True):
        rows.append({
            "bin": f"{100 * b.left:.0f}-{100 * b.right:.0f}%",
            "n": len(g),
            "mean_predicted": 100 * float(g._p.mean()),
            "observed": 100 * float(np.average(g.y, weights=g.weight)),
        })
    out = pd.DataFrame(rows)
    out["gap"] = out.mean_predicted - out.observed
    return out
