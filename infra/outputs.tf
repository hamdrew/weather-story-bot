output "function_name" {
  value = aws_lambda_function.bot.function_name
}

output "table_name" {
  value = aws_dynamodb_table.posted.name
}

output "bucket_name" {
  value = aws_s3_bucket.archive.bucket
}

output "alert_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
