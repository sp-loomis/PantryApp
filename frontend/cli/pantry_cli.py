#!/usr/bin/env python3
"""
Pantry CLI - Command-line interface for the Pantry App

This CLI provides commands for managing storage locations and inventory items
in the Pantry App system. All outputs are formatted as JSON to match API responses.
"""

import os
import sys
import json
from typing import Optional, List
from datetime import datetime

import boto3
import click
from dateutil.parser import parse as parse_date

from auth import (
    login as auth_login,
    sign_up as auth_signup,
    confirm_signup,
    get_valid_id_token,
    is_logged_in,
    clear_tokens
)

# Initialize Lambda client
lambda_client = boto3.client('lambda')

# Get configuration from environment
LAMBDA_FUNCTION_NAME = os.environ.get('PANTRY_LAMBDA_FUNCTION', 'dev-use2-pantry-lambda-core-api')
COGNITO_USER_POOL_ID = os.environ.get('COGNITO_USER_POOL_ID')
COGNITO_CLIENT_ID = os.environ.get('COGNITO_CLIENT_ID')


def invoke_lambda(method: str, path: str, body: Optional[dict] = None, query_params: Optional[dict] = None, user_id: Optional[str] = None) -> dict:
    """Invoke the Lambda function with the given parameters."""
    # Get authentication token if available
    id_token = None
    if COGNITO_CLIENT_ID:
        id_token = get_valid_id_token(COGNITO_CLIENT_ID)

    # Add user_id to query params if specified (for admin operations)
    if user_id and query_params is None:
        query_params = {}
    if user_id:
        query_params['user_id'] = user_id

    # Build the event
    headers = {}
    request_context = {"requestId": "cli-request"}

    # If we have a token, add it to the Authorization header and simulate Cognito authorizer context
    if id_token:
        headers['Authorization'] = f'Bearer {id_token}'
        # Simulate what API Gateway Cognito Authorizer would add
        # Note: This is a simplified version - in production, API Gateway would validate the JWT
        # and extract claims. For CLI direct Lambda invocation, we add minimal context.
        try:
            import base64
            # Parse JWT to get claims (simplified - just get the payload)
            parts = id_token.split('.')
            if len(parts) >= 2:
                # Decode payload (add padding if needed)
                payload_part = parts[1]
                padding = 4 - len(payload_part) % 4
                if padding != 4:
                    payload_part += '=' * padding
                claims = json.loads(base64.urlsafe_b64decode(payload_part))
                request_context['authorizer'] = {
                    'claims': claims
                }
        except Exception:
            pass  # If parsing fails, continue without claims

    event = {
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if body else None,
        "queryStringParameters": query_params,
        "headers": headers,
        "requestContext": request_context,
        "isBase64Encoded": False
    }

    try:
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )

        payload = json.loads(response['Payload'].read())

        # Check for Lambda execution errors
        if 'errorMessage' in payload:
            error_response = {
                "error": payload.get('errorMessage'),
                "errorType": payload.get('errorType'),
                "stackTrace": payload.get('stackTrace')
            }
            print(json.dumps(error_response, indent=2))
            sys.exit(1)

        # Parse the response body
        if 'body' in payload:
            return json.loads(payload['body'])
        return payload

    except Exception as e:
        error_response = {"error": str(e)}
        print(json.dumps(error_response, indent=2))
        sys.exit(1)


@click.group()
def cli():
    """Pantry App CLI - Manage your storage locations and inventory."""
    pass


# ============================================================================
# Location Commands
# ============================================================================

@cli.group()
def location():
    """Manage storage locations."""
    pass


@location.command(name='create')
@click.option('--name', required=True, help='Location name')
@click.option('--description', default='', help='Location description')
@click.option('--user-id', help='[Admin only] Create location for specific user')
def create_location(name: str, description: str, user_id: Optional[str]):
    """Create a new storage location."""
    result = invoke_lambda('POST', '/locations', {
        'name': name,
        'description': description
    }, user_id=user_id)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


@location.command(name='list')
@click.option('--user-id', help='[Admin only] List locations for specific user')
def list_locations(user_id: Optional[str]):
    """List all storage locations."""
    result = invoke_lambda('GET', '/locations', user_id=user_id)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


