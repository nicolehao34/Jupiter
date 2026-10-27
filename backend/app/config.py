from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    nebius_model: str = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
    nebius_timeout_seconds: float = 45.0
    nebius_max_retries: int = 2
    nebius_offline_demo: bool = False

    materials_project_api_key: str = ""
    materials_project_base_url: str = "https://api.materialsproject.org"

    jupiter_database_url: str = "sqlite:///./data/jupiter.sqlite"
    jupiter_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    jupiter_seed: int = 42

    @property
    def database_url(self) -> str:
        return self.jupiter_database_url

    @property
    def cors_origins(self) -> str:
        return self.jupiter_cors_origins

    @property
    def seed(self) -> int:
        return self.jupiter_seed

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def nebius_configured(self) -> bool:
        return bool(self.nebius_api_key.strip())

    @property
    def inference_mode(self) -> str:
        if self.nebius_offline_demo:
            return "offline_demo"
        if self.nebius_configured:
            return "live"
        return "unconfigured"


@lru_cache
def get_settings() -> Settings:
    return Settings()
