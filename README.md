# Homestead Manager

A serverless homestead management system: track pantry **inventory** across storage locations *and* stay on top of **tasks and chores** — one-shot deadlines plus recurring daily/weekly/every-N-days routines that gracefully disappear when a window passes. Built with AWS Lambda, DynamoDB, and a React web app.

> Formerly "Pantry App" — the inventory features are unchanged; task tracking is the latest addition.
>
> **Note:** the early-development Python CLI (`frontend/cli`) has been retired — the
> React SPA is the primary (and only) client. The REST API below is unchanged.

## Quick Start

### Prerequisites

- AWS Account with appropriate permissions
- Python 3.11+
- Node.js 18+ (for React frontend)
- AWS CLI configured

### Setup

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

## API Documentation

The REST API is the single contract for all clients. Every endpoint is Cognito-authenticated (Bearer token) and returns JSON.

### Locations

Storage locations represent physical areas where inventory is stored (pantry, freezer, tack room, etc.).

#### Create Location

**API Endpoint:** `POST /locations`

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

**API Endpoint:** `GET /items[?location_id=<id>&tag=<tag>]`

> Name search moved to `POST /search` (fuzzy & ranked). `GET /items` exposes only
> the structural `location`/`tag` filters.

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

**Input:** Same structure as Add Item (only include fields to update)

**Output:** Same structure as Get Item with updated values

#### Consume Item

**API Endpoint:** `POST /items/<item_id>/consume`

Records genuine **usage** of an item (distinct from deletion, which is a data
removal). Decrements the item's matching dimension by the consumed amount and
appends a ledger event; consuming the last of an item marks it depleted.

**Output:** The updated item (or a depleted marker when fully consumed).

#### Remove Item

**API Endpoint:** `DELETE /items/<item_id>`

Soft-deletes the item (removes it from active views while preserving history);
recorded in the ledger as a data removal, **not** a consumption.

**Output:**

```json
{
  "message": "Item deleted successfully"
}
```

#### Get Expiring Items

**API Endpoint:** `GET /items/expiring[?location_id=<id>&days=<days>]`

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

Name matching is **fuzzy, multi-word, and order-independent**: the query is split
into terms and _every_ term must match some word of the item name (by substring or
typo-tolerant similarity), so `name: "milk whole"` matches "Whole Milk". Results are
**ranked by relevance**, and each matched item carries a `match` object with the score
and whole-word highlight spans (character offsets into `name`) for the UI. `min_score`
tunes the fuzzy threshold (default `0.7`); the other criteria are applied as filters on
top of the name match.

**Input:**

```json
{
  "name": "beef",
  "location_id": "loc_abc123",
  "tags": ["meat", "frozen"],
  "use_by_date_start": "2024-01-01",
  "use_by_date_end": "2024-12-31",
  "min_score": 0.7
}
```

**Output:** (`match` present only when `name` was supplied)

```json
{
  "items": [
    {
      "item_id": "item_xyz789",
      "name": "Ground Beef",
      "match": { "score": 1.0, "spans": [{ "start": 7, "end": 11 }] },
      "...": "..."
    }
  ]
}
```

#### Aggregate Statistics

**API Endpoint:** `GET /aggregate[?location_id=<id>&tag=<tag>&weight_unit=<unit>&volume_unit=<unit>]`

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

### Reports & Notifications