@location.command(name='get')
@click.argument('location_id')
@click.option('--user-id', help='[Admin only] Get location for specific user')
def get_location(location_id: str, user_id: Optional[str]):
    """Get details of a specific location."""
    result = invoke_lambda('GET', f'/locations/{location_id}', user_id=user_id)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


@location.command(name='update')
@click.argument('location_id')
@click.option('--name', help='New location name')
@click.option('--description', help='New location description')
@click.option('--user-id', help='[Admin only] Update location for specific user')
def update_location(location_id: str, name: Optional[str], description: Optional[str], user_id: Optional[str]):
    """Update a storage location."""
    updates = {}
    if name:
        updates['name'] = name
    if description:
        updates['description'] = description

    if not updates:
        print(json.dumps({"error": "No updates provided"}, indent=2))
        sys.exit(1)

    result = invoke_lambda('PUT', f'/locations/{location_id}', updates, user_id=user_id)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


@location.command(name='delete')
@click.argument('location_id')
@click.option('--user-id', help='[Admin only] Delete location for specific user')
@click.confirmation_option(prompt='Are you sure you want to delete this location?')
def delete_location(location_id: str, user_id: Optional[str]):
    """Delete a storage location."""
    result = invoke_lambda('DELETE', f'/locations/{location_id}', user_id=user_id)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


# ============================================================================
# Item Commands
# ============================================================================

@cli.group()
def item():
    """Manage inventory items."""
    pass


@item.command(name='add')
@click.option('--name', required=True, help='Item name')
@click.option('--location', required=True, help='Location ID')
@click.option('--quantity', type=float, default=1.0, help='Quantity (legacy)')
@click.option('--unit', default='unit', help='Unit of measurement (legacy)')
@click.option('--count', type=float, help='Count dimension value')
@click.option('--weight', type=float, help='Weight dimension value')
@click.option('--weight-unit', default='lb', help='Weight unit (g, kg, oz, lb)')
@click.option('--volume', type=float, help='Volume dimension value')
@click.option('--volume-unit', default='cup', help='Volume unit (ml, l, tsp, tbsp, fl oz, cup, pint, quart, gallon)')
@click.option('--use-by', help='Use-by date (YYYY-MM-DD)')
@click.option('--tags', help='Comma-separated tags')
@click.option('--notes', default='', help='Additional notes')
def add_item(name: str, location: str, quantity: float, unit: str, count: Optional[float],
             weight: Optional[float], weight_unit: str, volume: Optional[float], volume_unit: str,
             use_by: Optional[str], tags: Optional[str], notes: str):
    """Add a new inventory item with optional dimensions."""
    item_data = {
        'name': name,
        'location_id': location,
        'quantity': quantity,
        'unit': unit,
        'notes': notes
    }

    # Build dimensions array
    dimensions = []
    if count is not None:
        dimensions.append({
            'dimension_type': 'count',
            'value': count,
            'unit': 'units'
        })
    if weight is not None:
        dimensions.append({
            'dimension_type': 'weight',
            'value': weight,
            'unit': weight_unit
        })
    if volume is not None:
        dimensions.append({
            'dimension_type': 'volume',
            'value': volume,
            'unit': volume_unit
        })

    if dimensions:
        item_data['dimensions'] = dimensions

    if use_by:
        try:
            # Validate date format
            parsed_date = parse_date(use_by)
            item_data['use_by_date'] = parsed_date.isoformat()
        except ValueError:
            print(json.dumps({"error": "Invalid date format. Use YYYY-MM-DD"}, indent=2))
            sys.exit(1)

    if tags:
        item_data['tags'] = [tag.strip() for tag in tags.split(',')]

    result = invoke_lambda('POST', '/items', item_data)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


@item.command(name='list')
@click.option('--location', help='Filter by location ID')
@click.option('--tag', help='Filter by tag')
@click.option('--name', help='Filter by name')
def list_items(location: Optional[str], tag: Optional[str], name: Optional[str]):
    """List inventory items."""
    query_params = {}
    if location:
        query_params['location_id'] = location
    if tag:
        query_params['tag'] = tag
    if name:
        query_params['name'] = name

    result = invoke_lambda('GET', '/items', query_params=query_params)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


