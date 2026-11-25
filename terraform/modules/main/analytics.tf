# ============================================================================
# Analytics tier — ledger stream -> S3 (JSONL) -> Glue -> Athena
#
# The ledger table's DynamoDB stream (NEW_IMAGE) triggers a consumer Lambda that
# writes each event to S3 as newline JSON, partitioned by event date
# (dt=YYYY-MM-DD). A Glue table with partition projection exposes it to Athena
# for SQL history/analytics. This tier is query-on-demand and scales to zero:
# the consumer is idle-free, Athena/Glue bill only per query/scan, S3 is cheap.
#
# Athena is for analysis ONLY — live SPA reads never touch it.
# ============================================================================

# --- S3 bucket for the JSONL event lake + Athena query results --------------
resource "aws_s3_bucket" "analytics" {
  bucket = "${var.name_prefix}-analytics"
  tags   = var.env_tags
}

resource "aws_s3_bucket_public_access_block" "analytics" {
  bucket                  = aws_s3_bucket.analytics.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "analytics" {
  bucket = aws_s3_bucket.analytics.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# --- Stream-consumer Lambda --------------------------------------------------
data "aws_iam_policy_document" "analytics_consumer_policy" {
  # Read the ledger stream.
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:GetRecords",
      "dynamodb:GetShardIterator",
      "dynamodb:DescribeStream",
      "dynamodb:ListStreams",
    ]
    resources = [
      module.ledger_table.stream_arn,
      "${module.ledger_table.stream_arn}/*",
    ]
  }

  # Write JSONL objects to the analytics bucket.
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.analytics.arn}/*"]
  }
}

module "analytics_consumer_role" {
  source = "../iam_role"

  role_name           = "${var.name_prefix}-role-analytics-consumer"
  environment         = var.environment
  service_principals  = ["lambda.amazonaws.com"]
  managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]

  inline_policies = {
    LedgerStreamToS3 = data.aws_iam_policy_document.analytics_consumer_policy.json
  }

  tags = var.env_tags
}

module "analytics_consumer_lambda" {
  source = "../lambda_function"

  function_name      = "${var.name_prefix}-lambda-analytics-consumer"
  environment        = var.environment
  source_dir         = "${path.module}/../../../analytics/consumer"
  handler            = "handler.handler"
  runtime            = var.lambda_runtime
  timeout            = 60
  memory_size        = 256
  role_arn           = module.analytics_consumer_role.role_arn
  log_retention_days = var.log_retention_days

  environment_variables = {
    ANALYTICS_BUCKET = aws_s3_bucket.analytics.bucket
    ANALYTICS_PREFIX = "events"
  }

  tags = var.env_tags
}

# Wire the ledger stream to the consumer.
resource "aws_lambda_event_source_mapping" "ledger_to_consumer" {
  event_source_arn                   = module.ledger_table.stream_arn
  function_name                      = module.analytics_consumer_lambda.function_arn
  starting_position                  = "LATEST"
  batch_size                         = 100
  maximum_batching_window_in_seconds = 30
  # Append-only inserts; a poison record shouldn't wedge the shard forever.
  maximum_retry_attempts         = 3
  bisect_batch_on_function_error = true
}

# --- Glue catalog + Athena ---------------------------------------------------
resource "aws_glue_catalog_database" "analytics" {
  name = replace("${var.name_prefix}_ledger", "-", "_")
}

# Events table over the JSONL lake, with partition projection on dt (no crawler).
# payload is a nested object per event type; it's left out of the explicit schema
# so the JSON SerDe tolerates it — query it with Athena's json_extract on the raw
# row, or add typed columns later as needs firm up.
resource "aws_glue_catalog_table" "events" {
  name          = "events"
  database_name = aws_glue_catalog_database.analytics.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification                = "json"
    "projection.enabled"          = "true"
    "projection.dt.type"          = "date"
    "projection.dt.range"         = "2024-01-01,NOW"
    "projection.dt.format"        = "yyyy-MM-dd"
    "projection.dt.interval"      = "1"
    "projection.dt.interval.unit" = "DAYS"
    "storage.location.template"   = "s3://${aws_s3_bucket.analytics.bucket}/events/dt=$${dt}"
    "EXTERNAL"                    = "TRUE"
  }

  partition_keys {
    name = "dt"
    type = "date"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.analytics.bucket}/events/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.openx.data.jsonserde.JsonSerDe"
      parameters = {
        "ignore.malformed.json" = "true"
      }
    }

    columns {
      name = "event_id"
      type = "string"
    }
    columns {
      name = "occurred_at"
      type = "string"
    }
    columns {
      name = "user_id"
      type = "string"
    }
    columns {
      name = "entity_type"
      type = "string"
    }
    columns {
      name = "entity_id"
      type = "string"
    }
    columns {
      name = "event_type"
      type = "string"
    }
  }
}

resource "aws_athena_workgroup" "analytics" {
  name = "${var.name_prefix}-analytics"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = false

    result_configuration {
      output_location = "s3://${aws_s3_bucket.analytics.bucket}/athena-results/"
    }
  }

  tags = var.env_tags
}
