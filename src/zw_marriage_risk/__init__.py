"""
zw-marriage-risk
================

District-level child marriage prevalence estimates for Zimbabwe's 91
districts, with credible intervals and driver analysis.

Estimates outcomes for **places, never individuals**. See the README.
"""

from . import data, explain, model

__version__ = "0.1.0"
__all__ = ["data", "explain", "model", "__version__"]
