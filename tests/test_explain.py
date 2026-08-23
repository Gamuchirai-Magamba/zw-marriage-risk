"""Tests for the explanation and fairness layer."""

import pytest

from zw_marriage_risk import data, explain, model

try:
    import paths  # noqa: F401

    HAVE_PATHS = True
except ImportError:
    HAVE_PATHS = False

needs_data = pytest.mark.skipif(
    not HAVE_PATHS, reason="paths.py not found - microdata not configured"
)


@pytest.fixture(scope="module")
def fitted():
    import paths

    df = data.build_analysis_table(
        paths.DHS_WOMEN, paths.DHS_GPS,
        paths.MICS_WOMEN, paths.MICS_GPS, paths.DISTRICTS,
    )
    cov = data.district_covariates(
        paths.DHS_GEOCOV, paths.DHS_GPS, paths.DISTRICTS
    )
    return model.fit(df, cov)


@needs_data
class TestDrivers:
    def test_every_district_explained(self, fitted):
        dr = explain.district_drivers(fitted)
        assert len(dr) == 91
        assert dr.summary.str.len().min() > 0

    def test_contributions_are_additive(self, fitted):
        """The decomposition must actually add up.

        This is what makes it exact rather than approximate - and it is
        the reason SHAP is unnecessary for this model.
        """
        dr = explain.district_drivers(fitted)
        parts = [*fitted["predictors"], "district_effect"]
        assert (dr[parts].sum(axis=1) - dr.total).abs().max() < 1e-9

    def test_summary_states_direction_not_just_sign(self, fitted):
        """A contribution's sign alone is ambiguous.

        Education has a negative coefficient, so a positive contribution
        means LESS education. The summary must say which, or a reader
        will invert the meaning.
        """
        dr = explain.district_drivers(fitted)
        text = " ".join(dr.summary)
        assert "below-average" in text
        assert "above-average" in text


@needs_data
class TestFairness:
    def test_covers_the_groups_that_matter(self, fitted):
        fa = explain.fairness_audit(fitted)
        assert set(fa.group) >= {"wealth", "rural", "province"}
        assert (fa.n > 0).all()

    def test_reports_bias_in_both_directions(self, fitted):
        """A fairness audit that only ever reports zero is not auditing."""
        fa = explain.fairness_audit(fitted)
        assert (fa.bias > 0).any() and (fa.bias < 0).any()

    def test_poorest_quintile_is_measured(self, fitted):
        """Whatever the answer, it must be produced - not skipped."""
        fa = explain.fairness_audit(fitted)
        poorest = fa[(fa.group == "wealth") & (fa.level == 1)]
        assert len(poorest) == 1
        assert poorest.brier.iloc[0] > 0


@needs_data
class TestCalibration:
    def test_bins_cover_the_sample(self, fitted):
        cal = explain.calibration(fitted)
        assert cal.n.sum() == len(fitted["frame"])

    def test_predictions_increase_with_observed(self, fitted):
        """Ranking must at least be right, even if calibration is imperfect."""
        cal = explain.calibration(fitted)
        assert cal.mean_predicted.is_monotonic_increasing
        assert cal.observed.corr(cal.mean_predicted) > 0.9
