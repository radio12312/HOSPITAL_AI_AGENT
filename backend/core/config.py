"""Application settings, loaded from environment variables and the repo-level .env file."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
# Generated CSVs and trained models; overridable so Docker can keep them on a volume.
DATA_DIR = Path(os.getenv("HWA_DATA_DIR", BACKEND_DIR / "data"))
ARTIFACT_DIR = Path(os.getenv("HWA_ARTIFACT_DIR", BACKEND_DIR / "ml" / "artifacts"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
                                      env_file_encoding="utf-8", extra="ignore")

    # --- infrastructure ---
    database_url: str = "postgresql+psycopg://hospital:hospital@localhost:5432/hospital"
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8080"
    log_level: str = "INFO"

    # --- auth ---
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # --- LLM (NVIDIA API catalog) ---
    nvidia_api_key: str | None = None
    nvidia_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nvidia_fallback_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nvidia_disable_thinking: bool = True
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1200
    llm_max_retries: int = 4
    llm_cache_enabled: bool = True
    llm_cache_dir: str = ".cache/llm"

    # --- agent workflow ---
    reviewer_mode: Literal["naive", "fixed"] = "fixed"
    max_revisions: int = 2

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cache_path(self) -> Path:
        p = Path(self.llm_cache_dir)
        return p if p.is_absolute() else REPO_DIR / p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
