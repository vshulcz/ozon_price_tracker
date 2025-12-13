# Руководство по развёртыванию

Production-ready развёртывание с использованием K3s и ArgoCD для GitOps continuous delivery.

## Требования

- Чистый сервер Ubuntu/Debian (4GB+ RAM, 20GB+ диск)
- Root/sudo доступ
- Домен (опционально, для ArgoCD UI)

## Быстрый старт

```bash
# 1. Установить K3s
curl -sfL https://get.k3s.io | sh -

# 2. Установить ArgoCD
kubectl create namespace argocd
kubectl apply -k k8s/argocd/install -n argocd

# 3. Создать секреты
kubectl create secret generic bot-secrets -n marketplace-bot-prod \
  --from-literal=BOT_TOKEN='your_telegram_bot_token' \
  --from-literal=POSTGRES_PASSWORD='your_db_password'

# 4. Задеплоить приложение
kubectl apply -f k8s/argocd/application-prod.yaml

# 5. Проверить статус
kubectl get pods -n marketplace-bot-prod
```

## Детальная настройка

### 1. Установка K3s

Установить лёгкую версию Kubernetes:

```bash
curl -sfL https://get.k3s.io | sh -
sudo systemctl status k3s
```

Настроить kubectl доступ:

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
export KUBECONFIG=~/.kube/config
```

Проверка:

```bash
kubectl get nodes
```

### 2. Установка ArgoCD

Установить hardened-манифест ArgoCD (патчи задают requests/limits для repo-server, ограничивают параллелизм и смягчают probes, чтобы ArgoCD устойчиво работал на слабых узлах):

```bash
kubectl create namespace argocd
kubectl apply -k k8s/argocd/install -n argocd
```

Дождаться запуска подов:

```bash
kubectl wait --for=condition=Ready pods --all -n argocd --timeout=300s
```

Получить пароль администратора:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

Доступ к ArgoCD UI:

```bash
# Port-forward
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Открыть: https://localhost:8080
# Логин: admin
# Пароль: <из предыдущего шага>
```

### 3. Настройка секретов

Создать секреты для обоих окружений:

```bash
# Production
kubectl create secret generic bot-secrets -n marketplace-bot-prod \
  --from-literal=BOT_TOKEN='your_prod_bot_token' \
  --from-literal=POSTGRES_PASSWORD='secure_password'

# Development
kubectl create secret generic bot-secrets -n marketplace-bot-dev \
  --from-literal=BOT_TOKEN='your_dev_bot_token' \
  --from-literal=POSTGRES_PASSWORD='dev_password'
```

**Важно:** Секреты не управляются через ArgoCD во избежание случайной перезаписи.

### 4. Развёртывание приложений

Развернуть production:

```bash
kubectl apply -f k8s/argocd/application-prod.yaml
```

Развернуть development:

```bash
kubectl apply -f k8s/argocd/application-dev.yaml
```

### 5. Проверка развёртывания

Проверить статус приложений:

```bash
kubectl get applications -n argocd
```

Проверить поды:

```bash
kubectl get pods -n marketplace-bot-prod
kubectl get pods -n marketplace-bot-dev
```

Просмотр логов:

```bash
kubectl logs -f deployment/marketplace-bot -n marketplace-bot-prod
kubectl logs -f deployment/postgres -n marketplace-bot-prod
```

## Архитектура

```
GitHub Repository (main branch)
    ↓
ArgoCD (опрос каждые 3 мин)
    ↓
K3s Cluster
    ├── Namespace: marketplace-bot-prod
    │   ├── PostgreSQL (PVC: 5Gi)
    │   └── Bot (ресурсы: 512Mi-1Gi)
    └── Namespace: marketplace-bot-dev
        ├── PostgreSQL (emptyDir)
        └── Bot (ресурсы: 256Mi-512Mi)
