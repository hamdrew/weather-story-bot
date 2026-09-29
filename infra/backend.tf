# Partial configuration: `make plan ENV=<env>` supplies the rest with
#   terraform init -backend-config=envs/<env>.backend.hcl
# (copy envs/<env>.backend.hcl.example to envs/<env>.backend.hcl first). Each environment has its
# own state key, and its own data dir (TF_DATA_DIR=.terraform-<env>), so a staging plan can never
# be initialized against production's state.
terraform {
  backend "s3" {}
}
