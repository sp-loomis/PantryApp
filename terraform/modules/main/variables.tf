variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource naming"
  type        = string
}

variable "lambda_runtime" {
  description = "Lambda runtime version"
  type        = string
  default     = "python3.11"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory_size" {
  description = "Lambda function memory size in MB"
  type        = number
  default     = 256
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 14
}

variable "dynamodb_billing_mode" {
  description = "DynamoDB billing mode"
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "env_tags" {
  description = "Environment-specific tags"
  type        = map(string)
  default     = {}
}

variable "report_sweep_schedule" {
  description = "EventBridge schedule expression for the scheduled-report sweep. Fires at the top of every hour (cron minute 0) so firing aligns with the on-the-hour granularity of report schedules; reports fire within the hour they are configured for."
  type        = string
  default     = "cron(0 * * * ? *)"
}

variable "web_allowed_origin" {
  description = <<-EOT
    Origin allowed by CORS for the API (Access-Control-Allow-Origin). Defaults
    to "*", which is safe because the API authenticates via Bearer token, not
    cookies. Tighten to the CloudFront/custom-domain origin once stable.
  EOT
  type        = string
  default     = "*"
}

variable "slack_client_id" {
  description = <<-EOT
    Slack app OAuth client_id (public-ish; injected into the Lambda env). The
    matching client_secret is NOT a variable — it is stored in Secrets Manager
    and populated out-of-band. Empty disables the Slack OAuth start flow.
  EOT
  type        = string
  default     = ""
}

variable "slack_redirect_uri" {
  description = <<-EOT
    HTTPS OAuth redirect URI registered on the Slack app for this environment,
    e.g. https://<api-domain>/slack/oauth/callback. Must match a redirect URL
    allowlisted on the Slack app.
  EOT
  type        = string
  default     = ""
}
