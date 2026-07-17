# Cockpit event store — a single DynamoDB table holding every cockpit collection
# (pk = collection name e.g. "events"/"attack_attempts", sk = zero-padded index).
# Used when STORAGE_BACKEND=dynamodb so the live UI reads/writes its run, events,
# attempts, bundles, metrics, and history on AWS instead of local JSON.
#
# NOTE: main.tf is currently out of sync with the deployed state (terraform.tfstate).
# To create THIS table without touching the drifted resources, either use the AWS CLI
# create-table command (see the app's run instructions) or a scoped apply:
#     terraform apply -target=aws_dynamodb_table.cockpit -var=aws_region=us-east-1

resource "aws_dynamodb_table" "cockpit" {
  name         = "Cockpit"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  tags = {
    Project   = "agent-immune-ci"
    ManagedBy = "terraform"
  }
}
