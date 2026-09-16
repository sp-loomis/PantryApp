"""
Pantry App - Core API Lambda Handler

This Lambda function provides the API for the Pantry App inventory management system.
It uses AWS Lambda Powertools for structured logging, tracing, and metrics.
"""

import os
from datetime import datetime
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig, Response

from services import (
    ItemService, LocationService, TagService, TaskService,
    ReportService, MessageService, ReportGenerator, SlackService,
)
from auth import get_effective_user_id, AuthenticationError

# Initialize Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PantryApp")
# CORS lets the CloudFront-hosted SPA call this API cross-origin. The allowed
# origin is injected by Terraform (ALLOWED_ORIGIN); "*" is safe here because the
# API authenticates with a Bearer token, not cookies. API Gateway answers the
# OPTIONS preflight via a MOCK integration (see terraform/modules/api_gateway),
# so this config just adds the CORS headers to real responses.
cors_config = CORSConfig(
    allow_origin=os.environ.get("ALLOWED_ORIGIN", "*"),
    allow_headers=["Authorization", "Content-Type"],
)
app = APIGatewayRestResolver(cors=cors_config)

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')

# Get table names from environment variables
ITEMS_TABLE = os.environ.get('ITEMS_TABLE_NAME')
LOCATIONS_TABLE = os.environ.get('LOCATIONS_TABLE_NAME')
ITEM_TAGS_TABLE = os.environ.get('ITEM_TAGS_TABLE_NAME')
TASKS_TABLE = os.environ.get('TASKS_TABLE_NAME')
REPORTS_TABLE = os.environ.get('REPORTS_TABLE_NAME')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE_NAME')
SLACK_CONNECTIONS_TABLE = os.environ.get('SLACK_CONNECTIONS_TABLE_NAME')
SLACK_NONCES_TABLE = os.environ.get('SLACK_NONCES_TABLE_NAME')

# Slack integration config (see docs/slack-integration-plan.md).
SLACK_CLIENT_ID = os.environ.get('SLACK_CLIENT_ID', '')
SLACK_REDIRECT_URI = os.environ.get('SLACK_REDIRECT_URI', '')
SLACK_KMS_KEY_ID = os.environ.get('SLACK_KMS_KEY_ID')
SLACK_SECRET_ARN = os.environ.get('SLACK_SECRET_ARN')
# The Flask dev shim sets ENVIRONMENT=local; that flips SlackService into a
# no-network mode (passthrough token "encryption", stubbed secret + Slack calls).
SLACK_LOCAL_MODE = os.environ.get('ENVIRONMENT') == 'local'

# Initialize services
item_service = ItemService(dynamodb.Table(ITEMS_TABLE), dynamodb.Table(ITEM_TAGS_TABLE))
location_service = LocationService(dynamodb.Table(LOCATIONS_TABLE))
tag_service = TagService(dynamodb.Table(ITEM_TAGS_TABLE))
task_service = TaskService(dynamodb.Table(TASKS_TABLE))
report_service = ReportService(dynamodb.Table(REPORTS_TABLE))
message_service = MessageService(dynamodb.Table(MESSAGES_TABLE))
report_generator = ReportGenerator(report_service, message_service, task_service, item_service)

# KMS/Secrets clients are lazy (boto3 resolves creds on first call), so building
# them at import time is cheap even when the Slack feature is unconfigured.
slack_service = SlackService(
    dynamodb.Table(SLACK_CONNECTIONS_TABLE) if SLACK_CONNECTIONS_TABLE else None,
    boto3.client('kms'),
    boto3.client('secretsmanager'),
    client_id=SLACK_CLIENT_ID,
    redirect_uri=SLACK_REDIRECT_URI,
    kms_key_id=SLACK_KMS_KEY_ID,
    secret_arn=SLACK_SECRET_ARN,
    nonces_table=dynamodb.Table(SLACK_NONCES_TABLE) if SLACK_NONCES_TABLE else None,
    local_mode=SLACK_LOCAL_MODE,
)


def _current_user_id() -> str:
    """Resolve the effective user_id for the current request (honors admin override)."""
    query_params = app.current_event.query_string_parameters or {}
    requested_user_id = query_params.get('user_id')
    return get_effective_user_id(app.current_event.raw_event, requested_user_id)


