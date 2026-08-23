# The post and the email

Two drafts. Edit them until they sound like you — that matters more than the wording
I have chosen.

---

# 1. The LinkedIn post

**Publish when the URLs are live.** Roughly 500 words, which is about the ceiling for
LinkedIn before people stop scrolling.

---

> **The number that made me build this: 5.**
>
> That is how many women aged 20–24 were interviewed in Kariba district in
> Zimbabwe's 2015 Demographic and Health Survey. Three of them had married before 18.
>
> Divide, and you get "59.3%". Put that on a map and Kariba is one of the darkest
> districts in the country.
>
> It is also almost meaningless. With five respondents the true value could plausibly
> be anywhere from 15% to 100%. If one more woman had answered differently, the number
> moves twenty points.
>
> ---
>
> **One in three Zimbabwean girls marries before she turns 18.** The national figure
> has barely moved in a decade — 32.4% in the 2015 DHS, 33.7% in the 2019 MICS.
>
> But an organisation with a budget cannot work in "Zimbabwe". They work in districts.
> And when I computed a rate for each of Zimbabwe's 91 districts the obvious way, the
> results ranged from 3.3% to 75.1% — with 23 districts based on fewer than 20 women.
>
> The districts that came out *worst* were largely the ones sampled *least*. Small
> samples produce extreme numbers. A map built that way would send money wherever the
> survey happened to be thinnest.
>
> ---
>
> **So I built something better.** A multilevel model where each district gets its own
> estimate, but those estimates borrow strength from districts that resemble them —
> weighted by how much data each one actually has.
>
> Kariba's estimate moved from 59.3% to 48.1%, with an interval of 34–63% that says
> plainly how uncertain it is. Bulawayo, with 399 respondents, moved 0.4 points and got
> an interval five points wide.
>
> Held-out districts are predicted 20% more accurately than simply assuming the
> national rate. Modest — and I would rather report it as modest than oversell it.
>
> ---
>
> **The thing that surprised me:** once education and wealth were in the model, the
> urban/rural coefficient collapsed to almost exactly zero.
>
> The urban/rural gap everyone quotes — 42% versus 20% — is mostly a schooling and
> income gap wearing different clothes. That is not visible in a cross-tabulation. It
> took a multivariate model to see it.
>
> **The thing that went wrong:** my first driver summaries said "education raises
> risk" for high-prevalence districts. Education has a *negative* coefficient, so a
> positive contribution means the district has *less* education. The sentence inverted
> the meaning of the finding. There is now a test that fails if the direction is
> dropped.
>
> ---
>
> **What I am least comfortable with,** and what is written in bold in the README: the
> model is more than twice as inaccurate for the poorest wealth quintile as for the
> richest. Those are precisely the girls this is meant to help. It is stated in the
> model card, in the API, and in the app itself — because someone deciding where to
> spend money deserves to know where the model is weakest.
>
> Map, code and model card: [link]
>
> Built on Zimbabwe DHS 2015 and MICS 2019 microdata, used under registered access.
> Every estimate describes a place. None of them describes a person, and the API has
> no endpoint that could.

---

### Notes on the draft

- **It opens with a number, not a claim.** "The number that made me build this: 5" is
  a hook; "I built a machine learning model" is not.
- **The "what went wrong" paragraph is the one people remember.** Engineers who admit
  a real mistake and explain how they caught it read as engineers.
- **The fairness paragraph is not modesty.** It is the strongest signal in the post —
  it says you audit your own work and publish what you find.
- Cut anything that feels like padding. Shorter is better.

---

# 2. The email

**Send after the site is live.** Four people, one message. Short, no ask.

The MICS readme in your data folder lists them as the people who should receive
publications based on that data — so you have both their addresses and a stated
reason to write.

**To:**
- Taizivei Mungate — ZIMSTAT
- Handrick Chigiji — ZIMSTAT
- Tawanda Chinembiri — Chief of Social Policy and Research, UNICEF Zimbabwe
- Rumbidza Evelyn Tizora — Social Policy and Research, UNICEF Zimbabwe

*(Check the exact addresses against `Read me_Zimbabwe_MICS6.txt` before sending.)*

**Subject:** District-level child marriage estimates from MICS 2019 and DHS 2015

---

> Dear all,
>
> The MICS6 documentation asks that work based on the data be shared with you, so I am
> writing to do that.
>
> I have pooled the MICS 2019 and DHS 2015 women's microdata to produce child marriage
> prevalence estimates for all 91 districts, using a multilevel model with credible
> intervals. Direct district estimates are unusable — 23 districts have fewer than 20
> respondents aged 20–24 — so the model borrows strength across districts and reports
> honestly where it is uncertain.
>
> Two things seemed worth flagging:
>
> **The national rate is flat but provinces diverged.** 32.4% in 2015 and 33.7% in
> 2019 nationally, but Masvingo rose almost 14 points while Mashonaland West fell
> about 7. Some of that is sampling variation at province cell sizes of 120–240, but
> the pattern of national stability masking subnational movement seems worth a closer
> look than the national indicator allows.
>
> **District assignment is possible for both surveys.** Because GPS displacement is
> constrained within Admin 2 boundaries, a point-in-polygon join recovers district
> exactly. It matched all 400 DHS clusters and all 462 MICS clusters, and agreed with
> the DHS-supplied province label on every one. That may be useful to others working
> with these files.
>
> Everything is open, including the model card and its limitations — the model is
> noticeably less accurate for the poorest quintile, which is stated plainly given who
> the work is meant to serve.
>
> Map: [link]
> Code and model card: [link]
>
> I would welcome any correction, particularly on the district name matching and on
> whether the estimates look plausible against what you see in the field.
>
> With thanks for making the data available,
>
> Gamuchirai Nomsa Magamba
> MSc Computer Science (Artificial Intelligence)
> Harare

---

### Notes on the email

- **No ask.** Not for a job, not for a meeting, not for a reply. The competence is the
  message.
- **It gives them something.** The district-assignment method is genuinely useful to
  anyone working with these files, and offering it costs you nothing.
- **It invites correction.** That is not false modesty — it is the thing most likely to
  get a reply, and a reply is the whole point.
- **It states the limitation.** They will find it anyway. Better it comes from you.

Send it once. Do not follow up. If someone replies, reply promptly and briefly.
