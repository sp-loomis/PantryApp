# Pantry App - Multi-User Authentication with AWS Cognito

This document describes the multi-user authentication system implemented for the Pantry App using AWS Cognito.

## Overview

The Pantry App now supports multiple separate users, each with their own isolated data. Authentication is handled by AWS Cognito User Pools with two user groups:
- **User**: Standard users who can only access their own data
- **Admin**: Administrative users who can access all users' data

## Architecture

### Components

1. **AWS Cognito User Pool**: Manages user registration, authentication, and JWT token issuance
2. **User Groups**: Admin and User groups for access control
3. **DynamoDB Tables**: Refactored with `user_id` as partition key for data isolation
4. **API Authentication**: All API endpoints require authentication via JWT tokens
5. **CLI Authentication**: CLI supports login, signup, and token management

### Data Model Changes

All DynamoDB tables have been refactored to use `user_id` (Cognito `sub` claim) as the partition key:

#### Items Table
- **Primary Key**: `user_id` (PK), `item_id` (SK)
- **GSIs**:
  - LocationIndex: `user_id` (PK), `location_id` (SK)
  - UseByDateIndex: `user_id` (PK), `use_by_date` (SK)
  - ItemNameIndex: `user_id` (PK), `item_name` (SK)

#### Locations Table
- **Primary Key**: `user_id` (PK), `location_id` (SK)

#### Item-Tags Table
- **Primary Key**: `user_id` (PK), `tag_item_composite` (SK)
- **GSIs**:
  - TagIndex: `user_id` (PK), `tag_name` (SK)
  - ItemTagsIndex: `user_id` (PK), `item_id` (SK)

## Setup Instructions

### 1. Deploy Infrastructure

Deploy the updated Terraform configuration to create the Cognito User Pool and refactored DynamoDB tables:

```bash
cd terraform/environments/dev  # or prod
terragrunt apply
```

**Important**: This will recreate the DynamoDB tables. All existing data will be lost. Back up any data you need before deploying.

### 2. Get Cognito Configuration

After deployment, retrieve the Cognito configuration:

```bash
terragrunt output
```

You'll need:
- `cognito_user_pool_id`: The User Pool ID
- `cognito_client_id`: The App Client ID

### 3. Configure CLI

Set environment variables for the CLI:

```bash
export COGNITO_USER_POOL_ID="<your-user-pool-id>"
export COGNITO_CLIENT_ID="<your-client-id>"
export PANTRY_LAMBDA_FUNCTION="<your-lambda-function-name>"
```

Add these to your `~/.bashrc` or `~/.zshrc` for persistence.

## Usage

### CLI Authentication

#### Sign Up
Create a new user account:

```bash
pantry auth signup --email john@example.com
# You'll be prompted for a password
```

You'll receive a verification code via email.

#### Confirm Signup
Verify your email address:

```bash
pantry auth confirm --email john@example.com --code 123456
```

#### Login
Authenticate and receive JWT tokens:

```bash
pantry auth login --email john@example.com
# You'll be prompted for your password
```

Tokens are stored securely in `~/.pantry/tokens.json` and automatically refreshed.

#### Check Status
Check if you're logged in:

```bash
pantry auth status
```

#### Logout
Clear stored tokens:

```bash
pantry auth logout
```

### Using the CLI

Once logged in, all CLI commands automatically include your authentication token:

```bash
# Create a location
pantry location create --name "Kitchen Pantry" --description "Main pantry"

# List your locations
pantry location list

# Add an item
pantry item add --name "Flour" --location <location-id> --quantity 2 --unit kg
```

### Admin Operations

Admin users can access other users' data by specifying the `--user-id` option:

```bash
# List locations for a specific user
pantry location list --user-id <user-sub>

# Create a location for another user
pantry location create --name "Test Location" --user-id <user-sub>
```

## API Usage

### Authentication

All API requests must include a valid JWT token in the Authorization header:

```
Authorization: Bearer <id-token>
```

### User Context

- **Regular Users**: API automatically filters data by the authenticated user's ID (from JWT `sub` claim)
- **Admin Users**: Can specify a `user_id` query parameter to access another user's data

