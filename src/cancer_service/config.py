from pathlib import Path

from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_path: str = str(ROOT / "artifacts" / "model.joblib")
    model_name: str | None = None
    mlflow_tracking_uri: str = "http://mlflow.localhost"

    database_url: str | None = None
    log_level: str = "INFO"


settings = Settings()
