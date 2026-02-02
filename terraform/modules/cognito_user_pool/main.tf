terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_cognito_user_pool" "pool" {
  name = var.pool_name

  # Auto-verify email addresses
  auto_verified_attributes = ["email"]

  # Email configuration
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # User attributes schema
  schema {
    name                     = "email"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = true
    string_attribute_constraints {
      min_length = 1
      max_length = 2048
    }
  }

  # Password policy
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  # Account recovery settings
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # User pool add-ons
  user_pool_add_ons {
    advanced_security_mode = "ENFORCED"
  }

  tags = merge(
    {
      Name        = var.pool_name
      Environment = var.environment
      Project     = "pantry"
    },
    var.tags
  )
}

# Create Admin user group
resource "aws_cognito_user_group" "admin" {
  name         = "Admin"
  user_pool_id = aws_cognito_user_pool.pool.id
  description  = "Administrator group with full access to all users' data"
  precedence   = 1
}

# Create User group
resource "aws_cognito_user_group" "user" {
  name         = "User"
  user_pool_id = aws_cognito_user_pool.pool.id
  description  = "Standard user group with access to own data only"
  precedence   = 2
}

# User pool client for CLI/API access
resource "aws_cognito_user_pool_client" "client" {
  name         = var.client_name
  user_pool_id = aws_cognito_user_pool.pool.id

  # Don't generate a secret - better for CLI/public clients
  generate_secret = false

  # Enable SRP auth for secure password-based authentication
  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_PASSWORD_AUTH"  # For CLI login
  ]

  # Token validity settings
  access_token_validity  = 1  # 1 hour
  id_token_validity      = 1  # 1 hour
  refresh_token_validity = 30 # 30 days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Prevent user existence errors for security
  prevent_user_existence_errors = "ENABLED"
}