def _current_tz() -> str:
    """Return the client's IANA timezone from the query string, or None.

    Task windows (today / this week / interval slots) are computed in the
    caller's local time so daily/weekly chores roll over at local midnight.
    """
    query_params = app.current_event.query_string_parameters or {}
    return query_params.get('tz')


# ============================================================================
# Storage Location Endpoints
# ============================================================================

@app.post("/locations")
@tracer.capture_method
def create_location():
    """Create a new storage location."""
    try:
        user_id = _current_user_id()

        data = app.current_event.json_body or {}
        if not data.get('name'):
            return {"error": "Missing required field: name"}, 400

        location = location_service.create_location(
            user_id=user_id,
            name=data['name'],
            description=data.get('description', '')
        )
        metrics.add_metric(name="LocationCreated", unit="Count", value=1)
        return {"location": location}, 201
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error creating location")
        metrics.add_metric(name="LocationCreationError", unit="Count", value=1)
        return {"error": str(e)}, 500


@app.get("/locations")
@tracer.capture_method
def list_locations():
    """List all storage locations for the authenticated user."""
    try:
        user_id = _current_user_id()
        locations = location_service.list_locations(user_id)
        return {"locations": locations}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error listing locations")
        return {"error": str(e)}, 500


@app.get("/locations/<location_id>")
@tracer.capture_method
def get_location(location_id: str):
    """Get a specific storage location."""
    try:
        user_id = _current_user_id()
        location = location_service.get_location(user_id, location_id)
        if not location:
            return {"error": "Location not found"}, 404
        return {"location": location}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error getting location")
        return {"error": str(e)}, 500


@app.put("/locations/<location_id>")
@tracer.capture_method
def update_location(location_id: str):
    """Update a storage location."""
    try:
        user_id = _current_user_id()
        data = app.current_event.json_body or {}
        location = location_service.update_location(user_id, location_id, data)
        if not location:
            return {"error": "Location not found"}, 404
        metrics.add_metric(name="LocationUpdated", unit="Count", value=1)
        return {"location": location}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error updating location")
        return {"error": str(e)}, 500


@app.delete("/locations/<location_id>")
@tracer.capture_method
def delete_location(location_id: str):
    """Delete a storage location."""
    try:
        user_id = _current_user_id()
        success = location_service.delete_location(user_id, location_id)
        if not success:
            return {"error": "Location not found"}, 404
        metrics.add_metric(name="LocationDeleted", unit="Count", value=1)
        return {"message": "Location deleted successfully"}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error deleting location")
        return {"error": str(e)}, 500


# ============================================================================
# Item Endpoints
#
# NOTE: Route registration order matters. Powertools matches the first route
# whose pattern matches, so more specific paths (e.g. /items/expiring,
# /items/<item_id>/tags) MUST be registered before /items/<item_id>.
# ============================================================================

@app.post("/items")
@tracer.capture_method
def create_item():
    """Create a new inventory item with optional dimensions."""
    try:
        user_id = _current_user_id()

        data = app.current_event.json_body or {}
        missing = [f for f in ("name", "location_id") if not data.get(f)]
        if missing:
            return {"error": f"Missing required field(s): {', '.join(missing)}"}, 400

        tags = data.get('tags', [])
        if not isinstance(tags, list):
            return {"error": "Invalid value for 'tags': must be a list"}, 400

        # copies>1 creates that many distinct entries; the service validates the
        # range and returns a single dict (copies==1) or a list (copies>1).
        copies = data.get('copies', 1)

        result = item_service.create_item(
            user_id=user_id,
            name=data['name'],
            location_id=data['location_id'],
            dimensions=data.get('dimensions', []),
            use_by_date=data.get('use_by_date'),
            tags=tags,
            notes=data.get('notes', ''),
            copies=copies
        )
        metrics.add_metric(name="ItemCreated", unit="Count", value=len(result) if isinstance(result, list) else 1)
        if isinstance(result, list):
            return {"items": result}, 201
        return {"item": result}, 201
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        logger.warning(f"Validation error creating item: {str(e)}")
        return {"error": str(e)}, 400
    except Exception as e:
        logger.exception("Error creating item")
        metrics.add_metric(name="ItemCreationError", unit="Count", value=1)
        return {"error": str(e)}, 500


