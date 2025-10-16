# SnSD Backend Infrastructure Summary

## 🎯 Project Overview

Complete AWS infrastructure for SnSD Backend with:
- **Domain**: api.snsdconsultant.com
- **Platform**: AWS ECS Fargate
- **Framework**: FastAPI (Python 3.12)
- **Database**: Supabase (External)
- **Storage**: AWS S3
- **CI/CD**: GitHub Actions
- **IaC**: Terraform

## 📁 Project Structure

```
snsd-backend/
├── app/
│   ├── routers/
│   │   └── files.py              # NEW: S3 file management API
│   ├── utils/
│   │   └── s3_client.py          # NEW: S3 helper utilities
│   └── main.py                   # Updated with files router
│
├── terraform/                    # NEW: Complete infrastructure
│   ├── main.tf                   # Root configuration
│   ├── variables.tf              # Input variables
│   ├── outputs.tf                # Output values
│   ├── terraform.tfvars.example  # Example configuration
│   └── modules/
│       ├── vpc/                  # Network infrastructure
│       ├── ecs/                  # Container service
│       ├── alb/                  # Load balancer
│       ├── ecr/                  # Docker registry
│       ├── s3/                   # File storage
│       ├── secrets/              # Secrets management
│       └── iam/                  # Permissions
│
├── .github/
│   └── workflows/
│       └── deploy.yml            # NEW: CI/CD pipeline
│
├── DEPLOYMENT.md                 # NEW: Deployment guide
├── requirements.txt              # Updated with boto3
├── .gitignore                    # Updated for Terraform
└── Dockerfile                    # Existing
```

## 🏗️ Infrastructure Components

### 1. Networking (VPC)
- **VPC**: 10.0.0.0/16
- **Public Subnets**: 2 (for ALB)
- **Private Subnets**: 2 (for ECS)
- **NAT Gateways**: 2 (high availability)
- **Internet Gateway**: 1
- **VPC Endpoint**: S3 (cost optimization)

### 2. Compute (ECS Fargate)
- **Cluster**: snsd-production-cluster
- **Service**: snsd-production-service
- **Task CPU**: 256 (0.25 vCPU)
- **Task Memory**: 512 MB
- **Auto-scaling**: 1-4 tasks
- **Triggers**: CPU > 70%, Memory > 80%

### 3. Load Balancing
- **Type**: Application Load Balancer
- **HTTPS**: Port 443 (SSL/TLS)
- **HTTP**: Port 80 (redirects to HTTPS)
- **Health Check**: /health endpoint
- **Target Group**: ECS tasks on port 8000

### 4. Container Registry (ECR)
- **Repository**: snsd-production
- **Image Scanning**: Enabled
- **Lifecycle**: Keep last 10 tagged images
- **Auto-cleanup**: Untagged images after 7 days

### 5. Storage (S3)
- **Primary Bucket**: snsd-file-uploads-production
- **Logging Bucket**: snsd-file-uploads-production-logs
- **Features**:
  - Versioning enabled
  - Encryption at rest (AES256)
  - CORS configured
  - Lifecycle policies (IA after 30 days, Glacier after 90)
  - Access logging

### 6. Secrets Management
- **Service**: AWS Secrets Manager
- **Secret**: snsd-production-secrets
- **Contents**:
  - SUPABASE_URL
  - SUPABASE_ANON_KEY
  - SUPABASE_SERVICE_ROLE_KEY
  - SUPABASE_JWT_SECRET
  - PORT

### 7. DNS & Domain
- **Service**: Route53
- **Record**: api.snsdconsultant.com
- **Type**: A (Alias to ALB)
- **SSL**: ACM Certificate (*.snsdconsultant.com)

### 8. Monitoring
- **Service**: CloudWatch
- **Log Group**: /ecs/snsd-production
- **Retention**: 30 days
- **Metrics**: CPU, Memory, Request Count
- **Alarms**: High response time, Unhealthy hosts

### 9. IAM Roles
- **ECS Task Execution Role**: Pull images, read secrets
- **ECS Task Role**: S3 access, CloudWatch logs
- **Policies**: Least privilege principle

## 🔐 Security Features

1. **Network Isolation**: ECS tasks in private subnets
2. **Encryption**:
   - In transit (HTTPS/TLS)
   - At rest (S3, Secrets Manager)
3. **Secrets**: Never in code, stored in Secrets Manager
4. **S3 Access**: Private bucket, presigned URLs
5. **Security Groups**: Minimal required ports
6. **IAM**: Least privilege policies

## 💰 Cost Estimate

| Service | Monthly Cost |
|---------|--------------|
| ECS Fargate (1 task) | $15-20 |
| Application Load Balancer | $20 |
| NAT Gateway (2) | $64 |
| S3 Storage + Requests | $1-5 |
| Secrets Manager | $0.40 |
| CloudWatch Logs | $5 |
| Route53 | $0.50 |
| **Total** | **~$105-115** |

### Cost Reduction Options:
- Use 1 NAT Gateway instead of 2: Save $32/month
- Reduce log retention to 7 days: Save $3/month
- Use smaller ECS task size: Save $5/month

## 🚀 Deployment Steps

### One-Time Setup

1. **Create Terraform State Backend**:
   ```bash
   aws s3api create-bucket --bucket snsd-terraform-state --region us-east-1
   aws dynamodb create-table --table-name snsd-terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST --region us-east-1
   ```

