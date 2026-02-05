output "user_pool_id" {
  description = "The ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.pool.id
}

output "user_pool_arn" {
  description = "The ARN of the Cognito User Pool"
  value       = aws_cognito_user_pool.pool.arn
}

output "user_pool_endpoint" {
  description = "The endpoint of the Cognito User Pool"
  value       = aws_cognito_user_pool.pool.endpoint
}

output "user_pool_client_id" {
  description = "The ID of the Cognito User Pool Client"
  value       = aws_cognito_user_pool_client.client.id
}

output "admin_group_name" {
  description = "The name of the Admin user group"
  value       = aws_cognito_user_group.admin.name
}

output "user_group_name" {
  description = "The name of the User group"
  value       = aws_cognito_user_group.user.name
}
