import time
import uuid
from contextlib import asynccontextmanager

import joblib
import json

import mlflow
import mlflow.sklearn
from mlflow import MlflowClient
import pandas as pd
from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Request,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask

from cancer_service.config import settings
from cancer_service.db import init_db, save_prediction


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
    prediction_label: str

    probability: float
    probability_class: str

    model_version: str
    request_id: str
    latency_ms: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.model_name:
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

        client = MlflowClient(
            tracking_uri=settings.mlflow_tracking_uri
        )

        version = client.get_model_version_by_alias(
            settings.model_name,
            settings.model_alias,
        )

        app.state.pipeline = mlflow.sklearn.load_model(
            f"models:/{settings.model_name}@{settings.model_alias}"
        )

        metadata_path = client.download_artifacts(
            version.run_id,
            "metadata.json",
        )

        with open(
            metadata_path,
            encoding="utf-8",
        ) as file:
            metadata = json.load(file)

        metadata["model_version"] = str(version.version)

        metadata["class_names"] = {
            int(key): value
            for key, value in metadata["class_names"].items()
        }

        app.state.metadata = metadata

    else:
        bundle = joblib.load(settings.model_path)

        app.state.pipeline = bundle["pipeline"]
        app.state.metadata = bundle["metadata"]

        if "model_version" not in app.state.metadata:
            app.state.metadata["model_version"] = str(
                app.state.metadata.get(
                    "registry_version",
                    "local",
                )
            )

    example_input = app.state.metadata.get(
        "example_input"
    )

    if example_input:
        warmup_frame = pd.DataFrame(
            [example_input]
        )[app.state.metadata["features"]]

        app.state.pipeline.predict_proba(
            warmup_frame
        )

    init_db()

    yield

    app.state.pipeline = None
    app.state.metadata = None


app = FastAPI(
    title="Breast Cancer Prediction Service",
    version="1.0.1",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    request.state.started_at = time.perf_counter()

    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    request_id = request.state.request_id

    latency_ms = (
        time.perf_counter() - request.state.started_at
    ) * 1000

    try:
        payload = await request.json()

        if not isinstance(payload, dict):
            payload = {"payload": payload}

    except ValueError:
        raw_body = (
            await request.body()
        ).decode("utf-8", errors="replace")

        payload = {"raw_body": raw_body}

    metadata = getattr(app.state, "metadata", {}) or {}

    model_version = metadata.get(
        "model_version",
        "unknown",
    )

    background = BackgroundTask(
        save_prediction,
        request_id,
        model_version,
        payload,
        None,
        None,
        latency_ms,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": jsonable_encoder(exc.errors())
        },
        background=background,
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "log_level": settings.log_level,
        "model_version": app.state.metadata[
            "model_version"
        ],
    }

@app.get("/ready")
async def ready():
    if getattr(app.state, "pipeline", None) is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not loaded",
        )

    return {
        "status": "ready",
        "model_version": app.state.metadata[
            "model_version"
        ],
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

    return frame[
        app.state.metadata["features"]
    ]


@app.post(
    "/v1/predict",
    response_model=PredictionResponse,
)
def predict(
    features: Features,
    request: Request,
    background_tasks: BackgroundTasks,
):
    if getattr(app.state, "pipeline", None) is None:
        raise HTTPException(
            status_code=503,
            detail="Model is not loaded",
        )

    request_id = request.state.request_id

    frame = to_frame(features)

    probability = float(
        app.state.pipeline.predict_proba(frame)[0, 1]
    )

    threshold = app.state.metadata["threshold"]

    prediction = int(
        probability >= threshold
    )

    class_names = app.state.metadata["class_names"]

    prediction_label = class_names[prediction]

    probability_class = app.state.metadata[
        "probability_class_name"
    ]

    latency_ms = (
        time.perf_counter()
        - request.state.started_at
    ) * 1000

    background_tasks.add_task(
        save_prediction,
        request_id,
        app.state.metadata["model_version"],
        features.model_dump(),
        prediction,
        probability,
        latency_ms,
        status.HTTP_200_OK,
    )

    return PredictionResponse(
        prediction=prediction,
        prediction_label=prediction_label,
        probability=probability,
        probability_class=probability_class,
        model_version=app.state.metadata[
            "model_version"
        ],
        request_id=request_id,
        latency_ms=latency_ms,
    )