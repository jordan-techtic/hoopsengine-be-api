from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Hoops Engine API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    DATABASE_URL: str

    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    REMEMBER_ME_TOKEN_EXPIRE_HOURS: int = 720
    RESET_TOKEN_EXPIRE_HOURS: int = 1
    RESET_TOKEN_HASH_ALGORITHM: str = "sha256"
    BCRYPT_ROUNDS: int = 12

    SUPERADMIN_EMAIL: str = "admin.hoopsengine@yopmail.com"
    SUPERADMIN_PASSWORD: str
    SUPERADMIN_FIRST_NAME: str = "Super"
    SUPERADMIN_LAST_NAME: str = "Admin"

    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = ""
    SENDGRID_FROM_NAME: str = "Hoops Engine"
    FRONTEND_URL: str = "http://localhost:3000"
    RESET_PASSWORD_URL: str = "http://localhost:5173/reset-password"
    EMAIL_VERIFICATION_OTP_EXPIRE_MINUTES: int = 15
    EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS: int = 60
    PASSWORD_RECOVERY_OTP_EXPIRE_MINUTES: int = 1440
    PLAYER_RESET_PASSWORD_URL: str = "http://localhost:5173/player/reset-password"
    SUPPORT_REQUEST_UPLOAD_DIR: str = "storage/support_requests"
    SUPPORT_REQUEST_MAX_ATTACHMENT_SIZE_MB: int = 5
    PROFILE_IMAGE_UPLOAD_DIR: str = "storage/profile_images"
    PROFILE_IMAGE_MAX_SIZE_MB: int = 2

    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_MIGRATION_PRORATION_BEHAVIOR: str = "none"

    SUPPORT_CONTACT_EMAIL: str = "support@hoopsengine.com"
    SUPPORT_CONTACT_PHONE: str = "+15558392001"
    SUPPORT_INQUIRY_SUBJECTS: list[str] = [
        "Technical Issue",
        "Billing Question",
        "Account Help",
        "Feature Request",
        "Other",
    ]
    SUPPORT_MESSAGE_MAX_LENGTH: int = 500
    SUPPORT_DUPLICATE_WINDOW_SECONDS: int = 300
    HELP_SUPPORT_ARTICLES: list[dict[str, str]] = []
    FAQ_INTRO_TITLE: str = "How can we help you?"
    FAQ_INTRO_DESCRIPTION: str = (
        "Find quick answers to common questions about managing drills, "
        "subscriptions, and team sessions."
    )


settings = Settings()