2. **Request SSL Certificate**:
   - AWS Certificate Manager (us-east-1)
   - Request for `*.snsdconsultant.com`
   - Validate via DNS

3. **Configure Variables**:
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   # Edit with your values
   ```

### Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### Push Docker Image

```bash
# Get ECR URL
ECR_URL=$(terraform output -raw ecr_repository_url)

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ECR_URL

# Build and push
docker build -t snsd-backend .
docker tag snsd-backend:latest $ECR_URL:latest
docker push $ECR_URL:latest

# Update ECS
aws ecs update-service \
  --cluster snsd-production-cluster \
  --service snsd-production-service \
  --force-new-deployment
```

### Setup GitHub Actions

1. Add secrets to GitHub repository:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

2. Push to main branch to trigger deployment

## 📡 S3 File Management API

### New Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/files/upload` | POST | Upload single file |
| `/files/upload-multiple` | POST | Upload multiple files |
| `/files/download/{path}` | GET | Download file |
| `/files/delete/{path}` | DELETE | Delete file |
| `/files/delete-multiple` | POST | Delete multiple files |
| `/files/list` | GET | List files in folder |
| `/files/metadata/{path}` | GET | Get file metadata |
| `/files/folder/create` | POST | Create folder |
| `/files/folder/delete` | DELETE | Delete folder |
| `/files/copy` | POST | Copy file |
| `/files/move` | POST | Move file |
| `/files/presigned-url/{path}` | GET | Get download URL |
| `/files/presigned-upload` | POST | Get upload URL |

### File Organization

Files are automatically organized by tenant:
```
s3://snsd-file-uploads-production/
  └── tenants/
      └── {tenant_id}/
          ├── documents/
          │   └── contract.pdf
          ├── images/
          │   └── logo.png
          └── data/
              └── export.csv
```

### Example Usage

```python
# Upload file
files = {"file": open("document.pdf", "rb")}
response = requests.post(
    "https://api.snsdconsultant.com/files/upload?folder=documents",
    files=files,
    headers={"Authorization": f"Bearer {token}"}
)

# Download file
response = requests.get(
    "https://api.snsdconsultant.com/files/download/documents/contract.pdf",
    headers={"Authorization": f"Bearer {token}"}
)

# Get presigned URL (for frontend direct upload)
response = requests.post(
    "https://api.snsdconsultant.com/files/presigned-upload?file_path=images/photo.jpg",
    headers={"Authorization": f"Bearer {token}"}
)
presigned = response.json()
# Use presigned["url"] and presigned["fields"] for browser upload
```

## 🔄 CI/CD Pipeline

GitHub Actions workflow automatically:

1. **On Push to Main**:
   - Run tests
   - Build Docker image
   - Push to ECR
   - Update ECS service
   - Wait for stable deployment

2. **On Failure**:
   - ECS circuit breaker rolls back automatically
   - Notifications in GitHub Actions

## 📊 Monitoring

### View Logs
```bash
aws logs tail /ecs/snsd-production --follow
```

### Check Service Health
```bash
aws ecs describe-services \
  --cluster snsd-production-cluster \
  --services snsd-production-service
```

### Test API
```bash
curl https://api.snsdconsultant.com/health
curl https://api.snsdconsultant.com/docs
```

## 🎛️ Scaling

### Current Auto-scaling:
- **Min**: 1 task
- **Max**: 4 tasks
- **Scale Out**: CPU > 70% or Memory > 80%
- **Scale In**: CPU < 70% and Memory < 80%
- **Cooldown**: 60s (out), 300s (in)

### Manual Scaling:
```bash
aws ecs update-service \
  --cluster snsd-production-cluster \
  --service snsd-production-service \
  --desired-count 2
```

## 🧹 Cleanup

To destroy all resources:
```bash
cd terraform
terraform destroy
```

**Warning**: This will delete everything including S3 files!

## 📚 Documentation

- [DEPLOYMENT.md](./DEPLOYMENT.md) - Detailed deployment guide
- [terraform/README.md](./terraform/README.md) - Terraform documentation
- [app/routers/files.py](./app/routers/files.py) - S3 API documentation

## ✅ Checklist

Before going to production:

- [ ] Domain purchased and hosted in Route53
- [ ] SSL certificate issued and validated
- [ ] Terraform state backend created
- [ ] AWS credentials configured
- [ ] GitHub secrets added
- [ ] First Docker image pushed
- [ ] ECS service healthy
- [ ] API accessible via https://api.snsdconsultant.com
- [ ] S3 file upload tested
- [ ] Monitoring alarms configured
- [ ] Backup strategy defined
- [ ] Cost alerts set up

## 🎉 Next Steps

1. **Frontend Deployment**:
   - Connect GitHub to AWS Amplify
   - Add domain snsdconsultant.com
   - Configure build settings
   - Deploy frontend

2. **Production Hardening**:
   - Set up CloudWatch alarms with SNS
   - Configure backup retention
   - Enable AWS WAF on ALB
   - Set up budget alerts

3. **Performance Optimization**:
   - Add CloudFront CDN
   - Implement caching strategy
   - Database query optimization
   - Load testing

## 📞 Support

For issues or questions:
1. Check CloudWatch Logs
2. Review ECS task events
3. Verify security groups
4. Check IAM permissions

---

**Created**: 2025-10-16
**Infrastructure as Code**: Terraform v1.0+
**Cloud Provider**: AWS
**Region**: us-east-1
