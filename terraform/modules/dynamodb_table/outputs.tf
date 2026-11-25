output "table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.table.name
}

output "table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.table.arn
}

output "table_id" {
  description = "ID of the DynamoDB table"
  value       = aws_dynamodb_table.table.id
}

output "stream_arn" {
  description = "ARN of the table's DynamoDB stream (null when stream_enabled is false)"
  value       = aws_dynamodb_table.table.stream_arn
}
