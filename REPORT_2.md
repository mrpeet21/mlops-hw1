# Homework 2 — CI/CD для ML-сервиса

## 1. Что было сделано

Во второй домашней работе CI/CD был построен поверх сервиса `cancer-service` из домашней работы 1.

В pipeline есть три job:

- `tests` — запускает `ruff` и `pytest` с настоящим PostgreSQL;
- `build` — собирает Docker-образ и публикует его в GHCR с тегом, равным SHA коммита;
- `deploy` — создаёт kind-кластер, поднимает PostgreSQL и `cancer-service`, после чего выполняет smoke-тест.

Также были добавлены:

- интеграционные тесты записи успешного запроса (`status_code = 200`) и невалидного запроса (`status_code = 422`) в PostgreSQL;
- `ConfigMap` с настройками `MODEL_PATH` и `LOG_LEVEL`;
- `Secret` для `DATABASE_URL`;
- smoke-тест, который отправляет реальные признаки модели и проверяет, что `prediction` равен `0` или `1`, а `probability` находится в диапазоне `[0, 1]`;
- шаг `Diagnostics`, который при ошибке печатает pod'ы, Kubernetes Events, текущие и предыдущие логи контейнеров;
- `pg_advisory_xact_lock` перед инициализацией схемы PostgreSQL.

---

## 2. Что предъявить

