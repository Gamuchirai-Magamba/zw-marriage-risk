# Putting it online — the simple version

Right now your map only works on your own laptop. This guide puts it on the internet
so anyone with the link can open it.

**Time:** about an hour. **Cost:** nothing.

---

# First — what does "deploying" actually mean?

At the moment, when you type `streamlit run app.py`, your laptop is doing two jobs:

1. **Running the program** — reading the data, drawing the map
2. **Showing it to you** — in your browser at `localhost:8501`

`localhost` means "this computer". Nobody else can reach it. Close your laptop and
the map disappears.

**Deploying means moving job 1 onto someone else's computer** — one that never sleeps
and has a public address. Then anyone in the world types that address and sees your
map.

You're doing this twice, because you built two things:

| What | Goes on | Ends up at |
|---|---|---|
| **The map** (`app.py`) | Streamlit Cloud | `something.streamlit.app` |
| **The API** (`api.py`) | Render | `something.onrender.com` |

Both are free. Both connect to your GitHub repository and rebuild automatically when
you push changes.

**The map is the important one.** That's the link you'll put on your CV. Do it first.
If you run out of time or patience, stopping after the map is completely fine.

---

# What you need before you start

Tick these off. If any is missing, the deploy will fail confusingly.

- [ ] **A GitHub account** — you have one
- [ ] **Git installed** — you have it
- [ ] **The app runs on your laptop** — `python -m streamlit run app.py` works
- [ ] **`app_data/` has three files in it**

Check that last one:

```powershell
cd C:\Users\ThinkPad\zwgirls\repos\zw-marriage-risk
dir app_data
```

You should see `districts.json`, `districts.geojson`, `meta.json`.

If not:

```powershell
python export_app_data.py
```

> **Why `app_data/` matters so much:** the online version has no access to your DHS
> and MICS files — and it must not, because you agreed not to redistribute them. So
> the online version reads *only* these three files. They're the finished answers, not
> the raw survey data. If they're missing or out of date, so is your website.

---

# PART 1 — Put your code on GitHub

Everything else depends on this. Streamlit and Render both read your code *from
GitHub*, not from your laptop.

## Step 1.1 — Check nothing dangerous is about to be uploaded

```powershell
git init
git add .
git status --short
```

You'll see a list of files. Now the safety check:

```powershell
git status --short | Select-String -Pattern '\.DTA|\.dta|\.sav|paths\.py'
```

**This must print nothing at all.**

If it prints anything, **stop**. It means survey microdata is about to become public.
Send me what it printed.

## Step 1.2 — Check `app_data` IS included

The opposite problem. `app_data/` contains `.json` files, and your `.gitignore` blocks
`.json` files generally — so it needs to be explicitly allowed.

```powershell
git status --short | Select-String "app_data"
```

**This must print three lines** (the three files).

If it prints nothing, they're being ignored. Fix it:

```powershell
git add -f app_data/
git status --short | Select-String "app_data"
```

*(`-f` means "force — add these even though .gitignore says not to".)*

## Step 1.3 — Save a snapshot

```powershell
git commit -m "feat: district-level child marriage estimates with API and map"
```

A "commit" is a saved snapshot of your project. Nothing has left your laptop yet.

## Step 1.4 — Make an empty home for it on GitHub

In your browser:

1. Go to **https://github.com/new**
2. **Repository name:** `zw-marriage-risk`
3. **Description:** `District-level child marriage estimates for Zimbabwe, with uncertainty`
4. Choose **Public**
5. ⚠️ **Leave all three tick-boxes UNTICKED** — "Add a README", "Add .gitignore",
   "Choose a license". You already have all three. Ticking them creates a clash that
   blocks your first upload.
6. Click **Create repository**

## Step 1.5 — Upload

```powershell
git remote add origin https://github.com/Gamuchirai-Magamba/zw-marriage-risk.git
git branch -M main
git push -u origin main
```

Three commands, three jobs:
- `remote add` — tells git where the GitHub copy lives
- `branch -M main` — names your main line of work `main` (what GitHub expects)
- `push` — uploads

Refresh the GitHub page. Your files are there.

---

# PART 2 — Put the map online

## Step 2.1 — Sign in

1. Go to **https://share.streamlit.io**
2. Click **Continue with GitHub**
3. Authorise it when asked

## Step 2.2 — Create the app

1. Click **Create app** (or **New app**)
2. Choose **Deploy a public app from GitHub**
3. Fill in three boxes:

| Box | Put this |
|---|---|
| Repository | `Gamuchirai-Magamba/zw-marriage-risk` |
| Branch | `main` |
| Main file path | `app.py` |

4. Click **Deploy**

## Step 2.3 — Wait

A log scrolls past. It's installing `streamlit`, `plotly` and `pandas` — the three
things listed in `requirements.txt`.

**About two minutes.** Then your map appears.

> **Why only three packages?** Because the online app just reads the finished JSON
> files. It doesn't fit the model, so it doesn't need `statsmodels`, `geopandas` or
> `scikit-learn`. That's why this deploy takes two minutes instead of ten.

## Step 2.4 — Give it a proper address

The default URL is ugly. Change it:

1. Click the **⋮** menu (top right) → **Settings**
2. Under **General**, find the custom subdomain box
3. Type: `zw-marriage-risk`
4. Save

Your URL is now **`https://zw-marriage-risk.streamlit.app`**

**Open it on your phone.** That's the test — if it works there, it works.

