#!/usr/bin/env bash
# Optional, run once by hand: PROJECT=my-gcp-project scripts/setup_secrets.sh
# Copies the two API keys from .env into your project's Secret Manager, creates the
# run secret, and adds it to your viewer on Vercel.
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT=${PROJECT:?Set PROJECT to your Google Cloud project}
value() { grep -E "^$1=" .env | head -1 | cut -d= -f2- | tr -d '"'; }
RUN_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
printf %s "$(value OPENROUTER_API_KEY)" | gcloud secrets create openrouter-key --project "$PROJECT" --replication-policy automatic --data-file=-
printf %s "$(value AI_GATEWAY_API_KEY)" | gcloud secrets create gateway-key --project "$PROJECT" --replication-policy automatic --data-file=-
printf %s "$RUN_SECRET" | gcloud secrets create run-secret --project "$PROJECT" --replication-policy automatic --data-file=-
(cd web && printf %s "$RUN_SECRET" | npx vercel env add RUN_SECRET production)
echo "Done. Nothing was printed or committed."
