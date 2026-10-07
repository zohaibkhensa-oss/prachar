# CURV AI — AWS Organization / SCP Blocker Forensic Report

**Date:** 2026-08-03
**Type:** Inspection + diagnosis only. No AWS resources created, modified, or deleted. No terraform apply. No IAM/SCP/Organizations changes.

---

## 1. ROOT CAUSE

**The AWS account 046451669176 is a "project" member account created through the NEW AWS sign-up experience (AWS Builder ID + AWS Projects + AWS Settings), and AWS applies a managed region-restriction SCP that denies every regional API call outside the project's assigned region: `ap-southeast-2` (Sydney).**

CURV AI's Terraform is configured for `ap-south-1` (Mumbai). Every call Terraform makes to `ap-south-1` — including `s3:CreateBucket` and `dynamodb:DescribeTable` during backend bootstrap — hits an explicit Deny in the AWS-managed SCP.

This is not an IAM problem. `AccountFullAccessRole` already has effectively-administrative IAM permissions. **An SCP sets the maximum possible permissions for the member account — no identity-based policy inside the account, including full admin, can exceed it.** An explicit Deny in an SCP cannot be overridden by any Allow in the member account.

Evidence chain:

1. AWS documentation ("Managed policies for your organization", docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html) confirms: **new-experience project accounts receive AWS-managed SCPs that cannot be changed**, including a per-region `Deny` with `NotAction` covering only partitional/global services, conditioned on `aws:RequestedRegion`.
2. The observed errors match exactly: `s3:CreateBucket` (regional, not in the NotAction allowlist) and `dynamodb:DescribeTable` (regional) denied in `ap-south-1`, while `sts:*`/`iam:*` calls succeed (they're in the allowlist).
3. AWS documentation ("AWS Regions for your projects") confirms new-experience projects are provisioned in exactly ONE of `us-east-2`, `eu-north-1`, or `ap-southeast-2` based on contact address — yours is `ap-southeast-2` because the contact address is Asia Pacific.

---

## 2. VERIFIED AWS ACCOUNT TOPOLOGY

```
AWS Builder ID:  curvai.developer@gmail.com
                      │
                      ▼  (signs in at settings.aws.com / console via Identity Center)
AWS Organization:  o-egm6np5riv  (AWS-managed — created automatically by new sign-up)
                      │
        ┌─────────────┴──────────────┐
        ▼                            ▼
Management account              Member account (the "project")
333033669622                    046451669176  ← "Hold My Coffee" project
(managed via AWS Settings       Project region: ap-southeast-2
 only — no classic root         Contains: IAM user curv-admin,
 login exists)                  AccountFullAccessRole (Identity Center),
                                AWSManaged* roles (trusted by 333033669622)
IAM Identity Center instance: ssoins-7223c8f36dd25489
```

### Root-login confusion — resolved

`curvai.developer@gmail.com` is an **AWS Builder ID**, not a root account email. In the new AWS experience, the management account has **no traditional root user** reachable via the standard "Root user" sign-in form — it is managed exclusively through **https://settings.aws.com** using the Builder ID. That is why root login for 333033669622 reports "account does not exist." **The organization is not broken — this is the designed authentication model.**

The `AWSManagedAccountManagementAccessRole`-style roles in the member account, trusted by 333033669622, are AWS's own management-plane roles (used by AWS Settings to administer the account on your behalf). They are not intended for — and should not be used for — your deployment operations.

---

## 3. CURRENT AUTHENTICATED IDENTITY

From your brief:

```
arn:aws:sts::046451669176:assumed-role/AccountFullAccessRole/...
```

- **Type:** Assumed role — provisioned by IAM Identity Center (SSO) into the member account
- **Account:** 046451669176 (member/project account)
- **Not:** the management account, not an IAM user, not root

On this machine: **no active AWS credentials** (`aws sts get-caller-identity` → `NoCredentials`). An expired `aws login`/SSO session cache exists at `~/.aws/cli/cache/session.db` (from Jul 13; used Oct 5). Identity Center sessions expire — re-auth with `aws login` before running any checks yourself.

**Org-level permissions this identity lacks (per your brief):** `organizations:ListAccounts`, `organizations:ListPoliciesForTarget` — expected. Organization APIs live in the management account; member-account identities cannot query them.

---

## 4. SCP p-khyrr43x FINDINGS

**Current credentials cannot inspect SCP p-khyrr43x.** SCP content can only be read via `organizations:DescribePolicy` from the management account (or a delegated administrator), which this identity cannot reach.

However, based on the AWS-documented managed policy set for project accounts plus the exact observed denials, p-khyrr43x is almost certainly the **AWS-managed region-restriction SCP** (or a bundle containing it). The documented structure:

```json
{
  "Sid": "<RegionName>Partitional",      // one statement per DISALLOWED region
  "Effect": "Deny",
  "NotAction": [ /* ~70 global/partitional services:
      account:*, acm:*, cloudfront:*, cloudtrail:LookupEvents,
      cloudwatch (read-only subset), ec2:DescribeRegions, iam:*,
      identitystore:*, kms (grant/decrypt/describe/list),
      logs:*, organizations:*, pricing:*, route53:*, s3:GetBucketLocation,
      s3:ListAllMyBuckets, servicequotas:*, signin:*, sso:*, sts:*,
      support:*, waf:*, wafv2:*, budgets:*, ce:*, ... */ ],
  "Resource": "*",
  "Condition": { "StringEquals": { "aws:RequestedRegion": "<disallowed-region>" } }
}
```

Plus the immutable `BlockOrgEscape` + `ProtectManagedRoles` statements, and account-management/billing/notification denies (the latter group is removed by "Activate advanced features").

**Key consequence for CURV AI:** `acm:*` IS allowlisted for `us-east-1` (CloudFront certs work), and `route53:*`, `cloudfront:*`, `waf:*` are allowlisted globally. **All other regional services — S3 writes, DynamoDB, EC2/VPC, ECS, RDS, ElastiCache, ALB, Secrets Manager, KMS key creation, SQS — are denied in every region except `ap-southeast-2`.**

**Confidence:** High on the mechanism and structure (documented AWS-managed policy + error signature matches perfectly). Cannot confirm the policy ID ↔ document mapping or rule out additional SCPs without management-account access.

---

## 5. EXACT ACTIONS BLOCKED

Confirmed by your observed errors:

| Call | Resource | Region | Result |
|------|----------|--------|--------|
| `s3:CreateBucket` | `arn:aws:s3:::prachar-tfstate` | ap-south-1 | Denied (SCP) |
| `dynamodb:DescribeTable` | `arn:aws:dynamodb:ap-south-1:046451669176:table/prachar-tf-locks` | ap-south-1 | Denied (SCP) |

Logically also blocked (same mechanism — any regional call in ap-south-1):

`ec2:*` (VPC/subnets/SGs/NAT), `ecs:*`, `rds:*`, `elasticache:*`, `elasticloadbalancing:*`, `secretsmanager:*`, `dynamodb:*`, `s3` write actions, `sns:*`, regional `kms:*`, and every other regional service CURV AI's Terraform stack needs. **This blocks not just the backend bootstrap — it blocks the entire deployment in ap-south-1.**

---

## 6. WHY CURV AI CANNOT RUN terraform init/apply

1. `terraform init` → S3 backend tries to read/write `s3://prachar-tfstate` in `ap-south-1` → `s3:CreateBucket`/`GetObject` denied by SCP (bucket doesn't exist; can't be created there).
2. `terraform init` → state locking calls `dynamodb:DescribeTable`/`GetItem` on `prachar-tf-locks` in `ap-south-1` → denied.
3. Even with a pre-created backend, `terraform apply` → every regional resource (VPC, ECS, RDS, Redis, ALB, Secrets Manager, S3 storage bucket) targets `ap-south-1` → all denied.
4. **Only** the `us-east-1` ACM certs, Route53 records, and CloudFront distribution would succeed — everything else fails.

---

## 7. MINIMUM AWS CHANGE REQUIRED

### Path A — No organization change (works today)

**Deploy staging to `ap-southeast-2` instead of `ap-south-1`.** The managed SCP permits all regional services inside the project's assigned region. Required code change is one variable:

```hcl
# infra/terraform/terraform.tfvars.dev
aws_region = "ap-southeast-2"
```

…plus region-aware values (AZ names, AMI-independent Fargate so none needed) and the bootstrap commands run with `--region ap-southeast-2`. Everything else in the Terraform config is already parameterized by `var.aws_region`.

**Trade-off:** ~70–110 ms higher latency to India vs Mumbai. Acceptable for staging; suboptimal for production.

### Path B — Organization-level change (required for ap-south-1)

**"Activate advanced features" in AWS Settings** (https://settings.aws.com → sign in with Builder ID `curvai.developer@gmail.com` → Account/Organization section). This is the documented conversion path from the project model to a full AWS account/organization: it removes the AWS-managed region-restriction SCP and account-management denies, unlocks all regions, and gives real management-account access (billing, Organizations console, SCP management).

Per AWS docs, `BlockOrgEscape`/`ProtectManagedRoles` statements persist even after activation — that's correct and fine.

### Do NOT attempt

- Editing/detaching the SCP — member accounts cannot touch SCPs; the managed policy is not editable even from the management account in this model.
- Creating IAM users/policies in the member account hoping to bypass — SCP caps everything.
- Using the `AWSManaged*` roles trusted by 333033669622 — they're AWS-internal.

### Probable additional blocker (verify)

New-experience **Free Plan** accounts restrict usage to free-tier-eligible services and support spend limits only on paid plans. Even in `ap-southeast-2`, ECS Fargate + RDS + ALB + NAT Gateway are paid services and will likely be rejected or immediately bill-blocked on a free plan. Check **AWS Settings → Plan**: if "Free plan", upgrade is required regardless of region. (Unverified — flag for confirmation.)

---

## 8. WHETHER MANAGEMENT-ACCOUNT ACCESS IS REQUIRED

- **Path A (ap-southeast-2):** NO management-account access needed. Member-account Identity Center role can create resources in the assigned region (subject to plan limits).
- **Path B (ap-south-1):** YES — but accessed via **AWS Settings with the Builder ID**, not root login. There is no root password to find; the login model is Builder ID → settings.aws.com → management-account actions.

---

## 9. WHETHER IAM IDENTITY CENTER CAN SOLVE IT

**No — not by itself.** Identity Center is only the authentication layer (it already works: `AccountFullAccessRole` is provisioned through it, `aws login` uses `ssoins-7223c8f36dd25489`). It cannot loosen an SCP. What Identity Center *does* enable post-activation: assigning a permission set on the **management account** so you can manage SCPs/Organizations without root. That's the right long-term setup after activating advanced features.

---

## 10. WHETHER THE TERRAFORM BACKEND SHOULD CHANGE

**Yes — code-side recommendation, independent of the SCP issue.** The repo has Terraform `>= 1.6`, installed `1.16.4`. DynamoDB state locking is **deprecated** since Terraform 1.10 in favor of S3-native locking:

```hcl
backend "s3" {
  bucket       = "prachar-tfstate"
  key          = "terraform.tfstate"
  region       = "ap-southeast-2"   # or var-driven
  encrypt      = true
  use_lockfile = true               # replaces dynamodb_table entirely
}
```

Benefits: eliminates the DynamoDB table (one less bootstrap resource, one less service the SCP needs to allow), removes a deprecated dependency, zero functional loss. If adopted, `storage.tf`'s `aws_dynamodb_table.tf_locks` and the bootstrap doc's step 6 should be updated, and `terraform.tfstate.tflock` handling noted in `.gitignore`.

**This does NOT remove the SCP blocker for the S3 bucket itself — it only shrinks the bootstrap surface to S3 alone.**

### Local-state alternative (Phase 9)

Technically possible (remove/comment the `backend "s3"` block → local `terraform.tfstate`). Safe only as throwaway bootstrap — local state on a laptop is a single point of failure, can't be shared with CI (your `deploy.yml` runs terraform), leaks secrets into a plaintext file on disk, and diverges from the production architecture. **Not recommended; it delays rather than solves the problem.** Given Path A exists, unnecessary.

---

## 11. REGION FINDINGS

| Region | Role | Status under managed SCP |
|--------|------|--------------------------|
| `ap-southeast-2` | Project's assigned region (Sydney) | ✅ All services allowed |
| `ap-south-1` | CURV AI's configured Terraform region (Mumbai) | ❌ All regional services denied |
| `us-east-1` | CloudFront ACM certs (required by AWS) | ✅ `acm:*` explicitly allowlisted |
| Global | Route53, CloudFront, IAM, STS, WAFv2 metadata | ✅ Allowlisted |

**Recommendation:** CURV AI should ultimately be in `ap-south-1` (target market is India — Mumbai latency). For *staging*, `ap-southeast-2` is fully functional today. Decide: (a) stage in Sydney now, production in Mumbai after activating advanced features; or (b) activate advanced features first, then everything in Mumbai. The region difference is one tfvars variable — no architecture change either way.

`ap-southeast-2` in AWS Settings does not force your app region; it's simply the only regional region the SCP currently permits.

---

## 12. SAFE NEXT STEP

1. Sign in to **https://settings.aws.com** with `curvai.developer@gmail.com` (Builder ID — do NOT use the root-user sign-in form).
2. Check **Plan**: Free vs paid. If free → the full CURV AI stack cannot run regardless of region → activating advanced features (or paid plan) is mandatory.
3. Decide region strategy: Sydney staging now vs Mumbai after activation.
4. Re-auth CLI: `aws login` (Identity Center), then verify region behavior with read-only calls (below).
5. Once unblocked: bootstrap state backend in the chosen region, `terraform init` → `plan` → `apply` (staging tfvars).

---

## 13. COMMANDS THE USER SHOULD RUN NEXT

```bash
# Re-authenticate (Identity Center session expired locally)
aws login

# Verify identity lands in member account
aws sts get-caller-identity

# Prove the region hypothesis — read-only calls, no resource creation:
# Should DENY in ap-south-1 (SCP):
aws dynamodb list-tables --region ap-south-1

# Should SUCCEED in ap-southeast-2 (assigned region):
aws dynamodb list-tables --region ap-southeast-2
aws s3api list-buckets --region ap-southeast-2

# Confirm account/plan: browser only → https://settings.aws.com
# If going Path A: run bootstrap commands with --region ap-southeast-2
# If going Path B: AWS Settings → activate advanced features, then
#   re-run the ap-south-1 check — it should stop returning SCP denials.
```

---

## 14. COMMANDS THAT MUST NOT BE RUN

```bash
terraform apply                          # any target — provisions infra
terraform destroy                        # destructive
aws s3api create-bucket ... --region ap-south-1          # will deny; pointless retries
aws dynamodb create-table ... --region ap-south-1        # will deny
aws iam create-access-key                # long-lived creds — prohibited
aws organizations detach-policy / update-policy ...      # can't run anyway (member acct)
aws account close-account / organizations leave-organization  # explicitly SCP-denied; dangerous
aws iam * on arn:*:iam::*:role/managed/*   # protected managed roles — SCP-denied
```

---

## 15. CONFIDENCE / UNKNOWN ITEMS

**High confidence:**
- Root cause is the AWS-managed region-restriction SCP on the new-experience project account (documented policy + matching error signature).
- Management account has no classic root login; Builder ID + settings.aws.com is the control plane.
- `ap-southeast-2` is the only region where regional services are permitted.
- ACM/Route53/CloudFront/WAF work globally — consistent with the allowlist design.
- No repository changes are required to explain or unblock this — the repo is fine.

**Cannot verify without access (need management-account or delegated-admin creds):**
- Exact JSON of `p-khyrr43x` and its attachment point (account vs OU vs root).
- Whether additional SCPs exist beyond the documented managed set.
- Whether the account is on Free vs Paid plan (check AWS Settings → Plan) — affects whether paid services run even in `ap-southeast-2`.

**Unverified on this machine:** all AWS calls — no active credentials (`aws login` needed; cached SSO session expired). All AWS-side findings are derived from your reported errors + AWS documentation, not live calls.

---

## FINAL CONCLUSION

**"CURV AI CAN PROCEED WITHOUT CHANGING THE AWS ORGANIZATION" — if staging deploys to `ap-southeast-2`;**
**"CURV AI REQUIRES A MANAGEMENT-ACCOUNT/SCP CHANGE BEFORE AWS DEPLOYMENT" — if `ap-south-1` is mandatory.**

**Why:** The blocker is an AWS-managed region-guardrail SCP inherent to the new-sign-up project account. Nothing in the repo, IAM, or the member account can override it. The organization already permits everything CURV AI needs inside `ap-southeast-2` — so staging in Sydney works today with a one-line tfvars change. Deploying to Mumbai (`ap-south-1`) is impossible until someone with Builder-ID access activates advanced features at https://settings.aws.com, which lifts the region restriction — and, if the account is on the Free Plan, upgrading is required anyway because ECS/RDS/ALB/NAT are paid services in every region.

**Recommended sequence:** (1) check Plan in AWS Settings, (2) activate advanced features — you will need full-account control for production regardless, (3) keep `ap-south-1`, (4) optionally switch the backend to `use_lockfile`, (5) bootstrap + `terraform init`/`plan`/`apply` for staging.
