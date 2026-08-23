"""Tests for the multilevel model.

The real-data tests are slow (each fit takes a few seconds) so they are
marked and skip without microdata, as elsewhere.
"""

import numpy as np
import pytest

from zw_marriage_risk import data, model

try:
    import paths  # noqa: F401

    HAVE_PATHS = True
except ImportError:
    HAVE_PATHS = False

needs_data = pytest.mark.skipif(
    not HAVE_PATHS, reason="paths.py not found - microdata not configured"
)


def test_fixed_effects_are_a_short_list():
    """3,487 rows will not support a wide feature set."""
    assert len(model.FIXED_EFFECTS) <= 6
    assert "education" in model.FIXED_EFFECTS


@pytest.fixture(scope="module")
def bundle():
    import paths

    df = data.build_analysis_table(
        paths.DHS_WOMEN, paths.DHS_GPS,
        paths.MICS_WOMEN, paths.MICS_GPS, paths.DISTRICTS,
    )
    cov = data.district_covariates(
        paths.DHS_GEOCOV, paths.DHS_GPS, paths.DISTRICTS
    )
    fitted = model.fit(df, cov)
    est = model.district_estimates(fitted)
    direct = data.direct_estimates(df)
    return df, cov, fitted, est, direct


@needs_data
class TestModel:
    def test_every_district_estimated(self, bundle):
        *_, est, _ = bundle
        assert len(est) == 91
        assert est[["estimate", "lo", "hi"]].isna().sum().sum() == 0

    def test_estimates_are_probabilities(self, bundle):
        *_, est, _ = bundle
        assert est.estimate.between(0, 100).all()
        assert (est.lo <= est.estimate).all()
        assert (est.estimate <= est.hi).all()

    def test_education_is_the_dominant_effect(self, bundle):
        _, _, fitted, _, _ = bundle
        res = fitted["result"]
        coefs = dict(zip(res.model.exog_names, res.fe_mean, strict=True))
        assert coefs["education"] < -0.5, "education should strongly reduce risk"
        assert abs(coefs["education"]) > abs(coefs["wealth"]), (
            "education should outweigh wealth - the central finding"
        )

    def test_uncertainty_tracks_sample_size(self, bundle):
        """The whole point of the method, asserted.

        Districts with less data must get wider intervals. If this
        correlation ever collapses, the model has stopped being honest.
        """
        *_, est, _ = bundle
        corr = np.corrcoef(est.width, 1 / est.n)[0, 1]
        assert corr > 0.5, f"width should track 1/n, got r={corr:.2f}"

    def test_shrinkage_compresses_the_range(self, bundle):
        """Model estimates must be less extreme than direct ones."""
        *_, est, direct = bundle
        direct_range = direct.direct.max() - direct.direct.min()
        model_range = est.estimate.max() - est.estimate.min()
        assert model_range < direct_range, "partial pooling must pull extremes in"

    def test_small_districts_move_more_than_large_ones(self, bundle):
        *_, est, direct = bundle
        j = est.join(direct[["direct"]])
        j["moved"] = (j.estimate - j.direct).abs()
        small = j.nsmallest(15, "n").moved.mean()
        large = j.nlargest(15, "n").moved.mean()
        assert small > large, (
            f"small districts should shrink more (moved {small:.1f} vs {large:.1f})"
        )

    @pytest.mark.slow
    def test_beats_the_national_mean_baseline(self, bundle):
        """If this fails, the district structure carries no real signal."""
        df, cov, *_ = bundle
        cv = model.crossval_districts(df, cov)
        assert cv["model_mae"] < cv["baseline_mae"], (
            "a model that cannot beat guessing the national rate is not worth "
            "shipping"
        )
