# Agent Immune CI — AWS infrastructure (reconciled to match the deployed state).
#
# This file was rebuilt from terraform.tfstate so `terraform plan` is clean: it now
# describes exactly what is already deployed (2 DynamoDB tables, the transcripts S3
# bucket + ownership controls, and the Lambda IAM role/policy). The cockpit event
# table lives in cockpit.tf. A `terraform plan` should show only the Cockpit table as
# "to add" and 0 to change / 0 to destroy.

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

# --- DynamoDB: the CLI loop's attack library + defender history -------------

resource "aws_dynamodb_table" "attack_strategies" {
  name         = "AttackStrategies"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "attack_id"

  attribute {
    name = "attack_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "defender_versions" {
  name         = "DefenderVersions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "version"

  attribute {
    name = "version"
    type = "S"
  }
}

# --- S3: per-attempt transcripts -------------------------------------------

resource "aws_s3_bucket" "transcripts" {
  bucket = "agent-immune-ci-transcripts-${data.aws_caller_identity.current.account_id}"

  tags = {
    Project   = "agent-immune-ci"
    ManagedBy = "terraform"
  }
}

resource "aws_s3_bucket_ownership_controls" "transcripts" {
  bucket = aws_s3_bucket.transcripts.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# --- IAM: execution role for the (future) Buildkite/Lambda pipeline ---------
# Not used by the current app runtime (which runs under the agent-immune-dev user),
# but part of the deployed infra, so it's captured here to keep state consistent.

resource "aws_iam_role" "lambda_exec" {
  name = "agent-immune-ci-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = {
    Project   = "agent-immune-ci"
    ManagedBy = "terraform"
  }
}

resource "aws_iam_policy" "lambda_storage" {
  name = "agent-immune-ci-lambda-storage"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
        ]
        Resource = [
          aws_dynamodb_table.attack_strategies.arn,
          aws_dynamodb_table.defender_versions.arn,
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:PutObjectAcl"]
        Resource = "${aws_s3_bucket.transcripts.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = "*"
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_storage" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_storage.arn
}
