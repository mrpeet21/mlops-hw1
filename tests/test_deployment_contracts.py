
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_config_value(file_path: str, key: str) -> str:
    """Read a simple YAML configuration value."""
    content = (ROOT / file_path).read_text(encoding="utf-8")

    match = re.search(
        rf"(?m)^\s*{re.escape(key)}:\s*(\S+)\s*$",
        content,
    )

    assert match is not None, (
        f"Configuration key {key} not found in {file_path}"
    )

    return match.group(1).strip("\"'")


def test_model_alias():
    alias = read_config_value(
        "k8s/configmap.yaml",
        "MODEL_ALIAS",
    )

    assert alias == "champion", (
        f"Expected MODEL_ALIAS=champion, got {alias}"
    )


def test_kind_cluster():
    cluster = read_config_value(
        ".github/workflows/ci.yml",
        "KIND_CLUSTER",
    )

    assert cluster == "mlops-hw1", (
        f"Expected KIND_CLUSTER=mlops-hw1, got {cluster}"
    )


def test_ingress_host():
    expected_host = read_config_value(
        ".github/workflows/ci.yml",
        "INGRESS_HOST",
    )

    ingress = (
        ROOT / "k8s/ingress.yaml"
    ).read_text(encoding="utf-8")

    assert re.search(
        rf"(?m)^\s*-\s*host:\s*{re.escape(expected_host)}\s*$",
        ingress,
    ), (
        f"Ingress route for {expected_host} not found"
    )
