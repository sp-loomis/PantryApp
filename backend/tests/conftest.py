"""
Shared test infrastructure for the Pantry App backend.

Provides:
- The DynamoDB table schema (mirrors production) via ``create_tables``.
- A ``dynamodb_tables`` fixture: a live ``mock_aws`` context with the 3 tables.
- A ``services`` fixture: ItemService + LocationService for service-layer tests.
- An ``api`` fixture: an ``ApiClient`` that drives the real ``app.lambda_handler``
  for end-to-end route tests.

E2E tests should go through ``ApiClient`` only, and should seed data through the
API (not the service layer) so each test traces a whole HTTP request.
"""

import importlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import boto3
import pytest
from moto import mock_aws

import schema

# Test-harness prefix; concrete names derive from the shared schema specs.
TEST_PREFIX = "test-"
ITEMS_TABLE = schema.TABLES["items"].name(TEST_PREFIX)
LOCATIONS_TABLE = schema.TABLES["locations"].name(TEST_PREFIX)
CATEGORIES_TABLE = schema.TABLES["categories"].name(TEST_PREFIX)
TASKS_TABLE = schema.TABLES["tasks"].name(TEST_PREFIX)
REPORTS_TABLE = schema.TABLES["reports"].name(TEST_PREFIX)
MESSAGES_TABLE = schema.TABLES["messages"].name(TEST_PREFIX)
SLACK_CONNECTIONS_TABLE = schema.TABLES["slack_connections"].name(TEST_PREFIX)
SLACK_NONCES_TABLE = schema.TABLES["slack_nonces"].name(TEST_PREFIX)

# Default authenticated user for requests that don't specify one.
USER = "user-1"


# ---------------------------------------------------------------------------
# Table schema (single source in ``schema.py``, shared with the local harness)
# ---------------------------------------------------------------------------

def create_tables(dynamodb) -> None:
    """Create all app tables with the same key schema/GSIs as production."""
    schema.create_all(dynamodb, TEST_PREFIX)


# ---------------------------------------------------------------------------
# Lambda context stand-in (Powertools logging touches a few attributes)
# ---------------------------------------------------------------------------

class FakeLambdaContext:
    """Minimal stand-in for the Lambda context object."""
    function_name = "test-fn"
    memory_limit_in_mb = 128
    invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-fn"
    aws_request_id = "test-request-id"


# ---------------------------------------------------------------------------
# E2E client: builds API Gateway REST events and calls the real handler
# ---------------------------------------------------------------------------

@dataclass
class Response:
    """Normalized view of a lambda_handler result."""
    status_code: int
    body: Dict[str, Any]