@app.get("/items")
@tracer.capture_method
def list_items():
    """List inventory items with optional filters."""
    try:
        query_params = app.current_event.query_string_parameters or {}
        user_id = _current_user_id()

        location_id = query_params.get('location_id')
        tag = query_params.get('tag')

        # location_id and tag stack (AND) when both are supplied.
        items = item_service.list_items(user_id, location_id, tag)

        return {"items": items}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error listing items")
        return {"error": str(e)}, 500


@app.get("/items/expiring")
@tracer.capture_method
def get_expiring_items():
    """Get items expiring soon."""
    try:
        query_params = app.current_event.query_string_parameters or {}
        user_id = _current_user_id()

        location_id = query_params.get('location_id')
        try:
            days = int(query_params.get('days', 7))
        except (TypeError, ValueError):
            return {"error": "Invalid value for 'days': must be an integer"}, 400
        if days < 0:
            return {"error": "'days' must be non-negative"}, 400

        items = item_service.get_expiring_items(user_id, location_id, days)
        return {"items": items}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error getting expiring items")
        return {"error": str(e)}, 500


@app.get("/items/<item_id>/tags")
@tracer.capture_method
def get_item_tags(item_id: str):
    """Get the tags for a specific item."""
    try:
        user_id = _current_user_id()
        tags = item_service.get_item_tags(user_id, item_id)
        if tags is None:
            return {"error": "Item not found"}, 404
        return {"tags": tags}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error getting item tags")
        return {"error": str(e)}, 500


@app.post("/items/<item_id>/tags")
@tracer.capture_method
def add_item_tags(item_id: str):
    """Add one or more tags to an item."""
    try:
        user_id = _current_user_id()
        data = app.current_event.json_body or {}
        tags = data.get('tags', [])
        if not tags:
            return {"error": "Missing required field: tags"}, 400

        result = item_service.add_item_tags(user_id, item_id, tags)
        if result is None:
            return {"error": "Item not found"}, 404
        metrics.add_metric(name="ItemTagsAdded", unit="Count", value=1)
        return {"tags": result}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error adding item tags")
        return {"error": str(e)}, 500


@app.delete("/items/<item_id>/tags/<tag>")
@tracer.capture_method
def remove_item_tag(item_id: str, tag: str):
    """Remove a single tag from an item."""
    try:
        user_id = _current_user_id()
        result = item_service.remove_item_tag(user_id, item_id, tag)
        if result is None:
            return {"error": "Item not found"}, 404
        metrics.add_metric(name="ItemTagRemoved", unit="Count", value=1)
        return {"tags": result}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error removing item tag")
        return {"error": str(e)}, 500


@app.get("/items/<item_id>")
@tracer.capture_method
def get_item(item_id: str):
    """Get a specific inventory item."""
    try:
        user_id = _current_user_id()
        item = item_service.get_item(user_id, item_id)
        if not item:
            return {"error": "Item not found"}, 404
        return {"item": item}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error getting item")
        return {"error": str(e)}, 500


@app.put("/items/<item_id>")
@tracer.capture_method
def update_item(item_id: str):
    """Update an inventory item, including dimensions and tags."""
    try:
        user_id = _current_user_id()
        data = app.current_event.json_body or {}
        if 'tags' in data and not isinstance(data['tags'], list):
            return {"error": "Invalid value for 'tags': must be a list"}, 400
        item = item_service.update_item(user_id, item_id, data)
        if not item:
            return {"error": "Item not found"}, 404
        metrics.add_metric(name="ItemUpdated", unit="Count", value=1)
        return {"item": item}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        logger.warning(f"Validation error updating item: {str(e)}")
        return {"error": str(e)}, 400
    except Exception as e:
        logger.exception("Error updating item")
        return {"error": str(e)}, 500


@app.delete("/items/<item_id>")
@tracer.capture_method
def delete_item(item_id: str):
    """Delete an inventory item (mark as used)."""
    try:
        user_id = _current_user_id()
        success = item_service.delete_item(user_id, item_id)
        if not success:
            return {"error": "Item not found"}, 404
        metrics.add_metric(name="ItemDeleted", unit="Count", value=1)
        return {"message": "Item deleted successfully"}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error deleting item")
        return {"error": str(e)}, 500


