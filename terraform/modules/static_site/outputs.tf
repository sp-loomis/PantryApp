output "bucket_name" {
  description = "Name of the S3 bucket holding the SPA assets"
  value       = aws_s3_bucket.web.bucket
}

output "distribution_id" {
  description = "CloudFront distribution ID (for cache invalidation)"
  value       = aws_cloudfront_distribution.web.id
}

output "distribution_domain_name" {
  description = "Auto-generated CloudFront domain (e.g. d1234.cloudfront.net)"
  value       = aws_cloudfront_distribution.web.domain_name
}