@item.command(name='get')
@click.argument('item_id')
def get_item(item_id: str):
    """Get details of a specific item."""
    result = invoke_lambda('GET', f'/items/{item_id}')

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


@item.command(name='update')
@click.argument('item_id')
@click.option('--name', help='New item name')
@click.option('--location', help='New location ID')
@click.option('--quantity', type=float, help='New quantity (legacy)')
@click.option('--unit', help='New unit (legacy)')
@click.option('--count', type=float, help='Count dimension value')
@click.option('--weight', type=float, help='Weight dimension value')
@click.option('--weight-unit', help='Weight unit (g, kg, oz, lb)')
@click.option('--volume', type=float, help='Volume dimension value')
@click.option('--volume-unit', help='Volume unit (ml, l, tsp, tbsp, fl oz, cup, pint, quart, gallon)')
@click.option('--use-by', help='New use-by date (YYYY-MM-DD)')
@click.option('--tags', help='New comma-separated tags')
@click.option('--notes', help='New notes')
def update_item(item_id: str, name: Optional[str], location: Optional[str], quantity: Optional[float],
                unit: Optional[str], count: Optional[float], weight: Optional[float], weight_unit: Optional[str],
                volume: Optional[float], volume_unit: Optional[str], use_by: Optional[str],
                tags: Optional[str], notes: Optional[str]):
    """Update an inventory item, including dimensions."""
    updates = {}

    if name:
        updates['name'] = name
    if location:
        updates['location_id'] = location
    if quantity is not None:
        updates['quantity'] = quantity
    if unit:
        updates['unit'] = unit

    # Build dimensions array if any dimension option is provided
    has_dimension_update = count is not None or weight is not None or volume is not None
    if has_dimension_update:
        dimensions = []
        if count is not None:
            dimensions.append({
                'dimension_type': 'count',
                'value': count,
                'unit': 'units'
            })
        if weight is not None:
            dimensions.append({
                'dimension_type': 'weight',
                'value': weight,
                'unit': weight_unit or 'lb'
            })
        if volume is not None:
            dimensions.append({
                'dimension_type': 'volume',
                'value': volume,
                'unit': volume_unit or 'cup'
            })
        updates['dimensions'] = dimensions

    if use_by:
        try:
            parsed_date = parse_date(use_by)
            updates['use_by_date'] = parsed_date.isoformat()
        except ValueError:
            print(json.dumps({"error": "Invalid date format. Use YYYY-MM-DD"}, indent=2))
            sys.exit(1)
    if tags:
        updates['tags'] = [tag.strip() for tag in tags.split(',')]
    if notes:
        updates['notes'] = notes

    if not updates:
        print(json.dumps({"error": "No updates provided"}, indent=2))
        sys.exit(1)

    result = invoke_lambda('PUT', f'/items/{item_id}', updates)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


@item.command(name='remove')
@click.argument('item_id')
@click.confirmation_option(prompt='Are you sure you want to remove this item?')
def remove_item(item_id: str):
    """Remove an inventory item (mark as used)."""
    result = invoke_lambda('DELETE', f'/items/{item_id}')

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


@item.command(name='expiring')
@click.option('--location', help='Filter by location ID')
@click.option('--days', type=int, default=7, help='Number of days to look ahead')
def expiring_items(location: Optional[str], days: int):
    """Show items expiring soon."""
    query_params = {'days': str(days)}
    if location:
        query_params['location_id'] = location

    result = invoke_lambda('GET', '/items/expiring', query_params=query_params)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


# ============================================================================
# Search Commands
# ============================================================================

@cli.command(name='search')
@click.option('--name', help='Search by name')
@click.option('--location', help='Filter by location ID')
@click.option('--tags', help='Filter by comma-separated tags')
@click.option('--use-by-start', help='Filter by use-by date start (YYYY-MM-DD)')
@click.option('--use-by-end', help='Filter by use-by date end (YYYY-MM-DD)')
def search_items(name: Optional[str], location: Optional[str], tags: Optional[str],
                 use_by_start: Optional[str], use_by_end: Optional[str]):
    """Advanced search for items."""
    search_data = {}

    if name:
        search_data['name'] = name
    if location:
        search_data['location_id'] = location
    if tags:
        search_data['tags'] = [tag.strip() for tag in tags.split(',')]
    if use_by_start:
        search_data['use_by_date_start'] = use_by_start
    if use_by_end:
        search_data['use_by_date_end'] = use_by_end

    result = invoke_lambda('POST', '/search', search_data)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


