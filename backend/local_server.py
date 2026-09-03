"""
Tier-1 local dev server for the Pantry App backend.

Wraps the real Lambda handler (``app.lambda_handler``) in a tiny Flask HTTP
server so a browser frontend can talk to the backend on ``localhost`` with no
AWS account and no API Gateway. For each request it builds an API Gateway
REST-proxy event (mirroring ``tests/conftest.py::ApiClient.call``), injects a
fixed dev Cognito ``sub`` claim (dev-bypass auth), and returns the handler's
response with permissive CORS for the Vite dev server.

Run:
    docker compose up -d            # DynamoDB Local on :8001
    python backend/seed_local.py    # create tables + sample data
    python backend/local_server.py  # serves on :8000

Env knobs:
    DEV_USER_ID       Cognito ``sub`` injected as the authenticated user (default "dev-user").
    DEV_USER_GROUPS   Comma-separated Cognito groups (e.g. "Admin") for admin testing.
    PORT              Server port (default 8000).
    DYNAMODB_ENDPOINT DynamoDB Local URL (default http://localhost:8001).
    CORS_ORIGIN       Allowed browser origin (default http://localhost:5173).

NOTE: this is a DEV-ONLY server. Auth is faked; never use it in a deployed tier.
"""

import json
import os

# ---------------------------------------------------------------------------
# Environment MUST be configured before importing ``app`` — the Lambda module
# builds its boto3 resource, table handles, and services at import time.
# ---------------------------------------------------------------------------
from local_schema import TABLE_NAMES

DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8001")

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
# botocore honors this to point the dynamodb client at DynamoDB Local. Only set
# it when an endpoint is configured, so leaving DYNAMODB_ENDPOINT empty falls
# back to default AWS resolution (e.g. for in-process moto-backed testing).
if DYNAMODB_ENDPOINT:
    os.environ.setdefault("AWS_ENDPOINT_URL_DYNAMODB", DYNAMODB_ENDPOINT)
# Silence X-Ray tracing outside Lambda.
os.environ.setdefault("POWERTOOLS_TRACE_DISABLED", "1")
os.environ.setdefault("POWERTOOLS_METRICS_NAMESPACE", "PantryAppLocal")
for env_name, table_name in TABLE_NAMES.items():
    os.environ.setdefault(env_name, table_name)

from flask import Flask, Response, request  # noqa: E402

import app as lambda_app  # noqa: E402

DEV_USER_ID = os.environ.get("DEV_USER_ID", "dev-user")
DEV_USER_GROUPS = os.environ.get("DEV_USER_GROUPS", "")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:5173")
PORT = int(os.environ.get("PORT", "8000"))

flask_app = Flask(__name__)


class _LambdaContext:
    """Minimal stand-in for the Lambda context object (Powertools reads a few attrs)."""

    function_name = "pantry-local"
    memory_limit_in_mb = 128
    invoked_function_arn = "arn:aws:lambda:us-east-1:000000000000:function:pantry-local"
    aws_request_id = "local-request-id"


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Max-Age": "86400",
    }


def _build_event(path: str) -> dict:
    """Translate the current Flask request into an API Gateway REST-proxy event."""
    claims = {"sub": DEV_USER_ID}
    if DEV_USER_GROUPS:
        claims["cognito:groups"] = DEV_USER_GROUPS

    query = dict(request.args) or None
    raw_body = request.get_data(as_text=True)

    return {
        "httpMethod": request.method,
        "path": path,
        "queryStringParameters": query,
        "headers": {"Content-Type": "application/json"},
        "requestContext": {"authorizer": {"claims": claims}},
        "body": raw_body if raw_body else None,
        "isBase64Encoded": False,
    }


@flask_app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
@flask_app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
def proxy(path: str):
    """Single catch-all route: forwards everything to the Lambda handler."""
    # CORS preflight — answer directly.
    if request.method == "OPTIONS":
        return Response(status=204, headers=_cors_headers())

    event = _build_event("/" + path)
    result = lambda_app.lambda_handler(event, _LambdaContext())

    body = result.get("body") or ""
    status = result.get("statusCode", 200)
    headers = _cors_headers()
    headers["Content-Type"] = "application/json"
    # Preserve any headers the handler set (without clobbering CORS).
    for key, value in (result.get("headers") or {}).items():
        headers.setdefault(key, value)
    return Response(body, status=status, headers=headers)


if __name__ == "__main__":
    print(f"Pantry local API → http://localhost:{PORT}")
    print(f"  dev user (sub): {DEV_USER_ID}" + (f"  groups: {DEV_USER_GROUPS}" if DEV_USER_GROUPS else ""))
    print(f"  DynamoDB Local: {DYNAMODB_ENDPOINT}")
    print(f"  CORS origin:    {CORS_ORIGIN}")
    # threaded=False keeps request handling serial and predictable for dev.
    flask_app.run(host="0.0.0.0", port=PORT, debug=True, use_reloader=False)
