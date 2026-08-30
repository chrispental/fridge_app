"""Application configuration, loaded from environment variables / `.env`."""
from pydantic_settings import BaseSettings, SettingsConfigDict

# The single user in local (no-auth) mode. UUID-shaped so `user_id` columns hold the
# same kind of value in both modes. Changing it after first run orphans existing rows.
DEFAULT_LOCAL_USER_ID = "00000000-0000-0000-0000-000000000001"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenRouter / AI
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_vision_model: str = "openai/gpt-4o-mini"
    openrouter_meal_model: str = "anthropic/claude-sonnet-4.6"
    ai_request_timeout: float = 90.0

    # Brave Search (recipe images, source links, weather snippets, delivery lookup)
    brave_api_key: str = ""
    brave_base_url: str = "https://api.search.brave.com/res/v1"
    brave_request_timeout: float = 10.0
    brave_country: str = "US"
    weather_cache_ttl: int = 3600  # seconds to cache a location's weather lookup

    # Storage
    database_url: str = "sqlite:////app/data/fridge.db"
    upload_dir: str = "/app/data/uploads"
    db_pool_size: int = 5  # non-SQLite only
    db_max_overflow: int = 5

    # Supabase (cloud mode). Leave SUPABASE_URL empty for single-user local mode.
    supabase_url: str = ""  # e.g. https://<ref>.supabase.co
    supabase_secret_key: str = ""  # sb_secret_... — backend only, never shipped to the browser
    supabase_jwt_audience: str = "authenticated"
    supabase_storage_bucket: str = "fridge-photos"
    blob_backend: str = "auto"  # auto | local | supabase
    local_user_id: str = DEFAULT_LOCAL_USER_ID

    # Image handling
    max_image_dim: int = 1024

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def auth_enabled(self) -> bool:
        """Cloud mode: Supabase Auth required on every API request."""
        return bool(self.supabase_url)

    @property
    def supabase_base(self) -> str:
        return self.supabase_url.rstrip("/")

    @property
    def supabase_issuer(self) -> str:
        return f"{self.supabase_base}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_base}/auth/v1/.well-known/jwks.json"


settings = Settings()
