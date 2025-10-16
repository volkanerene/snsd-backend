# AWS Secrets Manager for sensitive environment variables
resource "aws_secretsmanager_secret" "app" {
  name                    = "${var.project_name}-${var.environment}-secrets"
  description             = "Application secrets for ${var.project_name}"
  recovery_window_in_days = 7

  tags = {
    Name        = "${var.project_name}-${var.environment}-secrets"
    Environment = var.environment
  }
}

# Store secrets as JSON
resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    SUPABASE_URL              = var.supabase_url
    SUPABASE_ANON_KEY         = var.supabase_anon_key
    SUPABASE_SERVICE_ROLE_KEY = var.supabase_service_key
    SUPABASE_JWT_SECRET       = var.supabase_jwt_secret
    PORT                      = "8000"
  })
}

# Secret rotation configuration (optional - for future use)
# resource "aws_secretsmanager_secret_rotation" "app" {
#   secret_id           = aws_secretsmanager_secret.app.id
#   rotation_lambda_arn = aws_lambda_function.rotation.arn
#
#   rotation_rules {
#     automatically_after_days = 30
#   }
# }
