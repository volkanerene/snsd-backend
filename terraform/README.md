# Terraform Infrastructure for SnSD Backend

This directory contains the complete AWS infrastructure as code for the SnSD backend application.

## Quick Start

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply infrastructure
terraform apply

# Destroy infrastructure
terraform destroy
```

## Module Structure

```
terraform/
├── main.tf                 # Root module with all resources
├── variables.tf            # Input variables
├── outputs.tf              # Output values
├── terraform.tfvars        # Your values (git-ignored, create from example)
├── terraform.tfvars.example # Example values
└── modules/
    ├── vpc/               # VPC, subnets, NAT, IGW
    ├── ecs/               # ECS cluster, service, task definition
    ├── alb/               # Application Load Balancer
    ├── ecr/               # Docker image registry
    ├── s3/                # File storage bucket
    ├── secrets/           # Secrets Manager
    └── iam/               # IAM roles and policies
```

## Resources Created

### Networking (VPC Module)
- 1 VPC (10.0.0.0/16)
- 2 Public Subnets (for ALB)
- 2 Private Subnets (for ECS)
- 2 NAT Gateways (high availability)
- 1 Internet Gateway
- Route Tables
- VPC Endpoint for S3

### Compute (ECS Module)
- ECS Fargate Cluster
- ECS Service with auto-scaling (1-4 tasks)
- Task Definition
- CloudWatch Log Group
- Security Groups

### Load Balancing (ALB Module)
- Application Load Balancer
- Target Group
- HTTPS Listener (443)
- HTTP Listener (redirects to HTTPS)
- Security Group

### Container Registry (ECR Module)
- ECR Repository
- Lifecycle Policies
- Image Scanning

### Storage (S3 Module)
- S3 Bucket for file uploads
- S3 Bucket for access logs
- Versioning enabled
- Encryption at rest
- CORS configuration
- Lifecycle policies

### Secrets (Secrets Module)
- AWS Secrets Manager secret
- Stores all environment variables

### IAM (IAM Module)
- ECS Task Execution Role
- ECS Task Role
- Policies for S3, Secrets Manager, CloudWatch

### DNS (Main Module)
- Route53 A record for api.snsdconsultant.com

## Variables

See [variables.tf](./variables.tf) for all available variables.

Key variables to configure:

| Variable | Description | Default |
|----------|-------------|---------|
| aws_region | AWS region | us-east-1 |
| project_name | Project name | snsd |
| domain_name | Root domain | snsdconsultant.com |
| certificate_arn | ACM certificate ARN | Required |
| ecs_task_cpu | CPU units (256 = 0.25 vCPU) | 256 |
| ecs_task_memory | Memory in MB | 512 |

## Outputs

After applying, Terraform will output:

- `api_endpoint` - Your API URL (https://api.snsdconsultant.com)
- `ecr_repository_url` - Docker registry URL
- `s3_bucket_name` - File upload bucket name
- `alb_dns_name` - Load balancer DNS
- `vpc_id` - VPC identifier

View outputs:
```bash
terraform output
```

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **Terraform** installed (>= 1.0)
3. **AWS CLI** configured with credentials
4. **Route53 Hosted Zone** for your domain
5. **ACM Certificate** for HTTPS (in us-east-1)

## First-Time Setup

1. Create Terraform state backend:
   ```bash
   # Create S3 bucket
   aws s3api create-bucket --bucket snsd-terraform-state --region us-east-1

   # Enable versioning
   aws s3api put-bucket-versioning --bucket snsd-terraform-state \
     --versioning-configuration Status=Enabled

   # Create DynamoDB table for locking
   aws dynamodb create-table --table-name snsd-terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST --region us-east-1
   ```

2. Request ACM certificate:
   - Go to AWS Certificate Manager (us-east-1)
   - Request certificate for `*.snsdconsultant.com`
   - Use DNS validation
   - Add CNAME to Route53

3. Create your variables file:
   ```bash
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your values
   ```

## Deployment

```bash
# Initialize (first time only)
terraform init

# Plan (see what will be created)
terraform plan

# Apply (create resources)
terraform apply

# After apply, push Docker image
ECR_URL=$(terraform output -raw ecr_repository_url)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ECR_URL

docker build -t snsd-backend ..
docker tag snsd-backend:latest $ECR_URL:latest
docker push $ECR_URL:latest

# Update ECS service
aws ecs update-service \
  --cluster snsd-production-cluster \
  --service snsd-production-service \
  --force-new-deployment
```

## Cost Breakdown

Approximate monthly costs:

| Resource | Cost/Month |
|----------|------------|
| ECS Fargate (1 task) | $15-20 |
| ALB | $20 |
| NAT Gateway (2) | $64 |
| S3 Storage | ~$1 |
| Secrets Manager | $0.40 |
| CloudWatch Logs | $5 |
| Route53 | $0.50 |
| **Total** | **~$105-110** |

### Cost Optimization

To reduce NAT Gateway costs ($64/mo):
- Use single NAT Gateway instead of 2 (removes high availability)
- Or use public subnets for ECS (less secure)
- Or use VPC endpoints (reduces but doesn't eliminate NAT traffic)

## Updating Infrastructure

```bash
# Pull latest code
git pull

# See what changed
terraform plan

# Apply changes
terraform apply
```

## Destroying Infrastructure

```bash
# Preview what will be destroyed
terraform plan -destroy

# Destroy all resources
terraform destroy
```

**Warning**: This deletes everything! Make sure you have backups.

## Troubleshooting

### Issue: "Error acquiring the state lock"
**Solution**: Another process is using Terraform. Wait or:
```bash
terraform force-unlock LOCK_ID
```

### Issue: "Certificate ARN is invalid"
**Solution**: Certificate must be in us-east-1 region for ALB.

### Issue: "Route53 zone not found"
**Solution**: Ensure your domain has a hosted zone in Route53.

### Issue: "Insufficient capacity"
**Solution**: ECS Fargate capacity issue. Try different region or wait.

## State Management

Terraform state is stored in:
- **S3**: `s3://snsd-terraform-state/production/terraform.tfstate`
- **Lock**: DynamoDB table `snsd-terraform-locks`

Never edit state files manually!

## Security Notes

1. **Never commit** `terraform.tfvars` (contains secrets)
2. **Rotate secrets** regularly in AWS Secrets Manager
3. **Enable MFA** on AWS account
4. **Use least privilege** IAM policies
5. **Review** security groups regularly

## Module Documentation

Each module has its own README:
- [VPC Module](./modules/vpc/)
- [ECS Module](./modules/ecs/)
- [ALB Module](./modules/alb/)
- [S3 Module](./modules/s3/)
- [Secrets Module](./modules/secrets/)
- [IAM Module](./modules/iam/)
- [ECR Module](./modules/ecr/)

## References

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [Terraform Best Practices](https://www.terraform-best-practices.com/)
