"""
Step 2C: why each district scores as it does, and who the model fails.

    python explain_model.py

Produces:
    outputs/district_drivers.csv    per-district explanation
    outputs/fairness.csv            performance by subgroup
    outputs/fairness.png
    outputs/calibration.png
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import paths
from zw_marriage_risk import data, explain, model

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


df = data.build_analysis_table(
    paths.DHS_WOMEN, paths.DHS_GPS,
    paths.MICS_WOMEN, paths.MICS_GPS, paths.DISTRICTS,
)
cov = data.district_covariates(paths.DHS_GEOCOV, paths.DHS_GPS, paths.DISTRICTS)
fitted = model.fit(df, cov)
est = model.district_estimates(fitted)


# =====================================================================
rule("1. WHY IS THIS DISTRICT HIGH?")

print("""
  An estimate on its own is not actionable. "Mbire is 61%" tells a
  programme officer nothing about what to do there.

  So we decompose each district's estimate into the contribution of each
  factor, measured against the national average. Because the model is a
  GLM, its linear predictor is already additive - these contributions are
  exact, not approximated. They are the Shapley values, in closed form.
""")

drivers = explain.district_drivers(fitted, top=3)
drivers.to_csv(OUT / "district_drivers.csv")

print("  HIGHEST-RISK DISTRICTS\n")
for nm, r in drivers.head(4).iterrows():
    print(f"  {nm.upper()}  ({r.province}, n={int(r.n)})  ->  "
          f"{est.loc[nm, 'estimate']:.1f}%")
    print(f"      {r.summary}\n")

print("  LOWEST-RISK DISTRICTS\n")
for nm, r in drivers.tail(2).iterrows():
    print(f"  {nm.upper()}  ({r.province}, n={int(r.n)})  ->  "
          f"{est.loc[nm, 'estimate']:.1f}%")
    print(f"      {r.summary}\n")

big_effect = drivers.district_effect.abs().nlargest(3)
print("  DISTRICTS THE MODEL CANNOT EXPLAIN\n")
print("  A large 'district effect' means the district is worse (or better)")
print("  than its education, wealth and geography can account for. That is")
print("  a question to take to someone who knows the area - not an answer.\n")
for nm in big_effect.index:
    r = drivers.loc[nm]
    print(f"    {nm:26s}{r.district_effect:+6.2f}   ({r.province})")


# =====================================================================
rule("2. WHO DOES THE MODEL FAIL?")

fair = explain.fairness_audit(fitted)
fair.to_csv(OUT / "fairness.csv", index=False)

wealth = fair[fair.group == "wealth"].copy()
labels = {1: "poorest", 2: "poorer", 3: "middle", 4: "richer", 5: "richest"}
wealth["name"] = wealth.level.map(labels)

print("\n  BY WEALTH QUINTILE\n")
print(f"  {'quintile':12s}{'n':>6s}{'actual':>9s}{'predicted':>11s}"
      f"{'bias':>8s}{'brier':>8s}")
print("  " + "-" * 54)
for _, r in wealth.iterrows():
    print(f"  {r['name']:12s}{int(r.n):6d}{r.actual:8.1f}%{r.predicted:10.1f}%"
          f"{r.bias:+8.1f}{r.brier:8.3f}")

worst = wealth.loc[wealth.brier.idxmax()]
best = wealth.loc[wealth.brier.idxmin()]
print(f"""
  ** THE FINDING THAT MATTERS **

  The model is least accurate for the {worst['name'].upper()} women
  (Brier {worst.brier:.3f}) and most accurate for the {best['name']}
  ({best.brier:.3f}) - more than {worst.brier / best.brier:.1f}x the error.

  Those are precisely the girls this tool exists to help. This goes in
  the README in bold. Hiding it would be the worst thing we could do
  in this project.

  Why it happens: outcomes are near 50/50 among the poorest, which is
  inherently the hardest place to predict, while among the richest the
  answer is almost always "no". That is an explanation, not an excuse -
  the practical consequence is that estimates for the poorest districts
  deserve the widest caution.
