def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["model_version"] == "1.0.0"


def test_predict_success(client, valid_payload):
    response = client.post("/v1/predict", json=valid_payload)

    assert response.status_code == 200

    data = response.json()

    assert data["prediction"] in [0, 1]
    assert 0.0 <= data["probability"] <= 1.0
    assert data["model_version"] == "1.0.0"
    assert isinstance(data["request_id"], str)
    assert isinstance(data["latency_ms"], float)


def test_extra_field_returns_422(client, valid_payload):
    payload = valid_payload.copy()
    payload["garbage"] = "hello"

    response = client.post("/v1/predict", json=payload)

    assert response.status_code == 422


def test_invalid_value_returns_422(client, valid_payload):
    payload = valid_payload.copy()
    payload["mean_radius"] = -10

    response = client.post("/v1/predict", json=payload)

    assert response.status_code == 422


def test_wrong_type_returns_422(client, valid_payload):
    payload = valid_payload.copy()
    payload["mean_texture"] = "not-a-number"

    response = client.post("/v1/predict", json=payload)

    assert response.status_code == 422


def test_prediction_is_deterministic(client, valid_payload):
    first = client.post("/v1/predict", json=valid_payload).json()
    second = client.post("/v1/predict", json=valid_payload).json()

    assert first["prediction"] == second["prediction"]
    assert first["probability"] == second["probability"]


def test_missing_required_field_returns_422(client, valid_payload):
    payload = valid_payload.copy()
    payload.pop("mean_area")

    response = client.post("/v1/predict", json=payload)

    assert response.status_code == 422