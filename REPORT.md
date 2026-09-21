# Отчёт по домашнему заданию №1

## 1. Артефакт модели

Используется датасет Breast Cancer Wisconsin из
`scikit-learn`.

Задача — бинарная классификация.

Модель состоит из:

- `StandardScaler`;
- `LogisticRegression`.

Используются признаки:

- mean radius;
- mean texture;
- mean perimeter;
- mean area;
- mean smoothness;
- mean compactness.

Артефакт `artifacts/model.joblib` содержит:

- `pipeline`;
- `metadata`;
- версию модели `1.0.0`;
- список признаков в правильном порядке;
- threshold `0.5`;
- test accuracy.


---

## 2. FastAPI-сервис

Реализованы endpoints:

- `GET /health`;
- `GET /ready`;
- `POST /v1/predict`;
- `/docs`.

Модель загружается один раз при запуске приложения через lifespan.

Ответ `/v1/predict` содержит:

- prediction;
- probability;
- model_version;
- request_id;
- latency_ms.

Для входной схемы используется Pydantic с ограничениями значений и
`extra="forbid"`.

---

## 3. Тестирование

Реализовано 8 тестов:

- проверка `/health`;
- проверка `/ready`;
- smoke test предсказания;
- лишнее поле возвращает HTTP 422;
- значение вне допустимого диапазона возвращает HTTP 422;
- неправильный тип возвращает HTTP 422;
- одинаковый вход даёт одинаковое предсказание;
- отсутствие обязательного поля возвращает HTTP 422.

Все тесты успешно проходят.

![Pytest](docs/pytest.jpg)

---

## 4. PostgreSQL и Docker Compose

Каждый успешный запрос `/v1/predict` записывается в таблицу `predictions`.

Сохраняются:

- request_id;
- время запроса;
- версия модели;
- признаки в JSONB;
- prediction;
- probability;
- latency_ms;
- status_code.

Если `DATABASE_URL` отсутствует, сервис продолжает работать без записи
в PostgreSQL.

Docker Compose поднимает:

- FastAPI-сервис;
- PostgreSQL 16.

Для PostgreSQL настроен healthcheck, а API зависит от готовности базы.

### Запись предсказания в PostgreSQL

![PostgreSQL](docs/postgres.jpg)

---

## 5. Kubernetes

Сервис развернут в локальном kind-кластере.

Deployment содержит:

- 2 replicas;
- startupProbe;
- livenessProbe;
- readinessProbe;
- CPU requests и limits;
- memory requests и limits.

Для доступа к pod'ам используется `ClusterIP` Service.

Работа модели проверена через `kubectl port-forward`.

![Kubernetes](docs/kubernetes.jpg)

### k9s

Обе реплики сервиса работают в кластере.

![k9s](docs/k9s.jpg)

---

## 6. Журнал проблем

### IndentationError

После добавления фоновой записи предсказаний возникла ошибка:

`IndentationError: unexpected indent`

Причиной был неправильный отступ у `background_tasks.add_task`.

После исправления отступов все тесты снова прошли.

### README отсутствовал внутри Docker image

При сборке Docker возникла ошибка:

`failed to open file /app/README.md`

`uv` пытался установить проект, но `README.md`, указанный в
`pyproject.toml`, ещё не был скопирован в image.

В Dockerfile `README.md` был добавлен в `COPY` до второго `uv sync`.

### ghcr.io был недоступен

Во время сборки Docker возникла ошибка:

`failed to fetch anonymous token`

и DNS timeout при обращении к `ghcr.io`.

Причиной оказался включённый VPN. После его отключения все получилось
