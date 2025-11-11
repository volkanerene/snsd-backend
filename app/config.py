from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str | None = None  # JWT Secret for token verification
    OPENAI_API_KEY: str | None = None
    HEYGEN_FALLBACK_API_KEY: str | None = None
    API_URL: str = "https://api.snsdconsultant.com"  # Public API URL for webhooks
    API_BASE_URL: str = "https://api.snsdconsultant.com"  # API base URL for N8N callbacks
    N8N_WEBHOOK_URL: str | None = None  # N8N webhook for FRM32 AI scoring
    PORT: int | None = 8000
    DASHBOARD_BASE_URL: str = "https://app.snsdconsultant.com"

    # Brevo Email Service (SMTP)
    BREVO_SMTP_HOST: str | None = None
    BREVO_SMTP_PORT: int | None = 587
    BREVO_SMTP_USER: str | None = None
    BREVO_SMTP_PASSWORD: str | None = None
    BREVO_FROM_EMAIL: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
