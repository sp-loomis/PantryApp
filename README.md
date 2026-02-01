# Pantry App - Inventory Management System

A comprehensive inventory management system for tracking items across multiple storage locations (pantries, freezers, feed storage, etc.). Built with AWS serverless architecture and managed through an AI-assisted development workflow.

## Overview

The Pantry App helps you track:
- **Storage Locations**: Manage multiple storage areas (pantry, freezers, tack room, etc.)
- **Inventory Items**: Track what you have, where it is, and how much
- **Expiration Dates**: Never lose track of use-by dates
- **Tags**: Flexible categorization for easy searching
- **Quantities**: Track dimensions and units for each item
- **Search & Query**: Advanced filtering and aggregate statistics

## Architecture

### Tech Stack
- **Frontend**: Python CLI with Rich library for enhanced terminal output
- **Backend**: AWS Lambda with Lambda Powertools (Python 3.11)
- **Database**: DynamoDB with optimized GSIs for different access patterns
- **Infrastructure**: Terraform/Terragrunt for Infrastructure as Code
- **Deployment**: GitHub Actions with OIDC authentication (no hardcoded credentials)
- **Region**: US-East-2 (Ohio)

### Database Design

#### Items Table
- **Primary Key**: `item_id` (hash), `created_at` (range)
- **GSIs**:
  - `LocationIndex`: Query items by location
  - `UseByDateIndex`: Query items by expiration date
  - `ItemNameIndex`: Search items by name
- **Attributes**: name, location_id, quantity, unit, use_by_date, notes

#### Locations Table
- **Primary Key**: `location_id` (hash)
- **Attributes**: name, description

#### Item-Tags Table
- **Primary Key**: `tag_name` (hash), `item_id` (range)
- **GSI**: `ItemTagsIndex` for reverse lookup (item_id -> tags)

### Resource Naming Convention
All AWS resources follow: `{environment}-{region}-{project}-{resource_type}-{resource_name}`

Example: `dev-use2-pantry-lambda-core-api`

## Directory Structure

```
PantryApp/
├── frontend/
│   └── cli/                    # Python CLI application
│       ├── pantry_cli.py      # Main CLI with Click commands
│       └── requirements.txt    # Python dependencies
├── backend/                    # Lambda function code
│   ├── app.py                 # Main Lambda handler with Powertools
│   ├── models.py              # Data models (Item, Location, ItemTag)
│   ├── services.py            # Business logic services
│   └── requirements.txt       # Lambda dependencies
├── terraform/
│   ├── root.hcl               # Root Terragrunt configuration
│   ├── modules/               # Reusable Terraform modules
│   │   ├── dynamodb_table/    # DynamoDB table module
│   │   ├── lambda_function/   # Lambda function module
│   │   ├── iam_role/          # IAM role module
│   │   └── main/              # Main infrastructure composition
│   └── environments/
│       ├── dev/               # Dev environment config
│       │   ├── globals.hcl
│       │   └── terragrunt.hcl
│       └── prod/              # Prod environment config
│           ├── globals.hcl
│           └── terragrunt.hcl
└── .github/workflows/
    ├── claude-issue-handler.yml  # AI-assisted development workflow
    └── deploy.yml                # Infrastructure deployment
```

## Getting Started

### Prerequisites
- AWS Account with appropriate permissions
- Python 3.11+
- Terraform 1.6+
- Terragrunt 0.54+
- AWS CLI configured

### Initial Setup

#### 1. Configure AWS OIDC
Set up GitHub OIDC provider in AWS for secure, credential-free deployments:

1. Create an OIDC provider in IAM:
   - Provider URL: `https://token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`

2. Create an IAM role with trust policy for GitHub Actions:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
         },
         "Action": "sts:AssumeRoleWithWebIdentity",
         "Condition": {
           "StringEquals": {
             "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
             "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/PantryApp:ref:refs/heads/main"
           }
         }
       }
     ]
   }
   ```

3. Add the role ARN to GitHub Secrets:
   - Go to Settings > Secrets and variables > Actions
   - Add `AWS_ROLE_ARN` with the IAM role ARN

#### 2. Create Remote State Resources
Before deploying, manually create the S3 bucket and DynamoDB table for Terraform state:

```bash
# For dev environment
aws s3 mb s3://dev-use2-pantry-terraform-state --region us-east-2
aws dynamodb create-table \
  --table-name dev-use2-pantry-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-2
