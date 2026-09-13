# Cognito User Pool for authentication
module "cognito_pool" {
  source = "../cognito_user_pool"

  pool_name   = "${var.name_prefix}-user-pool"
  client_name = "${var.name_prefix}-client"
  environment = var.environment
  tags        = var.env_tags
}

# DynamoDB table for pantry items (user-scoped)
module "items_table" {
  source = "../dynamodb_table"

  table_name  = "${var.name_prefix}-table-items"
  environment = var.environment
  hash_key    = "user_id"
  range_key   = "item_id"

  attributes = [
    {
      name = "user_id"
      type = "S"
    },
    {
      name = "item_id"
      type = "S"
    },
    {
      name = "location_id"
      type = "S"
    },
    {
      name = "use_by_date"
      type = "S"
    }
  ]

  global_secondary_indexes = [
    {
      name            = "LocationIndex"
      hash_key        = "user_id"
      range_key       = "location_id"
      projection_type = "ALL"
    },
    {
      name            = "UseByDateIndex"
      hash_key        = "user_id"
      range_key       = "use_by_date"
      projection_type = "ALL"
    }
  ]

  billing_mode = var.dynamodb_billing_mode
  tags         = var.env_tags
}

# DynamoDB table for storage locations (user-scoped)
module "locations_table" {
  source = "../dynamodb_table"

  table_name  = "${var.name_prefix}-table-locations"
  environment = var.environment
  hash_key    = "user_id"
  range_key   = "location_id"

  attributes = [
    {
      name = "user_id"
      type = "S"
    },
    {
      name = "location_id"
      type = "S"
    }
  ]

  billing_mode = var.dynamodb_billing_mode
  tags         = var.env_tags
}

# DynamoDB table for item-tag relationships (user-scoped)
module "item_tags_table" {
  source = "../dynamodb_table"

  table_name  = "${var.name_prefix}-table-item-tags"
  environment = var.environment
  hash_key    = "user_id"
  range_key   = "tag_item_composite"

  attributes = [
    {
      name = "user_id"
      type = "S"
    },
    {
      name = "tag_item_composite"
      type = "S"
    },
    {
      name = "tag_name"
      type = "S"
    }
  ]

  # TagIndex supports reverse lookups (items-by-tag) and listing all of a
  # user's tags. Tags are also denormalized onto each item record, so no
  # per-item index is needed to read an item's tags.
  global_secondary_indexes = [
    {
      name            = "TagIndex"
      hash_key        = "user_id"
      range_key       = "tag_name"
      projection_type = "ALL"
    }
  ]

  billing_mode = var.dynamodb_billing_mode
  tags         = var.env_tags
}

# DynamoDB table for tasks/chores (user-scoped)
module "tasks_table" {
  source = "../dynamodb_table"

  table_name  = "${var.name_prefix}-table-tasks"
  environment = var.environment
  hash_key    = "user_id"
  range_key   = "task_id"

  attributes = [
    {
      name = "user_id"
      type = "S"
    },
    {
      name = "task_id"
      type = "S"
    },
    {
      name = "due_date"
      type = "S"
    }
  ]

  # DueDateIndex is sparse: only one-shot tasks with a due_date appear, mirroring
  # the items' UseByDateIndex. Recurring tasks carry no due_date and are read via
  # the full user-partition query, then have their status computed on the fly.
  global_secondary_indexes = [
    {
      name            = "DueDateIndex"
      hash_key        = "user_id"
      range_key       = "due_date"
      projection_type = "ALL"
    }
  ]

  billing_mode = var.dynamodb_billing_mode
  tags         = var.env_tags
}

# DynamoDB table for scheduled-report configs (user-scoped)
module "reports_table" {
  source = "../dynamodb_table"

  table_name  = "${var.name_prefix}-table-reports"
  environment = var.environment
  hash_key    = "user_id"
  range_key   = "report_id"

  attributes = [
    {
      name = "user_id"
      type = "S"
    },
    {
      name = "report_id"
      type = "S"
    }
  ]

  billing_mode = var.dynamodb_billing_mode
  tags         = var.env_tags
}

# DynamoDB table for the notification/message log (user-scoped)
module "messages_table" {
  source = "../dynamodb_table"

  table_name  = "${var.name_prefix}-table-messages"
  environment = var.environment
  hash_key    = "user_id"
  range_key   = "message_id"

