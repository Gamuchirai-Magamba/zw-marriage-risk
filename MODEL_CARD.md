# Model Card — `zw-marriage-risk`

**District-level child marriage prevalence estimates for Zimbabwe**

Version 0.1.0 · Gamuchirai Nomsa Magamba · August 2026

---

## Intended use

**What this is for:** helping organisations decide **where** to place child marriage
prevention programmes, when their budget covers a fraction of Zimbabwe's 91 districts.

**Intended users:** NGO programme staff, government planners, researchers.

**What it produces:** for each district, an estimated share of women aged 20–24 who
married or entered a union before 18, a 90% credible interval, and a plain-language
account of which factors drive that estimate.

---

## ⛔ Out-of-scope use

**This model must not be used to assess an individual.**

It estimates prevalence for **places**. It has no capacity to say anything about a
particular girl, and applying it that way would be both statistically invalid and
harmful — inviting stigma, targeting, and self-fulfilling intervention against
children who would have been fine.

Also out of scope:

- **Screening or case-finding.** There is no individual risk score here, by design.
- **Ranking districts without their intervals.** A district estimated at 45% [30–60]
  and one at 40% [38–42] are not comparable as point estimates.
- **Any use implying the estimates are current.** The data is from 2015 and 2019.
- **Countries other than Zimbabwe**, or units other than Admin 2 districts.

---

## Training data

| | |
|---|---|
| Sources | Zimbabwe DHS 2015; Zimbabwe MICS 2019 (MICS6) |
| Sample | 3,487 women aged 20–24 (1,782 DHS + 1,705 MICS) |
| Clusters | 839 |
| Districts | 91 (all of Zimbabwe) |
| Outcome | Married or in union before age 18 (DHS `v511`, MICS `WAGEM`) |
| National rate | 33.0% pooled — DHS 32.4%, MICS 33.7%, against UNICEF's published 34% |

**Individual predictors:** education level, wealth quintile, urban/rural, survey round.

**District predictors:** nightlights composite, travel time to nearest city,
population density, vegetation index, aridity — averaged from the DHS geospatial
covariate file.

**District assignment:** neither survey records district. Both displace cluster GPS
coordinates *within* Admin 2 boundaries, so a point-in-polygon join recovers district
exactly. Validated against DHS's own province labels: 100% agreement across all 400
DHS clusters.

Microdata is used under registered access and is **not redistributed**.

---

## Method

Multilevel (hierarchical) logistic regression with a random intercept per district,
fitted by variational Bayes (`statsmodels.BinomialBayesMixedGLM`).

**Why:** direct per-district estimates are unusable — 23 of 91 districts have fewer
than 20 respondents, and the naive range runs from 3.3% to 75.1%. Partial pooling
lets districts with little data borrow from districts that resemble them, while
districts with plenty of data stand on their own.

Intervals come from sampling each district's random intercept from its posterior and
recomputing the district's prevalence over its observed population composition.

---

## Evaluation

### Does it beat guessing?

Whole districts held out, so the model has never seen them:

| | Mean absolute error |
|---|---|
| **Model** | **11.07 points** |
| National-mean baseline | 13.91 points |
| Improvement | 2.83 points (**20% better**) |

Real, and modest. Predicting an unseen district from satellite context and population
composition alone is hard.

### Does uncertainty behave?

Correlation between interval width and 1/n: **0.71**. Widest interval 28.8 points
(Kariba, n=5); narrowest 5.1 points (Bulawayo, n=399).

### Calibration

Mean absolute gap between predicted and observed, across eight bins: **2.8 points**.

The pattern is **compression toward the middle** — the model under-states the top band
by ~4 points and over-states the bottom by ~3. This is characteristic of a shrinkage
estimator and is the price of not over-fitting small districts. Isotonic
recalibration is the obvious next improvement.

---

## ⚠️ Known biases and limitations

### **The model is least accurate for the poorest women**

| Wealth quintile | Brier score |
|---|---|
| **Poorest** | **0.226** |
| Poorer | 0.220 |
| Middle | 0.211 |
| Richer | 0.197 |
| Richest | 0.106 |

**More than twice the error for the poorest as for the richest.** Those are precisely
the girls this tool exists to help.

The mechanism: among the poorest, outcomes are near 50/50 — inherently the hardest
place to predict. Among the richest, the answer is almost always "no". That is an
explanation, not an excuse. **The practical consequence is that estimates for the
poorest districts deserve the widest caution**, and users should treat their intervals
as a floor rather than a ceiling.

### Other limitations

- **The data is old.** DHS 2015, MICS 2019. The 2023–24 DHS microdata is not yet
  public. Estimates describe the recent past, not today.
- **Variational Bayes is over-confident.** `fit_vb` approximates the posterior and is
  known to understate uncertainty. Real intervals are probably somewhat wider than
  reported. MCMC via PyMC is the upgrade path.
- **Survey weights are not in the likelihood.** Weighted likelihoods are not well
  defined for this estimator; the variables driving the weights (province,
  urban/rural) are included as covariates instead. This is the standard model-based
  approach, but it means model estimates and the weighted direct estimates are not
  strictly like-for-like.
- **Provincial bias up to ±5 points.** Mashonaland East is under-predicted by 4.8;
  Matabeleland South over-predicted by 4.5.
- **Association, not causation.** Education is by far the strongest predictor, but
  causation runs both ways — leaving school raises marriage risk, and impending
  marriage causes girls to leave school. This model cannot separate them.
- **One counter-intuitive coefficient.** Travel time to the nearest city is
  *negatively* associated with child marriage. This is probably geography rather than
  isolation — Matabeleland is both remote and low-prevalence; Mashonaland is closer to
  Harare and high. Flagged for investigation, not asserted as a finding.
- **Districts are not wards.** 91 districts is far better than 10 provinces, but
  programmes often plan at ward level, which this data cannot reach.

---

## Ethical considerations

The subject is vulnerable children. Three commitments shaped the design:

1. **Population-level only.** No individual risk scores are produced, and the API
   provides no endpoint that could be used to score a person.
2. **Uncertainty is never hidden.** Every estimate ships with its interval. A wide
   interval is information — it tells a user to commission local data before
   committing.
3. **Failures are published.** The wealth-quintile result above is in this card, the
   README, and the tool's own interface.

---

## Reproducing this

```bash
pip install -e ".[dev,viz]"
# obtain the microdata yourself - see data/README.md
python fit_model.py       # estimates + shrinkage chart
python explain_model.py   # drivers + fairness audit
python -m pytest          # 29 tests
```

## Contact

Issues and questions: the repository's issue tracker.

## Citation

> Zimbabwe Demographic and Health Survey 2015. ZIMSTAT and ICF International.
> Zimbabwe Multiple Indicator Cluster Survey 2019, MICS6. ZIMSTAT and UNICEF Zimbabwe.
> Both obtained under registered access; microdata not redistributed.
