# Terraform State Backend Bootstrap

The Terraform configuration uses an S3 backend with **S3-native state locking**
(`use_lockfile = true`, available in Terraform >= 1.10 — no DynamoDB table
required).

The S3 state bucket **must be created manually** before running
`terraform init`.

## Why manual bootstrap?

The S3 state bucket is referenced in the backend configuration
(`versions.tf`), but Terraform cannot create its own backend before
initializing — a chicken-and-egg problem. The bucket must exist before
`terraform init` can succeed.

## Important: region

The state backend is pinned to **ap-southeast-2 (Sydney)** in
`versions.tf`. The bucket must be created in that region.

Note: an AWS-managed service control policy on this account currently
restricts regional services to the project's assigned region
(ap-southeast-2). Do not attempt to create the bucket in ap-south-1 —
it will be denied by SCP.

## Bootstrap steps (run once, manually)

```bash
# 1. Set your AWS region (must match versions.tf)
export AWS_REGION=ap-southeast-2

# 2. Create the S3 bucket for state storage
aws s3api create-bucket \
  --bucket prachar-tfstate \
  --region ap-southeast-2 \
  --create-bucket-configuration LocationConstraint=ap-southeast-2

# 3. Enable versioning on the state bucket (critical for rollback)
aws s3api put-bucket-versioning \
  --bucket prachar-tfstate \
  --versioning-configuration Status=Enabled

# 4. Enable encryption on the state bucket
aws s3api put-bucket-encryption \
  --bucket prachar-tfstate \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# 5. Block public access on the state bucket
aws s3api put-public-access-block \
  --bucket prachar-tfstate \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# 6. Verify
aws s3 ls s3://prachar-tfstate
```

State locking is handled by a `.tflock` object in the same bucket — no
DynamoDB table is needed.

## After bootstrap

Once the bucket exists, run:

```bash
cd infra/terraform
terraform init
terraform plan
```

## Note

The `storage.tf` file also defines `aws_s3_bucket.tfstate`. This is
**for documentation purposes** — it shows what the bootstrap resource
looks like. If you run `terraform apply` after bootstrapping, Terraform
will attempt to manage it. To avoid conflicts, either:

1. Import the manually-created resource:
   `terraform import aws_s3_bucket.tfstate prachar-tfstate`
2. Or remove it from `storage.tf` after bootstrap (it's already created)

Option 1 is recommended — it brings the bootstrap resource under
Terraform management.
