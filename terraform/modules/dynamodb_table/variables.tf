variable "table_name" {
  description = "Name of the DynamoDB table"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "billing_mode" {
  description = "DynamoDB billing mode (PROVISIONED or PAY_PER_REQUEST)"
  type        = string
  default     = "PAY_PER_REQUEST"
}

variable "hash_key" {
  description = "Hash key (partition key) for the table"
  type        = string
}

variable "range_key" {
  description = "Range key (sort key) for the table"
  type        = string
  default     = null
}

variable "attributes" {
  description = "List of attribute definitions for the table"
  type = list(object({
    name = string
    type = string
  }))
}

variable "global_secondary_indexes" {
  description = "List of global secondary indexes"
  type = list(object({
    name               = string
    hash_key           = string
    range_key          = optional(string)
    projection_type    = string
    non_key_attributes = optional(list(string))
  }))
  default = []
}

variable "ttl_enabled" {
  description = "Enable TTL for the table"
  type        = bool
  default     = false
}

variable "ttl_attribute_name" {
  description = "Attribute name for TTL"
  type        = string
  default     = ""
}

variable "point_in_time_recovery" {
  description = "Enable point-in-time recovery"
  type        = bool
  default     = true
}

variable "encryption_enabled" {
  description = "Enable server-side encryption"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags for the table"
  type        = map(string)
  default     = {}
}