## Step 2.5 — Put the link in the README

Open `README.md` and find this line near the top:

```
### 🗺️ [Open the map](https://YOUR-APP.streamlit.app)
```

Replace `YOUR-APP.streamlit.app` with your real address.

## If it fails

| Message | What it means | Fix |
|---|---|---|
| `FileNotFoundError: app_data/...` | The data files didn't upload | Go back to Step 1.2 |
| `ModuleNotFoundError: X` | A package is missing | Add `X` to `requirements.txt`, commit, push |
| Page loads but maps are blank | Usually a data problem | Click **Manage app** (bottom right) to see the log |

**After any fix:** commit and push. Streamlit redeploys automatically within a minute.

---

# PART 3 — Put the API online

The API is for other programmers, not humans. Its main value to you is the
**`/docs` page** — an interactive page, generated automatically, where someone can
click "Try it out" and see your service respond.

Skip this if you're tired. The map is what matters most.

## Step 3.1 — Sign in

1. Go to **https://render.com**
2. **Get Started** → **GitHub**
3. Authorise

## Step 3.2 — Create the service

1. **New +** (top right) → **Web Service**
2. Find `zw-marriage-risk` → **Connect**
3. Render reads your `render.yaml` and fills most fields in. Confirm:

| Field | Should say |
|---|---|
| Language / Runtime | **Docker** |
| Instance type | **Free** |
| Health check path | `/health` |

4. **Deploy Web Service**

## Step 3.3 — Wait longer

**5 to 10 minutes** for the first build. It's constructing a small Linux computer with
your code inside.

When the log says **"Your service is live"**, you're done.

## Step 3.4 — Test it

Open these two addresses (using your real service name):

```
https://YOUR-SERVICE.onrender.com/health
```
Should show: `{"status":"ok","districts":91}`

```
https://YOUR-SERVICE.onrender.com/docs
```
Should show a page listing your endpoints, each expandable, each with a
**"Try it out"** button.

**That second page is your demo.** In an interview, open it, click "Try it out" on
`/districts/{name}`, type `kariba`, hit Execute. It's far more convincing than a
screenshot.

## Step 3.5 — Note the sleeping problem

Render's free tier **puts your service to sleep after 15 minutes of no visitors.** The
next request takes about 30 seconds while it wakes up.

Add this line to your README under the API link:

> The API sleeps after 15 minutes of inactivity. The first request after a quiet
> period takes about 30 seconds to respond.

Saying so is better than a visitor deciding your service is broken.

---

# PART 4 — Automatic testing

This gives you the small green **"tests passing"** badge at the top of your README.
Every time you push code, GitHub runs your 41 tests on its own machines. Hiring
managers notice it.

## Step 4.1 — Create the file

GitHub protects this kind of file, so it must be made by hand:

```powershell
mkdir .github\workflows
notepad .github\workflows\ci.yml
```

## Step 4.2 — Paste this, save, close

```yaml
name: tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip

      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev,app]"

      - name: Lint
        run: ruff check src tests

      - name: Test
        run: pytest -v -m "not slow"
```

⚠️ **YAML cares about indentation. Use spaces, never the Tab key.**

## Step 4.3 — Push it

```powershell
git add .github
git commit -m "ci: run tests on every push"
git push
```

## Step 4.4 — Watch it

On GitHub, click the **Actions** tab. You'll see a run in progress. Two to three
minutes.

**Green tick = passing.** The badge in your README goes green automatically.

> **What's clever here:** GitHub's computers have no DHS registration, so the tests
> needing microdata skip themselves. But the API tests still run — because
> `app_data/` is in the repository. **CI is genuinely testing the thing you
> deployed.**

---

# PART 5 — Finish the README

## Step 5.1 — Take a screenshot

Open your live map. Screenshot the top section with both maps visible
(**Windows key + Shift + S**).

Save it as:

```
C:\Users\ThinkPad\zwgirls\repos\zw-marriage-risk\outputs\screenshot.png
```

The README already references that exact path. **A README that opens with a picture
gets read; one that opens with text gets skimmed.**

## Step 5.2 — Fill in the links

Open `README.md`, replace:

- `https://YOUR-APP.streamlit.app` → your Streamlit address
- `https://YOUR-API.onrender.com/docs` → your Render address

## Step 5.3 — Push

```powershell
git add .
git commit -m "docs: add live links and screenshot"
git push
```

---

# You're done when

- [ ] Code is on GitHub
- [ ] Map opens at a `.streamlit.app` address — **tested on your phone**
- [ ] `/health` returns `{"status":"ok","districts":91}`
- [ ] `/docs` page loads and "Try it out" works
- [ ] Green tests badge on the README
- [ ] Screenshot at the top of the README
- [ ] Both links in the README are real

**When that list is complete, Phase 2 is finished** — and you can say
*"here, click this"* to anybody.

---

# Then, when you're ready

Two things in `WRITEUP.md`, both already drafted:

1. **A LinkedIn post.** Publish it once, with the link. Don't post before the site
   works — people click in the first hour or not at all.
2. **An email** to four named people at ZIMSTAT and UNICEF Zimbabwe. Short, no ask.
   Sleep on the wording before sending.

---

# If you get stuck

Copy the **whole error message** and send it to me. Deployment errors are usually one
small thing — a missing file, a typo in a name, a package left out — and they're much
easier to fix than they look.

Every developer's first deploy fails at something. It isn't a sign you've done
anything wrong.