class ApiClient:
    """Drives ``app.lambda_handler`` the way API Gateway would.

    Every E2E test uses this single seam. ``call`` builds a REST-proxy event
    (Cognito claims included), invokes the handler, and returns a parsed
    ``Response``.
    """

    def __init__(self, app_module):
        self._app = app_module

    def call(
        self,
        method: str,
        path: str,
        *,
        body: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, str]] = None,
        user: Optional[str] = USER,
        groups: Optional[List[str]] = None,
    ) -> Response:
        """Invoke the handler for one request.

        Args:
            method: HTTP method (e.g. "GET", "POST").
            path:   Resource path (e.g. "/items/abc").
            body:   JSON body; serialized into the event.
            query:  Query-string parameters.
            user:   Authenticated user's ``sub`` claim. ``None`` simulates an
                    unauthenticated request (no claims).
            groups: Cognito groups for the user (e.g. ["Admin"]).
        """
        claims: Dict[str, str] = {}
        if user is not None:
            claims["sub"] = user
        if groups:
            claims["cognito:groups"] = ",".join(groups)

        event = {
            "httpMethod": method,
            "path": path,
            "queryStringParameters": query,
            "headers": {"Content-Type": "application/json"},
            "requestContext": {"authorizer": {"claims": claims}},
            "body": json.dumps(body) if body is not None else None,
            "isBase64Encoded": False,
        }

        result = self._app.lambda_handler(event, FakeLambdaContext())
        parsed = json.loads(result["body"]) if result.get("body") else {}
        return Response(status_code=result["statusCode"], body=parsed)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dynamodb_tables():
    """A mocked DynamoDB with the three app tables, function-scoped."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_tables(dynamodb)
        yield dynamodb


@pytest.fixture
def category_service(dynamodb_tables):
    """CategoryService backed by mocked DynamoDB (service-layer tests)."""
    from services import CategoryService

    yield CategoryService(
        dynamodb_tables.Table(CATEGORIES_TABLE), dynamodb_tables.Table(ITEMS_TABLE)
    )


LEDGER_TABLE = schema.TABLES["ledger"].name(TEST_PREFIX)


@pytest.fixture
def ledger_service(dynamodb_tables):
    """LedgerService backed by mocked DynamoDB (service-layer tests)."""
    from services import LedgerService

    yield LedgerService(dynamodb_tables.Table(LEDGER_TABLE))


@pytest.fixture
def services(dynamodb_tables):
    """ItemService + LocationService backed by mocked DynamoDB (service-layer tests).

    ItemService is wired with a CategoryService (category assignment/validation)
    and a LedgerService (so ledger emits are exercised in service-layer tests).
    """
    from services import ItemService, LocationService, CategoryService, LedgerService

    categories = CategoryService(
        dynamodb_tables.Table(CATEGORIES_TABLE), dynamodb_tables.Table(ITEMS_TABLE)
    )
    ledger = LedgerService(dynamodb_tables.Table(LEDGER_TABLE))
    item_service = ItemService(
        dynamodb_tables.Table(ITEMS_TABLE),
        categories,
        ledger_service=ledger,
    )
    location_service = LocationService(dynamodb_tables.Table(LOCATIONS_TABLE))
    yield item_service, location_service, dynamodb_tables


@pytest.fixture
def task_service(dynamodb_tables):
    """TaskService backed by mocked DynamoDB (service-layer tests)."""
    from services import TaskService, LedgerService

    yield TaskService(
        dynamodb_tables.Table(TASKS_TABLE),
        ledger_service=LedgerService(dynamodb_tables.Table(LEDGER_TABLE)),
    )


@pytest.fixture
def report_service(dynamodb_tables):
    """ReportService backed by mocked DynamoDB (service-layer tests)."""
    from services import ReportService, CategoryService

    categories = CategoryService(
        dynamodb_tables.Table(CATEGORIES_TABLE), dynamodb_tables.Table(ITEMS_TABLE)
    )
    yield ReportService(dynamodb_tables.Table(REPORTS_TABLE), categories)


@pytest.fixture
def message_service(dynamodb_tables):
    """MessageService backed by mocked DynamoDB (service-layer tests)."""
    from services import MessageService

    yield MessageService(dynamodb_tables.Table(MESSAGES_TABLE))


@pytest.fixture
def report_generator(dynamodb_tables):
    """ReportGenerator wired to all backing services (service-layer tests)."""
    from services import (
        ReportService, MessageService, TaskService, ItemService, CategoryService,
        ReportGenerator,
    )

    categories = CategoryService(
        dynamodb_tables.Table(CATEGORIES_TABLE), dynamodb_tables.Table(ITEMS_TABLE)
    )
    reports = ReportService(dynamodb_tables.Table(REPORTS_TABLE), categories)
    messages = MessageService(dynamodb_tables.Table(MESSAGES_TABLE))
    tasks = TaskService(dynamodb_tables.Table(TASKS_TABLE))
    items = ItemService(dynamodb_tables.Table(ITEMS_TABLE), categories)
    yield ReportGenerator(reports, messages, tasks, items, category_service=categories)


@pytest.fixture
def api(dynamodb_tables):
    """An ApiClient wrapping a freshly-reloaded ``app`` bound to the mocked tables.

    ``app`` builds its service/table objects at import time, so the tables must
    exist and the env must be set *before* (re)loading it, inside the mock.
    """
    for env_name, table_name in schema.table_names(TEST_PREFIX).items():
        os.environ[env_name] = table_name
    # Local mode keeps SlackService off KMS/Secrets/Slack (canned responses) and
    # enables the dev-stub connect route, so Slack routes are E2E-testable.
    os.environ["ENVIRONMENT"] = "local"
    # Non-empty so build_authorize_url is configured (the OAuth start guard).
    os.environ["SLACK_CLIENT_ID"] = "test-client-id"
    os.environ["SLACK_REDIRECT_URI"] = "https://test.example.com/slack/oauth/callback"

    import app
    importlib.reload(app)
    return ApiClient(app)
