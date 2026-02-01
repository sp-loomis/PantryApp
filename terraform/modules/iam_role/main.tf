terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = var.service_principals
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "role" {
  name               = var.role_name
  assume_role_policy = data.aws_iam_policy_document.assume_role.json

  tags = merge(
    {
      Name        = var.role_name
      Environment = var.environment
      Project     = "pantry"
    },
    var.tags
  )
}

resource "aws_iam_role_policy_attachment" "policy_attachments" {
  for_each = toset(var.managed_policy_arns)

  role       = aws_iam_role.role.name
  policy_arn = each.value
}

resource "aws_iam_role_policy" "inline_policies" {
  for_each = var.inline_policies

  name   = each.key
  role   = aws_iam_role.role.id
  policy = each.value
}
