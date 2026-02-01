# Dev environment configuration

include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  root_vars = read_terragrunt_config(find_in_parent_folders("root.hcl"))
  env_vars  = read_terragrunt_config(find_in_parent_folders("globals.hcl"))

  name_prefix = local.root_vars.locals.name_prefix
}

# Main infrastructure for dev environment
terraform {
  source = "../../modules//main"
}

inputs = {
  environment        = local.env_vars.locals.environment
  name_prefix        = local.name_prefix
  lambda_runtime     = local.env_vars.locals.lambda_runtime
  lambda_timeout     = local.env_vars.locals.lambda_timeout
  lambda_memory_size = local.env_vars.locals.lambda_memory_size
  log_retention_days = local.env_vars.locals.log_retention_days

  # DynamoDB configuration
  dynamodb_billing_mode = local.env_vars.locals.dynamodb_billing_mode

  # Environment-specific tags
  env_tags = local.env_vars.locals.env_tags
}
