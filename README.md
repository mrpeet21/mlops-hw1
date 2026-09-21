# MLOps HW1 — Breast Cancer Prediction Service

Сервис бинарной классификации на основе датасета Breast Cancer Wisconsin.

Используется:
- `scikit-learn Pipeline`;
- Logistic Regression;
- FastAPI;
- PostgreSQL;
- Docker Compose;
- Kubernetes / kind.

Модель обучается в `notebooks/train.ipynb`.
Артефакт находится в `artifacts/model.joblib`.

Подробный отчёт: [REPORT.md](REPORT.md)

## Проверка

### 1. Тесты

```bash
uv sync && uv run pytest
```

### 2. Docker Compose

```bash
docker compose up -d --build
```

### 3. Kubernetes

```bash
docker build -t cancer-service:1.0 . && (kind get clusters | grep -qx mlops-hw1 || kind create cluster --name mlops-hw1) && kind load docker-image cancer-service:1.0 --name mlops-hw1 && kubectl apply -f k8s/ && kubectl rollout status deployment/cancer-service
```