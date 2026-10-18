# Compare DVC dataset versions on a shared test set.
#
# Restore v2 before running:
# uv run dvc get . data/breast_cancer.csv \
#     --rev 28387ee \
#     -o /tmp/breast_cancer_v2.csv
#
# v3 is read from the current working directory.
# Both models use C=0.01 and the same held-out test set.
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "mean radius",
    "mean texture",
    "mean perimeter",
    "mean area",
    "mean smoothness",
    "mean compactness",
]

C = 0.01
RANDOM_STATE = 42

# Загружаем обе версии
v2 = pd.read_csv("/tmp/breast_cancer_v2.csv")
v3 = pd.read_csv("data/breast_cancer.csv")


def row_keys(df):
    """Идентификаторы объектов по значениям признаков."""
    return (
        df[FEATURES]
        .round(8)
        .astype(str)
        .agg("|".join, axis=1)
    )


# Убеждаемся, что v3 действительно является подмножеством v2
v2_keys = row_keys(v2)
v3_keys = row_keys(v3)

assert v2_keys.is_unique
assert v3_keys.is_unique
assert set(v3_keys).issubset(set(v2_keys))

# Выбираем общий test только из объектов, имеющихся в обеих версиях
train_idx, test_idx = train_test_split(
    v3.index,
    test_size=0.2,
    random_state=RANDOM_STATE,
    stratify=v3["target"],
)

test = v3.loc[test_idx]
test_keys = set(v3_keys.loc[test_idx])

# Удаляем одни и те же тестовые объекты из обучения
train_v2 = v2.loc[~v2_keys.isin(test_keys)]
train_v3 = v3.loc[train_idx]

assert len(train_v2) == 477
assert len(train_v3) == 364
assert len(test) == 92
assert not set(row_keys(train_v2)) & test_keys
assert not set(row_keys(train_v3)) & test_keys

X_test = test[FEATURES]
y_test = test["target"]


def evaluate(df, name):
    model = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(
            C=C,
            max_iter=1000,
            random_state=RANDOM_STATE,
        )),
    ])

    model.fit(df[FEATURES], df["target"])

    # Вероятность класса 1 (benign), как в train.py
    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)

    return {
        "Dataset": name,
        "Train rows": len(df),
        "Test rows": len(test),
        "F1 malignant": round(
            f1_score(y_test, predictions, pos_label=0), 4
        ),
        "Precision malignant": round(
            precision_score(y_test, predictions, pos_label=0), 4
        ),
        "Recall malignant": round(
            recall_score(y_test, predictions, pos_label=0), 4
        ),
        "ROC-AUC": round(
    roc_auc_score(y_test, probabilities), 6
    ),
    "Log Loss": round(
    log_loss(y_test, probabilities), 6
    ),
    "Mean P(benign)": round(
    float(probabilities.mean()), 6
    ),
    }


results = pd.DataFrame([
    evaluate(train_v2, "v2"),
    evaluate(train_v3, "v3"),
])

print("\nСравнение моделей (C=0.01, общий test):")
print(results.to_string(index=False))

diff = (
    results.loc[1, "F1 malignant"]
    - results.loc[0, "F1 malignant"]
)

print(f"\nРазница F1 (v3 - v2): {diff:+.4f}")
