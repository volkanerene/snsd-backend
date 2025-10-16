# SnSD Backend Deployment Guide

This guide will help you deploy the SnSD backend to AWS using Terraform and GitHub Actions.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS Cloud                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              Route53 (DNS)                             │ │
│  │        api.snsdconsultant.com                          │ │
│  └─────────────────┬──────────────────────────────────────┘ │
│                    │                                         │
│  ┌─────────────────▼──────────────────────────────────────┐ │
│  │     Application Load Balancer (ALB)                    │ │
│  │              HTTPS (443)                               │ │
│  └─────────────────┬──────────────────────────────────────┘ │
│                    │                                         │
│  ┌─────────────────▼──────────────────────────────────────┐ │
│  │           ECS Fargate Service                          │ │
│  │      (Auto-scaling: 1-4 tasks)                         │ │
│  │                                                         │ │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                │ │
│  │  │  Task 1 │  │  Task 2 │  │  Task N │                │ │
│  │  │FastAPI  │  │FastAPI  │  │FastAPI  │                │ │
│  │  │  :8000  │  │  :8000  │  │  :8000  │                │ │
│  │  └─────────┘  └─────────┘  └─────────┘                │ │
│  └────────────────┬──────────┬──────────────────────────┬─┘ │
│                   │          │                          │    │
│  ┌────────────────▼──┐  ┌───▼──────┐  ┌───────────────▼──┐ │
│  │  Secrets Manager  │  │  S3      │  │  CloudWatch      │ │
│  │  (Env Variables)  │  │  Bucket  │  │  Logs            │ │
│  └───────────────────┘  └──────────┘  └──────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘

        │
        │ (External Connection)
        ▼
┌──────────────────┐
│    Supabase      │
│   (Database)     │
└──────────────────┘
```

## Prerequisites

### 1. AWS Account Setup

1. Create an AWS account if you don't have one
2. Create an IAM user with programmatic access
3. Attach the following policies:
   - AmazonEC2FullAccess
   - AmazonECS_FullAccess
   - AmazonVPCFullAccess
   - AmazonS3FullAccess
   - SecretsManagerReadWrite
   - AmazonRoute53FullAccess
   - ElasticLoadBalancingFullAccess
   - IAMFullAccess
   - CloudWatchLogsFullAccess

4. Save the Access Key ID and Secret Access Key

### 2. Domain Setup

1. Purchase domain `snsdconsultant.com` from Route53 (or transfer existing domain)
2. Create a hosted zone in Route53 (this is automatic if you purchase from Route53)
3. Note the hosted zone ID

### 3. SSL Certificate Setup

1. Go to AWS Certificate Manager (ACM) in **us-east-1** region
2. Request a public certificate
3. Add domain names:
   - `snsdconsultant.com`
   - `*.snsdconsultant.com` (wildcard for subdomains)
4. Choose DNS validation
5. Add the CNAME records to Route53 (ACM will provide these)
6. Wait for certificate to be issued (usually takes 5-30 minutes)
7. Copy the certificate ARN

### 4. Terraform State Backend (One-time setup)

Create S3 bucket and DynamoDB table for Terraform state:

```bash
# Create S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket snsd-terraform-state \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket snsd-terraform-state \
  --versioning-configuration Status=Enabled

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name snsd-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

## Deployment Steps

### Step 1: Configure Terraform Variables

1. Copy the example variables file:
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   ```

2. Edit `terraform.tfvars` with your actual values:
   ```hcl
   certificate_arn = "arn:aws:acm:us-east-1:123456789:certificate/your-cert-id"
   supabase_url = "your-actual-supabase-url"
   supabase_anon_key = "your-actual-anon-key"
   supabase_service_role_key = "your-actual-service-role-key"
   supabase_jwt_secret = "your-actual-jwt-secret"
   ```

   **IMPORTANT**: Never commit `terraform.tfvars` to Git! It contains secrets.

### Step 2: Deploy Infrastructure with Terraform

```bash
# Navigate to terraform directory
cd terraform

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Apply the configuration
terraform apply

