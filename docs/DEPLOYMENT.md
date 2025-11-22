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
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 3. Создать секреты
kubectl create secret generic bot-secrets -n ozon-bot-prod \
  --from-literal=BOT_TOKEN='your_telegram_bot_token' \
  --from-literal=POSTGRES_PASSWORD='your_db_password'

# 4. Задеплоить приложение
kubectl apply -f k8s/argocd/application-prod.yaml

# 5. Проверить статус
kubectl get pods -n ozon-bot-prod
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

Установить ArgoCD:

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
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
kubectl create secret generic bot-secrets -n ozon-bot-prod \
  --from-literal=BOT_TOKEN='your_prod_bot_token' \
  --from-literal=POSTGRES_PASSWORD='secure_password'

# Development
kubectl create secret generic bot-secrets -n ozon-bot-dev \
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
kubectl get pods -n ozon-bot-prod
kubectl get pods -n ozon-bot-dev
```

Просмотр логов:

```bash
kubectl logs -f deployment/ozon-bot -n ozon-bot-prod
kubectl logs -f deployment/postgres -n ozon-bot-prod
```

## Архитектура

```
GitHub Repository (main branch)
    ↓
ArgoCD (опрос каждые 3 мин)
    ↓
K3s Cluster
    ├── Namespace: ozon-bot-prod
    │   ├── PostgreSQL (PVC: 5Gi)
    │   └── Bot (ресурсы: 512Mi-1Gi)
    └── Namespace: ozon-bot-dev
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

## Управление базой данных

### Бэкап

```bash
kubectl exec -n ozon-bot-prod deployment/postgres -- \
  pg_dump -U admin price_tracker_bot > backup-$(date +%Y%m%d).sql
```

### Восстановление

```bash
kubectl cp backup.sql -n ozon-bot-prod postgres-pod:/tmp/restore.sql
kubectl exec -n ozon-bot-prod postgres-pod -- \
  psql -U admin -d price_tracker_bot -f /tmp/restore.sql
```

### Подключение через DBeaver

```bash
# Port-forward PostgreSQL
kubectl port-forward -n ozon-bot-prod svc/postgres 5433:5432

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
kubectl logs -f -l app=ozon-bot -n ozon-bot-prod

# События
kubectl get events -n ozon-bot-prod --sort-by='.lastTimestamp'

# Использование ресурсов
kubectl top pods -n ozon-bot-prod
```

## Troubleshooting

### Под не запускается

```bash
kubectl describe pod -n ozon-bot-prod <pod-name>
kubectl logs -n ozon-bot-prod <pod-name> --previous
```

### ArgoCD синхронизация провалилась

```bash
kubectl get application ozon-bot-prod -n argocd -o yaml
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller
```

### Проблемы с подключением к БД

```bash
kubectl get pods -n ozon-bot-prod -l app=postgres
kubectl logs -n ozon-bot-prod -l app=postgres
kubectl exec -n ozon-bot-prod postgres-pod -- psql -U admin -l
```

### Ошибки при pull образа

Проверить наличие образа:

```bash
docker manifest inspect ghcr.io/vshulcz/ozon_price_tracker:latest
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
kubectl rollout undo deployment/ozon-bot -n ozon-bot-prod
```

## Обслуживание

### Обновление приложения

Push изменения в ветку `main`. ArgoCD автоматически синхронизирует в течение 3 минут.

Принудительная синхронизация:

```bash
kubectl patch application ozon-bot-prod -n argocd --type merge \
  -p '{"operation":{"sync":{"revision":"HEAD"}}}'
```

### Масштабирование

```bash
kubectl scale deployment ozon-bot -n ozon-bot-prod --replicas=2
```

### Обновление секретов

```bash
kubectl delete secret bot-secrets -n ozon-bot-prod
kubectl create secret generic bot-secrets -n ozon-bot-prod \
  --from-literal=BOT_TOKEN='new_token' \
  --from-literal=POSTGRES_PASSWORD='new_password'
kubectl rollout restart deployment/ozon-bot -n ozon-bot-prod
kubectl rollout restart deployment/postgres -n ozon-bot-prod
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
