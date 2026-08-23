"""
Step 2B: fit the multilevel model and show what it did.

    python fit_model.py

Produces:
    outputs/district_estimates.csv   the deliverable - 91 districts with intervals
    outputs/shrinkage.png            the chart that explains the method
    outputs/uncertainty.png          why some districts are less certain
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import paths
from zw_marriage_risk import data, model

warnings.filterwarnings("ignore")

BLUE, ORANGE, INK, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"
OUT = Path("outputs")
OUT.mkdir(exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#d4d4d0", "axes.labelcolor": MUTED, "text.color": INK,
    "axes.titlecolor": INK, "axes.titlesize": 12, "axes.titleweight": "semibold",
    "xtick.color": MUTED, "ytick.color": MUTED, "font.size": 10,
    "grid.color": "#ececea", "grid.linewidth": 0.8,
})


def rule(t):
    print("\n" + "=" * 74)
    print(f"  {t}")
    print("=" * 74)


# =====================================================================
rule("1. THE INPUTS")

df = data.build_analysis_table(
    paths.DHS_WOMEN, paths.DHS_GPS,
    paths.MICS_WOMEN, paths.MICS_GPS, paths.DISTRICTS,
)
cov = data.district_covariates(paths.DHS_GEOCOV, paths.DHS_GPS, paths.DISTRICTS)
direct = data.direct_estimates(df)

print(f"\n  {len(df):,} women, {df.district.nunique()} districts")
print(f"  {cov.shape[1]} district-level covariates from satellite data")
print(f"  direct estimates range {direct.direct.min():.1f}% to {direct.direct.max():.1f}%"
      "   <- the problem")


# =====================================================================
rule("2. FITTING THE MODEL")

print("""
  A logistic regression where each district gets its own intercept, and
  those intercepts are themselves drawn from a shared distribution.

  That shared distribution is what makes districts talk to each other. A
  district with plenty of data pulls its own intercept where it wants; a
  district with almost none is held near the middle, because there is not
  enough evidence to justify moving it.
""")

fitted = model.fit(df, cov)
res = fitted["result"]

print(f"  {fitted['formula']}\n")
print(f"  {'effect':34s}{'coef':>9s}{'+/-':>8s}")
print("  " + "-" * 51)
for nm, mn, sd in zip(res.model.exog_names, res.fe_mean, res.fe_sd, strict=True):
    print(f"  {nm[:34]:34s}{mn:+9.3f}{sd:8.3f}")

print("""
  Reading these (log-odds; negative lowers the risk):

    education    -1.10   the dominant effect by a wide margin. Each step
                         up the education ladder roughly thirds the odds.
    wealth       -0.31   real, but a third the size of education.
    travel_times -0.34   counter-intuitive: MORE remote associates with
                         LESS child marriage. Probably geography rather
                         than isolation - Matabeleland is both remote and
                         low-prevalence, Mashonaland is closer to Harare
                         and high. Worth investigating, not asserting.
""")


# =====================================================================
rule("3. THE ESTIMATES")

est = model.district_estimates(fitted)
j = est.join(direct[["direct", "n_married"]])
j.to_csv(OUT / "district_estimates.csv")

print("\n  SMALLEST DISTRICTS - watch the estimate move\n")
print(f"  {'district':24s}{'n':>4s}{'direct':>9s}{'model':>9s}{'90% interval':>16s}")
print("  " + "-" * 62)
for nm, r in j.nsmallest(6, "n").iterrows():
    band = f"[{r.lo:.0f} - {r.hi:.0f}]"
    print(f"  {nm[:24]:24s}{int(r.n):4d}{r.direct:8.1f}%{r.estimate:8.1f}%{band:>16s}")

print("\n  LARGEST DISTRICTS - barely move\n")
print(f"  {'district':24s}{'n':>4s}{'direct':>9s}{'model':>9s}{'90% interval':>16s}")
print("  " + "-" * 62)
for nm, r in j.nlargest(5, "n").iterrows():
    band = f"[{r.lo:.0f} - {r.hi:.0f}]"
    print(f"  {nm[:24]:24s}{int(r.n):4d}{r.direct:8.1f}%{r.estimate:8.1f}%{band:>16s}")

print(f"""
  Range: direct {direct.direct.min():.1f}-{direct.direct.max():.1f}%  ->  model {est.estimate.min():.1f}-{est.estimate.max():.1f}%

  The extremes came in. They were never real - they were small samples.
