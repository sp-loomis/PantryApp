# Pantry App - Inventory Management System

A serverless inventory management system for tracking items across multiple storage locations. Built with AWS Lambda, DynamoDB, and a Python CLI that maintains strict alignment with the REST API.

## Quick Start

### Prerequisites
- AWS Account with appropriate permissions
- Python 3.11+
- Node.js 18+ (for React frontend)
- AWS CLI configured

### Setup

#### Python CLI

1. **Install CLI dependencies:**
   ```bash
   cd frontend/cli
   pip install -r requirements.txt
   chmod +x pantry_cli.py
   ```

2. **Configure Lambda function name:**
   ```bash
   export PANTRY_LAMBDA_FUNCTION=dev-use2-pantry-lambda-core-api
   ```

#### React Web Frontend

1. **Install dependencies:**
   ```bash
   cd frontend/react
   npm install
   ```

2. **Configure environment:**
   ```bash
   cd web
   cp .env.example .env
   # Edit .env with your AWS Cognito credentials
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```

See [frontend/react/README.md](frontend/react/README.md) for detailed React frontend documentation.

## API & CLI Documentation

The CLI maintains a one-to-one correspondence with the API. Every API endpoint has an equivalent CLI command that accepts the same parameters and returns the same JSON responses.

### Locations

Storage locations represent physical areas where inventory is stored (pantry, freezer, tack room, etc.).

#### Create Location

**API Endpoint:** `POST /locations`

**CLI Command:**
```bash
./pantry_cli.py location create --name <name> [--description <description>]
```

**Input:**
```json
{
  "name": "Main Freezer",
  "description": "Large chest freezer in garage"
}
```