```

## GitOps процесс

### Деплой в Production

1. Push в ветку `main`
2. CI собирает и публикует Docker образ с тегом `latest`
3. ArgoCD обнаруживает изменения (авто-синхронизация включена)
4. K3s применяет манифесты из `k8s/overlays/production/`
5. Rolling update без даунтайма

### Деплой в Development/тестирование PR

1. Открыть Pull Request
2. CI собирает образ с тегом `sha-{commit}`
3. Workflow `deploy-pr-to-dev` обновляет `k8s/overlays/dev/kustomization.yaml`
4. Коммитит изменения в ветку `main`
5. ArgoCD синхронизирует и деплоит образ PR в dev namespace

## Конфигурация

### Лимиты ресурсов

**Production:**
- Bot: 512Mi-1Gi RAM, 500m-1000m CPU
- PostgreSQL: 512Mi-1Gi RAM, 500m-1000m CPU

**Development:**
- Bot: 256Mi-512Mi RAM, 250m-500m CPU
- PostgreSQL: 256Mi-512Mi RAM, 250m-500m CPU

### Переменные окружения

Настраиваются через ConfigMap (`k8s/base/configmap.yaml`):

- `LOG_LEVEL`: Уровень логирования (по умолчанию: INFO)
- `AUTO_MIGRATE`: Авто-запуск Alembic миграций (по умолчанию: true)
- `PRICE_CHECK_HOURS`: Часы проверки цен (по умолчанию: 9,15,21)
- `POSTGRES_DB`: Имя базы данных
- `POSTGRES_USER`: Пользователь базы данных
- `METRICS_ENABLED`: Включить/отключить Prometheus-эндпоинт (по умолчанию: true)
- `METRICS_HOST`: Хост для HTTP-сервера метрик (по умолчанию: 0.0.0.0)
- `METRICS_PORT`: Порт эндпоинта (по умолчанию: 8000)

### Мониторинг и метрики

- Эндпоинт `http://<pod-ip>:8000/metrics` (контролируется `METRICS_HOST`/`METRICS_PORT`) отдаёт Prometheus-совместимые метрики.
- В `k8s/base/service.yaml` описан ClusterIP Service c аннотациями `prometheus.io/*`, поэтому Prometheus Operator автоматически подхватит таргет (или нужно подключить ServiceMonitor по тем же меткам `app: marketplace-price-tracker`).
- Переменная `METRICS_ENABLED` управляет запуском HTTP-сервера (по умолчанию включён).

#### Prometheus + Grafana через ArgoCD

- В репозитории добавлен отдельный Kustomize слой `k8s/monitoring/` (common + overlays per env) c Prometheus CR, ServiceMonitor и Grafana Operator CR.
- Мониторинг теперь развёртывается отдельными ArgoCD-приложениями (`k8s/argocd/application-monitoring-{dev,prod}.yaml`), а `application-{dev,prod}.yaml` управляют самим ботом. Такой подход устраняет конфликт namespace, упрощает права RBAC и позволяет обновлять стек наблюдения независимо от приложения.
- Для работы требуется установленный Prometheus Operator & Grafana Operator (см. kube-prometheus-stack или CRDs). Репозиторий предполагает, что CRDs уже присутствуют в кластере.
- Dev overlay использует namespace `monitoring-dev` c PVC 5Gi и дефолтным admin/admin паролем; prod - namespace `monitoring`, retention 15d и отдельный пароль (см. `k8s/monitoring/production/patches`).
- Grafana в автоматическом режиме подцепит дашборд из ConfigMap `marketplace-grafana-dashboards`. Для доступа используйте port-forward: `kubectl port-forward svc/marketplace-grafana -n monitoring 3000:3000` (или `monitoring-dev`).
- Prometheus доступен через `kubectl port-forward svc/marketplace-prometheus -n monitoring 9090:9090`.

##### Требования к операторам

Перед первой синхронизацией мониторинга в кластере уже должны работать Prometheus Operator и Grafana Operator, иначе создаваемые ArgoCD CR просто повиснут без контроллеров. Есть два типовых способа установки:

