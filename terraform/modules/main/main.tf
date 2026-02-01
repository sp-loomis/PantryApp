terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# DynamoDB table for pantry items
module "items_table" {
  source = "../dynamodb_table"

  table_name  = "${var.name_prefix}-table-items"
  environment = var.environment
  hash_key    = "item_id"
  range_key   = "created_at"

  attributes = [
    {
      name = "item_id"
      type = "S"
    },
    {
      name = "created_at"
      type = "S"
    },
    {
      name = "location_id"
      type = "S"
    },
    {
      name = "use_by_date"
      type = "S"
    },
    {
      name = "item_name"
      type = "S"
    }
  ]

  global_secondary_indexes = [
    {
      name            = "LocationIndex"
      hash_key        = "location_id"
      range_key       = "created_at"
      projection_type = "ALL"
    },
    {
      name            = "UseByDateIndex"
      hash_key        = "location_id"
      range_key       = "use_by_date"
      projection_type = "ALL"
    },
    {
      name            = "ItemNameIndex"
      hash_key        = "item_name"
      range_key       = "created_at"
      projection_type = "ALL"
    }
  ]

  billing_mode = var.dynamodb_billing_mode
  tags         = var.env_tags
}

# DynamoDB table for storage locations
module "locations_table" {
  source = "../dynamodb_table"

  table_name  = "${var.name_prefix}-table-locations"
  environment = var.environment
  hash_key    = "location_id"

  attributes = [
    {
      name = "location_id"
      type = "S"
    }
  ]

  billing_mode = var.dynamodb_billing_mode
  tags         = var.env_tags
}

# DynamoDB table for item-tag relationships
module "item_tags_table" {
  source = "../dynamodb_table"

  table_name  = "${var.name_prefix}-table-item-tags"
  environment = var.environment
  hash_key    = "tag_name"
  range_key   = "item_id"

  attributes = [
    {
      name = "tag_name"
      type = "S"
    },
    {
      name = "item_id"
      type = "S"
    }
  ]

  global_secondary_indexes = [
    {
      name            = "ItemTagsIndex"
      hash_key        = "item_id"
      range_key       = "tag_name"
      projection_type = "ALL"
    }
  ]

  billing_mode = var.dynamodb_billing_mode
  tags         = var.env_tags
}

# IAM role for Lambda function
data "aws_iam_policy_document" "lambda_dynamodb_policy" {
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem"
    ]
    resources = [
      module.items_table.table_arn,
      "${module.items_table.table_arn}/index/*",
      module.locations_table.table_arn,
      module.item_tags_table.table_arn,
      "${module.item_tags_table.table_arn}/index/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }
}

module "lambda_role" {
  source = "../iam_role"

  role_name           = "${var.name_prefix}-role-lambda-api"
  environment         = var.environment
  service_principals  = ["lambda.amazonaws.com"]
  managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]

  inline_policies = {
    DynamoDBAccess = data.aws_iam_policy_document.lambda_dynamodb_policy.json
  }

  tags = var.env_tags
}

# Lambda function for API
module "api_lambda" {
  source = "../lambda_function"

  function_name  = "${var.name_prefix}-lambda-core-api"
  environment    = var.environment
  source_dir     = "${path.module}/../../../backend"
  handler        = "app.lambda_handler"
  runtime        = var.lambda_runtime
  timeout        = var.lambda_timeout
  memory_size    = var.lambda_memory_size
  role_arn       = module.lambda_role.role_arn
  log_retention_days = var.log_retention_days

  environment_variables = {
    ITEMS_TABLE_NAME      = module.items_table.table_name
    LOCATIONS_TABLE_NAME  = module.locations_table.table_name
    ITEM_TAGS_TABLE_NAME  = module.item_tags_table.table_name
    ENVIRONMENT           = var.environment
  }

  tags = var.env_tags
}
