"""Application settings (pydantic-settings) + secrets file load."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env_files() -> None:
    """Load repo `.env`, then optional external secrets (override)."""
    import os

    repo_env = REPO_ROOT / ".env"
    if repo_env.is_file():
        load_dotenv(repo_env, override=False)

    secrets = os.environ.get("AGENT_SECRETS_FILE", "").strip()
    if secrets:
        path = Path(secrets).expanduser()
        if path.is_file():
            load_dotenv(path, override=True)


_load_env_files()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    agent_host: str = "127.0.0.1"
    agent_port: int = 8100

    algocraft_api_url: str = "http://127.0.0.1:8080"
    algocraft_user: str = "agent_bot"
    algocraft_pass: str = "changeme"

    agent_secrets_file: str | None = None

    agent_default_llm_provider: str | None = None
    agent_default_llm_model: str | None = None

    agent_max_iterations: int = 3
    agent_max_compile_attempts: int = 5
    agent_min_fills: int = 2
    agent_max_fills: int = 5000
    agent_soft_min_pnl_paise: int = 1
    agent_http_timeout_sec: float = 120
    agent_http_long_timeout_sec: float = 600
    agent_compile_timeout_sec: float = 180

    llm_catalog_path: Path = Field(default_factory=lambda: REPO_ROOT / "config" / "llm_catalog.yaml")


@lru_cache
def get_settings() -> Settings:
    return Settings()
