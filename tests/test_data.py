"""Tests for the analysis table.

Synthetic tests run anywhere. Tests needing microdata skip themselves
when ``paths.py`` is absent, so CI stays green without a DHS
registration.
"""

import numpy as np
import pandas as pd
import pytest

from zw_marriage_risk import data

try:
    import paths  # noqa: F401

    HAVE_PATHS = True
except ImportError:
    HAVE_PATHS = False

needs_data = pytest.mark.skipif(
    not HAVE_PATHS, reason="paths.py not found - microdata not configured"
)


# ---------------------------------------------------------------- synthetic


@pytest.fixture
def toy():
    """Two districts. One well-sampled, one dangerously small."""
    return pd.DataFrame({
        "y":         [1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1],
        "age":       [22] * 11,
        "education": [1, 1, 2, 2, 2, 3, 2, 2, 1, 1, 0],
        "wealth":    [1, 2, 3, 4, 5, 5, 4, 3, 1, 1, 1],
        "rural":     [1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1],
        "province":  ["a"] * 8 + ["b"] * 3,
        "district":  ["big"] * 8 + ["tiny"] * 3,
        "survey":    ["DHS2015"] * 11,
        "weight":    [1.0] * 11,
        "cluster":   [f"DHS-{i//3}" for i in range(11)],
    })


class TestDirectEstimates:
    def test_one_row_per_district(self, toy):
        out = data.direct_estimates(toy)
        assert len(out) == 2
        assert set(out.index) == {"big", "tiny"}

    def test_small_district_flagged(self, toy):
        out = data.direct_estimates(toy)
        assert out.loc["tiny", "unreliable"]
        assert out.loc["big", "unreliable"]  # 8 is also under 20

    def test_tiny_district_gives_extreme_estimate(self, toy):
        """The failure mode, asserted rather than assumed.

        Three women, all married, produces 100%. That is not a finding
        about the district - it is what small samples do, and it is the
        entire reason this project needs small-area estimation.
        """
        out = data.direct_estimates(toy)
        assert out.loc["tiny", "direct"] == 100.0
        assert out.loc["tiny", "n"] == 3

    def test_standard_error_larger_for_smaller_district(self, toy):
        out = data.direct_estimates(toy)
        assert out.loc["tiny", "n"] < out.loc["big", "n"]
        # a 100% estimate has zero binomial variance, so compare a case
        # that is not degenerate
        mixed = toy.copy()
        mixed.loc[10, "y"] = 0
        out2 = data.direct_estimates(mixed)
        assert out2.loc["tiny", "se"] > out2.loc["big", "se"]

    def test_sorted_by_rate(self, toy):
        out = data.direct_estimates(toy)
        assert out.direct.is_monotonic_decreasing


class TestSchema:
    def test_columns_are_the_documented_contract(self):
        assert data.ANALYSIS_COLUMNS[0] == "y"
        assert "cluster" in data.ANALYSIS_COLUMNS
        assert "weight" in data.ANALYSIS_COLUMNS
        assert "district" in data.ANALYSIS_COLUMNS


# ------------------------------------------------------------ with real data


@pytest.fixture(scope="module")
def df():
    import paths

    return data.build_analysis_table(
        paths.DHS_WOMEN, paths.DHS_GPS,
        paths.MICS_WOMEN, paths.MICS_GPS, paths.DISTRICTS,
    )


@needs_data
class TestRealData:

    def test_expected_size(self, df):
        assert len(df) == 3487, "1,782 DHS + 1,705 MICS women aged 20-24"
        assert df.district.nunique() == 91
        assert df.survey.value_counts().to_dict() == {
            "DHS2015": 1782, "MICS2019": 1705
        }

    def test_schema_exact(self, df):
        assert list(df.columns) == data.ANALYSIS_COLUMNS

    def test_no_nulls_in_modelling_columns(self, df):
        for col in ["y", "education", "wealth", "district", "weight"]:
            assert df[col].isna().sum() == 0, f"{col} has nulls"

    def test_pooled_rate_matches_the_surveys(self, df):
        rate = 100 * np.average(df.y, weights=df.weight)
        assert 30 < rate < 35, (
            f"pooled rate {rate:.1f}% - should sit between the DHS 32.4% "
            "and MICS 33.7%"
        )

    def test_clusters_are_unique_across_surveys(self, df):
        """DHS cluster 1 and MICS cluster 1 must not collide.

        If they did, cluster-grouped cross-validation would silently mix
        two different villages and leak.
        """
        assert df.cluster.str.startswith(("DHS-", "MICS-")).all()
        dhs_c = set(df[df.survey == "DHS2015"].cluster)
        mics_c = set(df[df.survey == "MICS2019"].cluster)
        assert not (dhs_c & mics_c)

    def test_direct_estimates_are_unusable(self, df):
        """The premise of the whole project, asserted.

        If this ever stops failing, small-area estimation is no longer
        needed and the README needs rewriting.
        """
        de = data.direct_estimates(df)
        assert len(de) == 91
        assert de.n.min() < 10, "some district should be dangerously small"
        assert de.direct.max() - de.direct.min() > 50, (
            "the direct estimates should swing wildly - that is the problem "
            "this project exists to solve"
        )
        assert de.unreliable.sum() >= 20

    def test_covariates_cover_every_district(self):
        import paths

        cov = data.district_covariates(
            paths.DHS_GEOCOV, paths.DHS_GPS, paths.DISTRICTS
        )
        assert len(cov) == 91
        assert cov.isna().sum().sum() == 0
