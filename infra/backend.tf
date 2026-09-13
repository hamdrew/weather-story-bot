# Partial configuration: supply the rest with
#   terraform init -backend-config=backend.hcl
# (copy backend.hcl.example to backend.hcl first).
terraform {
  backend "s3" {}
}