### Example API Calls

#### Get Own Locations
```bash
curl -H "Authorization: Bearer $ID_TOKEN" \
  https://api.example.com/locations
```

#### Admin: Get Another User's Locations
```bash
curl -H "Authorization: Bearer $ID_TOKEN" \
  "https://api.example.com/locations?user_id=<target-user-id>"
```

## Security Considerations

### Token Storage
- CLI tokens are stored in `~/.pantry/tokens.json` with 0600 permissions (owner read/write only)
- Tokens are automatically refreshed when they expire
- Tokens include: ID Token, Access Token, and Refresh Token

### Password Requirements
Cognito enforces the following password policy:
- Minimum 8 characters
- At least one lowercase letter
- At least one uppercase letter
- At least one number
- At least one special character

### Data Isolation
- All database queries are scoped by `user_id` at the service layer
- Users cannot access other users' data unless they are admins
- Admin privilege is determined by Cognito group membership

### API Gateway Integration (Future)

Currently, the Lambda function is invoked directly by the CLI. When deploying with API Gateway:

1. Add a Cognito User Pool Authorizer to API Gateway
2. Configure all routes to use the authorizer
3. API Gateway will validate JWT tokens automatically
4. Lambda will receive validated claims in `requestContext.authorizer.claims`

## User Management

### Adding Users to Admin Group

Use the AWS CLI to add users to the Admin group:

```bash
aws cognito-idp admin-add-user-to-group \
  --user-pool-id <pool-id> \
  --username <user-email> \
  --group-name Admin
```

Note: The `--username` parameter expects the user's email address since email is used as the username.

### Creating Users Programmatically

Admins can create users via AWS SDK:

```python
import boto3

cognito = boto3.client('cognito-idp')

cognito.admin_create_user(
    UserPoolId='<pool-id>',
    Username='newuser@example.com',  # Email is used as username
    UserAttributes=[
        {'Name': 'email', 'Value': 'newuser@example.com'},
        {'Name': 'email_verified', 'Value': 'true'}
    ],
    TemporaryPassword='TempPassword123!',
    MessageAction='SUPPRESS'  # Don't send welcome email
)
```

## Troubleshooting

### "User not authenticated" Error
- Ensure you're logged in: `pantry auth status`
- Login if needed: `pantry auth login --email <your-email>`
- Check that `COGNITO_CLIENT_ID` environment variable is set

### "Permission denied" Error
- You're trying to access another user's data without admin privileges
- Contact your administrator to be added to the Admin group

### "Token refresh failed" Error
- Your refresh token has expired (30 days)
- Login again: `pantry auth login --email <your-email>`

### CLI Not Using Authentication
- Verify environment variables are set: `echo $COGNITO_CLIENT_ID`
- Check token file exists: `cat ~/.pantry/tokens.json`
- Try logging out and back in

## Migration from Old System

### For Existing Data

The new system is **not backwards compatible** with the old table structure. To migrate:

1. **Export Old Data**: Use AWS CLI or SDK to scan and export all items from old tables
2. **Transform Data**: Add `user_id` field to all records
3. **Import to New Tables**: Put items with the new schema including `user_id`

Example export script:

```python
import boto3
import json

dynamodb = boto3.resource('dynamodb')
old_table = dynamodb.Table('old-items-table')

# Scan all items
items = []
response = old_table.scan()
items.extend(response['Items'])

while 'LastEvaluatedKey' in response:
    response = old_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response['Items'])

# Save to file
with open('items_backup.json', 'w') as f:
    json.dump(items, f, indent=2, default=str)
```

### For Testing

For testing the new system, it's recommended to:
1. Clear all data from tables
2. Create test users via CLI signup
3. Create fresh test data scoped to each user

## Next Steps

1. **API Gateway Integration**: Add Cognito authorizer to API Gateway routes
2. **Web UI**: Build a web interface for user management
3. **Email Customization**: Customize Cognito email templates
4. **MFA**: Enable multi-factor authentication for enhanced security
5. **User Profile**: Add user profile management endpoints
6. **Audit Logging**: Implement CloudWatch logging for user actions