**Через kubectl (server-side apply).** Такой режим обязателен для Prometheus CRD из-за ограничения Kubernetes на размер аннотаций (`kubectl.kubernetes.io/last-applied-configuration`):

```bash
# Prometheus Operator (кластерный bundle, CRD + контроллер)
kubectl apply --server-side --force-conflicts \
  -f https://github.com/prometheus-operator/prometheus-operator/releases/latest/download/bundle.yaml

# Grafana Operator (кластерный kustomize + отдельные CRD)
kubectl apply --server-side --force-conflicts \
  -f https://github.com/grafana/grafana-operator/releases/download/v5.20.0/kustomize-cluster_scoped.yaml
kubectl apply --server-side --force-conflicts \
  -f https://github.com/grafana/grafana-operator/releases/download/v5.20.0/crds.yaml
```

После применения следует проверить, что поды операторов в `prometheus-operator`/`grafana` namespace находятся в `Running`, а среди CRD присутствуют объекты `*.monitoring.coreos.com` и `*.grafana.integreatly.org` (например, `grafanas.grafana.integreatly.org`).

**Через Helm**:

```bash
# Prometheus Operator (без bundled Prometheus/Grafana)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install prometheus-operator prometheus-community/kube-prometheus-stack \
  --namespace monitoring-operators --create-namespace \
  --set grafana.enabled=false --set prometheus.enabled=false --set alertmanager.enabled=false

# Grafana Operator
helm repo add grafana https://grafana.github.io/helm-charts
helm upgrade --install grafana-operator grafana/grafana-operator \
  --namespace monitoring-operators --create-namespace
```

Любой другой способ (OLM, Terraform и т.д.) тоже подходит - главное, чтобы перед синхронизацией ArgoCD уже существовали CRD `prometheuses.monitoring.coreos.com`, `servicemonitors.monitoring.coreos.com`, `grafanas.grafana.integreatly.org` и управляющие их операторы.

##### Настройка учётных данных Grafana

По умолчанию логин/пароль задаются прямо в манифестах:

- Dev: `k8s/monitoring/dev/patches/grafana-auth.yaml` (admin/admin)
- Prod: `k8s/monitoring/production/patches/grafana-auth.yaml` (admin/admin)

Отредактируйте соответствующий файл перед деплоем (или переопределите patch через Kustomize) и задокументируйте реальные значения в менеджере секретов. После изменения пароля сделайте `git commit` и синхронизируйте ArgoCD - Grafana перезапустится с новыми кредами.

## Управление базой данных

### Бэкап

Автоматические резервные копии запускает CronJob `postgres-backup` каждый день в 02:00 UTC. Каждый запуск сохраняет файл `/backup/price_tracker_bot-<timestamp>.sql` в PVC `postgres-backup-pvc` и параллельно копирует его в `/srv/backups/price-tracker` на хосте, поэтому свежие дампы переживают и рестарты подов, и потенциальную потерю PVC.

```bash
# Проверить расписание и последние джобы
kubectl get cronjob -n marketplace-bot-prod postgres-backup
kubectl get jobs -n marketplace-bot-prod -l component=postgres-backup --sort-by=.metadata.creationTimestamp

# Скачать последнюю копию из зеркала на узле
ssh root@<server> "ls -1t /srv/backups/price-tracker | head -n 1"
scp root@<server>:/srv/backups/price-tracker/price_tracker_bot-<timestamp>.sql ./price_tracker_bot.sql
```

Ручной дамп (например перед рискованными изменениями) по‑прежнему доступен:

```bash
kubectl exec -n marketplace-bot-prod deployment/postgres -- \
  pg_dump -U admin price_tracker_bot > backup-$(date +%Y%m%d).sql
```

### Восстановление

```bash
kubectl cp backup.sql -n marketplace-bot-prod postgres-pod:/tmp/restore.sql
kubectl exec -n marketplace-bot-prod postgres-pod -- \
  PGPASSWORD=$(kubectl get secret bot-secrets -n marketplace-bot-prod -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d) \
  psql -U admin -d price_tracker_bot -f /tmp/restore.sql
```

