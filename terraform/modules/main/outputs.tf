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
