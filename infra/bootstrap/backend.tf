# Partial configuration: `make bootstrap-plan` supplies the rest with
#   terraform init -backend-config=backend.hcl
# (copy backend.hcl.example to backend.hcl first). The bootstrap stack has its own state key and its
# own data dir (TF_DATA_DIR=.terraform-bootstrap), so it can never be initialized against an
# environment's state. It is applied by hand with MFA, never by the pipeline, so the pipeline can't
# widen its own permissions.
terraform {
  backend "s3" {}
}
