resource "aws_sns_topic" "alarms" {
  name = "${var.project_name}-alarms"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "ec2_high_cpu" {
  alarm_name          = "${var.project_name}-ec2-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 70
  alarm_description   = "EC2 CPU >70% for 10 minutes"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = { InstanceId = aws_instance.app.id }
}

resource "aws_cloudwatch_metric_alarm" "ec2_high_memory" {
  alarm_name          = "${var.project_name}-ec2-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "mem_used_percent"
  namespace           = "AccountabilityAtlas"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "EC2 memory >80% for 10 minutes"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = { InstanceId = aws_instance.app.id }
}

resource "aws_cloudwatch_metric_alarm" "ec2_low_disk" {
  alarm_name          = "${var.project_name}-ec2-low-disk"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "disk_used_percent"
  namespace           = "AccountabilityAtlas"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "EC2 disk usage >85%"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    InstanceId = aws_instance.app.id
    path       = "/"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_high_cpu" {
  alarm_name          = "${var.project_name}-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU >80% for 10 minutes"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = { DBInstanceIdentifier = aws_db_instance.postgres.identifier }
}

resource "aws_cloudwatch_metric_alarm" "ec2_status_check" {
  alarm_name          = "${var.project_name}-ec2-status-check"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "EC2 status check failed for 5 minutes"
  alarm_actions       = [aws_sns_topic.alarms.arn, "arn:aws:automate:${var.region}:ec2:recover"]

  dimensions = { InstanceId = aws_instance.app.id }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/accountabilityatlas/prod"
  retention_in_days = 30
}
