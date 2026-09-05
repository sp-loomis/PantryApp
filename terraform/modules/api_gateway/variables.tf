variable "api_name" {
  description = "Name of the REST API"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod). Also used as the deployment stage name."
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the Lambda function to integrate (for the invoke permission)"
  type        = string
}

variable "lambda_invoke_arn" {
  description = "Invoke ARN of the Lambda function (used by the AWS_PROXY integration)"
  type        = string
}

variable "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool backing the authorizer"
  type        = string
}

variable "allowed_origin" {
  description = <<-EOT
    Value for the Access-Control-Allow-Origin CORS header. Defaults to "*",
    which is safe here because the API authenticates via a Bearer token (not
    cookies). Tighten to the CloudFront/custom-domain origin once it is stable.
  EOT
  type        = string
  default     = "*"
}

variable "tags" {
  description = "Additional tags for API Gateway resources"
  type        = map(string)
  default     = {}
}
