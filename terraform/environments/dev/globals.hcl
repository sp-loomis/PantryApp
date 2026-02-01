# Global variables for dev environment

locals {
  environment = "dev"

  # DynamoDB configuration for dev
  dynamodb_billing_mode = "PAY_PER_REQUEST"

  # Lambda configuration for dev
  lambda_runtime     = "python3.11"
  lambda_timeout     = 30
  lambda_memory_size = 256

  # Log retention for dev (shorter retention to save costs)
  log_retention_days = 7

  # Additional dev-specific tags
  env_tags = {
    CostCenter = "development"
  }
}
