variable "role_name" {
  description = "Name of the IAM role"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "service_principals" {
  description = "List of service principals that can assume the role"
  type        = list(string)
  default     = ["lambda.amazonaws.com"]
}

variable "managed_policy_arns" {
  description = "List of ARNs of managed policies to attach"
  type        = list(string)
  default     = []
}

variable "inline_policies" {
  description = "Map of inline policy names to policy documents"
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Additional tags for the IAM role"
  type        = map(string)
  default     = {}
}