User-defined **scheduled reports** render into an **in-app message log**, with a toolbar
notifications dropdown (unread badge) reachable anywhere in the web app. A report is an
ordered set of section rules — a custom message, a task query ("incomplete tasks matching
this query"), or an inventory query — fired on a simple daily/weekly/monthly schedule. A
periodic EventBridge sweep generates due reports; `POST /reports/<id>/run` generates one
immediately. Slack delivery is layered on the same engine (see below).

**API:**

- Reports: `POST /reports`, `GET /reports`, `GET /reports/<id>`, `PUT /reports/<id>`,
  `DELETE /reports/<id>`, `POST /reports/<id>/run`
- Messages: `GET /messages`, `GET /messages/unread`, `GET /messages/<id>`,
  `POST /messages/<id>/read`, `POST /messages/<id>/unread`, `DELETE /messages/<id>`

See [`docs/notifications-reports-plan.md`](docs/notifications-reports-plan.md) for the full
design.

### Slack Integration

**Bring-your-own-Slack**, multi-tenant: each user connects **their own** Slack
workspace via OAuth v2; the app stores a per-workspace bot token (encrypted with a
customer-managed KMS key) and posts to channels the user selects. One user's
connection can never post into another's workspace. Manage it in the web app under
**Settings → Integrations** ("Connect Slack", channel picker, send-test, disconnect).
`SlackService.post_message(...)` is the primitive the report engine delivers through.

**API:**

- OAuth (browser-redirect): `GET /slack/oauth/start` (Cognito-guarded,
  returns the authorize URL), `GET /slack/oauth/callback` (Slack redirect; bypasses
  Cognito, trust from a signed `state`)
- Connections: `GET /slack/connections`, `GET /slack/connections/<id>/channels`,
  `DELETE /slack/connections/<id>`, `POST /slack/connections/<id>/test`

**No endpoint ever returns the bot token.** The token is stored only as KMS ciphertext.
The Slack `client_secret` and the OAuth `state` HMAC secret live in a single Secrets
Manager secret (`<name_prefix>-slack-app`) whose value is **populated out-of-band** after
deploy — Terraform creates the secret but not its contents. Register the environment's
redirect URI on the Slack app before OAuth will work.

See [`docs/slack-integration-plan.md`](docs/slack-integration-plan.md) for the full design,
and [`LOCAL_DEV.md`](LOCAL_DEV.md) for the local dev-stub (no real Slack needed).

## Architecture

### Tech Stack

- **Backend**: AWS Lambda with Lambda Powertools (Python 3.11)
- **Database**: DynamoDB with GSIs for optimized access patterns
- **Frontend**: React Web App with AWS Cognito authentication
- **Analytics**: DynamoDB Streams → S3 (JSONL) → Glue/Athena for history & SQL queries
- **Infrastructure**: Terraform/Terragrunt
- **Deployment**: GitHub Actions with OIDC authentication
- **Region**: US-East-1 (Ohio)

### Database Tables

All tables are user-scoped (`user_id` hash key) and billed `PAY_PER_REQUEST`.

#### Items Table

- **Primary Key**: `user_id` (hash), `item_id` (range)
- **GSIs**:
  - `LocationIndex`: Query items by location
  - `UseByDateIndex`: Query items by expiration date
  - `CategoryIndex`: Query items by category

#### Locations Table

- **Primary Key**: `user_id` (hash), `location_id` (range)

#### Tasks / Reports / Messages / Categories / Slack

- Each is user-scoped with its own range key. Messages carry a sparse `UnreadIndex`;
  the ledger (append-only history) carries an `EntityIndex` for per-item/task lookups.

### Resource Naming Convention

All AWS resources follow: `{environment}-{region}-{project}-{resource_type}-{resource_name}`

Example: `dev-use1-pantry-lambda-core-api`

## Development

### Directory Structure

```
PantryApp/
├── frontend/
│   └── react/              # React web frontend
│       ├── shared/         # Platform-agnostic business logic
│       └── web/            # React web application
├── backend/                # Lambda function code
│   ├── app.py             # Main Lambda handler with Powertools
│   ├── models.py          # Data models
│   ├── schema.py          # Single-source DynamoDB table schema
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

### Local Testing

**Test Lambda locally:**

```bash
cd backend
pip install -r requirements.txt
python -c "from app import lambda_handler; print(lambda_handler({'httpMethod': 'GET', 'path': '/locations'}, {}))"
```

See [`LOCAL_DEV.md`](LOCAL_DEV.md) for the full local stack (DynamoDB Local + Flask shim + Vite).

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
   aws s3 mb s3://dev-use1-pantry-terraform-state --region us-east-1

   # Enable versioning
   aws s3api put-bucket-versioning \
     --bucket dev-use1-pantry-terraform-state \
     --versioning-configuration Status=Enabled

   # Create DynamoDB table for state locking
   aws dynamodb create-table \
     --table-name dev-use1-pantry-terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST \
     --region us-east-1
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

- Log group: `/aws/lambda/dev-use1-pantry-lambda-core-api`
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
