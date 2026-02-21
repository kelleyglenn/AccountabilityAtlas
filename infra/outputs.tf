output "ec2_public_ip" {
  description = "Elastic IP address of the EC2 instance"
  value       = aws_eip.ec2.public_ip
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_address" {
  description = "RDS PostgreSQL hostname (without port)"
  value       = aws_db_instance.postgres.address
}

output "ecr_registry" {
  description = "ECR registry URL"
  value       = split("/", aws_ecr_repository.services["user-service"].repository_url)[0]
}

output "ecr_repository_urls" {
  description = "ECR repository URLs by service"
  value       = { for k, v in aws_ecr_repository.services : k => v.repository_url }
}

output "sqs_queue_urls" {
  description = "SQS queue URLs by name"
  value       = { for k, v in aws_sqs_queue.main : k => v.url }
}

output "route53_nameservers" {
  description = "Route 53 nameservers (set these at your domain registrar)"
  value       = aws_route53_zone.main.name_servers
}

output "ec2_instance_id" {
  description = "EC2 instance ID (for start/stop scripts)"
  value       = aws_instance.app.id
}

output "rds_instance_id" {
  description = "RDS instance identifier (for start/stop scripts)"
  value       = aws_db_instance.postgres.identifier
}

output "ssh_command" {
  description = "SSH command to connect to the EC2 instance"
  value       = "ssh ec2-user@${aws_eip.ec2.public_ip}"
}
