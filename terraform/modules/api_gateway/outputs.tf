output "invoke_url" {
  description = "Base invoke URL for the deployed stage (e.g. https://{id}.execute-api.{region}.amazonaws.com/{stage})"
  value       = aws_api_gateway_stage.stage.invoke_url
}

output "rest_api_id" {
  description = "ID of the REST API"
  value       = aws_api_gateway_rest_api.api.id
}

output "stage_name" {
  description = "Name of the deployed stage"
  value       = aws_api_gateway_stage.stage.stage_name
}

output "execution_arn" {
  description = "Execution ARN of the REST API (for constructing method ARNs)"
  value       = aws_api_gateway_rest_api.api.execution_arn
}