**Output:**
```json
{
  "location": {
    "location_id": "loc_abc123",
    "name": "Main Freezer",
    "description": "Large chest freezer in garage",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

#### List Locations

**API Endpoint:** `GET /locations`

**CLI Command:**
```bash
./pantry_cli.py location list
```

**Output:**
```json
{
  "locations": [
    {
      "location_id": "loc_abc123",
      "name": "Main Freezer",
      "description": "Large chest freezer in garage",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### Get Location

**API Endpoint:** `GET /locations/<location_id>`

**CLI Command:**
```bash
./pantry_cli.py location get <location_id>
```

**Output:**
```json
{
  "location": {
    "location_id": "loc_abc123",
    "name": "Main Freezer",
    "description": "Large chest freezer in garage",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

#### Update Location

**API Endpoint:** `PUT /locations/<location_id>`

**CLI Command:**
```bash
./pantry_cli.py location update <location_id> [--name <name>] [--description <description>]
```

**Input:**
```json
{
  "name": "Large Freezer",
  "description": "Updated description"
}
```

**Output:**
```json
{
  "location": {
    "location_id": "loc_abc123",
    "name": "Large Freezer",
    "description": "Updated description",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-20T14:20:00Z"
  }
}
```

#### Delete Location

**API Endpoint:** `DELETE /locations/<location_id>`

**CLI Command:**
```bash
./pantry_cli.py location delete <location_id>
```

**Output:**
```json
{
  "message": "Location deleted successfully"
}
```

### Items

Inventory items track what you have, where it is, quantity, dimensions, expiration dates, and tags.

#### Add Item

**API Endpoint:** `POST /items`

**CLI Command:**
```bash
./pantry_cli.py item add --name <name> --location <location_id> \
  [--quantity <qty>] [--unit <unit>] \
  [--count <value>] \
  [--weight <value>] [--weight-unit <unit>] \
  [--volume <value>] [--volume-unit <unit>] \
  [--use-by <YYYY-MM-DD>] [--tags <tag1,tag2>] [--notes <text>]
```

**Input:**
```json
{
  "name": "Ground Beef",
  "location_id": "loc_abc123",
  "quantity": 5,
  "unit": "lbs",
  "dimensions": [
    {
      "dimension_type": "weight",
      "value": 5,
      "unit": "lb"
    },
    {
      "dimension_type": "count",
      "value": 3,
      "unit": "units"
    }
  ],
  "use_by_date": "2024-03-15T00:00:00Z",
  "tags": ["meat", "frozen"],
  "notes": "From farmer's market"
}
```

**Output:**
```json
{
  "item": {
    "item_id": "item_xyz789",
    "name": "Ground Beef",
    "location_id": "loc_abc123",
    "quantity": 5,
    "unit": "lbs",
    "dimensions": [
      {
        "dimension_type": "weight",
        "value": 5,
        "unit": "lb"
      },
      {
        "dimension_type": "count",
        "value": 3,
        "unit": "units"
      }
    ],
    "use_by_date": "2024-03-15T00:00:00Z",
    "tags": ["meat", "frozen"],
    "notes": "From farmer's market",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**Dimension Types:**
- **count**: Number of items (units)
- **weight**: Weight (g, kg, oz, lb)
- **volume**: Volume (ml, l, tsp, tbsp, fl oz, cup, pint, quart, gallon)

#### List Items

**API Endpoint:** `GET /items[?location_id=<id>&tag=<tag>&name=<name>]`

**CLI Command:**
```bash
./pantry_cli.py item list [--location <location_id>] [--tag <tag>] [--name <name>]
```

**Output:**
```json
{
  "items": [
    {
      "item_id": "item_xyz789",
      "name": "Ground Beef",
      "location_id": "loc_abc123",
      "quantity": 5,
      "unit": "lbs",
      "dimensions": [...],
      "use_by_date": "2024-03-15T00:00:00Z",
      "tags": ["meat", "frozen"],
      "notes": "From farmer's market",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### Get Item

**API Endpoint:** `GET /items/<item_id>`

**CLI Command:**
```bash
./pantry_cli.py item get <item_id>
```

**Output:**
```json
{
  "item": {
    "item_id": "item_xyz789",
    "name": "Ground Beef",
    "location_id": "loc_abc123",
    "quantity": 5,
    "unit": "lbs",
    "dimensions": [...],
    "use_by_date": "2024-03-15T00:00:00Z",
    "tags": ["meat", "frozen"],
    "notes": "From farmer's market",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

#### Update Item

**API Endpoint:** `PUT /items/<item_id>`

**CLI Command:**
```bash
./pantry_cli.py item update <item_id> \
  [--name <name>] [--location <location_id>] \
  [--quantity <qty>] [--unit <unit>] \
  [--count <value>] \
  [--weight <value>] [--weight-unit <unit>] \
  [--volume <value>] [--volume-unit <unit>] \
  [--use-by <YYYY-MM-DD>] [--tags <tag1,tag2>] [--notes <text>]
```

**Input:** Same structure as Add Item (only include fields to update)

**Output:** Same structure as Get Item with updated values

#### Remove Item

**API Endpoint:** `DELETE /items/<item_id>`

**CLI Command:**
```bash
./pantry_cli.py item remove <item_id>
```

**Output:**
```json
{
  "message": "Item deleted successfully"
}
```

#### Get Expiring Items

**API Endpoint:** `GET /items/expiring[?location_id=<id>&days=<days>]`

**CLI Command:**
```bash
./pantry_cli.py item expiring [--location <location_id>] [--days <days>]
```

**Query Parameters:**
- `location_id` (optional): Filter by location
- `days` (optional): Number of days to look ahead (default: 7)

**Output:**
```json
{
  "items": [
    {
      "item_id": "item_xyz789",
      "name": "Ground Beef",
      "location_id": "loc_abc123",
      "use_by_date": "2024-03-15T00:00:00Z",
      "days_until_expiry": 3,
      ...
    }
  ]
}
```

### Search & Statistics

#### Advanced Search

**API Endpoint:** `POST /search`

**CLI Command:**
```bash
./pantry_cli.py search \
  [--name <name>] [--location <location_id>] \
  [--tags <tag1,tag2>] \
  [--use-by-start <YYYY-MM-DD>] [--use-by-end <YYYY-MM-DD>]
```

**Input:**
```json
{
  "name": "beef",
  "location_id": "loc_abc123",
  "tags": ["meat", "frozen"],
  "use_by_date_start": "2024-01-01",
  "use_by_date_end": "2024-12-31"
}
```

**Output:**
```json
{
  "items": [
    {
      "item_id": "item_xyz789",
      "name": "Ground Beef",
      ...
    }
  ]
}
```

#### Aggregate Statistics

**API Endpoint:** `GET /aggregate[?location_id=<id>&tag=<tag>&weight_unit=<unit>&volume_unit=<unit>]`

**CLI Command:**
```bash
./pantry_cli.py stats \
  [--location <location_id>] [--tag <tag>] \
  [--weight-unit <unit>] [--volume-unit <unit>]
```

**Query Parameters:**
- `location_id` (optional): Filter by location
- `tag` (optional): Filter by tag
- `weight_unit` (optional): Preferred weight unit for aggregation (g, kg, oz, lb)
- `volume_unit` (optional): Preferred volume unit for aggregation (ml, l, cup, gallon, etc.)

**Output:**
```json
{
  "stats": {
    "total_items": 42,
    "total_locations": 5,
    "items_expiring_soon": 3,
    "dimensions": {
      "total_count": 150,
      "total_weight": {
        "value": 250.5,
        "unit": "lb"
      },
      "total_volume": {
        "value": 45.2,
        "unit": "gallon"
      }
    },
    "by_location": {
      "loc_abc123": {
        "name": "Main Freezer",
        "item_count": 20,
        "dimensions": {...}
      }
    }
  }
}
```

## Architecture

### Tech Stack
- **Backend**: AWS Lambda with Lambda Powertools (Python 3.11)
- **Database**: DynamoDB with GSIs for optimized access patterns
- **Frontend**:
  - Python CLI with Click (outputs JSON matching API responses)
  - React Web App with AWS Cognito authentication
- **Infrastructure**: Terraform/Terragrunt
- **Deployment**: GitHub Actions with OIDC authentication
- **Region**: US-East-2 (Ohio)

### Database Tables

#### Items Table
- **Primary Key**: `item_id` (hash), `created_at` (range)
- **GSIs**:
  - `LocationIndex`: Query items by location
  - `UseByDateIndex`: Query items by expiration date
  - `ItemNameIndex`: Search items by name

#### Locations Table
- **Primary Key**: `location_id` (hash)

#### Item-Tags Table
- **Primary Key**: `tag_name` (hash), `item_id` (range)
- **GSI**: `ItemTagsIndex` for reverse lookup

### Resource Naming Convention
All AWS resources follow: `{environment}-{region}-{project}-{resource_type}-{resource_name}`

Example: `dev-use2-pantry-lambda-core-api`

## Development

### Directory Structure

```
PantryApp/
├── frontend/
│   ├── cli/                # Python CLI application
│   └── react/              # React web frontend
│       ├── shared/         # Platform-agnostic business logic
│       └── web/            # React web application
├── backend/                # Lambda function code
│   ├── app.py             # Main Lambda handler with Powertools
│   ├── models.py          # Data models
│   └── services.py        # Business logic services
├── terraform/             # Infrastructure as Code
│   ├── modules/           # Reusable Terraform modules
│   └── environments/      # Environment configurations
└── .github/workflows/     # CI/CD workflows
```

### AI-Assisted Workflow

This project uses Claude as Lead Developer and Gemini CLI as Subject Matter Expert.

**To request changes:**
1. Create a GitHub Issue describing the feature or bug
2. Claude analyzes the codebase and implements changes
3. Review the PR and provide feedback

**Configuration:**
- `.claude/CLAUDE.md` - Instructions for Claude
- `GEMINI.md` - Instructions for Gemini CLI
- `CODEOWNERS` - Code ownership definitions

### CLI/API Alignment Standards

The project maintains strict one-to-one correspondence between CLI and API:

1. **One-to-One Mapping**: Every API endpoint has exactly one CLI command
2. **Argument Alignment**: CLI arguments match API parameters exactly
3. **JSON Output**: All CLI commands output pretty-printed JSON matching API responses
4. **Consistent Behavior**: Same input validation, error messages, and response structure

See `.claude/CLAUDE.md` for detailed alignment requirements.

### Local Testing

**Test Lambda locally:**
```bash
cd backend
pip install -r requirements.txt
python -c "from app import lambda_handler; print(lambda_handler({'httpMethod': 'GET', 'path': '/locations'}, {}))"
```

**Terraform operations:**
```bash
cd terraform/environments/dev
terragrunt plan
terragrunt apply
```

## Deployment

### Initial Setup

1. **Create OIDC Provider in AWS IAM:**
   - Provider URL: `https://token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`

2. **Create IAM Role** with trust policy for GitHub Actions

3. **Create Remote State Resources:**
   ```bash
   # Create S3 bucket for Terraform state
   aws s3 mb s3://dev-use2-pantry-terraform-state --region us-east-2

   # Enable versioning
   aws s3api put-bucket-versioning \
     --bucket dev-use2-pantry-terraform-state \
     --versioning-configuration Status=Enabled

   # Create DynamoDB table for state locking
   aws dynamodb create-table \
     --table-name dev-use2-pantry-terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-east-2
   ```

4. **Deploy via GitHub Actions:**
   ```bash
   gh workflow run deploy.yml -f environment=dev
   ```

## Monitoring

The Lambda function uses AWS Lambda Powertools (via AWS-managed Layer) for:
- **Structured Logging**: JSON logs with correlation IDs
- **X-Ray Tracing**: Distributed tracing
- **CloudWatch Metrics**: Custom metrics for operations

**View logs and metrics:**
- Log group: `/aws/lambda/dev-use2-pantry-lambda-core-api`
- Metrics namespace: `PantryApp`
- X-Ray traces: AWS X-Ray console

## Security

- OIDC authentication (no hardcoded credentials)
- IAM roles with least privilege
- DynamoDB encryption at rest
- Point-in-time recovery (prod)

## Contributing

1. Create an issue describing your change
2. Claude implements and creates a PR
3. Review and provide feedback
4. Changes are iterated until approved
5. Merge triggers automatic deployment

## License

[Specify your license here]