# When prompted, type 'yes' to confirm
```

This will create:
- VPC with public and private subnets
- NAT Gateways for private subnet internet access
- Application Load Balancer with HTTPS
- ECS Cluster and Service
- ECR Repository for Docker images
- S3 Bucket for file uploads
- Secrets Manager for environment variables
- IAM roles and policies
- CloudWatch log groups
- Route53 DNS record (api.snsdconsultant.com)

**Note**: The deployment will take approximately 10-15 minutes.

### Step 3: Build and Push Initial Docker Image

After Terraform completes, you'll have an ECR repository. Now push your first image:

```bash
# Get ECR login command
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Get the ECR repository URL from Terraform output
terraform output ecr_repository_url

# Build the Docker image
docker build -t snsd-backend .

# Tag the image
docker tag snsd-backend:latest YOUR_ECR_REPO_URL:latest

# Push to ECR
docker push YOUR_ECR_REPO_URL:latest
```

### Step 4: Update ECS Service

```bash
# Force a new deployment with the Docker image
aws ecs update-service \
  --cluster snsd-production-cluster \
  --service snsd-production-service \
  --force-new-deployment \
  --region us-east-1
```

### Step 5: Configure GitHub Actions

1. Go to your GitHub repository settings
2. Navigate to **Secrets and variables** → **Actions**
3. Add the following secrets:
   - `AWS_ACCESS_KEY_ID`: Your AWS access key
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key

4. Push to main branch to trigger automatic deployment:
   ```bash
   git add .
   git commit -m "feat: add AWS infrastructure and deployment"
   git push origin main
   ```

### Step 6: Verify Deployment

1. Check ECS service status:
   ```bash
   aws ecs describe-services \
     --cluster snsd-production-cluster \
     --services snsd-production-service \
     --region us-east-1
   ```

2. Check task health:
   ```bash
   aws ecs list-tasks \
     --cluster snsd-production-cluster \
     --service-name snsd-production-service \
     --region us-east-1
   ```

3. View logs:
   ```bash
   aws logs tail /ecs/snsd-production --follow --region us-east-1
   ```

4. Test the API:
   ```bash
   curl https://api.snsdconsultant.com/health
   ```

## Cost Optimization

### Current Configuration Costs (Approximate Monthly)

- **ECS Fargate**: ~$15-20/month (1 task, 0.25 vCPU, 0.5 GB RAM)
- **ALB**: ~$20/month
- **NAT Gateway**: ~$32/month (the most expensive component)
- **S3**: Pay per use (minimal for low traffic)
- **Route53**: ~$0.50/month
- **Secrets Manager**: ~$0.40/month
- **CloudWatch Logs**: ~$5/month (with 30-day retention)

**Total**: ~$70-80/month for minimal traffic

### Cost Reduction Options

1. **Remove NAT Gateway** (saves ~$32/month):
   - ECS tasks won't be able to pull from ECR or access internet
   - Not recommended for production

2. **Use EC2 instead of Fargate** (saves ~$10/month):
   - More management overhead
   - Need to handle scaling yourself

3. **Reduce log retention**:
   - Change from 30 days to 7 days in `terraform/main.tf`

## File Upload Features

The backend now includes comprehensive S3 file management:

### Available Endpoints

- `POST /files/upload` - Upload single file
- `POST /files/upload-multiple` - Upload multiple files
- `GET /files/download/{file_path}` - Download file
- `DELETE /files/delete/{file_path}` - Delete file
- `POST /files/delete-multiple` - Delete multiple files
- `GET /files/list` - List files in folder
- `GET /files/metadata/{file_path}` - Get file metadata
- `POST /files/folder/create` - Create folder
- `DELETE /files/folder/delete` - Delete folder
- `POST /files/copy` - Copy file
- `POST /files/move` - Move file
- `GET /files/presigned-url/{file_path}` - Get temporary download URL
- `POST /files/presigned-upload` - Get presigned upload URL for direct browser upload

### File Organization

Files are automatically organized by tenant:
```
s3://snsd-file-uploads-production/
  └── tenants/
      └── {tenant_id}/
          ├── documents/
          ├── images/
          └── files...
