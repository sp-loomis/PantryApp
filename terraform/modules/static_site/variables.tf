variable "bucket_name" {
  description = "Name of the S3 bucket that stores the built SPA assets"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "price_class" {
  description = "CloudFront price class (PriceClass_100 covers NA + EU)"
  type        = string
  default     = "PriceClass_100"
}

variable "tags" {
  description = "Additional tags for the static-site resources"
  type        = map(string)
  default     = {}
}