# ============================================================================
# Tag Endpoints
# ============================================================================

@app.get("/tags")
@tracer.capture_method
def list_tags():
    """List all distinct tags across the user's inventory."""
    try:
        user_id = _current_user_id()
        tags = item_service.list_all_tags(user_id)
        return {"tags": tags}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error listing tags")
        return {"error": str(e)}, 500


# ============================================================================
# Search and Query Endpoints
# ============================================================================

@app.post("/search")
@tracer.capture_method
def search_items():
    """Advanced search for items with multiple criteria."""
    try:
        user_id = _current_user_id()
        data = app.current_event.json_body or {}

        # Optional fuzzy-match threshold for name search; must be in (0, 1].
        min_score = data.get('min_score')
        if min_score is not None:
            try:
                min_score = float(min_score)
            except (TypeError, ValueError):
                return {"error": "Invalid value for 'min_score': must be a number"}, 400
            if not 0 < min_score <= 1:
                return {"error": "'min_score' must be between 0 (exclusive) and 1"}, 400

        tags = data.get('tags', [])
        if not isinstance(tags, list):
            return {"error": "Invalid value for 'tags': must be a list"}, 400

        # Validate the date-range bounds as ISO-8601; malformed values would
        # otherwise silently mis-filter.
        for field in ('use_by_date_start', 'use_by_date_end'):
            value = data.get(field)
            if value is not None:
                try:
                    datetime.fromisoformat(value)
                except (TypeError, ValueError):
                    return {"error": f"Invalid value for '{field}': must be an ISO-8601 date"}, 400

        search_kwargs = dict(
            user_id=user_id,
            name=data.get('name'),
            location_id=data.get('location_id'),
            tags=tags,
            use_by_date_start=data.get('use_by_date_start'),
            use_by_date_end=data.get('use_by_date_end'),
        )
        if min_score is not None:
            search_kwargs['min_score'] = min_score

        items = item_service.search_items(**search_kwargs)
        return {"items": items}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        logger.warning(f"Validation error searching items: {str(e)}")
        return {"error": str(e)}, 400
    except Exception as e:
        logger.exception("Error searching items")
        return {"error": str(e)}, 500


@app.get("/aggregate")
@tracer.capture_method
def get_aggregate_stats():
    """Get aggregate statistics for inventory with dimension support."""
    try:
        query_params = app.current_event.query_string_parameters or {}
        user_id = _current_user_id()

        location_id = query_params.get('location_id')
        tag = query_params.get('tag')

        # Parse requested units from query params
        # Format: ?weight_unit=kg&volume_unit=gallon
        requested_units = {}
        if query_params.get('weight_unit'):
            requested_units['weight'] = query_params['weight_unit']
        if query_params.get('volume_unit'):
            requested_units['volume'] = query_params['volume_unit']

        stats = item_service.get_aggregate_stats(user_id, location_id, tag, requested_units or None)
        return {"stats": stats}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        # e.g. an unrecognized weight_unit/volume_unit requested for conversion.
        logger.warning(f"Validation error getting aggregate stats: {str(e)}")
        return {"error": f"Invalid unit: {str(e)}"}, 400
    except Exception as e:
        logger.exception("Error getting aggregate stats")
        return {"error": str(e)}, 500


# ============================================================================
# Task Endpoints
#
# NOTE: Route registration order matters (see the Item section). The specific
# /tasks/<task_id>/complete and /uncomplete paths MUST be registered before the
# bare /tasks/<task_id> routes.
# ============================================================================

@app.post("/tasks")
@tracer.capture_method
def create_task():
    """Create a new task (one-shot or recurring)."""
    try:
        user_id = _current_user_id()
        data = app.current_event.json_body or {}
        if not data.get('name'):
            return {"error": "Missing required field: name"}, 400

        tags = data.get('tags', [])
        if not isinstance(tags, list):
            return {"error": "Invalid value for 'tags': must be a list"}, 400

        task = task_service.create_task(
            user_id=user_id,
            name=data['name'],
            notes=data.get('notes', ''),
            tags=tags,
            recurrence_type=data.get('recurrence_type', 'none'),
            recurrence_interval=data.get('recurrence_interval'),
            anchor_date=data.get('anchor_date'),
            due_date=data.get('due_date'),
            graceful=data.get('graceful', True),
            tz=_current_tz(),
        )
        metrics.add_metric(name="TaskCreated", unit="Count", value=1)
        return {"task": task}, 201
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        logger.warning(f"Validation error creating task: {str(e)}")
        return {"error": str(e)}, 400
    except Exception as e:
        logger.exception("Error creating task")
        metrics.add_metric(name="TaskCreationError", unit="Count", value=1)
        return {"error": str(e)}, 500