  attributes = [
    {
      name = "user_id"
      type = "S"
    },
    {
      name = "message_id"
      type = "S"
    },
    {
      name = "unread_sort"
      type = "S"
    }
  ]

  # UnreadIndex is sparse: only unread messages carry the unread_sort attribute
  # (their created_at), so only they appear in the index. Marking a message read
  # removes the attribute — and thus the row — from the index, giving the toolbar
  # an unread count/list without scanning the whole table.
  global_secondary_indexes = [
    {
      name            = "UnreadIndex"
      hash_key        = "user_id"
      range_key       = "unread_sort"
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
      "${module.item_tags_table.table_arn}/index/*",
      module.tasks_table.table_arn,
      "${module.tasks_table.table_arn}/index/*",
      module.reports_table.table_arn,
      module.messages_table.table_arn,
      "${module.messages_table.table_arn}/index/*"
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

# Get the current AWS region for constructing layer ARN
data "aws_region" "current" {}

# Lambda function for API
module "api_lambda" {
  source = "../lambda_function"

  function_name      = "${var.name_prefix}-lambda-core-api"
  environment        = var.environment
  source_dir         = "${path.module}/../../../backend"
  handler            = "app.lambda_handler"
  runtime            = var.lambda_runtime
  timeout            = var.lambda_timeout
  memory_size        = var.lambda_memory_size
  role_arn           = module.lambda_role.role_arn
  log_retention_days = var.log_retention_days

  # AWS Powertools Lambda Layer (Python 3.11)
  # ARN format: arn:aws:lambda:{region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python311-x86_64:3
  # Version 3 contains aws-lambda-powertools[all]==3.x
  layers = [
    "arn:aws:lambda:${data.aws_region.current.name}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python311-x86_64:3"
  ]

  environment_variables = {
    ITEMS_TABLE_NAME     = module.items_table.table_name
    LOCATIONS_TABLE_NAME = module.locations_table.table_name
    ITEM_TAGS_TABLE_NAME = module.item_tags_table.table_name
    TASKS_TABLE_NAME     = module.tasks_table.table_name
    REPORTS_TABLE_NAME   = module.reports_table.table_name
    MESSAGES_TABLE_NAME  = module.messages_table.table_name
    COGNITO_USER_POOL_ID = module.cognito_pool.user_pool_id
    COGNITO_CLIENT_ID    = module.cognito_pool.user_pool_client_id
    ENVIRONMENT          = var.environment
    # Origin echoed back in CORS headers on real (Lambda-generated) responses.
    # Kept in sync with the API Gateway CORS config below.
    ALLOWED_ORIGIN = var.web_allowed_origin
  }

  tags = var.env_tags
}

# ============================================================================
# Scheduled report sweep — EventBridge periodic trigger
#
# One cron rule fires the API Lambda on a fixed cadence. The handler detects the
# EventBridge event (source "aws.events") and runs run_report_sweep(), which
# generates every report whose next_run is due. A single rule scales to any
# number of reports (the sweep scans for due ones), so no per-report schedules.
# ============================================================================
resource "aws_cloudwatch_event_rule" "report_sweep" {
  name                = "${var.name_prefix}-rule-report-sweep"
  description         = "Periodic trigger for the scheduled-report sweep"
  schedule_expression = var.report_sweep_schedule
  tags                = var.env_tags
}

resource "aws_cloudwatch_event_target" "report_sweep" {
  rule = aws_cloudwatch_event_rule.report_sweep.name
  arn  = module.api_lambda.function_arn
}

resource "aws_lambda_permission" "report_sweep" {
  statement_id  = "AllowEventBridgeReportSweep"
  action        = "lambda:InvokeFunction"
  function_name = module.api_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.report_sweep.arn
}

# ============================================================================
# API Gateway — public HTTPS endpoint for the Lambda
# ============================================================================
module "api_gateway" {
  source = "../api_gateway"

  api_name              = "${var.name_prefix}-api"
  environment           = var.environment
  lambda_function_name  = module.api_lambda.function_name
  lambda_invoke_arn     = module.api_lambda.invoke_arn
  cognito_user_pool_arn = module.cognito_pool.user_pool_arn
  allowed_origin        = var.web_allowed_origin
  tags                  = var.env_tags
}

# ============================================================================
# Static site — S3 + CloudFront hosting for the React SPA
# ============================================================================
module "static_site" {
  source = "../static_site"

  bucket_name = "${var.name_prefix}-web"
  environment = var.environment
  tags        = var.env_tags
}
