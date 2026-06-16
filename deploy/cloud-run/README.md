# Cloud Run migration — Eunice Lite

**Goal:** host the partner-facing app on Google Cloud Run so it never shows
Streamlit's "this app has gone to sleep" button. Cloud Run scales to zero (free
when idle) and cold-starts automatically in a few seconds on the next request —
no human has to click anything.

## Already in the repo (no action needed)

| File | Purpose |
|------|---------|
| `Dockerfile` | One image that can run any app here; entry file chosen at deploy time via the `APP_FILE` env var (default `app_lite.py`). |
| `.dockerignore` | Bakes in the small `data_lite.sqlite`; keeps the 110 MB `data.sqlite`, `.git`, and any secrets out of the image. |
| `.github/workflows/deploy-cloudrun.yml` | Redeploys on every push to `main` (so the daily `data_lite.sqlite` refresh ships automatically). Gated on the `DEPLOY_CLOUD_RUN` repo variable. |

## One-time GCP setup (you do this — I can't reach your Google account)

Needs the `gcloud` CLI (`gcloud auth login`) or the Cloud Console. Set these
placeholders first:

```bash
PROJECT_ID=renewablox-eunice          # pick or confirm your project id
REGION=europe-west2                   # London — lowest latency for UK partners
REPO=Callum-RenewaBlox/Eunice-Platform
SA_NAME=github-deployer
```

**1. Project + billing** (Cloud Run's free tier still needs billing enabled):
```bash
gcloud projects create "$PROJECT_ID"          # skip if it already exists
gcloud config set project "$PROJECT_ID"
# Then link a billing account in the Console: Billing → Link account
```

**2. Enable the APIs:**
```bash
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com iamcredentials.googleapis.com
```

**3. Deploy service account + roles:**
```bash
gcloud iam service-accounts create "$SA_NAME" --display-name="GitHub Actions deployer"
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
for ROLE in roles/run.admin roles/cloudbuild.builds.editor \
            roles/artifactregistry.admin roles/storage.admin \
            roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" --role="$ROLE"
done
```

**4. Workload Identity Federation** (keyless GitHub → GCP auth, no JSON key to leak):
```bash
gcloud iam workload-identity-pools create github \
  --location=global --display-name="GitHub Actions"
POOL=$(gcloud iam workload-identity-pools describe github \
  --location=global --format='value(name)')

gcloud iam workload-identity-pools providers create-oidc github-oidc \
  --location=global --workload-identity-pool=github \
  --display-name="GitHub OIDC" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='$REPO'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

# Let the repo impersonate the deploy SA:
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/$POOL/attribute.repository/$REPO"

# Print the value you'll paste into the GCP_WIF_PROVIDER secret:
gcloud iam workload-identity-pools providers describe github-oidc \
  --location=global --workload-identity-pool=github --format='value(name)'
```

**5. Add GitHub repo Secrets** (Settings → Secrets and variables → Actions → *Secrets*):
- `GCP_PROJECT_ID` — your project id
- `GCP_SERVICE_ACCOUNT` — `$SA_EMAIL` (e.g. `github-deployer@renewablox-eunice.iam.gserviceaccount.com`)
- `GCP_WIF_PROVIDER` — the provider resource name printed at the end of step 4
  (`projects/<NUMBER>/locations/global/workloadIdentityPools/github/providers/github-oidc`)

And repo **Variables** (same page → *Variables*):
- `GCP_REGION` — `europe-west2`
- `DEPLOY_CLOUD_RUN` — `true`  ← this switches the deploy workflow on

**6. First deploy:** GitHub → Actions → **Deploy to Cloud Run** → *Run workflow*
(or just push any change to `main`). The run prints the live URL
(`https://eunice-lite-….a.run.app`). Open it and check the savings calc, live
rates, and chart all work.

## Custom domain (optional)
```bash
gcloud run domain-mappings create --service=eunice-lite \
  --domain=savings.renewablox.com --region="$REGION"
```
Add the DNS records it prints at your registrar (verify domain ownership in
Google Search Console first if prompted).

## Cutover
1. Confirm the Cloud Run URL works end to end.
2. Point partners at the Cloud Run URL (or the custom domain).
3. Keep the Streamlit Cloud app as a warm backup for a week, then retire it. The
   keep-alive Action can stay as-is, or drop `renewablox-savings` from its `APPS`
   list once you've cut over.

## Tuning / notes
- **Cost:** scale-to-zero, comfortably inside Cloud Run's monthly free tier for a
  low-traffic partner tool (~£0).
- **Zero cold-start:** set `--min-instances=1` in the deploy workflow to keep one
  instance always warm (small always-on cost, a few £/month). Default `0` = free,
  ~3-8 s cold start on the first hit after idle.
- **Add the full Eunice app:** same image — add a second deploy step for service
  `eunice` with `--set-env-vars=APP_FILE=app.py`. Ask me and I'll wire it in.
- **If the app loads but the spinner never connects** (proxy blocking the
  WebSocket), add `--server.enableCORS=false --server.enableXsrfProtection=false`
  to the `Dockerfile` CMD. Session affinity (already enabled) usually makes this
  unnecessary.
