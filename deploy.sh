#!/usr/bin/env bash
# Optional. Deploys the run server to Google Cloud Run in your own project, so the
# viewer can run pages live. Set these first:
#   PROJECT=my-gcp-project VIEWER_ORIGIN=https://my-viewer.example.com SITE=example ./deploy.sh
# Optional: KEEP_RUNS=0 saves nothing about a run (screenshots come back inline),
# RUN_SECRET_NAME picks the secret for run tokens, DAILY_RUNS caps runs per day.
# Expects an image at $REGION-docker.pkg.dev/$PROJECT/server/app:$TAG, a bucket
# gs://$PROJECT-runs, and the secrets made by scripts/setup_secrets.sh.
set -euo pipefail
cd "$(dirname "$0")"

PROJECT=${PROJECT:?Set PROJECT to your Google Cloud project}
VIEWER=${VIEWER_ORIGIN:?Set VIEWER_ORIGIN to where your viewer is hosted}
SITE=${SITE:-example}
REGION=${REGION:-us-west1}
TAG=${1:-latest}
IMAGE=$REGION-docker.pkg.dev/$PROJECT/server/app:$TAG
SERVICE=${SERVICE:-attribute-finder}
KEEP_RUNS=${KEEP_RUNS:-1}
RUN_SECRET_NAME=${RUN_SECRET_NAME:-run-secret}
DAILY_RUNS=${DAILY_RUNS:-20}
NUMBER=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")
ACCOUNT=$NUMBER-compute@developer.gserviceaccount.com

for secret in openrouter-key gateway-key "$RUN_SECRET_NAME"; do
  gcloud secrets add-iam-policy-binding "$secret" --project "$PROJECT" \
    --member "serviceAccount:$ACCOUNT" --role roles/secretmanager.secretAccessor -q > /dev/null
done
gcloud storage buckets add-iam-policy-binding "gs://$PROJECT-runs" \
  --member "serviceAccount:$ACCOUNT" --role roles/storage.objectAdmin -q > /dev/null

gcloud run deploy "$SERVICE" --project "$PROJECT" --region "$REGION" --image "$IMAGE" \
  --memory 2Gi --cpu 2 --timeout 900 --concurrency 1 --max-instances 3 --min-instances 0 \
  --allow-unauthenticated \
  --set-env-vars "RUNS_BUCKET=$PROJECT-runs,VIEWER_ORIGIN=$VIEWER,CLIENT=$SITE,KEEP_RUNS=$KEEP_RUNS,DAILY_RUNS=$DAILY_RUNS" \
  --set-secrets "OPENROUTER_API_KEY=openrouter-key:latest,AI_GATEWAY_API_KEY=gateway-key:latest,RUN_SECRET=$RUN_SECRET_NAME:latest" \
  -q

URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format="value(status.url)")
gcloud run services update "$SERVICE" --project "$PROJECT" --region "$REGION" --update-env-vars "PUBLIC_URL=$URL" -q
echo "$URL"