@app.get("/tasks")
@tracer.capture_method
def list_tasks():
    """List tasks with computed status, optionally filtered by status/tag."""
    try:
        query_params = app.current_event.query_string_parameters or {}
        user_id = _current_user_id()

        tasks = task_service.list_tasks(
            user_id,
            tz=_current_tz(),
            status=query_params.get('status'),
            tag=query_params.get('tag'),
        )
        return {"tasks": tasks}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error listing tasks")
        return {"error": str(e)}, 500


@app.post("/tasks/<task_id>/complete")
@tracer.capture_method
def complete_task(task_id: str):
    """Mark a task complete for its current window."""
    try:
        user_id = _current_user_id()
        task = task_service.complete_task(user_id, task_id, tz=_current_tz())
        if task is None:
            return {"error": "Task not found"}, 404
        metrics.add_metric(name="TaskCompleted", unit="Count", value=1)
        return {"task": task}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error completing task")
        return {"error": str(e)}, 500


@app.post("/tasks/<task_id>/uncomplete")
@tracer.capture_method
def uncomplete_task(task_id: str):
    """Undo completion of a task for its current window."""
    try:
        user_id = _current_user_id()
        task = task_service.uncomplete_task(user_id, task_id, tz=_current_tz())
        if task is None:
            return {"error": "Task not found"}, 404
        metrics.add_metric(name="TaskUncompleted", unit="Count", value=1)
        return {"task": task}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error uncompleting task")
        return {"error": str(e)}, 500


@app.get("/tasks/<task_id>")
@tracer.capture_method
def get_task(task_id: str):
    """Get a specific task with computed status."""
    try:
        user_id = _current_user_id()
        task = task_service.get_task(user_id, task_id, tz=_current_tz())
        if not task:
            return {"error": "Task not found"}, 404
        return {"task": task}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error getting task")
        return {"error": str(e)}, 500


@app.put("/tasks/<task_id>")
@tracer.capture_method
def update_task(task_id: str):
    """Update a task."""
    try:
        user_id = _current_user_id()
        data = app.current_event.json_body or {}
        if 'tags' in data and not isinstance(data['tags'], list):
            return {"error": "Invalid value for 'tags': must be a list"}, 400
        task = task_service.update_task(user_id, task_id, data, tz=_current_tz())
        if not task:
            return {"error": "Task not found"}, 404
        metrics.add_metric(name="TaskUpdated", unit="Count", value=1)
        return {"task": task}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        logger.warning(f"Validation error updating task: {str(e)}")
        return {"error": str(e)}, 400
    except Exception as e:
        logger.exception("Error updating task")
        return {"error": str(e)}, 500


@app.delete("/tasks/<task_id>")
@tracer.capture_method
def delete_task(task_id: str):
    """Delete a task."""
    try:
        user_id = _current_user_id()
        success = task_service.delete_task(user_id, task_id)
        if not success:
            return {"error": "Task not found"}, 404
        metrics.add_metric(name="TaskDeleted", unit="Count", value=1)
        return {"message": "Task deleted successfully"}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error deleting task")
        return {"error": str(e)}, 500


# ============================================================================
# Report Endpoints
#
# Reports are user-defined scheduled-notification configs. NOTE: route order
# matters — the specific /reports/<report_id>/run path is registered before the
# bare /reports/<report_id> routes.
# ============================================================================

