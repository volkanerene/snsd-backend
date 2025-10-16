terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Terraform state will be stored in S3
  backend "s3" {
    bucket         = "snsd-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "eu-central-1"
    encrypt        = true
    dynamodb_table = "snsd-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "SnSD"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Data source for Route53 zone
data "aws_route53_zone" "main" {
  name = var.domain_name
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
}

# ECR Module
module "ecr" {
  source = "./modules/ecr"

  project_name = var.project_name
  environment  = var.environment
}

# S3 Module for File Uploads
module "s3" {
  source = "./modules/s3"

  project_name = var.project_name
  environment  = var.environment
  bucket_name  = var.s3_bucket_name
}

# Secrets Manager Module
module "secrets" {
  source = "./modules/secrets"

  project_name          = var.project_name
  environment           = var.environment
  supabase_url          = var.supabase_url
  supabase_anon_key     = var.supabase_anon_key
  supabase_service_key  = var.supabase_service_role_key
  supabase_jwt_secret   = var.supabase_jwt_secret
}

# IAM Module
module "iam" {
  source = "./modules/iam"

  project_name     = var.project_name
  environment      = var.environment
  s3_bucket_arn    = module.s3.bucket_arn
  secrets_arn      = module.secrets.secret_arn
}

# Application Load Balancer Module
module "alb" {
  source = "./modules/alb"

  project_name    = var.project_name
  environment     = var.environment
  vpc_id          = module.vpc.vpc_id
  public_subnets  = module.vpc.public_subnets
  certificate_arn = var.certificate_arn
}

# ECS Module
module "ecs" {
  source = "./modules/ecs"

  project_name         = var.project_name
  environment          = var.environment
  vpc_id               = module.vpc.vpc_id
  private_subnets      = module.vpc.private_subnets
  ecr_repository_url   = module.ecr.repository_url
  task_execution_role_arn = module.iam.ecs_task_execution_role_arn
  task_role_arn        = module.iam.ecs_task_role_arn
  target_group_arn     = module.alb.target_group_arn
  alb_security_group_id = module.alb.alb_security_group_id
  secrets_arn          = module.secrets.secret_arn
  s3_bucket_name       = module.s3.bucket_name
  container_port       = var.container_port
  desired_count        = var.ecs_desired_count
  cpu                  = var.ecs_task_cpu
  memory               = var.ecs_task_memory
}

# Route53 Record for API subdomain
resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "api.${var.domain_name}"
  type    = "A"

  alias {
    name                   = module.alb.alb_dns_name
    zone_id                = module.alb.alb_zone_id
    evaluate_target_health = true
  }
}