| Пункт | Ссылка |
|---|---|
| Зелёный pipeline `tests → build → deploy` | [Actions run](https://github.com/mrpeet21/mlops-hw1/actions/runs/36344362973) |
| GHCR-образ с SHA-тегом | [Package](https://github.com/mrpeet21/mlops-hw1/pkgs/container/mlops-hw1) |


---

## 3. Три красных прогона с диагнозом

### 3.1. Неправильный путь к модели в ConfigMap

**Красный job:** `deploy`  
**Красный шаг:** `Deploy cancer service`  
**Статус pod:** `CrashLoopBackOff`

Шаг `kubectl rollout status` завершился по timeout. В логах приложения было:

```text
FileNotFoundError: [Errno 2] No such file or directory:
'/app/artifacts/missing-model.joblib'
```

По логам видно, что контейнер уже смог запуститься, но приложение падает во время startup на загрузке модели через `joblib.load(settings.model_path)`. Значит, проблема находится в пути к артефакту модели, а не в PostgreSQL или планировщике Kubernetes.

**Исправление:** значение `MODEL_PATH` возвращено к:

```text
/app/artifacts/model.joblib
```

Красный run: [Actions run](https://github.com/mrpeet21/mlops-hw1/actions/runs/36344873165)

Зелёный run после исправления: [Actions run](https://github.com/mrpeet21/mlops-hw1/actions/runs/36345650806)

### 3.2. Неправильный `secretRef`

**Красный job:** `deploy`  
**Статус pod:** `CreateContainerConfigError`

В Kubernetes Events было:

```text
Error: secret "cancer-secret-broken" not found
```

По этому сообщению видно, что контейнер ещё не начал выполнять приложение: Kubernetes не смог собрать его конфигурацию из-за ссылки на отсутствующий Secret. Поэтому причина определяется по Events, а не по логам FastAPI.

**Исправление:** в `Deployment` возвращено корректное имя:

```yaml
secretRef:
  name: cancer-secret
```

Красный run: [Actions run](https://github.com/mrpeet21/mlops-hw1/actions/runs/36345865678)  
Зелёный run после исправления: [Actions run](https://github.com/mrpeet21/mlops-hw1/actions/runs/36346457943)

### 3.3. Слишком большой запрос памяти

**Красный job:** `deploy`  
**Статус pod:** `Pending`

В Kubernetes Events было:

```text
Warning  FailedScheduling
0/1 nodes are available: 1 Insufficient memory
```

Pod остаётся в `Pending`, а `FailedScheduling` с `Insufficient memory` показывает, что scheduler не может назначить pod ни на одну ноду из-за слишком большого `requests.memory`. Контейнер ещё не создавался, поэтому логов приложения для этой ошибки нет.

**Исправление:** ресурсы возвращены к рабочим значениям:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

Красный run: [Actions run](https://github.com/mrpeet21/mlops-hw1/actions/runs/36346875330)  
Зелёный run после исправления: [Actions run](https://github.com/mrpeet21/mlops-hw1/actions/runs/36347547320)

---

## 4. Ответы на вопросы

### 1. Сколько шёл `build` в первом и втором прогоне? Что взялось из кэша?

В первом полном прогоне job `build` выполнялся **46 секунд**, во втором — **17 секунд**. Во втором прогоне сработал Docker layer cache; в частности, повторно использовался дорогой слой установки зависимостей:

```dockerfile
RUN uv sync --frozen --no-dev --no-install-project
```

Он может быть взят из кэша, потому что до него копируются `pyproject.toml` и `uv.lock`, а они между этими прогонами не менялись. Во втором прогоне изменения относились к Kubernetes-конфигурации и не затрагивали файлы, которые Dockerfile копирует в слои приложения, поэтому большая часть слоёв образа могла быть переиспользована.

Первый прогон: [Actions run](https://github.com/mrpeet21/mlops-hw1/actions/runs/36344362973)  
Второй прогон: [Actions run](https://github.com/mrpeet21/mlops-hw1/actions/runs/36344873165)

### 2. Почему во время deploy видны pod'ы в `ImagePullBackOff`, но прогон может быть зелёным?

Сначала `kubectl apply -f k8s/deployment.yaml` создаёт ReplicaSet с образом `cancer-service:1.0`. Такого образа в Docker Hub нет, поэтому эти временные pod'ы могут попасть в `ErrImagePull` / `ImagePullBackOff`.

Затем workflow выполняет `kubectl set image` и подставляет реальный образ из GHCR с SHA-тегом. Deployment создаёт новый ReplicaSet уже с правильным образом, он становится Ready, а старый ReplicaSet масштабируется до нуля. Поэтому наличие старых pod'ов в `ImagePullBackOff` во время rollout не означает, что итоговый deploy завершился ошибкой.

### 3. Как пароль PostgreSQL попадает из GitHub в pod и почему его нельзя хранить в ConfigMap?

Пароль задаётся в `Settings → Secrets and variables → Actions` как `POSTGRES_PASSWORD`. В workflow он читается как `${{ secrets.POSTGRES_PASSWORD }}`, после чего команда `kubectl create secret` создаёт Kubernetes Secret; для приложения из этого значения формируется `DATABASE_URL`, который затем попадает в pod через `secretRef`.

Пароль нельзя записывать в `configmap.yaml`, потому что ConfigMap предназначен для несекретной конфигурации, а сам файл хранится в публичном Git-репозитории. Пароли и ключи не должны попадать ни в Git, ни в Docker-образ.

### 4. Что будет, если убрать `needs: tests` у job `build`?

Без `needs: tests` сборка Docker-образа сможет начаться независимо от результата тестов. Например, pytest может обнаружить сломанный API, но параллельно `build` уже успешно соберёт и опубликует образ.

Поскольку `deploy` зависит от `build`, а не напрямую от `tests`, такой образ потенциально сможет дойти до deployment. `needs: tests` гарантирует, что сборка начинается только после успешной проверки кода.

### 5. Почему на pull request выполняются только тесты?

У `build` и `deploy` стоит условие:

```yaml
if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

Поэтому на событии `pull_request` запускается только `tests`, а `build` и `deploy` отображаются как `skipped`. Это сделано, чтобы проверять изменения до merge, но не публиковать Docker-образы и не выполнять deployment для кода, который ещё не попал в `main`.

### 6. Зачем нужен `pg_advisory_xact_lock`?

В `init_db()` перед DDL используется:

```sql
SELECT pg_advisory_xact_lock(424242);
```

У `cancer-service` в Deployment две реплики, то есть два pod'а приложения могут практически одновременно стартовать и вызвать `init_db()` на одной пустой базе. Advisory lock сериализует инициализацию схемы: один pod выполняет создание/изменение таблицы, второй ждёт завершения транзакции.

Без блокировки два экземпляра приложения могли бы одновременно выполнять DDL и получить race condition, конфликт блокировок или ошибку при миграции. Под «репликами» здесь имеются в виду две реплики `cancer-service`, а не две реплики PostgreSQL.

### 7. Расположите три статуса pod в порядке его жизни

Порядок получился таким:

```text
Pending
→ CreateContainerConfigError
→ CrashLoopBackOff
```

`Pending` возникает раньше всего: scheduler ещё не смог назначить pod на ноду, как в случае `Insufficient memory`. `CreateContainerConfigError` возникает после того, как Kubernetes пытается подготовить контейнер, но не может собрать его конфигурацию, например из-за отсутствующего Secret.

`CrashLoopBackOff` возникает позже: контейнер уже создаётся и приложение запускается, но процесс падает и Kubernetes многократно пытается его перезапустить. В нашем случае причиной был `FileNotFoundError` при загрузке модели.

---

## 5. Журнал проблем

| Проблема | Текст / симптом | Как нашли причину | Как исправили |
|---|---|---|---|
| `ruff` отсутствовал в окружении | `Failed to spawn: ruff` / `No such file or directory` | Команда `uv run ruff check .` не смогла запустить executable | Добавила `ruff` как dev-зависимость через `uv add --dev ruff`, обновились `pyproject.toml` и `uv.lock` |
| Ruff нашёл старые нарушения форматирования | `I001 Import block is un-sorted` и `SIM117` | Запустила `ruff check`; он указал конкретные файлы и строки | Выполнила `ruff --fix`, вручную объединили вложенные `with`, затем `ruff` и все 11 тестов стали зелёными |
| `build` был неправильно расположен в YAML | `Workflow runs completed with no jobs` | Проверила структуру `.github/workflows/ci.yml` и увидела, что `build:` находится вне `jobs:` | Исправила отступ: `build` разместила на одном уровне с `tests` внутри `jobs` |

---


