"""
zw-marriage-risk
================

District-level child marriage prevalence estimates for Zimbabwe's 91
districts, with credible intervals and driver analysis.

Estimates outcomes for **places, never individuals**. See the README.

Why the imports here are lazy
-----------------------------
``api`` needs only FastAPI and Pydantic - it serves frozen JSON and does
no modelling. ``data``, ``model`` and ``explain`` need numpy, pandas,
statsmodels and geopandas.

If this module imported all four eagerly, then ``import
zw_marriage_risk.api`` would drag in the entire modelling stack, and the
deployed container would have to install it just to read three JSON
files.

So submodules load on first use (PEP 562). The container installs
FastAPI, Pydantic and the package itself - nothing else - and the API
starts.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

__version__ = "0.1.0"

_SUBMODULES = frozenset({"data", "model", "explain", "api"})

__all__ = ["api", "data", "explain", "model", "__version__"]

if TYPE_CHECKING:  # for editors and type checkers only - never at runtime
    from . import api, data, explain, model


def __getattr__(name: str):
    """Import a submodule the first time it is asked for."""
    if name in _SUBMODULES:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module          # cache, so this runs once
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _SUBMODULES)
