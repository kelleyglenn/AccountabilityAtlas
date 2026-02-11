#!/bin/bash
# Initialize SQS queues for local development
# This script runs when LocalStack is ready

set -e

ENDPOINT="http://localhost:4566"

echo "Creating SQS queues..."

# Video events queue
awslocal sqs create-queue --queue-name video-events
awslocal sqs create-queue --queue-name video-events-dlq

# Moderation events queue
awslocal sqs create-queue --queue-name moderation-events
awslocal sqs create-queue --queue-name moderation-events-dlq

# User events queue
awslocal sqs create-queue --queue-name user-events
awslocal sqs create-queue --queue-name user-events-dlq

echo "SQS queues created:"
awslocal sqs list-queues

echo "LocalStack SQS initialization complete!"
