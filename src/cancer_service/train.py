import argparse
import hashlib
import json
import os
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]

DATA_PATH = ROOT / "data" / "breast_cancer.csv"

ARTIFACT_DIR = ROOT / "artifacts"
ARTIFACT_PATH = ARTIFACT_DIR / "model.joblib"
METADATA_PATH = ARTIFACT_DIR / "metadata.json"

TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "http://mlflow.localhost",
)

MODEL_NAME = os.getenv(
    "MODEL_NAME",
    "cancer-classifier",
)

EXPERIMENT_NAME = "cancer-training"

GATE_METRIC = "f1_malignant"
MIN_GAIN = 0.01

FEATURES = [
    "mean radius",
    "mean texture",
    "mean perimeter",
    "mean area",
    "mean smoothness",
    "mean compactness",
]

CLASS_NAMES = {
    0: "malignant",
    1: "benign",
}


def train_model(c: float, threshold: float) -> None:
    df = pd.read_csv(DATA_PATH)

    X = df[FEATURES]
    y = df["target"]

    data_md5 = hashlib.md5(
        DATA_PATH.read_bytes()
    ).hexdigest()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=c,
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ]
    )

    pipeline.fit(X_train, y_train)

    probabilities = pipeline.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= threshold).astype(int)

    accuracy = float(
        accuracy_score(y_test, predictions)
    )

    roc_auc = float(
        roc_auc_score(y_test, probabilities)
    )

    f1_malignant = float(
        f1_score(
            y_test,
            predictions,
            pos_label=0,
        )
    )

    precision_malignant = float(
        precision_score(
            y_test,
            predictions,
            pos_label=0,
        )
    )

    recall_malignant = float(
        recall_score(
            y_test,
            predictions,
            pos_label=0,
        )
    )

    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    client = MlflowClient()

    try:
        previous_champion = client.get_model_version_by_alias(
            MODEL_NAME,
            "champion",
        )
    except MlflowException:
        previous_champion = None

    with mlflow.start_run(
        run_name=f"logreg-C-{c:g}"
    ) as run:
        mlflow.log_params(
            {
                "C": c,
                "threshold": threshold,
                "test_size": 0.2,
                "random_state": 42,
                "data_md5": data_md5,
            }
        )

        mlflow.log_metrics(
            {
                "accuracy": accuracy,
                "roc_auc": roc_auc,
                "f1_malignant": f1_malignant,
                "precision_malignant": precision_malignant,
                "recall_malignant": recall_malignant,
            }
        )

        fig, ax = plt.subplots(figsize=(6, 5))

        ConfusionMatrixDisplay.from_predictions(
            y_test,
            predictions,
            display_labels=[
                "malignant",
                "benign",
            ],
            ax=ax,
        )

        ax.set_title("Confusion matrix")

        mlflow.log_figure(
            fig,
            "confusion_matrix.png",
        )

        plt.close(fig)

        signature = infer_signature(
            X_train,
            pipeline.predict(X_train),
        )

        model_info = mlflow.sklearn.log_model(
            sk_model=pipeline,
            name="model",
            registered_model_name=MODEL_NAME,
            signature=signature,
            input_example=X_train.head(3),
        )

        version = model_info.registered_model_version

        if version is None:
            raise RuntimeError(
                "MLflow did not return registered model version"
            )

        version = str(version)

        client.set_registered_model_alias(
            MODEL_NAME,
            "challenger",
            version,
        )

        if previous_champion is None:
            gate_passed = True
            champion_score = None

        else:
            champion_run = client.get_run(
                previous_champion.run_id
            )

            champion_score = float(
                champion_run.data.metrics[GATE_METRIC]
            )

            gate_passed = (
                f1_malignant
                >= champion_score + MIN_GAIN
            )

        if gate_passed:
            client.set_registered_model_alias(
                MODEL_NAME,
                "champion",
                version,
            )

        metadata = {
            "model_name": MODEL_NAME,
            "registry_version": version,
            "run_id": run.info.run_id,
            "features": FEATURES,
            "threshold": threshold,
            "class_names": CLASS_NAMES,
            "probability_class": 1,
            "probability_class_name": "benign",
            "data_md5": data_md5,
            "gate_metric": GATE_METRIC,
            "gate_score": f1_malignant,
            "min_gain": MIN_GAIN,
            "gate_passed": bool(gate_passed),
        }

        ARTIFACT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        with METADATA_PATH.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                metadata,
                file,
                indent=2,
                ensure_ascii=False,
            )

        bundle = {
            "pipeline": pipeline,
            "metadata": metadata,
        }

        joblib.dump(
            bundle,
            ARTIFACT_PATH,
        )

        mlflow.log_artifact(
            METADATA_PATH,
        )

        print()
        print(f"Run ID: {run.info.run_id}")
        print(f"Model: {MODEL_NAME}")
        print(f"Registered version: {version}")
        print(f"C: {c}")
        print(f"Data MD5: {data_md5}")
        print(
            f"F1 malignant: {f1_malignant:.4f}"
        )

        if previous_champion is None:
            print(
                "GATE: PASS - first model, "
                f"version {version} becomes champion"
            )

        elif gate_passed:
            print(
                "GATE: PASS - "
                f"{f1_malignant:.4f} >= "
                f"{champion_score:.4f} + "
                f"{MIN_GAIN:.4f}"
            )
            print(
                f"Champion -> version {version}"
            )

        else:
            print(
                "GATE: FAIL - "
                f"{f1_malignant:.4f} < "
                f"{champion_score:.4f} + "
                f"{MIN_GAIN:.4f}"
            )
            print(
                "Champion remains version "
                f"{previous_champion.version}"
            )

        print(
            f"Challenger -> version {version}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--c",
        type=float,
        default=0.003,
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
    )

    args = parser.parse_args()

    train_model(
        c=args.c,
        threshold=args.threshold,
    )