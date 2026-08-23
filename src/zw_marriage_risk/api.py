"""
The API.

    uvicorn zw_marriage_risk.api:app --reload

Serves the frozen output of ``export_app_data.py``. It loads three small
JSON files at startup and holds them in memory - no model fitting, no
microdata, no database. Cold start is milliseconds.

A note on what is deliberately absent
-------------------------------------
There is **no endpoint that scores an individual**. Not one that is
disabled, or gated - one that does not exist. This model estimates
prevalence for places, and an API that accepted a girl's attributes and
returned a probability would be both statistically invalid and harmful,
whatever the caller intended.

``POST /estimate`` accepts a *district profile* - average education,
average wealth, share rural - and returns an expected prevalence for a
place with those characteristics.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

#: Environment variable that overrides where the frozen data lives.
#: Containers should set this - see the Dockerfile.
APP_DATA_ENV = "ZWMR_APP_DATA"


def _candidate_dirs() -> list[Path]:
    """Places ``app_data/`` might be, most explicit first.

    Why this is not a single hard-coded path: the package runs from two
    quite different layouts.

    * **From the repo** it lives at ``<repo>/src/zw_marriage_risk/api.py``,
      so ``app_data/`` is three levels up.
    * **Installed in a container** it lives in ``site-packages/``, where
      three levels up is ``/usr/local/lib/`` - nowhere near the data.

    Guessing from ``__file__`` alone works locally and fails on deploy,
    which is a bad way round for a bug to happen. So the environment
    variable comes first and the working directory second.
    """
    here = Path(__file__).resolve()
    return [
        Path.cwd() / "app_data",          # container WORKDIR, or repo root
        here.parents[2] / "app_data",     # <repo>/src/pkg/api.py  -> <repo>/
        here.parent / "app_data",         # data shipped inside the package
    ]


def resolve_app_data() -> Path:
    """Find the frozen model output, or return the best guess for the error."""
    override = os.getenv(APP_DATA_ENV)
    if override:
        return Path(override)

    for candidate in _candidate_dirs():
        if (candidate / "districts.json").exists():
            return candidate

    return _candidate_dirs()[0]


APP_DATA = resolve_app_data()


# --------------------------------------------------------------- schemas


class District(BaseModel):
    """A district's estimate."""

    district: str
    province: str
    n: int = Field(description="women aged 20-24 interviewed here")
    estimate: float = Field(description="estimated % married before 18")
    lo: float = Field(description="lower bound, 90% credible interval")
    hi: float = Field(description="upper bound, 90% credible interval")
    width: float = Field(description="interval width in percentage points")
    direct: float = Field(description="the naive estimate, for comparison")
    summary: str = Field(description="plain-language drivers")

    model_config = {
        "json_schema_extra": {
            "example": {
                "district": "kariba",
                "province": "mashonaland west",
                "n": 5,
                "estimate": 48.1,
                "lo": 34.0,
                "hi": 63.0,
                "width": 28.8,
                "direct": 59.3,
                "summary": "below-average education, raising risk (+0.51)",
            }
        }
    }


class Profile(BaseModel):
    """A hypothetical district's characteristics."""

    education: float = Field(
        1.9, ge=0, le=3,
        description="mean education level: 0 none, 1 primary, 2 secondary, 3 higher",
    )
    wealth: float = Field(
        3.0, ge=1, le=5, description="mean wealth quintile, 1 poorest to 5 richest"
    )
    rural: float = Field(
        0.5, ge=0, le=1, description="share of the district that is rural"
    )


class Estimate(BaseModel):
    estimate: float
    note: str


# --------------------------------------------------------------- loading


@lru_cache(maxsize=1)
def _load() -> tuple[dict, dict]:
    """Read the frozen model output once, at first request."""
    base = resolve_app_data()
    dpath, mpath = base / "districts.json", base / "meta.json"
    if not dpath.exists():
        looked = "\n  ".join(str(p) for p in _candidate_dirs())
        raise RuntimeError(
            f"districts.json not found at {dpath}.\n"
            f"Set {APP_DATA_ENV} to the folder containing it, or run "
            f"`python export_app_data.py` to create it.\n"
            f"Searched:\n  {looked}\n"
            f"(cwd is {Path.cwd()})"
        )
    districts = {d["district"]: d for d in json.loads(dpath.read_text())}
    meta = json.loads(mpath.read_text())
    return districts, meta


# --------------------------------------------------------------- the app


app = FastAPI(
    title="Zimbabwe child marriage — district estimates",
    version="0.1.0",
    description=(
        "Estimated prevalence of marriage before 18 among women aged 20-24, "
        "for each of Zimbabwe's 91 districts, with 90% credible intervals.\n\n"
        "**These estimates describe places, not people.** There is no endpoint "
        "that scores an individual, by design.\n\n"
        "Built from Zimbabwe DHS 2015 and MICS 2019 microdata using a multilevel "
        "model. See `/meta` for validation figures and known limitations."
    ),
)


@app.get("/health")
def health() -> dict:
    """Liveness check."""
    try:
        districts, _ = _load()
        return {"status": "ok", "districts": len(districts)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/districts", response_model=list[District])
def list_districts(min_estimate: float = 0.0, max_width: float | None = None):
    """All 91 districts, highest estimate first.

    ``max_width`` filters to districts the model is reasonably confident
    about - useful when you want a shortlist you can act on rather than
    the full ranking.
    """
    districts, _ = _load()
    out = [d for d in districts.values() if d["estimate"] >= min_estimate]
    if max_width is not None:
        out = [d for d in out if d["width"] <= max_width]
    return sorted(out, key=lambda d: -d["estimate"])


@app.get("/districts/{name}", response_model=District)
def get_district(name: str):
    """One district, with its drivers."""
    districts, _ = _load()
    key = name.lower().strip()
    if key not in districts:
        close = [d for d in districts if key in d or d in key]
        raise HTTPException(
            status_code=404,
            detail=f"unknown district {name!r}"
            + (f". Did you mean: {', '.join(close[:5])}?" if close else ""),
        )
    return districts[key]


@app.get("/meta")
def meta() -> dict:
    """Model details, validation figures, and the caveats.

    Read this before using the numbers. It includes the fairness result:
    the model is least accurate for the poorest wealth quintile.
    """
    _, m = _load()
    return m


@app.post("/estimate", response_model=Estimate)
def estimate(profile: Profile):
    """Expected prevalence for a *place* with these characteristics.

    Applies the fitted fixed effects. It has no district random intercept
    - this is what an average district with this profile looks like, not
    a specific one. For a real district use ``GET /districts/{name}``.
    """
    import math

    _, m = _load()
    c = m["model"]["coefficients"]

    eta = (
        c.get("Intercept", 0.0)
        + c.get("education", 0.0) * profile.education
        + c.get("wealth", 0.0) * profile.wealth
        + c.get("rural", 0.0) * profile.rural
    )
    p = 100 / (1 + math.exp(-eta))

    return Estimate(
        estimate=round(p, 1),
        note=(
            "Population-level estimate for a district with this profile. "
            "Not applicable to any individual. Excludes district-specific "
            "and geographic effects, so it is less accurate than a named "
            "district's own estimate."
        ),
    )
