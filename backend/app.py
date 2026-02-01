"""
Pantry App - Core API Lambda Handler

This Lambda function provides the API for the Pantry App inventory management system.
It uses AWS Lambda Powertools for structured logging, tracing, and metrics.
"""

import os
import json
from typing import Dict, Any
from datetime import datetime

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.validation import validate

from models import Item, Location, ItemTag
from services import ItemService, LocationService, TagService

# Initialize Powertools utilities
logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="PantryApp")
app = APIGatewayRestResolver()

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


# ============================================================================
# Storage Location Endpoints
# ============================================================================

@app.post("/locations")
@tracer.capture_method
def create_location():
    """Create a new storage location."""
    try:
        data = app.current_event.json_body
        location = location_service.create_location(
            name=data['name'],
            description=data.get('description', '')
        )
        metrics.add_metric(name="LocationCreated", unit="Count", value=1)
        return {"location": location}, 201
    except Exception as e:
        logger.exception("Error creating location")
        metrics.add_metric(name="LocationCreationError", unit="Count", value=1)
        return {"error": str(e)}, 500


@app.get("/locations")
@tracer.capture_method
def list_locations():
    """List all storage locations."""
    try:
        locations = location_service.list_locations()
        return {"locations": locations}
    except Exception as e:
        logger.exception("Error listing locations")
        return {"error": str(e)}, 500


@app.get("/locations/<location_id>")
@tracer.capture_method
def get_location(location_id: str):
    """Get a specific storage location."""
    try:
        location = location_service.get_location(location_id)
        if not location:
            return {"error": "Location not found"}, 404
        return {"location": location}
    except Exception as e:
        logger.exception("Error getting location")
        return {"error": str(e)}, 500


@app.put("/locations/<location_id>")
@tracer.capture_method
def update_location(location_id: str):
    """Update a storage location."""
    try:
        data = app.current_event.json_body
        location = location_service.update_location(location_id, data)
        if not location:
            return {"error": "Location not found"}, 404
        metrics.add_metric(name="LocationUpdated", unit="Count", value=1)
        return {"location": location}
    except Exception as e:
        logger.exception("Error updating location")
        return {"error": str(e)}, 500


@app.delete("/locations/<location_id>")
@tracer.capture_method
def delete_location(location_id: str):
    """Delete a storage location."""
    try:
        success = location_service.delete_location(location_id)
        if not success:
            return {"error": "Location not found"}, 404
        metrics.add_metric(name="LocationDeleted", unit="Count", value=1)
        return {"message": "Location deleted successfully"}
    except Exception as e:
        logger.exception("Error deleting location")
        return {"error": str(e)}, 500


# ============================================================================
# Item Endpoints
# ============================================================================

@app.post("/items")
@tracer.capture_method
def create_item():
    """Create a new inventory item."""
    try:
        data = app.current_event.json_body
        item = item_service.create_item(
            name=data['name'],
            location_id=data['location_id'],
            quantity=data.get('quantity', 1),
            unit=data.get('unit', 'unit'),
            use_by_date=data.get('use_by_date'),
            tags=data.get('tags', []),
            notes=data.get('notes', '')
        )
        metrics.add_metric(name="ItemCreated", unit="Count", value=1)
        return {"item": item}, 201
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

        location_id = query_params.get('location_id')
        tag = query_params.get('tag')
        name = query_params.get('name')

        if location_id:
            items = item_service.get_items_by_location(location_id)
        elif tag:
            items = item_service.get_items_by_tag(tag)
        elif name:
            items = item_service.search_items_by_name(name)
        else:
            items = item_service.list_all_items()

        return {"items": items}
    except Exception as e:
        logger.exception("Error listing items")
        return {"error": str(e)}, 500


@app.get("/items/<item_id>")
@tracer.capture_method
def get_item(item_id: str):
    """Get a specific inventory item."""
    try:
        item = item_service.get_item(item_id)
        if not item:
            return {"error": "Item not found"}, 404
        return {"item": item}
    except Exception as e:
        logger.exception("Error getting item")
        return {"error": str(e)}, 500


@app.put("/items/<item_id>")
@tracer.capture_method
def update_item(item_id: str):
    """Update an inventory item."""
    try:
        data = app.current_event.json_body
        item = item_service.update_item(item_id, data)
        if not item:
            return {"error": "Item not found"}, 404
        metrics.add_metric(name="ItemUpdated", unit="Count", value=1)
        return {"item": item}
    except Exception as e:
        logger.exception("Error updating item")
        return {"error": str(e)}, 500


@app.delete("/items/<item_id>")
@tracer.capture_method
def delete_item(item_id: str):
    """Delete an inventory item (mark as used)."""
    try:
        success = item_service.delete_item(item_id)
        if not success:
            return {"error": "Item not found"}, 404
        metrics.add_metric(name="ItemDeleted", unit="Count", value=1)
        return {"message": "Item deleted successfully"}
    except Exception as e:
        logger.exception("Error deleting item")
        return {"error": str(e)}, 500


@app.get("/items/expiring")
@tracer.capture_method
def get_expiring_items():
    """Get items expiring soon."""
    try:
        query_params = app.current_event.query_string_parameters or {}
        location_id = query_params.get('location_id')
        days = int(query_params.get('days', 7))

        items = item_service.get_expiring_items(location_id, days)
        return {"items": items}
    except Exception as e:
        logger.exception("Error getting expiring items")
        return {"error": str(e)}, 500


# ============================================================================
# Search and Query Endpoints
# ============================================================================

@app.post("/search")
@tracer.capture_method
def search_items():
    """Advanced search for items with multiple criteria."""
    try:
        data = app.current_event.json_body
        items = item_service.search_items(
            name=data.get('name'),
            location_id=data.get('location_id'),
            tags=data.get('tags', []),
            use_by_date_start=data.get('use_by_date_start'),
            use_by_date_end=data.get('use_by_date_end')
        )
        return {"items": items}
    except Exception as e:
        logger.exception("Error searching items")
        return {"error": str(e)}, 500


@app.get("/aggregate")
@tracer.capture_method
def get_aggregate_stats():
    """Get aggregate statistics for inventory."""
    try:
        query_params = app.current_event.query_string_parameters or {}
        location_id = query_params.get('location_id')
        tag = query_params.get('tag')

        stats = item_service.get_aggregate_stats(location_id, tag)
        return {"stats": stats}
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
