# Cloud Run image for the Eunice Streamlit apps.
#
# One image holds every app in this repo; which one a Cloud Run service runs is
# chosen at deploy time via the APP_FILE env var (defaults to app_lite.py — the
# partner-facing "Eunice Lite" savings tool). The small data_lite.sqlite is baked
# in at build time; the 110 MB LFS-tracked data.sqlite is NOT needed at runtime
# and is excluded by .dockerignore. A fresh data_lite.sqlite (committed daily by
# the refresh Action) triggers an automatic redeploy — see
# .github/workflows/deploy-cloudrun.yml.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install deps first so this layer caches across code/data changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# App code + the small normal-file database (see .dockerignore for exclusions).
COPY . .

# Which app this container serves. Override per service at deploy time:
#   gcloud run deploy eunice      --set-env-vars=APP_FILE=app.py
#   gcloud run deploy eunice-lite --set-env-vars=APP_FILE=app_lite.py
ENV APP_FILE=app_lite.py

# Cloud Run sends traffic to $PORT (8080 by default). Streamlit must bind
# 0.0.0.0:$PORT and run headless. Shell form so $PORT/$APP_FILE expand at runtime.
ENV PORT=8080
EXPOSE 8080
CMD streamlit run "$APP_FILE" \
      --server.port="$PORT" \
      --server.address=0.0.0.0 \
      --server.headless=true \
      --browser.gatherUsageStats=false
