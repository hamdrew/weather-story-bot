output "artifacts_bucket" {
  description = "Holds the Lambda zips and saved production plans. The main stack's artifacts_bucket variable."
  value       = aws_s3_bucket.artifacts.bucket
}

output "boundary_arns" {
  description = "Each environment's permissions boundary. The main stack's permissions_boundary_arn variable."
  value       = local.boundary_arns
}

output "ci_role_arns" {
  description = "The roles the workflows assume."
  value       = { for k, r in aws_iam_role.ci : k => r.arn }
}