@app.post("/reports")
@tracer.capture_method
def create_report():
    """Create a new scheduled report."""
    try:
        user_id = _current_user_id()
        data = app.current_event.json_body or {}
        if not data.get('name'):
            return {"error": "Missing required field: name"}, 400
        if not isinstance(data.get('schedule'), dict):
            return {"error": "Missing or invalid required field: schedule"}, 400

        report = report_service.create_report(
            user_id=user_id,
            name=data['name'],
            schedule=data['schedule'],
            sections=data.get('sections', []),
            enabled=data.get('enabled', True),
        )
        metrics.add_metric(name="ReportCreated", unit="Count", value=1)
        return {"report": report}, 201
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        logger.warning(f"Validation error creating report: {str(e)}")
        return {"error": str(e)}, 400
    except Exception as e:
        logger.exception("Error creating report")
        metrics.add_metric(name="ReportCreationError", unit="Count", value=1)
        return {"error": str(e)}, 500


@app.get("/reports")
@tracer.capture_method
def list_reports():
    """List a user's reports."""
    try:
        user_id = _current_user_id()
        reports = report_service.list_reports(user_id)
        return {"reports": reports}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error listing reports")
        return {"error": str(e)}, 500


@app.post("/reports/<report_id>/run")
@tracer.capture_method
def run_report(report_id: str):
    """Generate a report now (manual trigger; same path the sweep uses)."""
    try:
        user_id = _current_user_id()
        report = report_service.get_report(user_id, report_id)
        if not report:
            return {"error": "Report not found"}, 404
        message = report_generator.generate(report, tz=_current_tz())
        metrics.add_metric(name="ReportRun", unit="Count", value=1)
        return {"message": message}, 201
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error running report")
        return {"error": str(e)}, 500


@app.get("/reports/<report_id>")
@tracer.capture_method
def get_report(report_id: str):
    """Get a specific report."""
    try:
        user_id = _current_user_id()
        report = report_service.get_report(user_id, report_id)
        if not report:
            return {"error": "Report not found"}, 404
        return {"report": report}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error getting report")
        return {"error": str(e)}, 500


@app.put("/reports/<report_id>")
@tracer.capture_method
def update_report(report_id: str):
    """Update a report."""
    try:
        user_id = _current_user_id()
        data = app.current_event.json_body or {}
        report = report_service.update_report(user_id, report_id, data)
        if not report:
            return {"error": "Report not found"}, 404
        metrics.add_metric(name="ReportUpdated", unit="Count", value=1)
        return {"report": report}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        logger.warning(f"Validation error updating report: {str(e)}")
        return {"error": str(e)}, 400
    except Exception as e:
        logger.exception("Error updating report")
        return {"error": str(e)}, 500


@app.delete("/reports/<report_id>")
@tracer.capture_method
def delete_report(report_id: str):
    """Delete a report."""
    try:
        user_id = _current_user_id()
        success = report_service.delete_report(user_id, report_id)
        if not success:
            return {"error": "Report not found"}, 404
        metrics.add_metric(name="ReportDeleted", unit="Count", value=1)
        return {"message": "Report deleted successfully"}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error deleting report")
        return {"error": str(e)}, 500


# ============================================================================
# Message Endpoints
#
# The in-app notification log. NOTE: route order matters — the specific
# /messages/unread path is registered before the bare /messages/<message_id>
# routes so it is not swallowed by the parametric matcher.
# ============================================================================

@app.get("/messages/unread")
@tracer.capture_method
def list_unread_messages():
    """List unread messages plus the unread count (for the toolbar badge)."""
    try:
        user_id = _current_user_id()
        messages = message_service.list_unread(user_id)
        return {"messages": messages, "unread_count": len(messages)}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error listing unread messages")
        return {"error": str(e)}, 500


@app.get("/messages")
@tracer.capture_method
def list_messages():
    """List a user's messages (newest first)."""
    try:
        user_id = _current_user_id()
        messages = message_service.list_messages(user_id)
        return {"messages": messages}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error listing messages")
        return {"error": str(e)}, 500


@app.post("/messages/<message_id>/read")
@tracer.capture_method
def mark_message_read(message_id: str):
    """Mark a message as read."""
    try:
        user_id = _current_user_id()
        message = message_service.mark_read(user_id, message_id)
        if message is None:
            return {"error": "Message not found"}, 404
        return {"message": message}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error marking message read")
        return {"error": str(e)}, 500


