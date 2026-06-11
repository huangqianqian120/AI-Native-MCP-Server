from __future__ import annotations
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"

    # App
    app_name: str = "AI-Native Mini Program Generator"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:3000"]

    # Generation
    output_dir: str = "/tmp/miniprogram-generator"
    max_zip_size_mb: int = 50
    cleanup_ttl_hours: int = 24

    # DB
    database_url: str = "sqlite+aiosqlite:///./generator.db"

    model_config = {"env_file": ".env", "env_prefix": ""}


settings = Settings()
