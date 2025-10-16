# SnSD Backend - Quick Start Guide

## 🚀 Infrastructure is LIVE!

Your AWS infrastructure has been successfully deployed to **eu-central-1** (Frankfurt).

### 📡 Endpoints

- **API**: https://api.snsdconsultant.com
- **Health Check**: https://api.snsdconsultant.com/health
- **API Docs**: https://api.snsdconsultant.com/docs

### 🏗️ Deployed Resources

```
✅ VPC with public and private subnets
✅ Application Load Balancer with HTTPS
✅ ECS Fargate Cluster (snsd-production-cluster)
✅ ECR Repository (046621545065.dkr.ecr.eu-central-1.amazonaws.com/snsd-production)
✅ S3 Bucket for file uploads (snsd-file-uploads-production)
✅ Secrets Manager with Supabase credentials
✅ Route53 DNS (api.snsdconsultant.com)
✅ Auto-scaling (1-4 tasks)
✅ CloudWatch Logs
```

## 🎯 Next Steps

### 1. Add GitHub Secrets

Go to: **GitHub Repository → Settings → Secrets and variables → Actions → New repository secret**

Add these two secrets:

**Secret 1:**
- Name: `AWS_ACCESS_KEY_ID`
- Value: (Get from your AWS IAM user credentials)

**Secret 2:**
- Name: `AWS_SECRET_ACCESS_KEY`
- Value: (Get from your AWS IAM user credentials)

> 💡 **Note:** Use the credentials from your AWS IAM user for the Terraform/ECS deployment.
> The credentials should have permissions for ECR, ECS, and related services.

### 2. Push to Deploy

```bash
git add .
git commit -m "feat: add AWS infrastructure and deployment pipeline"
git push origin main
```

GitHub Actions will automatically:
1. Run tests
2. Build Docker image
3. Push to ECR
4. Deploy to ECS
5. Wait for deployment stability

**First deployment takes ~5-10 minutes**

### 3. Monitor Deployment

Watch the deployment in real-time:
- GitHub: Actions tab
- AWS Console: ECS → Clusters → snsd-production-cluster

### 4. Verify API

After deployment completes:

```bash
# Health check
curl https://api.snsdconsultant.com/health

# API documentation
open https://api.snsdconsultant.com/docs
```

## 📊 View Logs

```bash
# Via AWS CLI
aws logs tail /ecs/snsd-production --follow --region eu-central-1

# Or in AWS Console
CloudWatch → Log Groups → /ecs/snsd-production
```

## 🔄 Continuous Deployment

Every push to `main` branch will automatically deploy:

```bash
git add .
git commit -m "your changes"
git push origin main
```

## 🗂️ File Upload API

Your backend now includes comprehensive S3 file management at `/files/*`:

- Upload: `POST /files/upload`
- Download: `GET /files/download/{path}`
- List: `GET /files/list`
- Delete: `DELETE /files/delete/{path}`
- And more...

See full API docs at: https://api.snsdconsultant.com/docs

## 💰 Monthly Cost Estimate

Current configuration (eu-central-1):
- ECS Fargate: ~€15-20
- ALB: ~€20
- NAT Gateway: ~€60
- S3: ~€1
- Other: ~€5
- **Total: ~€100-110/month**

## 🛠️ Management Commands

```bash
# View infrastructure outputs
cd terraform
terraform output

# Scale ECS service manually
aws ecs update-service \
  --cluster snsd-production-cluster \
  --service snsd-production-service \
  --desired-count 2 \
  --region eu-central-1

# View service status
aws ecs describe-services \
  --cluster snsd-production-cluster \
  --services snsd-production-service \
  --region eu-central-1
```

## 📚 Documentation

- [Deployment Guide](./DEPLOYMENT.md) - Detailed deployment instructions
- [Infrastructure Summary](./INFRASTRUCTURE_SUMMARY.md) - Architecture overview
- [Terraform README](./terraform/README.md) - Infrastructure details

## 🎉 You're All Set!

Just add the GitHub secrets and push your code. The rest is automatic! 🚀
