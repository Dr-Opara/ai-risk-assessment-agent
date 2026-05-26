"""
Application configuration using Pydantic Settings.

Loads from environment variables and/or .env file.
Follows 12-factor app methodology — never hardcode secrets.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== Application Metadata =====
    APP_NAME: str = "AI Risk Assessment Agent"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = (
        "Enterprise agent for assessing prompt injection, privacy, "
        "hallucination, drift, and compliance risks in AI systems."
    )

    # ===== Environment =====
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # ===== API Server =====
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # ===== CORS =====
    # Comma-separated list in .env, e.g. CORS_ORIGINS=http://localhost:8501,https://app.example.com
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:8501"])

    # ===== OpenAI / LLM =====
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key (required)")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_MAX_TOKENS: int = 1500
    OPENAI_TIMEOUT_SECONDS: int = 30
    OPENAI_MAX_RETRIES: int = 2

    # ===== Risk Assessment Tunables =====
    RISK_SCORE_THRESHOLD_HIGH: float = 0.75
    RISK_SCORE_THRESHOLD_MEDIUM: float = 0.40
    MAX_INPUT_CHARS: int = 20_000  # guardrail for intake payloads

    # ===== Validators =====
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v):
        """Allow CORS_ORIGINS as comma-separated string in .env."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("OPENAI_TEMPERATURE")
    @classmethod
    def _validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("OPENAI_TEMPERATURE must be between 0.0 and 2.0")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached settings instance.

    Using lru_cache ensures Settings() is instantiated only once
    per process — important for performance and consistency.
    Use FastAPI's Depends(get_settings) to inject into routes.
    """
    return Settings()


# Convenience export — for non-DI usage (scripts, agents)
settings = get_settings()