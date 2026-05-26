"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
Secrets are never logged or exposed via API responses.
"""
from functools import lru_cache
from typing import Optional, Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== App Metadata =====
    app_name: str = Field(default="AI Risk Assessment Agent")
    app_version: str = Field(default="0.6.0")
    environment: Literal["development", "staging", "production"] = Field(
        default="development"
    )
    debug: bool = Field(default=False)

    # ===== API =====
    api_v1_prefix: str = Field(default="/api/v1")
    cors_origins: list[str] = Field(default=["*"])

    # ===== OpenAI / LLM =====
    # SecretStr ensures the key is never accidentally printed/logged.
    openai_api_key: Optional[SecretStr] = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")
    openai_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    openai_max_tokens: int = Field(default=800, ge=50, le=4000)
    openai_timeout_seconds: int = Field(default=30, ge=5, le=120)

    # ===== Feature Flags =====
    enable_ai_analysis: bool = Field(default=True)

    # ===== Logging =====
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # ===== Helper Properties =====
    @property
    def has_openai_key(self) -> bool:
        """Check if a usable OpenAI key is configured (no secret exposure)."""
        if self.openai_api_key is None:
            return False
        key_value = self.openai_api_key.get_secret_value()
        return bool(key_value and key_value.strip() and key_value != "your-key-here")

    @property
    def ai_enabled(self) -> bool:
        """AI analysis runs only if feature flag is on AND key is present."""
        return self.enable_ai_analysis and self.has_openai_key

    def get_openai_key(self) -> Optional[str]:
        """Safe accessor — only used inside services, never returned via API."""
        if self.openai_api_key is None:
            return None
        return self.openai_api_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton (avoids re-reading .env per request)."""
    return Settings()