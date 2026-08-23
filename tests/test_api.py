"""API tests.

These run without microdata - they need only app_data/, which is the
frozen model output. That is the point of the export step: the deployed
service has no dependency on restricted files.
"""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from zw_marriage_risk.api import APP_DATA, app  # noqa: E402

needs_export = pytest.mark.skipif(
    not (APP_DATA / "districts.json").exists(),
    reason="run export_app_data.py first",
)

client = TestClient(app)


@needs_export
class TestEndpoints:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["districts"] == 91

    def test_list_returns_all_districts_sorted(self):
        r = client.get("/districts")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 91
        estimates = [d["estimate"] for d in body]
        assert estimates == sorted(estimates, reverse=True)

    def test_every_district_carries_its_interval(self):
        """An estimate without its interval is not shippable here."""
        for d in client.get("/districts").json():
            assert d["lo"] <= d["estimate"] <= d["hi"]
            assert d["width"] > 0
            assert d["summary"]

    def test_confidence_filter(self):
        wide = client.get("/districts").json()
        narrow = client.get("/districts?max_width=15").json()
        assert 0 < len(narrow) < len(wide)
        assert all(d["width"] <= 15 for d in narrow)

    def test_single_district(self):
        r = client.get("/districts/bulawayo")
        assert r.status_code == 200
        assert r.json()["district"] == "bulawayo"

    def test_district_lookup_is_case_insensitive(self):
        assert client.get("/districts/BULAWAYO").status_code == 200

    def test_unknown_district_gets_a_helpful_404(self):
        r = client.get("/districts/atlantis")
        assert r.status_code == 404
        assert "unknown district" in r.json()["detail"]

    def test_meta_carries_the_caveats(self):
        m = client.get("/meta").json()
        assert "caveats" in m
        joined = " ".join(m["caveats"]).lower()
        assert "never individuals" in joined or "not individuals" in joined
        assert "poorest" in joined, "the fairness finding must be surfaced"

    def test_estimate_accepts_a_district_profile(self):
        body_in = {"education": 1.0, "wealth": 1.0, "rural": 1.0}
        r = client.post("/estimate", json=body_in)
        assert r.status_code == 200
        body = r.json()
        assert 0 <= body["estimate"] <= 100
        assert "individual" in body["note"].lower()

    def test_more_education_lowers_the_estimate(self):
        base = {"wealth": 3, "rural": 0.5}
        low = client.post("/estimate", json={**base, "education": 1.0})
        high = client.post("/estimate", json={**base, "education": 3.0})
        assert high.json()["estimate"] < low.json()["estimate"], (
            "education must reduce estimated prevalence - the central finding"
        )

    def test_profile_bounds_are_enforced(self):
        r = client.post("/estimate", json={"education": 9, "wealth": 3, "rural": 0.5})
        assert r.status_code == 422


@needs_export
def test_no_individual_scoring_endpoint_exists():
    """The absence is deliberate and worth locking in.

    If someone later adds an endpoint taking a person's attributes, this
    test should be the thing that makes them stop and think.
    """
    paths = {r.path for r in app.routes}
    for banned in ("/score", "/predict", "/risk", "/individual", "/person"):
        assert banned not in paths
