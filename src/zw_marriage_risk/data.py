"""
Build the analysis table.

One row per woman aged 20-24, from both surveys, with her district
attached and the columns harmonised so DHS and MICS can be pooled.

Why 20-24
---------
The standard denominator for child marriage. Old enough that childhood is
complete (so the outcome is fully observed), recent enough to reflect
current conditions.

Why pool the surveys
--------------------
DHS 2015 alone gives 1,782 women. MICS 2019 adds 1,705. Pooling nearly
doubles the sample, which matters enormously when the unit of analysis is
a district with a median of 15 respondents.

The surveys are four years apart, so ``survey`` is kept as a column - the
model can then estimate a round effect rather than pretending the two are
interchangeable.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from zw_gender_data import dhs, geo, indicators, mics

__all__ = [
    "build_analysis_table",
    "direct_estimates",
    "district_covariates",
    "ANALYSIS_COLUMNS",
]


#: The harmonised schema. Both surveys are mapped onto exactly these columns.
ANALYSIS_COLUMNS = [
    "y",           # married before 18 (0/1)
    "age",         # current age in years
    "education",   # 0 none, 1 primary, 2 secondary, 3 higher
    "wealth",      # 1 poorest .. 5 richest
    "rural",       # 1 rural, 0 urban
    "province",
    "district",
    "survey",      # DHS2015 | MICS2019
    "weight",      # survey weight, ready for np.average
    "cluster",     # unique across surveys - the CV grouping key
]


def _dhs_frame(women_path, gps_path, districts) -> pd.DataFrame:
    w = dhs.load_women(women_path)
    w = w[w.v013 == 2].copy()                       # 20-24

    xw = geo.assign_districts(gps_path, districts, id_col="DHSCLUST")
    w = w.merge(xw, left_on="v001", right_on="DHSCLUST", how="left")

    return pd.DataFrame({
        "y":         indicators.married_before(w, 18, age_union_col="v511"),
        "age":       w.v012,
        "education": w.v106,
        "wealth":    w.v190,
        "rural":     (w.v025 == 2).astype(int),
        "province":  w.province,
        "district":  w.district,
        "survey":    "DHS2015",
        "weight":    w.weight,
        "cluster":   "DHS-" + w.v001.astype(int).astype(str),
    })


def _mics_frame(women_path, gps_path, districts) -> pd.DataFrame:
    w = mics.load_women(women_path)
    w = w[w.WAGE == 2].copy()                       # 20-24
    w["HH1"] = w.HH1.astype(int)

    xw = geo.assign_districts(gps_path, districts, id_col="HH1")
    w = w.merge(xw, on="HH1", how="left")

    return pd.DataFrame({
        "y":         indicators.married_before(w, 18, age_union_col="WAGEM"),
        "age":       w.WB4,
        # 99 is "Missing/DK" in MICS, not a real level
        "education": w.welevel.replace(99, np.nan),
        "wealth":    w.windex5,
        "rural":     (w.HH6 == 2).astype(int),
        "province":  w.province,
        "district":  w.district,
        "survey":    "MICS2019",
        "weight":    w.weight,
        "cluster":   "MICS-" + w.HH1.astype(str),
    })


def build_analysis_table(
    dhs_women: str | Path,
    dhs_gps: str | Path,
    mics_women: str | Path,
    mics_gps: str | Path,
    districts: str | Path,
    *,
    dropna: bool = True,
) -> pd.DataFrame:
    """Pool both surveys into one modelling table.

    Parameters
    ----------
    dropna
        Drop rows missing the target or any core predictor. Default True.
        Set False to inspect what would be dropped.

    Returns
    -------
    DataFrame
        Columns exactly :data:`ANALYSIS_COLUMNS`, one row per woman.

    Notes
    -----
    Province strings are lower-cased and stripped so the two surveys'
    spellings match. ``cluster`` is prefixed per survey so a DHS cluster 1
    and a MICS cluster 1 are never confused - this matters because
    ``cluster`` is the grouping key for cross-validation.
    """
    poly = geo.load_districts(districts)

    frames = [
        _dhs_frame(dhs_women, dhs_gps, poly),
        _mics_frame(mics_women, mics_gps, poly),
    ]
    df = pd.concat(frames, ignore_index=True)

    for col in ("province", "district"):
        df[col] = df[col].str.lower().str.strip()

    df = df[ANALYSIS_COLUMNS]

    if dropna:
        before = len(df)
        df = df.dropna(subset=["y", "education", "wealth", "district"])
        dropped = before - len(df)
        if dropped / before > 0.05:
            raise ValueError(
                f"dropna removed {dropped} of {before} rows "
                f"({100 * dropped / before:.1f}%). "
                "That is more than expected - inspect with dropna=False before "
                "proceeding."
            )

    return df.reset_index(drop=True)


def direct_estimates(df: pd.DataFrame) -> pd.DataFrame:
    """Naive per-district rates - the thing that does NOT work.

    Computed so its failure can be shown rather than asserted. With a
    median of ~30 women per district and a minimum in single figures,
    these swing wildly and are the justification for small-area
    estimation.

    Returns
    -------
    DataFrame
        Indexed by district: ``n``, ``n_married``, ``direct`` (percent),
        ``se`` (naive standard error, percent), and ``unreliable``.
    """
    rows = []
    for district, g in df.groupby("district"):
        p = float(np.average(g.y, weights=g.weight))
        n = len(g)
        rows.append({
            "district": district,
            "province": g.province.iloc[0],
            "n": n,
            "n_married": int(g.y.sum()),
            "direct": 100 * p,
            # naive binomial SE - itself unreliable at small n, which is
            # part of the point
            "se": 100 * np.sqrt(max(p * (1 - p), 1e-9) / n),
            "unreliable": n < 20,
        })
    return (
        pd.DataFrame(rows)
        .set_index("district")
        .sort_values("direct", ascending=False)
    )


def district_covariates(
    dhs_geocov: str | Path,
    dhs_gps: str | Path,
    districts: str | Path,
    variables: list[str] | None = None,
) -> pd.DataFrame:
    """District-level context from the DHS geospatial covariate file.

    The DHS ships 131 pre-computed covariates per cluster. Averaging them
    to district level gives the model something to say about a district
    beyond its own respondents - which is exactly what lets a district
    with 8 women borrow sensibly from districts that resemble it.

    Defaults to a deliberately small set. Adding all 131 to a model with
    ~3,500 rows would overfit comprehensively.
    """
    variables = variables or [
        "Nightlights_Composite",        # electrification / economic activity
        "Travel_Times_2015",            # hours to nearest city - rural isolation
        "UN_Population_Density_2015",
        "Enhanced_Vegetation_Index_2015",
        "Aridity_2015",
    ]

    gc = pd.read_csv(dhs_geocov)
    missing = set(variables) - set(gc.columns)
    if missing:
        raise KeyError(f"not in the covariate file: {sorted(missing)}")

    xw = geo.assign_districts(dhs_gps, districts, id_col="DHSCLUST")
    gc = gc.merge(xw, left_on="DHSCLUST", right_on="DHSCLUST", how="left")
    gc["district"] = gc.district.str.lower().str.strip()

    out = gc.groupby("district")[variables].mean()
    out.columns = [c.lower() for c in out.columns]
    return out
