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

ITEMS_TABLE = "test-items"
LOCATIONS_TABLE = "test-locations"
ITEM_TAGS_TABLE = "test-item-tags"
TASKS_TABLE = "test-tasks"
REPORTS_TABLE = "test-reports"
MESSAGES_TABLE = "test-messages"
SLACK_CONNECTIONS_TABLE = "test-slack-connections"
SLACK_NONCES_TABLE = "test-slack-nonces"

# Default authenticated user for requests that don't specify one.
USER = "user-1"


# ---------------------------------------------------------------------------
# Table schema (kept in one place so unit and E2E tests share it)
# ---------------------------------------------------------------------------

def _gsi(name: str, hash_key: str, range_key: str) -> Dict[str, Any]:
    return {
        "IndexName": name,
        "KeySchema": [
            {"AttributeName": hash_key, "KeyType": "HASH"},
            {"AttributeName": range_key, "KeyType": "RANGE"},
        ],
        "Projection": {"ProjectionType": "ALL"},
    }


def create_tables(dynamodb) -> None:
    """Create the three tables with the same key schema/GSIs as production."""
    dynamodb.create_table(
        TableName=ITEMS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "item_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "item_id", "AttributeType": "S"},
            {"AttributeName": "location_id", "AttributeType": "S"},
            {"AttributeName": "use_by_date", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            _gsi("LocationIndex", "user_id", "location_id"),
            _gsi("UseByDateIndex", "user_id", "use_by_date"),
        ],
    )
    dynamodb.create_table(
        TableName=LOCATIONS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "location_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "location_id", "AttributeType": "S"},
        ],
    )
    dynamodb.create_table(
        TableName=ITEM_TAGS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "tag_item_composite", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "tag_item_composite", "AttributeType": "S"},
            {"AttributeName": "tag_name", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[_gsi("TagIndex", "user_id", "tag_name")],
    )
    dynamodb.create_table(
        TableName=TASKS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "task_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "task_id", "AttributeType": "S"},
            {"AttributeName": "due_date", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[_gsi("DueDateIndex", "user_id", "due_date")],
    )
    dynamodb.create_table(
        TableName=REPORTS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "report_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "report_id", "AttributeType": "S"},
        ],
    )
    dynamodb.create_table(
        TableName=MESSAGES_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "message_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "message_id", "AttributeType": "S"},
            {"AttributeName": "unread_sort", "AttributeType": "S"},
        ],
        # UnreadIndex is sparse: only unread messages carry unread_sort.
        GlobalSecondaryIndexes=[_gsi("UnreadIndex", "user_id", "unread_sort")],
    )
    dynamodb.create_table(
        TableName=SLACK_CONNECTIONS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "connection_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "connection_id", "AttributeType": "S"},
        ],
    )
    dynamodb.create_table(
        TableName=SLACK_NONCES_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[{"AttributeName": "nonce", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "nonce", "AttributeType": "S"}],
    )


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
def services(dynamodb_tables):
    """ItemService + LocationService backed by mocked DynamoDB (service-layer tests)."""
    from services import ItemService, LocationService

    item_service = ItemService(
        dynamodb_tables.Table(ITEMS_TABLE), dynamodb_tables.Table(ITEM_TAGS_TABLE)
    )
    location_service = LocationService(dynamodb_tables.Table(LOCATIONS_TABLE))
    yield item_service, location_service, dynamodb_tables


@pytest.fixture
def task_service(dynamodb_tables):
    """TaskService backed by mocked DynamoDB (service-layer tests)."""
    from services import TaskService

    yield TaskService(dynamodb_tables.Table(TASKS_TABLE))


@pytest.fixture
def report_service(dynamodb_tables):
    """ReportService backed by mocked DynamoDB (service-layer tests)."""
    from services import ReportService

    yield ReportService(dynamodb_tables.Table(REPORTS_TABLE))


@pytest.fixture
def message_service(dynamodb_tables):
    """MessageService backed by mocked DynamoDB (service-layer tests)."""
    from services import MessageService

    yield MessageService(dynamodb_tables.Table(MESSAGES_TABLE))


@pytest.fixture
def report_generator(dynamodb_tables):
    """ReportGenerator wired to all backing services (service-layer tests)."""
    from services import (
        ReportService, MessageService, TaskService, ItemService, ReportGenerator,
    )

    reports = ReportService(dynamodb_tables.Table(REPORTS_TABLE))
    messages = MessageService(dynamodb_tables.Table(MESSAGES_TABLE))
    tasks = TaskService(dynamodb_tables.Table(TASKS_TABLE))
    items = ItemService(
        dynamodb_tables.Table(ITEMS_TABLE), dynamodb_tables.Table(ITEM_TAGS_TABLE)
    )
    yield ReportGenerator(reports, messages, tasks, items)


@pytest.fixture
def api(dynamodb_tables):
    """An ApiClient wrapping a freshly-reloaded ``app`` bound to the mocked tables.

    ``app`` builds its service/table objects at import time, so the tables must
    exist and the env must be set *before* (re)loading it, inside the mock.
    """
    os.environ["ITEMS_TABLE_NAME"] = ITEMS_TABLE
    os.environ["LOCATIONS_TABLE_NAME"] = LOCATIONS_TABLE
    os.environ["ITEM_TAGS_TABLE_NAME"] = ITEM_TAGS_TABLE
    os.environ["TASKS_TABLE_NAME"] = TASKS_TABLE
    os.environ["REPORTS_TABLE_NAME"] = REPORTS_TABLE
    os.environ["MESSAGES_TABLE_NAME"] = MESSAGES_TABLE
    os.environ["SLACK_CONNECTIONS_TABLE_NAME"] = SLACK_CONNECTIONS_TABLE
    os.environ["SLACK_NONCES_TABLE_NAME"] = SLACK_NONCES_TABLE
    # Local mode keeps SlackService off KMS/Secrets/Slack (canned responses) and
    # enables the dev-stub connect route, so Slack routes are E2E-testable.
    os.environ["ENVIRONMENT"] = "local"
    # Non-empty so build_authorize_url is configured (the OAuth start guard).
    os.environ["SLACK_CLIENT_ID"] = "test-client-id"
    os.environ["SLACK_REDIRECT_URI"] = "https://test.example.com/slack/oauth/callback"

    import app
    importlib.reload(app)
    return ApiClient(app)
