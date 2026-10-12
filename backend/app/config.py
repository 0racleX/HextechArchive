from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwks_url: str = ""
    ollama_base_url: str = "http://localhost:11434"
    chat_model: str = "qwen2.5:3b"
    embed_model: str = "nomic-embed-text"
    similarity_threshold: float = 0.55
    top_k: int = 5
    max_upload_mb: int = 10
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
