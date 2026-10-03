output "function_name" {
  value = aws_lambda_function.bot.function_name
}

output "region" {
  value = var.region
}

output "schedule_name" {
  value = aws_scheduler_schedule.bot.name
}

output "alarm_names" {
  value = local.alarm_names
}

output "mvp_table_name" {
  value = one(aws_dynamodb_table.posted[*].name)
}

output "state_table_name" {
  value = aws_dynamodb_table.state.name
}

output "bucket_name" {
  value = aws_s3_bucket.archive.bucket
}

output "alert_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
