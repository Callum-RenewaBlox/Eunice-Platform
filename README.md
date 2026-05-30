# Eunice — RenewaBlox

**E**nergy **U**tilisation, **N**etwork **I**nsight & **C**omparison **E**ngine — a 7-day half-hourly UK electricity price predictor with a client-facing savings calculator for solar + battery scenarios.

Tech stack: Python · Streamlit · SQLite · scikit-learn (HistGradientBoosting quantile regression).

---

## Local development

```bash
# One-time setup
python -m venv .venv
.\.venv\Scripts\activate              # Windows
# source .venv/bin/activate          # macOS / Linux
pip install -r requirements.txt
cp .env.example .env                  # then fill in METOFFICE_API_KEY

# Run the dashboard
streamlit run app.py

# Run the data pipeline (ingest tariff / weather / grid + retrain + predict)
python ingest.py
```

The app expects `data.sqlite` in the project root. The first ingest run will populate it with ~2 years of half-hourly data across all 14 GSP regions.

---

## Production deploy — Streamlit Community Cloud + GitHub Actions

This is the cheapest viable path (£0/month). Streamlit Cloud hosts the dashboard, GitHub Actions runs the daily ingest, and the SQLite DB is checked into the repo via Git LFS.

### 1. Prepare the repo locally

```bash
# Install Git LFS once on your machine (if not already)
git lfs install

# Initialise the repo (already configured to track data.sqlite via .gitattributes)
git init
git lfs track "data.sqlite"          # picks up the .gitattributes rule
git add .
git commit -m "Initial commit"
```

Sanity check before pushing — make sure `.env` is NOT in the staged files:

```bash
git status --short | grep -E "^A.*\.env$"   # must return nothing
```

### 2. Create a private GitHub repo and push

```bash
# Create the repo via the GitHub web UI (https://github.com/new) — PRIVATE.
# Then:
git remote add origin git@github.com:<your-user>/eunice-renewablox.git
git branch -M main
git push -u origin main
```

The first push will be slow because Git LFS uploads the ~110 MB `data.sqlite` separately. Subsequent pushes only send the delta.

### 3. Configure GitHub Actions secrets

In the repo, go to **Settings → Secrets and variables → Actions → New repository secret**. Add:

| Secret name        | Value                                  |
| ------------------ | -------------------------------------- |
| `METOFFICE_API_KEY` | (your Met Office DataHub JWT — same value as in `.env`) |

The workflow `.github/workflows/daily-ingest.yml` will use this at 16:35 UTC each day.

To test the workflow now, go to **Actions → Daily ingest + model refit → Run workflow**.

### 4. Deploy to Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **New app**, point it at the `eunice-renewablox` repo, branch `main`, main file `app.py`.
3. Under **Advanced settings → Secrets**, paste:

   ```toml
   METOFFICE_API_KEY = "paste-your-met-office-jwt-here"
   # Optional shared password gate:
   # app_password = "set-a-strong-password"
   ```

4. Click **Deploy**. First build takes ~5 minutes (installs deps, pulls LFS DB).

Your app URL will be something like `https://eunice-renewablox.streamlit.app`.

### 5. Lock it down for clients (recommended)

Streamlit Cloud has native OIDC auth — gate the app to specific Google email addresses:

1. In the Streamlit Cloud dashboard → your app → **Settings → Sharing**.
2. Enable **Viewer authentication** → Google.
3. Add the email addresses of each client you want to grant access.

This is free and gives every client a clean Google login flow. No password sharing.

---

## How the daily refresh works in production

```
┌────────────────────────────────────────────────────────────────────┐
│  16:35 UTC daily — GitHub Actions cron fires                        │
│  └─→ Checkout repo (with LFS) → pip install → python ingest.py     │
│       ├─→ Pulls latest tariff / weather / BMRS / carbon intensity   │
│       ├─→ Retrains HistGradientBoosting quantile models             │
│       ├─→ Writes 7-day forecasts to data.sqlite                     │
│       └─→ git commit data.sqlite → git push                         │
│                                                                     │
│  Streamlit Cloud detects new commit → rebuilds the app             │
│  (rebuild takes ~30s — clients see fresh data within 1 min)        │
└────────────────────────────────────────────────────────────────────┘
```

### Manual ad-hoc refresh

Trigger the workflow yourself from **Actions → Daily ingest + model refit → Run workflow**.

---

## Cost summary

| Service | Tier | Cost |
| ------- | ---- | ---- |
| Streamlit Community Cloud | Free | £0/mo |
| GitHub Actions (private repo) | Free 2000 min/mo (we use ~5 min/day = 150 min/mo) | £0/mo |
| Git LFS storage / bandwidth | Free 1 GB / 1 GB/mo (DB is 110 MB, daily delta tiny) | £0/mo |
| **Total** | | **£0/mo** |

If the LFS bandwidth budget gets tight (unlikely until you have many concurrent client viewers triggering rebuilds), upgrade to a single GitHub LFS data pack: $5/month for 50 GB.

---

## Files reference

- `app.py` — Streamlit dashboard
- `ingest.py` — daily data + retrain pipeline (entrypoint for GitHub Actions)
- `config.py` — region map, tariff product codes, API endpoints
- `db.py` — SQLite schema + upserts
- `model.py` — HistGradientBoosting quantile + spike classifier
- `features.py` — feature engineering
- `scenarios.py` — client-facing savings calculator
- `region_lookup.py` — postcode → GSP region resolution
- `octopus.py` / `weather.py` / `bmrs.py` / `carbon_intensity.py` — API clients
- `.github/workflows/daily-ingest.yml` — production cron
- `.streamlit/config.toml` — theme + server settings
- `.streamlit/secrets.toml.example` — secrets template
- `.gitattributes` — Git LFS tracking for `data.sqlite`
