import uuid

import psycopg2

from cancer_service.config import settings


def fetch_prediction(request_id: str):
    with psycopg2.connect(settings.database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT
                    request_id,
                    model_version,
                    features,
                    prediction,
                    probability,
                    latency_ms,
                    status_code
                FROM predictions
                WHERE request_id = %s
                """,
            (request_id,),
        )

        return cur.fetchone()


def test_successful_request_is_logged(
    client,
    valid_payload,
):
    response = client.post(
        "/v1/predict",
        json=valid_payload,
    )

    assert response.status_code == 200

    response_data = response.json()
    request_id = response_data["request_id"]

    row = fetch_prediction(request_id)

    assert row is not None

    (
        saved_request_id,
        model_version,
        features,
        prediction,
        probability,
        latency_ms,
        status_code,
    ) = row

    assert str(saved_request_id) == request_id
    assert model_version == "1.0.1"
    assert features == valid_payload
    assert prediction in {0, 1}
    assert 0.0 <= probability <= 1.0
    assert latency_ms >= 0
    assert status_code == 200


def test_validation_error_is_logged_in_postgres(
    client,
    valid_payload,
):
    marker = str(uuid.uuid4())

    payload = valid_payload.copy()
    payload["garbage"] = marker

    response = client.post(
        "/v1/predict",
        json=payload,
    )

    assert response.status_code == 422

    with psycopg2.connect(settings.database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT
                    features,
                    prediction,
                    probability,
                    status_code
                FROM predictions
                WHERE features ->> 'garbage' = %s
                ORDER BY ts DESC
                LIMIT 1
                """,
            (marker,),
        )

        row = cur.fetchone()

    assert row is not None

    features, prediction, probability, status_code = row

    assert features["garbage"] == marker
    assert prediction is None
    assert probability is None
    assert status_code == 422

