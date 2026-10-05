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

The state bucket is intentionally **not** declared as a Terraform
resource. Terraform cannot safely manage the bucket that stores its own
state — creating it requires the bucket to already exist, and destroying
it would orphan the state. It is created out-of-band (steps above) and
managed manually.

If the bucket was previously imported into state, remove those state
entries so Terraform forgets the resource without touching AWS:

```bash
terraform state rm aws_s3_bucket.tfstate \
  aws_s3_bucket_versioning.tfstate \
  aws_s3_bucket_server_side_encryption_configuration.tfstate \
  aws_s3_bucket_public_access_block.tfstate
```
