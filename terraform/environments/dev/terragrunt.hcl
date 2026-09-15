# Dev environment configuration

include "root" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  root_vars   = read_terragrunt_config(find_in_parent_folders("root.hcl"))
  global_vars = read_terragrunt_config(find_in_parent_folders("globals.hcl"))

  # Environment-specific variables for dev
  environment        = "dev"

  # Build name_prefix from THIS file's explicit environment. Do not reuse
  # root_vars.locals.name_prefix: root.hcl derives the environment from
  # path_relative_to_include(), which only resolves inside an include chain and
  # returns "." (falling back to "dev") when read via read_terragrunt_config().
  name_prefix = "${local.environment}-${local.root_vars.locals.region_abbr}-${local.root_vars.locals.project_name}"
  lambda_memory_size = 256
  log_retention_days = 7

  # Slack integration (see docs/slack-integration-plan.md). client_id is not
  # secret; the client_secret + state HMAC live in Secrets Manager (populated
  # out-of-band). The redirect URI must be registered on the Slack app and
  # match the deployed API domain, e.g.
  # https://<api-id>.execute-api.<region>.amazonaws.com/<stage>/slack/oauth/callback.
  # Fill these in once the dev Slack app + API domain are known.
  slack_client_id    = ""
  slack_redirect_uri = ""

  # Environment-specific tags
  env_tags = {
    CostCenter = "development"
  }
}

# Main infrastructure for dev environment
terraform {
  source = "../../..//terraform/modules/main"
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

  # Slack integration
  slack_client_id    = local.slack_client_id
  slack_redirect_uri = local.slack_redirect_uri

  # Environment-specific tags
  env_tags = local.env_tags
}