@app.post("/messages/<message_id>/unread")
@tracer.capture_method
def mark_message_unread(message_id: str):
    """Mark a message as unread."""
    try:
        user_id = _current_user_id()
        message = message_service.mark_unread(user_id, message_id)
        if message is None:
            return {"error": "Message not found"}, 404
        return {"message": message}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error marking message unread")
        return {"error": str(e)}, 500


@app.get("/messages/<message_id>")
@tracer.capture_method
def get_message(message_id: str):
    """Get a specific message."""
    try:
        user_id = _current_user_id()
        message = message_service.get_message(user_id, message_id)
        if not message:
            return {"error": "Message not found"}, 404
        return {"message": message}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error getting message")
        return {"error": str(e)}, 500


@app.delete("/messages/<message_id>")
@tracer.capture_method
def delete_message(message_id: str):
    """Delete a message."""
    try:
        user_id = _current_user_id()
        success = message_service.delete_message(user_id, message_id)
        if not success:
            return {"error": "Message not found"}, 404
        metrics.add_metric(name="MessageDeleted", unit="Count", value=1)
        return {"message": "Message deleted successfully"}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error deleting message")
        return {"error": str(e)}, 500


# ============================================================================
# Scheduled report sweep (EventBridge)
# ============================================================================

def run_report_sweep(now=None) -> Dict[str, Any]:
    """Generate every report whose next_run is due.

    Invoked by the periodic EventBridge rule (not an HTTP request). Iterates all
    due reports across users and renders each into a message, advancing each
    report's next_run. Report timezone is taken from its own schedule, so the
    sweep passes no per-request tz. Best-effort: a failure on one report is logged
    and does not abort the rest.
    """
    due = report_service.list_due_reports(now)
    generated = 0
    failed = 0
    for report in due:
        try:
            tz = (report.get("schedule") or {}).get("tz")
            report_generator.generate(report, tz=tz, now=now)
            generated += 1
        except Exception:
            failed += 1
            logger.exception(
                f"Failed to generate report {report.get('report_id')} "
                f"for user {report.get('user_id')}"
            )
    logger.info(f"Report sweep complete: {generated} generated, {failed} failed")
    metrics.add_metric(name="ReportsGenerated", unit="Count", value=generated)
    return {"generated": generated, "failed": failed, "due": len(due)}


# ============================================================================
# Slack Integration Endpoints
# ============================================================================
# Bring-your-own-Slack (OAuth v2). See docs/slack-integration-plan.md.
# `/slack/oauth/start` is Cognito-guarded and returns the authorize URL as JSON
# (the SPA fetches it, then does a full-page redirect). `/slack/oauth/callback`
# is hit by Slack's redirect with NO Cognito context, so it bypasses the
# authorizer at API Gateway and its trust comes entirely from the signed `state`.

@app.get("/slack/oauth/start")
@tracer.capture_method
def slack_oauth_start():
    """Return the Slack authorize URL for the logged-in user to redirect to."""
    try:
        user_id = _current_user_id()
        return {"authorize_url": slack_service.build_authorize_url(user_id)}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        # Slack app not configured (missing client_id / redirect_uri).
        logger.warning(f"Slack OAuth start unavailable: {str(e)}")
        return {"error": str(e)}, 400
    except Exception as e:
        logger.exception("Error starting Slack OAuth")
        return {"error": str(e)}, 500


@app.get("/slack/oauth/callback")
@tracer.capture_method
def slack_oauth_callback():
    """Finish OAuth: verify state, exchange code, store token, redirect to SPA.

    Identity is NOT taken from Cognito claims here — it is bound into the signed
    `state` and recovered by complete_oauth. On success/failure we 302 back to
    the SPA Integrations page with a status flag so the user lands somewhere sane.
    """
    params = app.current_event.query_string_parameters or {}
    spa_base = os.environ.get("ALLOWED_ORIGIN", "")
    try:
        code = params.get("code")
        state = params.get("state")
        if not code or not state:
            return {"error": "Missing code or state"}, 400
        slack_service.complete_oauth(code=code, state=state)
        metrics.add_metric(name="SlackConnected", unit="Count", value=1)
        location = f"{spa_base}/settings/integrations?slack=connected"
    except ValueError as e:
        # Bad/expired state — do not reveal detail, just send the user back.
        logger.warning(f"Slack OAuth callback rejected: {str(e)}")
        location = f"{spa_base}/settings/integrations?slack=error"
    except Exception:
        logger.exception("Error completing Slack OAuth")
        location = f"{spa_base}/settings/integrations?slack=error"
    return Response(status_code=302, content_type="text/plain", body="", headers={"Location": location})


