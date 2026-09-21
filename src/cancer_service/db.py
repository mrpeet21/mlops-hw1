import json
import logging

import psycopg2

from cancer_service.config import settings


log = logging.getLogger(__name__)


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS predictions (
    request_id UUID PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_version TEXT NOT NULL,
    features JSONB NOT NULL,
    prediction INTEGER NOT NULL,
    probability DOUBLE PRECISION NOT NULL,
    latency_ms REAL NOT NULL,
    status_code INTEGER NOT NULL
);
"""


def init_db() -> None:
    if not settings.database_url:
        return

    try:
        with psycopg2.connect(settings.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_TABLE_SQL)
    except Exception:
        log.exception("Could not initialize database")


def save_prediction(
    request_id: str,
    model_version: str,
    features: dict,
    prediction: int,
    probability: float,
    latency_ms: float,
    status_code: int,
) -> None:
    if not settings.database_url:
        return

    try:
        with psycopg2.connect(settings.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO predictions (
                        request_id,
                        model_version,
                        features,
                        prediction,
                        probability,
                        latency_ms,
                        status_code
                    )
                    VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)
                    """,
                    (
                        request_id,
                        model_version,
                        json.dumps(features),
                        prediction,
                        probability,
                        latency_ms,
                        status_code,
                    ),
                )
    except Exception:
        log.exception("Could not save prediction")