""")

print("  BY RESIDENCE\n")
for _, r in fair[fair.group == "rural"].iterrows():
    nm = "rural" if r.level == 1 else "urban"
    print(f"    {nm:8s}n={int(r.n):5d}   actual {r.actual:5.1f}%   "
          f"predicted {r.predicted:5.1f}%   bias {r.bias:+.1f}")

print("\n  PROVINCES WHERE THE MODEL IS MOST WRONG\n")
prov = fair[fair.group == "province"].assign(ab=lambda x: x.bias.abs())
for _, r in prov.nlargest(4, "ab").iterrows():
    d = "over" if r.bias > 0 else "under"
    print(f"    {r.level:22s}{d}-predicts by {abs(r.bias):4.1f} points  "
          f"(n={int(r.n)})")


# =====================================================================
rule("3. ARE THE PROBABILITIES REAL?")

cal = explain.calibration(fitted)
print("""
  A model can rank districts correctly and still be badly calibrated.
  That matters here: a programme officer reads "38%" as a probability,
  not as a rank.
""")
print(f"  {'predicted band':16s}{'n':>6s}{'mean pred':>11s}{'observed':>10s}{'gap':>8s}")
print("  " + "-" * 51)
for _, r in cal.iterrows():
    print(f"  {r['bin']:16s}{int(r.n):6d}{r.mean_predicted:10.1f}%"
          f"{r.observed:9.1f}%{r.gap:+8.1f}")

print(f"""
  Mean absolute gap: {cal.gap.abs().mean():.1f} points.

  The pattern is compression toward the middle - the model under-states
  the high band and over-states the low. That is characteristic of a
  shrinkage estimator and is the price of not over-fitting small
  districts. It is reported, not hidden, and isotonic recalibration is
  the obvious next improvement.
""")


# =====================================================================
rule("4. CHARTS")

fig, ax = plt.subplots(figsize=(7.2, 4.2))
x = np.arange(len(wealth))
ax.bar(x - 0.19, wealth.actual, width=0.36, color=BLUE, label="actual")
ax.bar(x + 0.19, wealth.predicted, width=0.36, color=ORANGE, label="model")
ax.set_xticks(x, wealth["name"])
ax.set_ylabel("married before 18 (%)")
ax.set_title("Model vs reality, by wealth quintile", loc="left")
ax.legend(frameon=False)
ax.grid(axis="y")
ax.set_axisbelow(True)
for i, r in enumerate(wealth.itertuples()):
    ax.text(i, max(r.actual, r.predicted) + 1.5, f"brier {r.brier:.2f}",
            ha="center", fontsize=8, color=MUTED)
fig.tight_layout()
fig.savefig(OUT / "fairness.png", bbox_inches="tight")
plt.close(fig)

fig, ax = plt.subplots(figsize=(5.6, 5.4))
ax.plot([0, 75], [0, 75], color="#c9c9c5", lw=1.5, ls="--", zorder=1)
ax.plot(cal.mean_predicted, cal.observed, "o-", color=BLUE, lw=2,
        markersize=8, zorder=2)
ax.set_xlabel("mean predicted (%)")
ax.set_ylabel("observed (%)")
ax.set_title("Calibration — perfect would sit on the line", loc="left")
ax.grid(zorder=0)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT / "calibration.png", bbox_inches="tight")
plt.close(fig)

print(f"""
  written:
    {OUT / 'district_drivers.csv'}
    {OUT / 'fairness.csv'}
    {OUT / 'fairness.png'}
    {OUT / 'calibration.png'}
""")


# =====================================================================
rule("SUMMARY")

print(f"""
  Every district now has a plain-language explanation.
  Every subgroup has a published accuracy figure.
  Calibration is measured and reported, gaps and all.

  Headline for the README:
    least accurate for the {worst['name']} ({worst.brier:.3f} Brier vs
    {best.brier:.3f} for the {best['name']}) - stated plainly, because the
    poorest girls are who this is for.

  Next: 2D - put it behind an API and a map.
""")
