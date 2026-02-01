# Root configuration for Terragrunt
# This file contains common configuration shared across all environments

locals {
  # Project-wide settings
  project_name = "pantry"
  region       = "us-east-2"
  region_abbr  = "use2"

  # Parse environment from the directory name (either "dev" or "prod")
  parsed_path = split("/", get_terragrunt_dir())
  environment = element(local.parsed_path, length(local.parsed_path) - 1)

  # Common naming convention: {environment}-{region}-{project}-{resource_type}-{resource_name}
  name_prefix = "${local.environment}-${local.region_abbr}-${local.project_name}"

  # Common tags
  common_tags = {
    Project     = local.project_name
    Environment = local.environment
    ManagedBy   = "Terragrunt"
    Repository  = "PantryApp"
  }
}

# Configure Terragrunt to automatically store tfstate files in S3
remote_state {
  backend = "s3"

  config = {
    encrypt        = true
    bucket         = "${local.name_prefix}-terraform-state"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = local.region
    dynamodb_table = "${local.name_prefix}-terraform-locks"
  }

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

# Generate an AWS provider block
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "${local.region}"

  default_tags {
    tags = ${jsonencode(local.common_tags)}
  }
}
EOF
}

# Configure retry settings
retryable_errors = [
  "(?s).*Error.*429.*",
  "(?s).*Error.*TooManyRequestsException.*",
  "(?s).*Error.*ResourceConflictException.*",
]
