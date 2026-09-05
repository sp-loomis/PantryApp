#!/usr/bin/env bash
#
# Build the React SPA with the deployed backend's settings and publish it to
# S3 + CloudFront. Reads all configuration from Terragrunt outputs, so the
# infrastructure (terraform/modules/{api_gateway,static_site}) must be applied
# first.
#
# Usage:
#   scripts/deploy-web.sh <env>      # env = dev | prod (default: dev)
#
# Requirements: aws CLI, node/npm, terragrunt — all with valid AWS credentials.

set -euo pipefail

ENV="${1:-dev}"
AWS_REGION="${AWS_REGION:-us-east-2}"

# Resolve repo root regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TG_DIR="${REPO_ROOT}/terraform/environments/${ENV}"

if [[ ! -d "${TG_DIR}" ]]; then
  echo "error: unknown environment '${ENV}' (no ${TG_DIR})" >&2
  exit 1
fi

echo "==> Reading Terragrunt outputs for '${ENV}'"
tg_output() {
  terragrunt output --terragrunt-working-dir "${TG_DIR}" --terragrunt-non-interactive -raw "$1"
}

API_URL="$(tg_output api_gateway_invoke_url)"
POOL_ID="$(tg_output cognito_user_pool_id)"
CLIENT_ID="$(tg_output cognito_client_id)"
BUCKET="$(tg_output web_bucket_name)"
DIST_ID="$(tg_output cloudfront_distribution_id)"
WEB_URL="$(tg_output web_url)"

echo "    API_URL=${API_URL}"
echo "    BUCKET=${BUCKET}"
echo "    DIST_ID=${DIST_ID}"

echo "==> Installing dependencies"
cd "${REPO_ROOT}"
npm ci

echo "==> Building SPA (cognito auth mode)"
VITE_API_GATEWAY_URL="${API_URL}" \
VITE_AUTH_MODE="cognito" \
VITE_COGNITO_USER_POOL_ID="${POOL_ID}" \
VITE_COGNITO_CLIENT_ID="${CLIENT_ID}" \
VITE_AWS_REGION="${AWS_REGION}" \
  npm run build

DIST_DIR="${REPO_ROOT}/frontend/react/web/dist"

# Sync assets first (long cache), then index.html (no-cache) so clients pick up
# new asset hashes immediately without serving a stale entrypoint.
echo "==> Syncing assets to s3://${BUCKET}"
aws s3 sync "${DIST_DIR}" "s3://${BUCKET}" \
  --delete \
  --exclude "index.html" \
  --cache-control "public,max-age=31536000,immutable"

aws s3 cp "${DIST_DIR}/index.html" "s3://${BUCKET}/index.html" \
  --cache-control "no-cache"

echo "==> Invalidating CloudFront distribution ${DIST_ID}"
aws cloudfront create-invalidation \
  --distribution-id "${DIST_ID}" \
  --paths "/*" \
  --query "Invalidation.Id" --output text

echo "==> Done. App is live at: ${WEB_URL}"
