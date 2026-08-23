"""
The map.

    streamlit run app.py

Reads only ``app_data/`` - the frozen model output. No microdata, no
model fitting, no server-side state.

Design notes
------------
Two maps, not one. The prevalence map answers "where is it worst?"; the
uncertainty map answers "where do we actually know?" Publishing the first
without the second would invite an NGO to act on a number built from five
respondents.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DATA = Path(__file__).parent / "app_data"

st.set_page_config(
    page_title="Zimbabwe child marriage by district",
    page_icon="🗺️",
    layout="wide",
)


@st.cache_data
def load():
    districts = pd.read_json(APP_DATA / "districts.json")
    geo = json.loads((APP_DATA / "districts.geojson").read_text())
    meta = json.loads((APP_DATA / "meta.json").read_text())
    return districts, geo, meta


try:
    df, geojson, meta = load()
except FileNotFoundError:
    st.error(
        "`app_data/` is missing. Run `python export_app_data.py` to generate it "
        "from the microdata."
    )
    st.stop()


# ---------------------------------------------------------------- header

st.title("Where should child marriage programmes go?")
st.markdown(
    """
Estimated share of women aged 20–24 who married before 18, for each of Zimbabwe's
**91 districts** — from the DHS 2015 and MICS 2019 surveys.

**These estimates describe places, not people.** They cannot say anything about
an individual girl, and must not be used to.
"""
)

national = 33.0
c1, c2, c3, c4 = st.columns(4)
c1.metric("National rate", f"{national:.0f}%", help="pooled across both surveys")
c2.metric("Districts", len(df))
c3.metric("Highest", f"{df.estimate.max():.0f}%",
          df.loc[df.estimate.idxmax(), "district"].title())
c4.metric("Widest interval", f"±{df.width.max() / 2:.0f} pts",
          df.loc[df.width.idxmax(), "district"].title())

st.divider()


# ---------------------------------------------------------------- maps

left, right = st.columns(2)

with left:
    st.subheader("Estimated prevalence")
    fig = px.choropleth(
        df, geojson=geojson, locations="district",
        featureidkey="properties.district",
        color="estimate",
        color_continuous_scale="Blues",
        range_color=(0, df.estimate.max()),
        hover_name="district",
        hover_data={"district": False, "estimate": ":.1f", "lo": ":.0f",
                    "hi": ":.0f", "n": True},
        labels={"estimate": "% married before 18", "n": "women surveyed"},
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=420)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("How much we actually know")
    fig2 = px.choropleth(
        df, geojson=geojson, locations="district",
        featureidkey="properties.district",
        color="width",
        color_continuous_scale="Oranges",
        hover_name="district",
        hover_data={"district": False, "width": ":.0f", "n": True},
        labels={"width": "interval width (pts)", "n": "women surveyed"},
    )
    fig2.update_geos(fitbounds="locations", visible=False)
    fig2.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=420)
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "Darker = less certain. These are districts where the survey interviewed "
        "very few women. Treat their estimates as a prompt to collect local data, "
        "not as a finding."
    )


# ---------------------------------------------------------------- shortlist

st.divider()
st.subheader("Shortlist")

col_a, col_b = st.columns([1, 2])
with col_a:
    max_width = st.slider(
        "Only show districts I can be reasonably confident about "
        "(maximum interval width, points)",
        min_value=int(df.width.min()), max_value=int(df.width.max()),
        value=int(df.width.quantile(0.6)),
    )
    top_n = st.number_input("How many districts can you fund?", 1, 91, 10)

shortlist = (
    df[df.width <= max_width]
    .sort_values("estimate", ascending=False)
    .head(int(top_n))
)

with col_b:
    if shortlist.empty:
        st.warning(
            "No districts meet that confidence threshold. Widen it — or read that "
            "as the survey being too thin to support this decision."
        )
    else:
        st.dataframe(
            shortlist[["district", "province", "estimate", "lo", "hi", "n"]]
            .rename(columns={"estimate": "estimate %", "lo": "low", "hi": "high",
                             "n": "women surveyed"})
            .style.format({"estimate %": "{:.1f}", "low": "{:.0f}", "high": "{:.0f}"}),
            use_container_width=True, hide_index=True,
        )
        dropped = len(df[df.estimate >= shortlist.estimate.min()]) - len(shortlist)
        if dropped > 0:
            st.caption(
                f"{dropped} district(s) with estimates this high were excluded for "
                "being too uncertain. That is the filter doing its job."
            )


# ---------------------------------------------------------------- detail

st.divider()
st.subheader("One district at a time")

pick = st.selectbox(
    "District", sorted(df.district), index=sorted(df.district).index("kariba")
    if "kariba" in set(df.district) else 0,
    format_func=str.title,
)
row = df[df.district == pick].iloc[0]

d1, d2, d3 = st.columns(3)
d1.metric("Estimate", f"{row.estimate:.1f}%")
d2.metric("90% interval", f"{row.lo:.0f}% – {row.hi:.0f}%")
d3.metric("Women surveyed", int(row.n))

st.markdown(f"**Why:** {row.summary}")

if row.n < 20:
    st.warning(
        f"Only **{int(row.n)} women** were interviewed in {pick.title()}. The naive "
        f"estimate from that sample alone was **{row.direct:.1f}%**; the model puts it "
        f"at **{row.estimate:.1f}%**, pulled toward comparable districts because "
        f"{int(row.n)} responses cannot support the extreme. The wide interval is the "
        "honest reading."
    )

with st.expander("Compare with the naive estimate"):
    st.write(
        pd.DataFrame({
            "": ["Direct (this district's women only)", "Model (partial pooling)"],
            "estimate": [f"{row.direct:.1f}%", f"{row.estimate:.1f}%"],
            "interval": ["none — a single sample proportion",
                         f"{row.lo:.0f}% – {row.hi:.0f}%"],
        })
    )


# ---------------------------------------------------------------- honesty

st.divider()
with st.expander("⚠️ How much should you trust this?", expanded=False):
    st.markdown(
        f"""
**Validation.** Holding out whole districts, the model predicts them with a mean
absolute error of **{meta['validation']['cv_model_mae']} points**, against
**{meta['validation']['cv_baseline_mae']} points** for simply assuming the national
rate. Real, and modest.

**Calibration.** Mean gap between predicted and observed: **
{meta['validation']['calibration_mean_abs_gap']} points**, with compression toward
the middle.

**The model is least accurate for the poorest women.** Brier score by wealth
quintile:
"""
    )
    fair = pd.DataFrame(meta["fairness_by_wealth"])
    fair["quintile"] = fair.level.map(
        {1: "poorest", 2: "poorer", 3: "middle", 4: "richer", 5: "richest"}
    )
    st.dataframe(
        fair[["quintile", "n", "actual", "predicted", "brier"]],
        use_container_width=True, hide_index=True,
    )
    st.markdown(
        "Those are precisely the girls this tool exists to help. It is stated here "
        "rather than buried because a user deciding where to spend money deserves "
        "to know where the model is weakest."
    )
    st.markdown("**Other caveats**")
    for c in meta["caveats"]:
        st.markdown(f"- {c}")


st.caption(
    "Sources: Zimbabwe DHS 2015 (ZIMSTAT & ICF) and Zimbabwe MICS 2019 (ZIMSTAT & "
    "UNICEF), used under registered access. Microdata is not redistributed — this "
    "app serves district-level aggregates only. Code and model card on GitHub."
)
