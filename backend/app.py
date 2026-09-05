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
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig

from services import ItemService, LocationService, TagService
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

# Initialize services
item_service = ItemService(dynamodb.Table(ITEMS_TABLE), dynamodb.Table(ITEM_TAGS_TABLE))
location_service = LocationService(dynamodb.Table(LOCATIONS_TABLE))
tag_service = TagService(dynamodb.Table(ITEM_TAGS_TABLE))


def _current_user_id() -> str:
    """Resolve the effective user_id for the current request (honors admin override)."""
    query_params = app.current_event.query_string_parameters or {}
    requested_user_id = query_params.get('user_id')
    return get_effective_user_id(app.current_event.raw_event, requested_user_id)


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
    logger.info("Processing request", extra={
        "path": event.get("path"),
        "method": event.get("httpMethod")
    })

    return app.resolve(event, context)
