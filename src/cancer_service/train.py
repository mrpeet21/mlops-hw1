from pathlib import Path

import joblib
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts"
ARTIFACT_PATH = ARTIFACT_DIR / "model.joblib"


def train_model() -> None:
    data = load_breast_cancer(as_frame=True)
    df = data.frame.copy()

    features = [
        "mean radius",
        "mean texture",
        "mean perimeter",
        "mean area",
        "mean smoothness",
        "mean compactness",
    ]

    X = df[features]
    y = df["target"]

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
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ]
    )

    pipeline.fit(X_train, y_train)

    accuracy = pipeline.score(X_test, y_test)

    class_names = {
        int(index): str(name)
        for index, name in enumerate(data.target_names)
    }

    example_input = {
        feature: float(X_train.iloc[0][feature])
        for feature in features
    }

    metadata = {
        "model_version": "1.0.1",
        "features": features,
        "threshold": 0.5,
        "test_accuracy": float(accuracy),
        "class_names": class_names,
        "probability_class": 1,
        "probability_class_name": class_names[1],
        "example_input": example_input,
    }

    bundle = {
        "pipeline": pipeline,
        "metadata": metadata,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, ARTIFACT_PATH)

    print(f"Model saved to: {ARTIFACT_PATH}")
    print(f"Model version: {metadata['model_version']}")
    print(f"Features: {metadata['features']}")
    print(f"Classes: {metadata['class_names']}")
    print(
        "Probability means P(class=1) = "
        f"P({metadata['probability_class_name']})"
    )
    print(f"Test accuracy: {accuracy:.4f}")


if __name__ == "__main__":
    train_model()