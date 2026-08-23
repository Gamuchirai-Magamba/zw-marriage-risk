"""
Small-area estimation: district-level prevalence with honest uncertainty.

The problem
-----------
``data.direct_estimates`` shows why the obvious approach fails. Kariba has
five respondents; three married before 18; the "rate" is 59% give or take
twenty-two points. Twenty-three of ninety-one districts are in that
position.

The approach
------------
A **multilevel logistic regression** with a random intercept per district.

Each district gets its own deviation from the national pattern, but those
deviations are themselves modelled as coming from a common distribution.
The practical consequence is **partial pooling**:

* a district with 400 respondents has enough evidence to move the model,
  so its estimate stays close to its own data
* a district with 5 respondents cannot move the model much, so its
  estimate is pulled toward what comparable districts look like, and its
  interval stays wide

Nothing is thrown away and nothing is invented. The amount of pooling is
determined by the data, through the estimated between-district variance.

Why this library
----------------
``statsmodels.BinomialBayesMixedGLM`` fits in seconds, needs no compiler,
and returns posterior means *and* standard deviations for every random
effect. That last part is what gives us intervals.

**Honest caveat:** ``fit_vb`` is variational Bayes, an approximation.
Variational posteriors are known to be over-confident - real intervals
are usually a little wider than these. For a portfolio project that is an
acceptable trade for a model that fits in three seconds; it is stated in
the model card, and the upgrade path is MCMC via PyMC.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM

__all__ = ["FIXED_EFFECTS", "fit", "district_estimates", "crossval_districts"]


#: Individual-level predictors. Deliberately few - 3,487 rows will not
#: support a wide feature set, and the point of this model is the
#: district structure, not a kitchen sink of covariates.
FIXED_EFFECTS = ["education", "wealth", "rural", "survey_mics"]


def _design(df: pd.DataFrame, covariates: pd.DataFrame | None = None):
    """Assemble the modelling frame."""
    d = df.copy()
    d["survey_mics"] = (d.survey == "MICS2019").astype(int)

    if covariates is not None:
        # standardise district-level context so coefficients are comparable
        cov = (covariates - covariates.mean()) / covariates.std()
        d = d.merge(cov, left_on="district", right_index=True, how="left")
        extra = list(cov.columns)
        if d[extra].isna().any().any():
            raise ValueError("some districts have no covariates - check the join")
    else:
        extra = []

    return d, FIXED_EFFECTS + extra


def fit(df: pd.DataFrame, covariates: pd.DataFrame | None = None):
    """Fit the multilevel model.

    Parameters
    ----------
    df
        Output of :func:`data.build_analysis_table`.
    covariates
        Optional district-level context from
        :func:`data.district_covariates`. Including it lets a
        thinly-sampled district borrow from districts that *resemble* it
        rather than only from the national average.

    Returns
    -------
    dict
        ``result`` (the fitted model), ``frame`` (the design frame),
        ``predictors`` (fixed-effect names), ``districts`` (the level
        order matching the random effects).

    Notes
    -----
    Survey weights are **not** passed to the likelihood. Weighted
    likelihoods are not well defined for this estimator, and the design
    variables that drive the weights (province, urban/rural) are in the
    model as covariates instead. This is the standard model-based
    approach to small-area estimation, and it is a real methodological
    choice worth stating rather than hiding - the direct estimates in
    ``data.direct_estimates`` remain weighted, so the two are not
    strictly like-for-like.
    """
    d, predictors = _design(df, covariates)

    formula = "y ~ " + " + ".join(predictors)
    vc_formula = {"district": "0 + C(district)"}

    model = BinomialBayesMixedGLM.from_formula(formula, vc_formula, d, vcp_p=2)
    result = model.fit_vb(verbose=False)

    # the random effects come out in the order pandas categorises them
    districts = sorted(d.district.unique())

    return {
        "result": result,
        "frame": d,
        "predictors": predictors,
        "districts": districts,
        "formula": formula,
    }


def district_estimates(
    fitted: dict,
    *,
    n_draws: int = 4000,
    interval: float = 0.90,
    seed: int = 42,
) -> pd.DataFrame:
    """District prevalence with credible intervals.

    For each district we predict a probability for every woman actually
    observed there, then average. That makes the estimate reflect the
    district's real composition rather than a hypothetical average woman.

    Uncertainty comes from drawing the district's random intercept from
    its posterior and recomputing the prevalence each time.

    Returns
    -------
    DataFrame
        Indexed by district. ``n``, ``estimate``, ``lo``, ``hi``,
        ``width``, ``re_mean`` (the district effect in log-odds).
    """
    rng = np.random.default_rng(seed)
    res = fitted["result"]
    d = fitted["frame"]
    preds = fitted["predictors"]
    districts = fitted["districts"]

    # fixed-effect linear predictor, without the district term
    exog = np.column_stack([np.ones(len(d))] + [d[p].to_numpy(float) for p in preds])
    fe = exog @ res.fe_mean

    re_mean = np.asarray(res.vc_mean, dtype=float)
    re_sd = np.asarray(res.vc_sd, dtype=float)

    lo_q = (1 - interval) / 2
    hi_q = 1 - lo_q

    rows = []
    for i, name in enumerate(districts):
        mask = (d.district == name).to_numpy()
        base = fe[mask]

        draws = rng.normal(re_mean[i], re_sd[i], size=n_draws)
        # (n_draws, n_women) -> probability for each woman under each draw
        p = 1.0 / (1.0 + np.exp(-(base[None, :] + draws[:, None])))
        prevalence = p.mean(axis=1)

        rows.append({
            "district": name,
            "province": d.loc[mask, "province"].iloc[0],
            "n": int(mask.sum()),
            "estimate": 100 * float(prevalence.mean()),
            "lo": 100 * float(np.quantile(prevalence, lo_q)),
            "hi": 100 * float(np.quantile(prevalence, hi_q)),
            "re_mean": float(re_mean[i]),
        })

    out = pd.DataFrame(rows).set_index("district")
    out["width"] = out.hi - out.lo
    return out.sort_values("estimate", ascending=False)


def crossval_districts(
    df: pd.DataFrame,
    covariates: pd.DataFrame | None = None,
    *,
    n_folds: int = 5,
    seed: int = 42,
) -> dict:
    """Hold out whole districts and see if the model beats the national mean.

    This is the honest test. If the model cannot predict a district it has
    never seen better than simply guessing the national rate, then the
    district structure is not carrying real information and the whole
    exercise is decoration.

    Whole districts are held out - not random rows - because the question
    is whether district-level context generalises.

    Returns
    -------
    dict
        ``model_mae`` and ``baseline_mae`` in percentage points, plus the
        per-fold detail.
    """
    rng = np.random.default_rng(seed)
    districts = np.array(sorted(df.district.unique()))
    rng.shuffle(districts)
    folds = np.array_split(districts, n_folds)

    model_err, base_err = [], []

    for held in folds:
        train = df[~df.district.isin(held)]
        test = df[df.district.isin(held)]

        cov_train = None
        if covariates is not None:
            cov_train = covariates.loc[covariates.index.isin(train.district.unique())]

        f = fit(train, cov_train)
        res = f["result"]

        # predict held-out districts using fixed effects only: an unseen
        # district has no random intercept, so it gets the population mean
        d_test, preds = _design(test, covariates)
        exog = np.column_stack(
            [np.ones(len(d_test))] + [d_test[p].to_numpy(float) for p in preds]
        )
        p_hat = 1.0 / (1.0 + np.exp(-(exog @ res.fe_mean)))

        national = float(np.average(train.y, weights=train.weight))

        for name, g in d_test.groupby("district"):
            truth = 100 * float(np.average(g.y, weights=g.weight))
            idx = d_test.district.to_numpy() == name
            model_err.append(abs(100 * p_hat[idx].mean() - truth))
            base_err.append(abs(100 * national - truth))

    return {
        "model_mae": float(np.mean(model_err)),
        "baseline_mae": float(np.mean(base_err)),
        "n_districts": len(model_err),
        "improvement": float(np.mean(base_err) - np.mean(model_err)),
    }