@cli.command(name='stats')
@click.option('--location', help='Filter by location ID')
@click.option('--tag', help='Filter by tag')
@click.option('--weight-unit', help='Preferred weight unit (g, kg, oz, lb)')
@click.option('--volume-unit', help='Preferred volume unit (ml, l, tsp, tbsp, fl oz, cup, pint, quart, gallon)')
def aggregate_stats(location: Optional[str], tag: Optional[str], weight_unit: Optional[str], volume_unit: Optional[str]):
    """Show aggregate statistics for inventory with dimension support."""
    query_params = {}
    if location:
        query_params['location_id'] = location
    if tag:
        query_params['tag'] = tag
    if weight_unit:
        query_params['weight_unit'] = weight_unit
    if volume_unit:
        query_params['volume_unit'] = volume_unit

    result = invoke_lambda('GET', '/aggregate', query_params=query_params)

    print(json.dumps(result, indent=2))

    if 'error' in result:
        sys.exit(1)


# ============================================================================
# Authentication Commands
# ============================================================================

@cli.group()
def auth():
    """Manage authentication."""
    pass


@auth.command(name='login')
@click.option('--username', required=True, help='Username or email')
@click.option('--password', required=True, prompt=True, hide_input=True, help='Password')
def login(username: str, password: str):
    """Login to Pantry App."""
    if not COGNITO_USER_POOL_ID or not COGNITO_CLIENT_ID:
        result = {
            "error": "Cognito configuration not found. Set COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID environment variables."
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    try:
        tokens = auth_login(username, password, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID)
        result = {
            "message": "Login successful",
            "user": username
        }
        print(json.dumps(result, indent=2))
    except Exception as e:
        result = {"error": str(e)}
        print(json.dumps(result, indent=2))
        sys.exit(1)


@auth.command(name='logout')
def logout():
    """Logout from Pantry App."""
    clear_tokens()
    result = {"message": "Logged out successfully"}
    print(json.dumps(result, indent=2))


@auth.command(name='signup')
@click.option('--username', required=True, help='Desired username')
@click.option('--email', required=True, help='Email address')
@click.option('--password', required=True, prompt=True, hide_input=True, confirmation_prompt=True, help='Password')
def signup(username: str, email: str, password: str):
    """Sign up for a new Pantry App account."""
    if not COGNITO_USER_POOL_ID or not COGNITO_CLIENT_ID:
        result = {
            "error": "Cognito configuration not found. Set COGNITO_USER_POOL_ID and COGNITO_CLIENT_ID environment variables."
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    try:
        signup_result = auth_signup(username, password, email, COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID)
        result = {
            "message": "Signup successful. Please check your email for a verification code.",
            "user_confirmed": signup_result['UserConfirmed'],
            "user_id": signup_result['UserSub']
        }
        print(json.dumps(result, indent=2))
    except Exception as e:
        result = {"error": str(e)}
        print(json.dumps(result, indent=2))
        sys.exit(1)


@auth.command(name='confirm')
@click.option('--username', required=True, help='Username')
@click.option('--code', required=True, help='Verification code from email')
def confirm(username: str, code: str):
    """Confirm user signup with verification code."""
    if not COGNITO_CLIENT_ID:
        result = {
            "error": "Cognito configuration not found. Set COGNITO_CLIENT_ID environment variable."
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

    try:
        confirm_signup(username, code, COGNITO_CLIENT_ID)
        result = {"message": "Account confirmed successfully. You can now login."}
        print(json.dumps(result, indent=2))
    except Exception as e:
        result = {"error": str(e)}
        print(json.dumps(result, indent=2))
        sys.exit(1)


@auth.command(name='status')
def status():
    """Check authentication status."""
    if is_logged_in():
        result = {"status": "authenticated", "message": "You are logged in"}
    else:
        result = {"status": "unauthenticated", "message": "You are not logged in"}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    cli()
