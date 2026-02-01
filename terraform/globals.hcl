# Global variables shared across all environments
# Environment-specific variables should be defined in each environment's terragrunt.hcl

locals {
  # Lambda configuration (shared across environments)
  lambda_runtime = "python3.11"
  lambda_timeout = 30

  # DynamoDB configuration (shared across environments)
  dynamodb_billing_mode = "PAY_PER_REQUEST"
}
