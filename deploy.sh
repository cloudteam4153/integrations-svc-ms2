#!/usr/bin/env bash
set -e 

# -----------------------------
# CONFIG
# -----------------------------
PROJECT_ID="optical-hangar-475419-n3"
REGION="us-central1"
REPO="cloud4153-msvcs"
SERVICE="integrations-svc-ms2"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}"

# -----------------------------
# SAFETY CHECKS
# -----------------------------
echo "Deploying service: ${SERVICE}"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Image: ${IMAGE}"
echo ""

read -p "Continue with deploy? (y/n): " CONFIRM
if [[ "$CONFIRM" != "y" ]]; then
  echo "Deploy cancelled."
  exit 1
fi

# -----------------------------
# BUILD + PUSH IMAGE
# -----------------------------
echo ""
echo "Building and pushing Docker image..."
gcloud builds submit --tag "${IMAGE}"

# -----------------------------
# DEPLOY TO CLOUD RUN
# -----------------------------
echo ""
echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --allow-unauthenticated

# -----------------------------
# SHOW RECENT LOGS
# -----------------------------
echo ""
echo "Showing recent logs..."
gcloud run services logs read "${SERVICE}" \
  --region "${REGION}" \
  --limit 50

echo ""
echo "Deploy finished successfully."