```

#### 3. Deploy Infrastructure
Push changes to trigger deployment or manually run:

```bash
# Deploy to dev
gh workflow run deploy.yml -f environment=dev

# Deploy to prod
gh workflow run deploy.yml -f environment=prod
```

### Using the CLI

#### Installation
```bash
cd frontend/cli
pip install -r requirements.txt
chmod +x pantry_cli.py
```

#### Configure Lambda Function Name
```bash
export PANTRY_LAMBDA_FUNCTION=dev-use2-pantry-lambda-core-api
```

#### Example Commands

**Manage Locations:**
```bash
# Create a location
./pantry_cli.py location create --name "Main Freezer" --description "Large chest freezer in garage"

# List all locations
./pantry_cli.py location list

# Get location details
./pantry_cli.py location get <location-id>
```

**Manage Items:**
```bash
# Add an item
./pantry_cli.py item add \
  --name "Ground Beef" \
  --location <location-id> \
  --quantity 5 \
  --unit "lbs" \
  --use-by "2024-03-15" \
  --tags "meat,frozen" \
  --notes "From farmer's market"

# List all items
./pantry_cli.py item list

# List items by location
./pantry_cli.py item list --location <location-id>

# List items by tag
./pantry_cli.py item list --tag "frozen"

# Check expiring items
./pantry_cli.py item expiring --days 7
```

**Search and Stats:**
```bash
# Advanced search
./pantry_cli.py search \
  --name "beef" \
  --location <location-id> \
  --tags "meat,frozen" \
  --use-by-start "2024-01-01" \
  --use-by-end "2024-12-31"

# Get aggregate statistics
./pantry_cli.py stats
./pantry_cli.py stats --location <location-id>
./pantry_cli.py stats --tag "frozen"
```

## API Endpoints

The Lambda function exposes the following REST-style endpoints:

### Locations
- `POST /locations` - Create location
- `GET /locations` - List all locations
- `GET /locations/{id}` - Get location
- `PUT /locations/{id}` - Update location
- `DELETE /locations/{id}` - Delete location

### Items
- `POST /items` - Create item
- `GET /items` - List items (with optional filters)
- `GET /items/{id}` - Get item
- `PUT /items/{id}` - Update item
- `DELETE /items/{id}` - Delete item
- `GET /items/expiring` - Get expiring items

### Search
- `POST /search` - Advanced search
- `GET /aggregate` - Aggregate statistics

## Development

### AI-Assisted Workflow

This project uses Claude as the Lead Developer and Gemini CLI as a Subject Matter Expert.

**To request changes:**
1. Create a GitHub Issue describing the feature or bug
2. Claude will analyze the codebase, implement changes, and create a PR
3. Review the PR and provide feedback
4. Claude will address feedback and update the PR

**Configuration files:**
- `.claude/CLAUDE.md` - Instructions for Claude
- `GEMINI.md` - Instructions for Gemini CLI
- `CODEOWNERS` - Code ownership definitions

### Manual Development

**Testing Lambda locally:**
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

## Monitoring and Observability

The Lambda function uses AWS Lambda Powertools for:
- **Structured Logging**: JSON logs with correlation IDs
- **X-Ray Tracing**: Distributed tracing across services
- **CloudWatch Metrics**: Custom metrics for operations

View logs and metrics in CloudWatch:
- Log group: `/aws/lambda/dev-use2-pantry-lambda-core-api`
- Metrics namespace: `pantry-dev`

## Security

- No hardcoded AWS credentials (OIDC authentication)
- IAM roles follow least privilege principle
- DynamoDB encryption at rest enabled
- Point-in-time recovery enabled for prod
- VPC integration available (currently disabled for cost)

## Cost Optimization

- DynamoDB uses PAY_PER_REQUEST billing (scales to zero)
- Lambda charged per-invocation (generous free tier)
- CloudWatch log retention: 7 days (dev), 30 days (prod)
- No NAT Gateway or VPC costs (Lambda runs in AWS network)

## Contributing

This project follows an AI-assisted development workflow. To contribute:

1. Create an issue describing your change
2. Allow Claude to implement and create a PR
3. Review and provide feedback on the PR
4. Changes will be iterated until approved
5. Merge to main triggers automatic deployment

## License

[Specify your license here]

## Support

For issues or questions:
- Create a GitHub Issue
- Tag @sp-loomis for urgent matters
- Check existing issues for similar problems
