# app/core/settings.py
# Single source of truth for configuration. Values come from .env (see .env.example).

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root: app/core/settings.py -> parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

APP_NAME = "Yojak"
APP_VERSION = "1.0.0"


def _resolve(path: Path) -> Path:
    """Relative paths are resolved against the repo root, not the CWD."""
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        protected_namespaces=("settings_",),
    )

    # --- Neo4j ---
    neo4j_uri: str = Field(default="neo4j://127.0.0.1:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="", alias="NEO4J_PASSWORD")

    # --- Data paths ---
    esco_data_dir: Path = Field(default=Path("data/raw/esco"), alias="ESCO_DATA_DIR")
    naukri_data_dir: Path = Field(default=Path("data/raw/naukri"), alias="NAUKRI_DATA_DIR")
    external_data_dir: Path = Field(default=Path("data/raw/external"), alias="EXTERNAL_DATA_DIR")
    reference_data_dir: Path = Field(default=Path("data/reference"), alias="REFERENCE_DATA_DIR")
    gold_data_dir: Path = Field(default=Path("data/gold"), alias="GOLD_DATA_DIR")
    processed_data_dir: Path = Field(default=Path("data/processed"), alias="PROCESSED_DATA_DIR")
    artifacts_dir: Path = Field(default=Path("artifacts"), alias="ARTIFACTS_DIR")
    reports_dir: Path = Field(default=Path("reports"), alias="REPORTS_DIR")

    # --- ML ---
    faiss_index_path: Path = Field(
        default=Path("data/processed/occupation.index"), alias="FAISS_INDEX_PATH"
    )
    # English / legacy SkillAlign model (baseline B2).
    model_name: str = Field(
        default="sentence-transformers/all-mpnet-base-v2", alias="MODEL_NAME"
    )
    # Multilingual model used for Hindi / Punjabi / romanised input.
    multilingual_model_name: str = Field(
        default="sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        alias="MULTILINGUAL_MODEL_NAME",
    )

    # --- App ---
    environment: str = Field(default="development", alias="ENVIRONMENT")
    uvicorn_port: int = Field(default=8000, alias="UVICORN_PORT")
    # Demo-grade guard for admin write routes. Empty string disables the check
    # only in development; production refuses to start without it.
    admin_token: str = Field(default="", alias="ADMIN_TOKEN")
    # Load embedding models in a background thread at startup (off in tests).
    warm_up_models: bool = Field(default=True, alias="WARM_UP_MODELS")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000", alias="CORS_ORIGINS"
    )

    @field_validator(
        "esco_data_dir",
        "naukri_data_dir",
        "external_data_dir",
        "reference_data_dir",
        "gold_data_dir",
        "processed_data_dir",
        "artifacts_dir",
        "reports_dir",
        "faiss_index_path",
        mode="after",
    )
    @classmethod
    def _abs(cls, v: Path) -> Path:
        return _resolve(v)

    @property
    def occupation_metadata_path(self) -> Path:
        return self.faiss_index_path.parent / "occupation_metadata.csv"

    @property
    def neo4j_auth(self) -> tuple[str, str]:
        return (self.neo4j_user, self.neo4j_password)

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
