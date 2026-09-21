import pytest
from fastapi.testclient import TestClient

from cancer_service.service.app import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_payload():
    return {
        "mean_radius": 14.0,
        "mean_texture": 20.0,
        "mean_perimeter": 90.0,
        "mean_area": 600.0,
        "mean_smoothness": 0.1,
        "mean_compactness": 0.12,
    }