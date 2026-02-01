# Dev environment configuration

include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  root_vars   = read_terragrunt_config(find_in_parent_folders("root.hcl"))
  global_vars = read_terragrunt_config(find_in_parent_folders("globals.hcl"))

  name_prefix = local.root_vars.locals.name_prefix

  # Environment-specific variables for dev
  environment        = "dev"
  lambda_memory_size = 256
  log_retention_days = 7

  # Environment-specific tags
  env_tags = {
    CostCenter = "development"
  }
}

# Main infrastructure for dev environment
terraform {
  source = "../../modules//main"
}

inputs = {
  environment        = local.environment
  name_prefix        = local.name_prefix
  lambda_runtime     = local.global_vars.locals.lambda_runtime
  lambda_timeout     = local.global_vars.locals.lambda_timeout
  lambda_memory_size = local.lambda_memory_size
  log_retention_days = local.log_retention_days

  # DynamoDB configuration
  dynamodb_billing_mode = local.global_vars.locals.dynamodb_billing_mode

  # Environment-specific tags
  env_tags = local.env_tags
}
