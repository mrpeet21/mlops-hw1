# MLOps HW1 — Breast Cancer Prediction Service

Домашнее задание №1 по MLOps: путь ML-модели от артефакта до FastAPI-сервиса, Docker Compose и Kubernetes.

## Модель

Используется датасет Breast Cancer Wisconsin из `scikit-learn`.

Модель:

- `StandardScaler`;
- `LogisticRegression`;
- preprocessing и модель объединены в один `sklearn Pipeline`.

Версия модели: `1.0.1`.

### Семантика классов

В исходном датасете:

- `0` — `malignant` — злокачественная опухоль;
- `1` — `benign` — доброкачественная опухоль.

Поле `probability` содержит вероятность класса `1`, то есть `P(benign)`.

Для устранения неоднозначности API дополнительно возвращает:

- `prediction_label`;
- `probability_class`.

Соответствие классов также хранится в metadata артефакта.

Обучение модели находится в `notebooks/train.ipynb`.

Подробный отчёт: [REPORT.md](REPORT.md).

## API

Сервис предоставляет:

- `GET /health`;
- `GET /ready`;
- `POST /v1/predict`;
- `GET /docs`.

Пример успешного ответа:

```json
{
  "prediction": 1,
  "prediction_label": "benign",
  "probability": 0.5229,
  "probability_class": "benign",
  "model_version": "1.0.1",
  "request_id": "...",
  "latency_ms": 25.0
}
```

## Проверка

### 1. Тесты

```bash
uv sync && uv run pytest
```

### 2. Docker Compose, API и PostgreSQL

```bash
docker compose up -d --build \
&& until curl -fsS http://localhost:8000/ready >/dev/null 2>&1; do sleep 1; done \
&& curl -sS -X POST http://localhost:8000/v1/predict \
-H "Content-Type: application/json" \
-d '{"mean_radius":14.0,"mean_texture":20.0,"mean_perimeter":90.0,"mean_area":600.0,"mean_smoothness":0.1,"mean_compactness":0.12}' \
&& echo \
&& curl -sS -o /dev/null -w "invalid request -> HTTP %{http_code}\n" \
-X POST http://localhost:8000/v1/predict \
-H "Content-Type: application/json" \
-d '{"mean_radius":-10,"mean_texture":20.0,"mean_perimeter":90.0,"mean_area":600.0,"mean_smoothness":0.1,"mean_compactness":0.12}' \
&& sleep 1 \
&& docker compose exec -T db psql -U postgres -d cancer \
-P null='NULL' \
-c "SELECT request_id, prediction, probability, status_code FROM predictions ORDER BY ts DESC LIMIT 5;"
```

### 3. Kubernetes

```bash
docker build -t cancer-service:1.0 . && (kind get clusters | grep -qx mlops-hw1 || kind create cluster --name mlops-hw1) && kind load docker-image cancer-service:1.0 --name mlops-hw1 && kubectl apply -f k8s/ && kubectl rollout restart deployment/cancer-service && kubectl rollout status deployment/cancer-service
```

## Доказательства

### Pytest

![Pytest](docs/pytest.png)

### PostgreSQL

![PostgreSQL](docs/postgres.png)

### Kubernetes

![Kubernetes](docs/kubernetes.png)

### k9s

![k9s](docs/k9s.png)