""")


# =====================================================================
rule("4. DOES IT ACTUALLY BEAT GUESSING?")

print("""
  The honest test: hold out whole districts, fit on the rest, and see
  whether the model predicts them better than simply assuming the
  national rate.

  Held-out districts get NO random intercept - the model has never seen
  them. So any improvement comes purely from generalisable structure.
""")

cv = model.crossval_districts(df, cov)
print(f"  model mean absolute error    {cv['model_mae']:5.2f} percentage points")
print(f"  national-mean baseline       {cv['baseline_mae']:5.2f} percentage points")
print(f"  improvement                  {cv['improvement']:5.2f} points "
      f"({100 * cv['improvement'] / cv['baseline_mae']:.0f}% better)")

print("""
  Modest, and worth reporting as modest. Predicting an unseen district
  from satellite context and population composition alone is genuinely
  hard. A 20% reduction in error is a real result, not a triumph - and
  saying so is the difference between a report and a sales pitch.
""")


# =====================================================================
rule("5. THE CHARTS")

# ---- shrinkage ----
fig, ax = plt.subplots(figsize=(6.6, 6.2))
ax.plot([0, 80], [0, 80], color="#c9c9c5", lw=1.5, ls="--", zorder=1)
sizes = 12 + 260 * (j.n / j.n.max())
ax.scatter(j.direct, j.estimate, s=sizes, color=BLUE, alpha=0.65,
           edgecolor="white", linewidth=1.2, zorder=2)

for nm in ["gokwe south urban", "kariba", "bulawayo", "hurungwe"]:
    if nm in j.index:
        r = j.loc[nm]
        ax.annotate(nm.title(), (r.direct, r.estimate),
                    textcoords="offset points", xytext=(9, -4),
                    fontsize=8.5, color=MUTED)

ax.set_xlabel("Direct estimate (%)  —  what the district's own women said")
ax.set_ylabel("Model estimate (%)")
ax.set_title("Partial pooling: small districts get pulled in", loc="left")
ax.set_xlim(0, 80)
ax.set_ylim(0, 80)
ax.grid(zorder=0)
ax.set_axisbelow(True)
ax.text(2, 75, "dashed line = no change\nbubble size = sample size",
        fontsize=8.5, color=MUTED, va="top")
fig.tight_layout()
fig.savefig(OUT / "shrinkage.png", bbox_inches="tight")
plt.close(fig)

# ---- uncertainty vs sample size ----
fig, ax = plt.subplots(figsize=(7.4, 4.2))
ax.scatter(j.n, j.width, s=42, color=BLUE, alpha=0.7,
           edgecolor="white", linewidth=1)
ax.set_xscale("log")
ax.set_xlabel("women interviewed in the district (log scale)")
ax.set_ylabel("width of 90% interval (points)")
ax.set_title("Less data, wider interval — the model says so honestly", loc="left")
ax.grid()
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT / "uncertainty.png", bbox_inches="tight")
plt.close(fig)

print(f"""
  written:
    {OUT / 'district_estimates.csv'}   <- the deliverable
    {OUT / 'shrinkage.png'}
    {OUT / 'uncertainty.png'}

  The shrinkage chart is the one for the README. Points on the dashed
  line did not move; points far below it were pulled down hard. Bubble
  size is sample size, and the pattern is unmistakable - the big bubbles
  sit on the line, the small ones fall away from it.
""")


# =====================================================================
rule("SUMMARY")

corr = np.corrcoef(j.width, 1 / j.n)[0, 1]
print(f"""
  91 districts estimated, each with a 90% credible interval.

    mean interval width          {est.width.mean():.1f} points
    narrowest                    {est.width.min():.1f}  ({est.width.idxmin()})
    widest                       {est.width.max():.1f}  ({est.width.idxmax()})
    corr(width, 1/n)             {corr:.2f}   <- uncertainty tracks data scarcity

    cross-validated MAE          {cv['model_mae']:.2f} vs {cv['baseline_mae']:.2f} baseline

  That correlation is the point. The model is not equally confident
  everywhere, and it tells you where it is guessing.

  Next: 2C - per-district drivers, and the fairness audit.
""")
