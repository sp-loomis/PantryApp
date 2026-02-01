#!/usr/bin/env python3
"""
Pantry CLI - Command-line interface for the Pantry App

This CLI provides commands for managing storage locations and inventory items
in the Pantry App system.
"""

import os
import sys
import json
from typing import Optional, List
from datetime import datetime

import boto3
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from dateutil.parser import parse as parse_date

# Initialize console for rich output
console = Console()

# Initialize Lambda client
lambda_client = boto3.client('lambda')

# Get Lambda function name from environment
LAMBDA_FUNCTION_NAME = os.environ.get('PANTRY_LAMBDA_FUNCTION', 'dev-use2-pantry-lambda-core-api')


def invoke_lambda(method: str, path: str, body: Optional[dict] = None, query_params: Optional[dict] = None) -> dict:
    """Invoke the Lambda function with the given parameters."""
    event = {
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if body else None,
        "queryStringParameters": query_params,
        "headers": {},
        "requestContext": {"requestId": "cli-request"},
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
            console.print(f"[red]Lambda execution error: {payload.get('errorMessage')}[/red]")
            if 'errorType' in payload:
                console.print(f"[yellow]Error type: {payload['errorType']}[/yellow]")
            if 'stackTrace' in payload:
                console.print(f"[dim]Stack trace: {json.dumps(payload['stackTrace'], indent=2)}[/dim]")
            sys.exit(1)

        # Parse the response body
        if 'body' in payload:
            return json.loads(payload['body'])
        return payload

    except Exception as e:
        console.print(f"[red]Error invoking Lambda: {str(e)}[/red]")
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
def create_location(name: str, description: str):
    """Create a new storage location."""
    result = invoke_lambda('POST', '/locations', {
        'name': name,
        'description': description
    })

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    if 'location' not in result:
        console.print(f"[red]Unexpected response format. Expected 'location' key but got: {list(result.keys())}[/red]")
        console.print(f"[yellow]Full response: {json.dumps(result, indent=2)}[/yellow]")
        sys.exit(1)

    location = result['location']
    console.print(Panel(
        f"[green]Location created successfully![/green]\n\n"
        f"ID: {location['location_id']}\n"
        f"Name: {location['name']}\n"
        f"Description: {location['description']}",
        title="New Location"
    ))


@location.command(name='list')
def list_locations():
    """List all storage locations."""
    result = invoke_lambda('GET', '/locations')

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    locations = result.get('locations', [])

    if not locations:
        console.print("[yellow]No locations found.[/yellow]")
        return

    table = Table(title="Storage Locations")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description", style="white")
    table.add_column("Created", style="yellow")

    for loc in locations:
        table.add_row(
            loc['location_id'][:8] + '...',
            loc['name'],
            loc.get('description', ''),
            loc['created_at'][:10]
        )

    console.print(table)


@location.command(name='get')
@click.argument('location_id')
def get_location(location_id: str):
    """Get details of a specific location."""
    result = invoke_lambda('GET', f'/locations/{location_id}')

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    loc = result['location']
    console.print(Panel(
        f"ID: {loc['location_id']}\n"
        f"Name: {loc['name']}\n"
        f"Description: {loc.get('description', '')}\n"
        f"Created: {loc['created_at']}\n"
        f"Updated: {loc['updated_at']}",
        title=f"Location: {loc['name']}"
    ))


@location.command(name='update')
@click.argument('location_id')
@click.option('--name', help='New location name')
@click.option('--description', help='New location description')
def update_location(location_id: str, name: Optional[str], description: Optional[str]):
    """Update a storage location."""
    updates = {}
    if name:
        updates['name'] = name
    if description:
        updates['description'] = description

    if not updates:
        console.print("[yellow]No updates provided.[/yellow]")
        return

    result = invoke_lambda('PUT', f'/locations/{location_id}', updates)

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    console.print("[green]Location updated successfully![/green]")


@location.command(name='delete')
@click.argument('location_id')
@click.confirmation_option(prompt='Are you sure you want to delete this location?')
def delete_location(location_id: str):
    """Delete a storage location."""
    result = invoke_lambda('DELETE', f'/locations/{location_id}')

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    console.print("[green]Location deleted successfully![/green]")


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
            console.print("[red]Invalid date format. Use YYYY-MM-DD[/red]")
            sys.exit(1)

    if tags:
        item_data['tags'] = [tag.strip() for tag in tags.split(',')]

    result = invoke_lambda('POST', '/items', item_data)

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    if 'item' not in result:
        console.print(f"[red]Unexpected response format. Expected 'item' key but got: {list(result.keys())}[/red]")
        console.print(f"[yellow]Full response: {json.dumps(result, indent=2)}[/yellow]")
        sys.exit(1)

    item = result['item']

    # Format dimensions for display
    dimensions_text = ""
    if item.get('dimensions'):
        dimensions_text = "\nDimensions:\n"
        for dim in item['dimensions']:
            dim_type = dim['dimension_type'].capitalize()
            dimensions_text += f"  {dim_type}: {dim['value']} {dim['unit']}\n"

    console.print(Panel(
        f"[green]Item added successfully![/green]\n\n"
        f"ID: {item['item_id']}\n"
        f"Name: {item['name']}\n"
        f"Quantity: {item['quantity']} {item['unit']}" +
        dimensions_text +
        f"Location: {item['location_id']}\n" +
        (f"Use by: {item['use_by_date']}\n" if item.get('use_by_date') else ""),
        title="New Item"
    ))


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

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    items = result.get('items', [])

    if not items:
        console.print("[yellow]No items found.[/yellow]")
        return

    table = Table(title="Inventory Items")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Quantity", style="yellow")
    table.add_column("Dimensions", style="magenta")
    table.add_column("Location", style="blue")
    table.add_column("Use By", style="red")
    table.add_column("Tags", style="white")

    for item in items:
        # Format dimensions for compact display
        dimensions_str = ""
        if item.get('dimensions'):
            dim_parts = []
            for dim in item['dimensions']:
                dim_type_short = dim['dimension_type'][0].upper()  # C, W, or V
                dim_parts.append(f"{dim_type_short}:{dim['value']}{dim['unit']}")
            dimensions_str = " ".join(dim_parts)

        table.add_row(
            item['item_id'][:8] + '...',
            item['name'],
            f"{item['quantity']} {item['unit']}",
            dimensions_str,
            item['location_id'][:8] + '...',
            item.get('use_by_date', 'N/A')[:10] if item.get('use_by_date') else 'N/A',
            ', '.join(item.get('tags', []))
        )

    console.print(table)


@item.command(name='get')
@click.argument('item_id')
def get_item(item_id: str):
    """Get details of a specific item."""
    result = invoke_lambda('GET', f'/items/{item_id}')

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    item = result['item']

    # Format dimensions for display
    dimensions_text = ""
    if item.get('dimensions'):
        dimensions_text = "Dimensions:\n"
        for dim in item['dimensions']:
            dim_type = dim['dimension_type'].capitalize()
            dimensions_text += f"  {dim_type}: {dim['value']} {dim['unit']}\n"

    console.print(Panel(
        f"ID: {item['item_id']}\n"
        f"Name: {item['name']}\n"
        f"Quantity: {item['quantity']} {item['unit']}\n" +
        (dimensions_text if dimensions_text else "") +
        f"Location: {item['location_id']}\n"
        f"Use by: {item.get('use_by_date', 'N/A')}\n"
        f"Tags: {', '.join(item.get('tags', []))}\n"
        f"Notes: {item.get('notes', '')}\n"
        f"Created: {item['created_at']}\n"
        f"Updated: {item['updated_at']}",
        title=f"Item: {item['name']}"
    ))


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
            console.print("[red]Invalid date format. Use YYYY-MM-DD[/red]")
            sys.exit(1)
    if tags:
        updates['tags'] = [tag.strip() for tag in tags.split(',')]
    if notes:
        updates['notes'] = notes

    if not updates:
        console.print("[yellow]No updates provided.[/yellow]")
        return

    result = invoke_lambda('PUT', f'/items/{item_id}', updates)

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    console.print("[green]Item updated successfully![/green]")


@item.command(name='remove')
@click.argument('item_id')
@click.confirmation_option(prompt='Are you sure you want to remove this item?')
def remove_item(item_id: str):
    """Remove an inventory item (mark as used)."""
    result = invoke_lambda('DELETE', f'/items/{item_id}')

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    console.print("[green]Item removed successfully![/green]")


@item.command(name='expiring')
@click.option('--location', help='Filter by location ID')
@click.option('--days', type=int, default=7, help='Number of days to look ahead')
def expiring_items(location: Optional[str], days: int):
    """Show items expiring soon."""
    query_params = {'days': str(days)}
    if location:
        query_params['location_id'] = location

    result = invoke_lambda('GET', '/items/expiring', query_params=query_params)

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    items = result.get('items', [])

    if not items:
        console.print(f"[green]No items expiring in the next {days} days.[/green]")
        return

    table = Table(title=f"Items Expiring in {days} Days")
    table.add_column("Name", style="green")
    table.add_column("Quantity", style="yellow")
    table.add_column("Dimensions", style="magenta")
    table.add_column("Location", style="blue")
    table.add_column("Use By", style="red")

    for item in items:
        # Format dimensions for compact display
        dimensions_str = ""
        if item.get('dimensions'):
            dim_parts = []
            for dim in item['dimensions']:
                dim_type_short = dim['dimension_type'][0].upper()
                dim_parts.append(f"{dim_type_short}:{dim['value']}{dim['unit']}")
            dimensions_str = " ".join(dim_parts)

        table.add_row(
            item['name'],
            f"{item['quantity']} {item['unit']}",
            dimensions_str,
            item['location_id'][:8] + '...',
            item.get('use_by_date', 'N/A')[:10]
        )

    console.print(table)


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

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    items = result.get('items', [])

    if not items:
        console.print("[yellow]No items found matching the search criteria.[/yellow]")
        return

    table = Table(title="Search Results")
    table.add_column("Name", style="green")
    table.add_column("Quantity", style="yellow")
    table.add_column("Dimensions", style="magenta")
    table.add_column("Location", style="blue")
    table.add_column("Use By", style="red")
    table.add_column("Tags", style="white")

    for item in items:
        # Format dimensions for compact display
        dimensions_str = ""
        if item.get('dimensions'):
            dim_parts = []
            for dim in item['dimensions']:
                dim_type_short = dim['dimension_type'][0].upper()
                dim_parts.append(f"{dim_type_short}:{dim['value']}{dim['unit']}")
            dimensions_str = " ".join(dim_parts)

        table.add_row(
            item['name'],
            f"{item['quantity']} {item['unit']}",
            dimensions_str,
            item['location_id'][:8] + '...',
            item.get('use_by_date', 'N/A')[:10] if item.get('use_by_date') else 'N/A',
            ', '.join(item.get('tags', []))
        )

    console.print(table)


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

    if 'error' in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        sys.exit(1)

    stats = result['stats']

    table = Table(title="Inventory Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")

    table.add_row("Total Items", str(stats['total_items']))
    table.add_row("Total Quantity", str(stats['total_quantity']))
    table.add_row("Items with Expiry Date", str(stats['items_with_expiry']))

    console.print(table)

    # Display aggregated dimensions
    if stats.get('aggregated_dimensions'):
        dim_table = Table(title="Aggregated Dimensions")
        dim_table.add_column("Dimension Type", style="cyan")
        dim_table.add_column("Total", style="yellow")

        for dim_type, dim_data in stats['aggregated_dimensions'].items():
            dim_type_display = dim_type.capitalize()
            value_display = f"{dim_data['value']:.2f} {dim_data['unit']}"
            dim_table.add_row(dim_type_display, value_display)

        console.print(dim_table)

    # Display legacy quantities by unit
    if stats.get('quantities_by_unit'):
        unit_table = Table(title="Quantities by Unit (Legacy)")
        unit_table.add_column("Unit", style="green")
        unit_table.add_column("Total Quantity", style="yellow")

        for unit, qty in stats['quantities_by_unit'].items():
            unit_table.add_row(unit, str(qty))

        console.print(unit_table)


if __name__ == '__main__':
    cli()
