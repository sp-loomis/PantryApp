# Pantry App Backend API

This directory contains the AWS Lambda function that powers the Pantry App API.

## Architecture

The backend uses:
- **AWS Lambda** with Python 3.11 runtime
- **AWS Lambda Powertools** for structured logging, tracing, and metrics
- **DynamoDB** for data storage
- **API Gateway REST Resolver** from Powertools for request routing

## Dependency Management

### AWS Lambda Powertools

**Important:** AWS Lambda Powertools is provided via an **AWS-managed Lambda Layer**, not bundled with the deployment package.

The Lambda layer is configured in `terraform/modules/main/main.tf`:
```hcl
layers = [
  "arn:aws:lambda:${region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python311-x86_64:3"
]
```

**Why use a Lambda Layer?**
- AWS maintains official Powertools layers for each Python version
- Reduces deployment package size (faster deployments)
- Always up-to-date with the latest compatible version
- No need to package these dependencies

**Layer Details:**
- ARN format: `arn:aws:lambda:{region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python311-x86_64:{version}`
- Account `017000801446` is the official AWS Serverless Application Repository account
- Contains `aws-lambda-powertools[all]==3.x` with all optional dependencies
- Compatible with Python 3.11 (x86_64 architecture)

### Other Dependencies

**boto3** - Already included in the Lambda runtime environment, no need to bundle.

If you add additional dependencies in the future:
1. Add them to `requirements.txt`
2. The GitHub Actions workflow will automatically install and bundle them
3. They will be zipped with your code and deployed

## Local Development

To test locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (when test suite is added)
pytest tests/
```

## Lambda Handler

The main handler is in `app.py`:
- `lambda_handler(event, context)` - Main entry point
- Uses Powertools' `APIGatewayRestResolver` for routing
- All routes are decorated with `@app.post()`, `@app.get()`, etc.

## Environment Variables

The Lambda function requires these environment variables (configured via Terraform):
- `ITEMS_TABLE_NAME` - DynamoDB table for items
- `LOCATIONS_TABLE_NAME` - DynamoDB table for storage locations
- `ITEM_TAGS_TABLE_NAME` - DynamoDB table for item-tag relationships
- `ENVIRONMENT` - Deployment environment (dev/prod)

## Powertools Features Used

### Logger
```python
from aws_lambda_powertools import Logger
logger = Logger()
logger.info("Event received", extra={"request_id": context.request_id})
```

### Tracer (X-Ray)
```python
from aws_lambda_powertools import Tracer
tracer = Tracer()

@tracer.capture_method
def my_function():
    ...
```

### Metrics (CloudWatch)
```python
from aws_lambda_powertools import Metrics
metrics = Metrics()

@metrics.log_metrics
def lambda_handler(event, context):
    metrics.add_metric(name="ItemCreated", unit="Count", value=1)
```

### Event Handler (API Gateway)
```python
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
app = APIGatewayRestResolver()

@app.post("/items")
def create_item():
    return {"message": "Item created"}
```

## Deployment

Deployment is handled automatically via GitHub Actions (`.github/workflows/deploy.yml`):

1. Code is checked out
2. Backend dependencies are installed (if any)
3. Terraform/Terragrunt packages the code
4. Lambda function is deployed with the Powertools layer attached

## Monitoring

With Powertools enabled, you get:
- **Structured logs** in CloudWatch Logs (JSON format)
- **Distributed tracing** in AWS X-Ray
- **Custom metrics** in CloudWatch Metrics
- **Request/response logging** with correlation IDs

## References

- [AWS Lambda Powertools Documentation](https://docs.powertools.aws.dev/lambda/python/latest/)
- [AWS Lambda Layers](https://docs.aws.amazon.com/lambda/latest/dg/chapter-layers.html)
- [Official Powertools Layer ARNs](https://docs.powertools.aws.dev/lambda/python/latest/#lambda-layer)
