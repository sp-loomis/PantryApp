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
