from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    jwt_secret: str  # required: app refuses to start without it
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    ai_api_key: str = ""
    ai_model: str = "gemini-3.8-flash"
    ai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    upload_dir: str = "uploads"
    max_upload_mb: int = 10
    max_ocr_pages: int = 20


settings = Settings()