@app.get("/slack/connections")
@tracer.capture_method
def list_slack_connections():
    """List the user's connected Slack workspaces (never includes the token)."""
    try:
        user_id = _current_user_id()
        return {"connections": slack_service.list_connections(user_id)}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error listing Slack connections")
        return {"error": str(e)}, 500


@app.get("/slack/connections/<connection_id>/channels")
@tracer.capture_method
def list_slack_channels(connection_id: str):
    """List channels for the picker (conversations.list for this connection)."""
    try:
        user_id = _current_user_id()
        return {"channels": slack_service.list_channels(user_id, connection_id)}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        return {"error": str(e)}, 404
    except Exception as e:
        logger.exception("Error listing Slack channels")
        return {"error": str(e)}, 500


@app.delete("/slack/connections/<connection_id>")
@tracer.capture_method
def disconnect_slack(connection_id: str):
    """Revoke + delete a Slack connection."""
    try:
        user_id = _current_user_id()
        deleted = slack_service.disconnect(user_id, connection_id)
        if not deleted:
            return {"error": "Connection not found"}, 404
        return {"deleted": True, "connection_id": connection_id}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except Exception as e:
        logger.exception("Error disconnecting Slack")
        return {"error": str(e)}, 500


@app.post("/slack/connections/<connection_id>/test")
@tracer.capture_method
def test_slack_connection(connection_id: str):
    """Post a "connection works" message — exercises the post_message seam."""
    try:
        user_id = _current_user_id()
        data = app.current_event.json_body or {}
        channel_id = data.get("channel_id")
        if not channel_id:
            return {"error": "Missing required field: channel_id"}, 400
        result = slack_service.post_message(
            user_id, connection_id, channel_id,
            text="Homestead Manager connection works ✅",
        )
        return {"ok": True, "ts": result.get("ts"), "channel": result.get("channel")}
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except PermissionError as e:
        logger.warning(f"Permission denied: {str(e)}")
        return {"error": str(e)}, 403
    except ValueError as e:
        return {"error": str(e)}, 404
    except Exception as e:
        logger.exception("Error testing Slack connection")
        return {"error": str(e)}, 500


@app.post("/slack/connections/dev-stub")
@tracer.capture_method
def slack_dev_stub_connect():
    """LOCAL-ONLY: insert a fake connection row so UI/API work without real Slack.

    Returns 404 outside local mode so the route is invisible in deployed tiers.
    """
    if not SLACK_LOCAL_MODE:
        return {"error": "Not found"}, 404
    try:
        user_id = _current_user_id()
        data = app.current_event.json_body or {}
        connection = slack_service.dev_stub_connect(
            user_id, team_name=data.get("team_name", "Local Dev Workspace")
        )
        return {"connection": connection}, 201
    except AuthenticationError as e:
        logger.warning(f"Unauthenticated request: {str(e)}")
        return {"error": str(e)}, 401
    except Exception as e:
        logger.exception("Error creating Slack dev stub")
        return {"error": str(e)}, 500


def _is_scheduled_event(event: Dict[str, Any]) -> bool:
    """True if this Lambda invocation is the EventBridge scheduled sweep."""
    return (
        event.get("source") == "aws.events"
        or event.get("detail-type") == "Scheduled Event"
    )


# ============================================================================
# Lambda Handler
# ============================================================================

@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Main Lambda handler for the Pantry App API.

    Uses AWS Lambda Powertools for:
    - Structured logging with correlation IDs
    - X-Ray tracing
    - CloudWatch metrics
    """
    # EventBridge scheduled sweep: not an API Gateway request, so handle it
    # before the REST resolver (which expects httpMethod/path).
    if _is_scheduled_event(event):
        logger.info("Processing scheduled report sweep")
        return run_report_sweep()

    logger.info("Processing request", extra={
        "path": event.get("path"),
        "method": event.get("httpMethod")
    })

    return app.resolve(event, context)
