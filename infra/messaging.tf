locals {
  sqs_queues = [
    "video-events",
    "video-status-events",
    "moderation-events",
    "search-moderation-events",
    "user-events",
  ]
}

resource "aws_sqs_queue" "dlq" {
  for_each = toset(local.sqs_queues)

  name = "${var.project_name}-${each.key}-dlq"
}

resource "aws_sqs_queue" "main" {
  for_each = toset(local.sqs_queues)

  name = "${var.project_name}-${each.key}"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = 3
  })
}
