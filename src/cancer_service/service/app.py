from contextlib import asynccontextmanager
import time
import uuid

import joblib
import pandas as pd
from fastapi import BackgroundTasks, FastAPI, HTTPException

from cancer_service.db import init_db, save_prediction
from pydantic import BaseModel, ConfigDict, Field

from cancer_service.config import settings


class Features(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mean_radius: float = Field(gt=0, le=50)
    mean_texture: float = Field(gt=0, le=50)
    mean_perimeter: float = Field(gt=0, le=250)
    mean_area: float = Field(gt=0, le=5000)
    mean_smoothness: float = Field(gt=0, le=1)
    mean_compactness: float = Field(gt=0, le=1)


class PredictionResponse(BaseModel):
    prediction: int
    probability: float
    model_version: str
    request_id: str
    latency_ms: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    bundle = joblib.load(settings.model_path)

    app.state.pipeline = bundle["pipeline"]
    app.state.metadata = bundle["metadata"]

    init_db()

    yield

    app.state.pipeline = None
    app.state.metadata = None


app = FastAPI(
    title="Breast Cancer Prediction Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if getattr(app.state, "pipeline", None) is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")

    return {
        "status": "ready",
        "model_version": app.state.metadata["model_version"],
    }


def to_frame(features: Features) -> pd.DataFrame:
    row = {
        "mean radius": features.mean_radius,
        "mean texture": features.mean_texture,
        "mean perimeter": features.mean_perimeter,
        "mean area": features.mean_area,
        "mean smoothness": features.mean_smoothness,
        "mean compactness": features.mean_compactness,
    }

    frame = pd.DataFrame([row])

    return frame[app.state.metadata["features"]]

@app.post("/v1/predict", response_model=PredictionResponse)
def predict(features: Features, background_tasks: BackgroundTasks):
    if getattr(app.state, "pipeline", None) is None:
        raise HTTPException(status_code=503, detail="Model is not loaded")

    request_id = str(uuid.uuid4())
    started_at = time.perf_counter()

    frame = to_frame(features)

    probability = float(
        app.state.pipeline.predict_proba(frame)[0, 1]
    )

    threshold = app.state.metadata["threshold"]
    prediction = int(probability >= threshold)

    latency_ms = (time.perf_counter() - started_at) * 1000

    background_tasks.add_task(
        save_prediction,
        request_id,
        app.state.metadata["model_version"],
        features.model_dump(),
        prediction,
        probability,
        latency_ms,
        200,
    )

    return PredictionResponse(
        prediction=prediction,
        probability=probability,
        model_version=app.state.metadata["model_version"],
        request_id=request_id,
        latency_ms=latency_ms,
    )