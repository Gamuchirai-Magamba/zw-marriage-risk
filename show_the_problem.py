"""
Why this project needs a proper model.

    python show_the_problem.py

Step 2A built one table: every woman aged 20-24 from both surveys, with
her district attached. This script uses it to demonstrate - not assert -
that the obvious way of estimating district rates does not work.

Everything printed here goes into the README.
"""

from __future__ import annotations

import warnings

import numpy as np

import paths
from zw_marriage_risk import data

warnings.filterwarnings("ignore")


def rule(t):
    print("\n" + "=" * 74)
    print(f"  {t}")
    print("=" * 74)


# =====================================================================
rule("1. THE TABLE WE BUILT")

df = data.build_analysis_table(
    paths.DHS_WOMEN, paths.DHS_GPS,
    paths.MICS_WOMEN, paths.MICS_GPS, paths.DISTRICTS,
)

print(f"\n  {len(df):,} women aged 20-24")
print(f"  {df.district.nunique()} districts")
print(f"  {df.cluster.nunique()} clusters (villages/neighbourhoods)")
print(f"  {df.survey.value_counts().to_dict()}")
print(f"\n  National rate (weighted): "
      f"{100 * np.average(df.y, weights=df.weight):.1f}%")

print("\n  One row per woman. This is the input to everything that follows.\n")
print(df.head(4).to_string(index=False))

print("""
  What to look for: 3,487 rows, 91 districts, both surveys present, and a
  national rate between the DHS 32.4% and the MICS 33.7%. Anything else
  means the pooling went wrong.""")


# =====================================================================
rule("2. THE OBVIOUS APPROACH")

de = data.direct_estimates(df)

print("""
  The obvious thing to do: for each district, take its women, average
  them, call that the district's rate. Let us do exactly that and look
  at what comes out.""")

print(f"\n  districts      : {len(de)}")
print(f"  lowest rate    : {de.direct.min():.1f}%")
print(f"  highest rate   : {de.direct.max():.1f}%")
print(f"  women per district: median {int(de.n.median())}, "
      f"min {int(de.n.min())}, max {int(de.n.max())}")


# =====================================================================
rule("3. WHY IT IS WRONG")

print("\n  The five districts with the FEWEST women:\n")
small = de.nsmallest(5, "n")
print(f"  {'district':24s}{'women':>7s}{'married':>9s}{'estimate':>11s}{'give or take':>15s}")
print("  " + "-" * 66)
for name, r in small.iterrows():
    print(f"  {name[:24]:24s}{int(r.n):7d}{int(r.n_married):9d}"
          f"{r.direct:10.1f}%{'+/- ' + format(r.se, '.0f') + ' points':>15s}")

worst = de.nsmallest(1, "n").iloc[0]
name = de.nsmallest(1, "n").index[0]
print(f"""
  Read the first row slowly.

  {name.title()}: {int(worst.n)} women were interviewed. {int(worst.n_married)} of them married before 18.
  So the "rate" is {worst.direct:.1f}%.

  But the uncertainty is +/- {worst.se:.0f} percentage points. The true value could
  plausibly be anywhere from about {max(0, worst.direct - 2*worst.se):.0f}% to {min(100, worst.direct + 2*worst.se):.0f}%.

  That is not an estimate. That is a coin toss with a decimal point.

  If one more woman had answered differently, the number would move by
  {100/worst.n:.0f} points. A map built on this would rank districts by luck.""")

print("\n  And the five districts that come out HIGHEST:\n")
print(f"  {'district':24s}{'women':>7s}{'married':>9s}{'estimate':>11s}")
print("  " + "-" * 51)
for nm, r in de.head(5).iterrows():
    flag = "  <- fewer than 20 women" if r.unreliable else ""
    print(f"  {nm[:24]:24s}{int(r.n):7d}{int(r.n_married):9d}{r.direct:10.1f}%{flag}")

n_flagged = int(de.unreliable.sum())
print(f"""
  {n_flagged} of {len(de)} districts have fewer than 20 women.

  Notice how many of the "worst" districts are also the smallest ones.
  That is the tell. Small samples produce extreme numbers, so a naive
  ranking puts the least-measured districts at the top - and an NGO
  reading that map would send money to wherever the survey happened to
  be thinnest.""")


# =====================================================================
rule("4. THE SIZE OF THE PROBLEM")

print()
buckets = [(0, 10), (10, 20), (20, 30), (30, 50), (50, 1000)]
for lo, hi in buckets:
    k = int(((de.n >= lo) & (de.n < hi)).sum())
    label = f"{lo}-{hi if hi < 1000 else '400'} women"
    print(f"  {label:16s} {k:3d} districts  {'#' * k}")

print("""
  Roughly a third of Zimbabwe's districts were sampled too thinly to
  stand on their own. We cannot fix that by collecting more data - the
  surveys are finished.

  What we CAN do is let districts borrow information from districts that
  resemble them. That is Step 2B.""")


# =====================================================================
rule("5. WHAT LETS US BORROW")

cov = data.district_covariates(paths.DHS_GEOCOV, paths.DHS_GPS, paths.DISTRICTS)

print(f"""
  For every one of the {len(cov)} districts we also have context that has
  nothing to do with who was interviewed - satellite and geographic
  measurements covering the whole country:
""")
for c in cov.columns:
    print(f"    {c}")

print(f"""
  So when a district has {int(worst.n)} women, the model does not have to guess
  blindly. It can ask: what do districts with similar night-time light,
  similar travel time to a city, similar population density look like?

  A district with 400 women speaks for itself. A district with {int(worst.n)} gets
  pulled toward its peers - and reports a wide interval saying so.

  That is called partial pooling, and it is Step 2B.""")


# =====================================================================
rule("SUMMARY")

print(f"""
  Built:      a table of {len(df):,} women across {df.district.nunique()} districts
  Showed:     direct estimates range {de.direct.min():.1f}% to {de.direct.max():.1f}% and cannot be trusted
  Because:    {n_flagged} districts have under 20 respondents
  Next:       a multilevel model that borrows strength and reports honest
              uncertainty

  Nothing here is a failure. Establishing that the simple approach breaks
  IS the result - it is what justifies the method that follows, and it is
  the part most portfolio projects skip.
""")
