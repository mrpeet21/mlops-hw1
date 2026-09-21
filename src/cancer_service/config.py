from pathlib import Path

from pydantic_settings import BaseSettings


ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_path: str = str(ROOT / "artifacts" / "model.joblib")
    database_url: str | None = None
    log_level: str = "INFO"


settings = Settings()