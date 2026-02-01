# Global variables for prod environment

locals {
  environment = "prod"

  # DynamoDB configuration for prod
  dynamodb_billing_mode = "PAY_PER_REQUEST"

  # Lambda configuration for prod
  lambda_runtime     = "python3.11"
  lambda_timeout     = 30
  lambda_memory_size = 512

  # Log retention for prod (longer retention for compliance)
  log_retention_days = 30

  # Additional prod-specific tags
  env_tags = {
    CostCenter = "production"
  }
}