```

## Scaling Configuration

### Auto-scaling is already configured:

- **Minimum tasks**: 1
- **Maximum tasks**: 4
- **Scale up**: When CPU > 70% or Memory > 80%
- **Scale down**: When CPU < 70% and Memory < 80%

### To change scaling parameters:

Edit `terraform/modules/ecs/main.tf`:

```hcl
resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = 10  # Increase maximum tasks
  min_capacity       = 2   # Increase minimum tasks
  ...
}
```

## Monitoring and Debugging

### View Logs
```bash
# Tail logs in real-time
aws logs tail /ecs/snsd-production --follow

# Filter by error
aws logs tail /ecs/snsd-production --follow --filter-pattern "ERROR"

# View specific time range
aws logs tail /ecs/snsd-production --since 1h
```

### Check Service Health
```bash
# Get service details
aws ecs describe-services \
  --cluster snsd-production-cluster \
  --services snsd-production-service

# Get task details
aws ecs describe-tasks \
  --cluster snsd-production-cluster \
  --tasks TASK_ARN
```

### CloudWatch Metrics

View metrics in AWS Console:
1. Go to CloudWatch
2. Select **Metrics** → **ECS**
3. View CPU, Memory, and Request metrics

## Updating the Application

### Automatic Updates (via GitHub Actions)

Simply push to main branch:
```bash
git add .
git commit -m "feat: your changes"
git push origin main
```

GitHub Actions will:
1. Run tests
2. Build Docker image
3. Push to ECR
4. Update ECS service
5. Wait for deployment to stabilize

### Manual Updates

```bash
# Build and push new image
docker build -t snsd-backend .
docker tag snsd-backend:latest YOUR_ECR_REPO_URL:latest
docker push YOUR_ECR_REPO_URL:latest

# Force new deployment
aws ecs update-service \
  --cluster snsd-production-cluster \
  --service snsd-production-service \
  --force-new-deployment
```

## Rollback

If deployment fails, ECS will automatically roll back due to circuit breaker configuration.

To manually rollback to previous task definition:

```bash
# List task definitions
aws ecs list-task-definitions --family-prefix snsd-production

# Update service to previous version
aws ecs update-service \
  --cluster snsd-production-cluster \
  --service snsd-production-service \
  --task-definition snsd-production:PREVIOUS_VERSION
```

## Security Best Practices

1. **Secrets**: All secrets are stored in AWS Secrets Manager, never in code
2. **HTTPS**: All traffic is encrypted via ALB SSL/TLS
3. **Private Subnets**: ECS tasks run in private subnets with no direct internet access
4. **IAM Roles**: Tasks use minimal required permissions
5. **S3**: Bucket is private, uses encryption at rest
6. **VPC**: Network isolation with security groups

## Troubleshooting

### Issue: ECS tasks keep stopping

**Solution**: Check CloudWatch logs for errors:
```bash
aws logs tail /ecs/snsd-production --follow
```

Common causes:
- Missing environment variables
- Database connection issues
- Health check failures

### Issue: Can't access API

**Solution**:
1. Check Route53 DNS propagation (can take up to 48 hours)
2. Verify ALB target health:
   ```bash
   aws elbv2 describe-target-health \
     --target-group-arn YOUR_TARGET_GROUP_ARN
   ```

### Issue: 502 Bad Gateway

**Solution**: ECS tasks are unhealthy
- Check if application is listening on port 8000
- Verify `/health` endpoint exists and returns 200

### Issue: GitHub Actions deployment fails

**Solution**:
1. Verify AWS credentials in GitHub secrets
2. Check if ECR repository exists
3. Ensure IAM user has required permissions

## Cleanup

To destroy all resources and avoid charges:

```bash
cd terraform
terraform destroy
```

**Warning**: This will delete all resources including S3 buckets (with files) and databases!

## Support

For issues:
1. Check CloudWatch Logs
2. Review ECS task events
3. Verify security group rules
4. Check IAM permissions

## Next Steps

1. **Configure Amplify for Frontend**:
   - Connect GitHub repository
   - Add domain snsdconsultant.com
   - Set build settings
   - Deploy frontend

2. **Set up monitoring alerts**:
   - SNS topics for critical errors
   - Email notifications for failed deployments
   - Slack integration for deployment status

3. **Add backup strategy**:
   - S3 versioning (already enabled)
   - Database backups via Supabase
   - Disaster recovery plan

4. **Performance optimization**:
   - CloudFront CDN for static assets
   - ElastiCache for caching
   - Database query optimization

## References

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
