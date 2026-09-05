output "items_table_name" {
  description = "Name of the items DynamoDB table"
  value       = module.items_table.table_name
}

output "locations_table_name" {
  description = "Name of the locations DynamoDB table"
  value       = module.locations_table.table_name
}

output "item_tags_table_name" {
  description = "Name of the item tags DynamoDB table"
  value       = module.item_tags_table.table_name
}

output "lambda_function_name" {
  description = "Name of the API Lambda function"
  value       = module.api_lambda.function_name
}

output "lambda_function_arn" {
  description = "ARN of the API Lambda function"
  value       = module.api_lambda.function_arn
}

output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = module.cognito_pool.user_pool_id
}

output "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool"
  value       = module.cognito_pool.user_pool_arn
}

output "cognito_client_id" {
  description = "ID of the Cognito User Pool Client"
  value       = module.cognito_pool.user_pool_client_id
}

output "cognito_admin_group" {
  description = "Name of the Admin user group"
  value       = module.cognito_pool.admin_group_name
}

output "cognito_user_group" {
  description = "Name of the User group"
  value       = module.cognito_pool.user_group_name
}

# ============================================================================
# API Gateway
# ============================================================================
output "api_gateway_invoke_url" {
  description = "Base invoke URL of the deployed API (frontend VITE_API_GATEWAY_URL)"
  value       = module.api_gateway.invoke_url
}

# ============================================================================
# Static site (S3 + CloudFront)
# ============================================================================
output "web_bucket_name" {
  description = "S3 bucket that holds the built SPA assets"
  value       = module.static_site.bucket_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for cache invalidation)"
  value       = module.static_site.distribution_id
}

output "cloudfront_domain_name" {
  description = "Auto-generated CloudFront domain name"
  value       = module.static_site.distribution_domain_name
}

output "web_url" {
  description = "Public HTTPS URL of the deployed web app"
  value       = "https://${module.static_site.distribution_domain_name}"
}
