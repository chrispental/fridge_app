"""Application configuration, loaded from environment variables / `.env`."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenRouter / AI
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_vision_model: str = "openai/gpt-4o-mini"
    openrouter_meal_model: str = "anthropic/claude-sonnet-4.6"
    ai_request_timeout: float = 90.0

    # Storage
    database_url: str = "sqlite:////app/data/fridge.db"
    upload_dir: str = "/app/data/uploads"

    # Image handling
    max_image_dim: int = 1024

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