### Подключение через DBeaver

```bash
# Port-forward PostgreSQL
kubectl port-forward -n marketplace-bot-prod svc/postgres 5433:5432

# Настройки DBeaver:
# Хост: localhost
# Порт: 5433
# База данных: price_tracker_bot
# Имя пользователя: admin
# Пароль: <из секрета>
```

## Мониторинг

Просмотр статуса приложения:

```bash
# ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Логи
kubectl logs -f -l app=marketplace-price-tracker -n marketplace-bot-prod

# События
kubectl get events -n marketplace-bot-prod --sort-by='.lastTimestamp'

# Использование ресурсов
kubectl top pods -n marketplace-bot-prod
```

## Troubleshooting

### Под не запускается

```bash
kubectl describe pod -n marketplace-bot-prod <pod-name>
kubectl logs -n marketplace-bot-prod <pod-name> --previous
```

### ArgoCD синхронизация провалилась

```bash
kubectl get application marketplace-bot-prod -n argocd -o yaml
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller
```

### Проблемы с подключением к БД

```bash
kubectl get pods -n marketplace-bot-prod -l app=postgres
kubectl logs -n marketplace-bot-prod -l app=postgres
kubectl exec -n marketplace-bot-prod postgres-pod -- psql -U admin -l
```

### Ошибки при pull образа

Проверить наличие образа:

```bash
docker manifest inspect ghcr.io/vshulcz/marketplace_price_tracker:latest
```

Проверить завершение CI:

```bash
gh run list --workflow=ci.yml --limit 5
```

## Откат версии

Через ArgoCD UI:
1. Открыть приложение
2. Перейти в "History"
3. Выбрать предыдущую версию
4. Нажать "Rollback"

Через CLI:

```bash
kubectl rollout undo deployment/marketplace-bot -n marketplace-bot-prod
```

## Обслуживание

### Обновление приложения

Push изменения в ветку `main`. ArgoCD автоматически синхронизирует в течение 3 минут.

Принудительная синхронизация:

```bash
kubectl patch application marketplace-bot-prod -n argocd --type merge \
  -p '{"operation":{"sync":{"revision":"HEAD"}}}'
```

### Масштабирование

```bash
kubectl scale deployment marketplace-bot -n marketplace-bot-prod --replicas=2
```

### Обновление секретов

```bash
kubectl delete secret bot-secrets -n marketplace-bot-prod
kubectl create secret generic bot-secrets -n marketplace-bot-prod \
  --from-literal=BOT_TOKEN='new_token' \
  --from-literal=POSTGRES_PASSWORD='new_password'
kubectl rollout restart deployment/marketplace-bot -n marketplace-bot-prod
kubectl rollout restart deployment/postgres -n marketplace-bot-prod
```

## Удалённый доступ

Для удалённого доступа `kubectl` с локальной машины:

```bash
# На сервере
sudo cat /etc/rancher/k3s/k3s.yaml

# На локальной машине
mkdir -p ~/.kube
nano ~/.kube/config
# Вставить содержимое, изменить server: https://<server-ip>:6443

kubectl get nodes
```

## Безопасность

- Секреты хранятся в Kubernetes, не в Git
- Образы загружаются из GHCR (приватный по умолчанию)
- PostgreSQL не доступен извне (ClusterIP service)
- Использовать сильные пароли для production
- Регулярные бэкапы рекомендуются

## Интеграция CI/CD

GitHub Actions workflows:

- `.github/workflows/ci.yml`: Тесты, lint, сборка Docker образа
- `.github/workflows/deploy-pr-to-dev.yaml`: Авто-деплой PR в dev
- `.github/workflows/deploy-k3s-argocd.yaml`: Ручной деплой в production

## Дополнительная информация

- [K3s Документация](https://docs.k3s.io/)
- [ArgoCD Документация](https://argo-cd.readthedocs.io/)
- [Kustomize Документация](https://kubectl.docs.kubernetes.io/references/kustomize/)
