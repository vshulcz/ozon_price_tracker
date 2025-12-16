# Deployment Guide

Production-ready deployment using K3s and ArgoCD for GitOps continuous delivery.

## Prerequisites

- Fresh Ubuntu/Debian server (4GB+ RAM, 20GB+ disk)
- Root/sudo access
- Domain name (optional, for ArgoCD UI)

## Quick Start

```bash
# 1. Install K3s
curl -sfL https://get.k3s.io | sh -

# 2. Install ArgoCD
kubectl create namespace argocd
kubectl apply -k k8s/argocd/install -n argocd

# 3. Create secrets
kubectl create secret generic bot-secrets -n marketplace-bot-prod \
  --from-literal=BOT_TOKEN='your_telegram_bot_token' \
  --from-literal=POSTGRES_PASSWORD='your_db_password'

# 4. Deploy application
kubectl apply -f k8s/argocd/application-prod.yaml

# 5. Monitor deployment
kubectl get pods -n marketplace-bot-prod
```

## Detailed Setup

### 1. K3s Installation

Install lightweight Kubernetes:

```bash
curl -sfL https://get.k3s.io | sh -
sudo systemctl status k3s
```

Configure kubectl access:

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
export KUBECONFIG=~/.kube/config
```

Verify:

```bash
kubectl get nodes
```

#### Linking your local kubectl to K3s

To manage the cluster from your laptop, copy the kubeconfig from the server:

```bash
scp root@<server>:/etc/rancher/k3s/k3s.yaml ~/.kube/k3s-marketplace.yaml
```

Replace the default `https://127.0.0.1:6443` server entry with the public IP/DNS of the node:

```bash
SERVER_IP=<your_public_ip>
sed -i '' "s/127.0.0.1/${SERVER_IP}/" ~/.kube/k3s-marketplace.yaml
```

Merge the file with your existing kubeconfig:

```bash
KUBECONFIG=$HOME/.kube/config:$HOME/.kube/k3s-marketplace.yaml \
  kubectl config view --flatten > $HOME/.kube/config-merged
mv $HOME/.kube/config-merged $HOME/.kube/config
```

Rename the new context for clarity:

```bash
kubectl config rename-context default k3s-marketplace
```

You can now target the cluster explicitly:

```bash
kubectl --context k3s-marketplace get pods -A
```

### 2. ArgoCD Installation

Install the hardened ArgoCD manifest (adds repo-server resource requests, relaxed probes, and limited parallelism so it survives on small clusters):

```bash
kubectl create namespace argocd
kubectl apply -k k8s/argocd/install -n argocd
```

Wait for pods:

```bash
kubectl wait --for=condition=Ready pods --all -n argocd --timeout=300s
```

Get admin password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

Access ArgoCD UI:

```bash
# Port-forward
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open: https://localhost:8080
# Login: admin
# Password: <from previous step>
```

### 3. Configure Secrets

Create secrets for both environments:

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

**Note:** Secrets are not managed by ArgoCD to prevent accidental overwrites.

### 4. Deploy Applications

Deploy production:

```bash
kubectl apply -f k8s/argocd/application-prod.yaml
```

Deploy development:

```bash
kubectl apply -f k8s/argocd/application-dev.yaml
```

### 5. Verify Deployment

Check application status:

```bash
kubectl get applications -n argocd
```

Check pods:

```bash
kubectl get pods -n marketplace-bot-prod
kubectl get pods -n marketplace-bot-dev
```

View logs:

```bash
kubectl logs -f deployment/marketplace-bot -n marketplace-bot-prod
kubectl logs -f deployment/postgres -n marketplace-bot-prod
```

## Architecture

```
GitHub Repository (main branch)
    ↓
ArgoCD (polls every 3 min)
    ↓
K3s Cluster
    ├── Namespace: marketplace-bot-prod
    │   ├── PostgreSQL (PVC: 5Gi)
    │   └── Bot (resources: 512Mi-1Gi)
    └── Namespace: marketplace-bot-dev
        ├── PostgreSQL (emptyDir)
        └── Bot (resources: 256Mi-512Mi)
```

## GitOps Workflow

### Production Deployment

1. Push to `main` branch
2. CI builds and publishes Docker image with `latest` tag
3. ArgoCD detects changes (auto-sync enabled)
4. K3s applies manifests from `k8s/overlays/production/`
5. Rolling update with zero downtime

### Development/PR Testing

1. Open Pull Request
2. CI builds image with `sha-{commit}` tag
3. `deploy-pr-to-dev` workflow updates `k8s/overlays/dev/kustomization.yaml`
4. Commits change to `main` branch
5. ArgoCD syncs and deploys PR image to dev namespace

## Configuration

### Resource Limits

**Production:**
- Bot: 512Mi-1Gi RAM, 500m-1000m CPU
- PostgreSQL: 512Mi-1Gi RAM, 500m-1000m CPU

**Development:**
- Bot: 256Mi-512Mi RAM, 250m-500m CPU
- PostgreSQL: 256Mi-512Mi RAM, 250m-500m CPU

### Environment Variables

Configured via ConfigMap (`k8s/base/configmap.yaml`):

- `LOG_LEVEL`: Logging level (default: INFO)
- `AUTO_MIGRATE`: Run Alembic migrations automatically (default: true)
- `PRICE_CHECK_HOURS`: Comma-separated hours for price checks (default: 9,15,21)
- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database user
- `METRICS_ENABLED`: Toggle Prometheus endpoint (default: true)
- `METRICS_HOST`: Host for the metrics HTTP server (default: 0.0.0.0)
- `METRICS_PORT`: Port for the endpoint (default: 8000)
- `OZON_COOKIE_PATH`: File path for cached Ozon anti-bot cookies (defaults to `.ozon_cookies.json` in the app directory)

### Monitoring & metrics

- The bot exposes a Prometheus endpoint on `http://<pod-ip>:8000/metrics` (tunable through `METRICS_HOST`/`METRICS_PORT`).
- `k8s/base/service.yaml` adds a ClusterIP Service with `prometheus.io/*` annotations, so Prometheus Operator or any standard Prometheus scrape config can discover it via the `app=marketplace-price-tracker` label.
- Use `METRICS_ENABLED=false` if you need to disable metrics in specific environments.

#### Prometheus + Grafana via ArgoCD

- The repo ships with a dedicated Kustomize stack under `k8s/monitoring/` (common + env overlays) that defines Prometheus CR, ServiceMonitor, Grafana Operator CR and dashboard ConfigMap.
- The monitoring stack is deployed via dedicated ArgoCD applications (`k8s/argocd/application-monitoring-{dev,prod}.yaml`), while `k8s/argocd/application-{dev,prod}.yaml` handle the bot itself. This separation prevents namespace conflicts, simplifies RBAC, and lets you roll out observability independently.
- The dev overlay uses the `monitoring-dev` namespace with a 5Gi PVC, 3-day retention and default admin/admin credentials; prod uses `monitoring`, 50Gi PVC, 15-day retention and a stronger password from `k8s/monitoring/production/patches`.
- Grafana automatically mounts dashboards from the `marketplace-grafana-dashboards` ConfigMap. Access it via `kubectl port-forward svc/marketplace-grafana -n monitoring 3000:3000` (or `monitoring-dev`).
- Prometheus is exposed through `svc/marketplace-prometheus`; use `kubectl port-forward svc/marketplace-prometheus -n monitoring 9090:9090` to open the UI locally.

##### Operator prerequisites

Before the first sync of the monitoring overlay you must have both Prometheus Operator and Grafana Operator (their CRDs + controllers) installed in the cluster, otherwise the CR objects created by ArgoCD will never reconcile. Two common approaches:

**Via kubectl (server-side apply).** This mode is required for Prometheus CRDs because standard `kubectl apply` would exceed the annotation size limit.

```bash
# Prometheus Operator (cluster-wide bundle: CRD + controller)
kubectl apply --server-side --force-conflicts \
  -f https://github.com/prometheus-operator/prometheus-operator/releases/latest/download/bundle.yaml

# Grafana Operator (cluster-scoped kustomize + CRDs)
kubectl apply --server-side --force-conflicts \
  -f https://github.com/grafana/grafana-operator/releases/download/v5.20.0/kustomize-cluster_scoped.yaml
kubectl apply --server-side --force-conflicts \
  -f https://github.com/grafana/grafana-operator/releases/download/v5.20.0/crds.yaml
```

After applying, confirm the controllers are `Running` in the `prometheus-operator` / `grafana` namespaces and that CRDs such as `prometheuses.monitoring.coreos.com` and `grafanas.grafana.integreatly.org` (note the extra `.grafana.` segment) exist.

**Via Helm.** If you prefer Helm charts:

```bash
# Prometheus Operator (without bundled Prometheus/Grafana instances)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm upgrade --install prometheus-operator prometheus-community/kube-prometheus-stack \
  --namespace monitoring-operators --create-namespace \
  --set grafana.enabled=false --set prometheus.enabled=false --set alertmanager.enabled=false

# Grafana Operator
helm repo add grafana https://grafana.github.io/helm-charts
helm upgrade --install grafana-operator grafana/grafana-operator \
  --namespace monitoring-operators --create-namespace
```

Any other method (OLM, Terraform, etc.) works too-the critical requirement is that CRDs like `prometheuses.monitoring.coreos.com`, `servicemonitors.monitoring.coreos.com`, and `grafanas.grafana.integreatly.org` plus their operators are present before ArgoCD applies our monitoring stack.

##### Configuring Grafana credentials

Admin login/password values live directly in the Kustomize patches:

- Dev: `k8s/monitoring/dev/patches/grafana-auth.yaml` (admin/admin)
- Production: `k8s/monitoring/production/patches/grafana-auth.yaml` (admin/admin)

Edit those files (or provide your own overlay) to set environment-specific credentials. After committing the change and letting ArgoCD sync, Grafana pods restart with the new password - make sure to store the real values in your secrets manager/runbook for future reference.

##### Grafana alerts

`k8s/monitoring/common/grafana-alerts.yaml` provisions a `GrafanaRule` folder called “Marketplace Alerts” with several rules wired to the runbooks in this document:

- `Ozon price scraper failures`/`Wildberries price scraper failures` trigger when `marketplace_bot_requests_total` reports ≥3 non-success results for the respective marketplace within 5 minutes (cookie/run blocking issues).
- `Scheduler stalled` fires if no successful run was recorded for 10 minutes.
- `Price refresh errors` watches `marketplace_bot_price_check_errors_total` and alerts once ≥3 products failed inside 15 minutes.
- `Refresh queue stuck` uses the `marketplace_bot_products_refresh_inflight` gauge to detect queues above 30 items for 10 minutes.
- `Scraper latency p95 high` detects `marketplace_bot_request_duration_seconds_bucket` p95 >20 s for at least 5 minutes.
- `Scheduler error rate` triggers when `marketplace_bot_scheduler_runs_total{status!="success"}` increases, indicating the cron job aborted.

After syncing the overlay:

1. Go to Grafana → Alerting → Contact points and configure the destination (email, Slack, Telegram, etc.).
2. In Alerting → Notification policies, route alerts from the “Marketplace Alerts” folder to that contact point.
3. Tune any rule (threshold, lookback window, or datasource UID) directly in the YAML if your environment needs different limits.


## Database Management

### Backup

Nightly automated backups run at 02:00 UTC via the `postgres-backup` CronJob. Every run produces `/backup/price_tracker_bot-<timestamp>.sql` inside the `postgres-backup-pvc` volume and simultaneously mirrors the file to `/srv/backups/price-tracker` on the host, so the most recent copies survive both pod restarts and PVC loss.

```bash
# Inspect schedule and last run
kubectl get cronjob -n marketplace-bot-prod postgres-backup
kubectl get jobs -n marketplace-bot-prod -l component=postgres-backup --sort-by=.metadata.creationTimestamp

# Download the newest backup file to your machine from the hostPath mirror
ssh root@<server> "ls -1t /srv/backups/price-tracker | head -n 1"
scp root@<server>:/srv/backups/price-tracker/price_tracker_bot-<timestamp>.sql ./price_tracker_bot.sql
```

Manual on-demand dump (for example, before risky changes) is still available:

```bash
kubectl exec -n marketplace-bot-prod deployment/postgres -- \
  pg_dump -U admin price_tracker_bot > backup-$(date +%Y%m%d).sql
```

### Restore

```bash
kubectl cp backup.sql -n marketplace-bot-prod postgres-pod:/tmp/restore.sql
kubectl exec -n marketplace-bot-prod postgres-pod -- \
  PGPASSWORD=$(kubectl get secret bot-secrets -n marketplace-bot-prod -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d) \
  psql -U admin -d price_tracker_bot -f /tmp/restore.sql
```

### Connect via DBeaver

```bash
# Port-forward PostgreSQL
kubectl port-forward -n marketplace-bot-prod svc/postgres 5433:5432

# DBeaver settings:
# Host: localhost
# Port: 5433
# Database: price_tracker_bot
# Username: admin
# Password: <from secret>
```

## Monitoring

View application status:

```bash
# ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Logs
kubectl logs -f -l app=marketplace-price-tracker -n marketplace-bot-prod

# Events
kubectl get events -n marketplace-bot-prod --sort-by='.lastTimestamp'

# Resource usage
kubectl top pods -n marketplace-bot-prod
```

## Troubleshooting

### Pod not starting

```bash
kubectl describe pod -n marketplace-bot-prod <pod-name>
kubectl logs -n marketplace-bot-prod <pod-name> --previous
```

### ArgoCD sync failed

```bash
kubectl get application marketplace-bot-prod -n argocd -o yaml
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller
```

### Database connection issues

```bash
kubectl get pods -n marketplace-bot-prod -l app=postgres
kubectl logs -n marketplace-bot-prod -l app=postgres
kubectl exec -n marketplace-bot-prod postgres-pod -- psql -U admin -l
```

### Image pull errors

Check image exists:

```bash
docker manifest inspect ghcr.io/vshulcz/marketplace_price_tracker:latest
```

Verify CI completed:

```bash
gh run list --workflow=ci.yml --limit 5
```

### Price refresh errors

1. Inspect the scheduler logs to locate the failing product IDs and stack traces:

```bash
kubectl logs -n marketplace-bot-prod deploy/marketplace-bot | grep -E "price_check|Failed to refresh product"
```

2. Open Grafana’s “Price refresh errors (30m)” panel to confirm whether the failures are isolated to one marketplace or affect everything.
3. For per-product issues (for example, the link is dead or requires authentication), temporarily disable that product in PostgreSQL:

```bash
kubectl exec -n marketplace-bot-prod deploy/postgres -- \
  psql -U admin -d price_tracker_bot \
  -c "update products set is_active=false where id=<problem-id>;"
```

4. If errors are HTTP-related, run the local probe (`PYTHONPATH=. uv run python test.py --log-level DEBUG --url <product-url>`) from within the bot pod to reproduce and capture more context.

### Refresh queue backlog

1. When the “Inflight products” panel and the `Refresh queue stuck` alert stay high, first confirm that the scheduler loop is still making progress:

```bash
kubectl logs -n marketplace-bot-prod deploy/marketplace-bot | grep price_check_started
```

2. Check whether the scrapers are blocked (Ozon/Wildberries alerts) or slow (see the latency runbook below)—backlogs frequently originate there.
3. Scale the worker temporarily if you simply need more concurrency:

```bash
kubectl scale deployment marketplace-bot -n marketplace-bot-prod --replicas=2
```

4. After the queue drains, return to the normal replica count and consider raising resources permanently or splitting refresh windows if the inflight metric frequently exceeds 30 (this metric is also the target for future autoscaling controllers).

### Slow scraper latency

1. Open the “Request latency p95” panel and switch the legend to see which marketplace breaches the threshold.
2. Check the bot logs for timeouts or Playwright warnings:

```bash
kubectl logs -n marketplace-bot-prod deploy/marketplace-bot | grep -E "timeout|challenge|chromium"
```

3. Execute a quick network smoke test from the pod to verify outbound access:

```bash
kubectl exec -n marketplace-bot-prod deploy/marketplace-bot -- \
  curl -I https://www.ozon.ru/product/000000/
```

4. If latency only affects Ozon, refresh cookies (see below) and restart the deployment; for Wildberries investigate recent site changes.

### Scheduler errors

1. Look at the `scheduler_runs_total` panel to see whether runs end in `failed`.
2. Tail the scheduler logs to grab the stack trace:

```bash
kubectl logs -n marketplace-bot-prod deploy/marketplace-bot | grep -A5 -B1 "scheduler"
```

3. Verify PostgreSQL availability (`kubectl logs -n marketplace-bot-prod -l app=postgres`) and restart the deployment if the scheduler crashed.
4. After fixing the underlying issue, restart the deployment to trigger a fresh run immediately:

```bash
kubectl rollout restart deployment marketplace-bot -n marketplace-bot-prod
```

### Resetting Ozon cookies

The anti-bot challenge is solved once and the resulting cookies are cached in `.ozon_cookies.json` (or whatever `OZON_COOKIE_PATH` points to). The file lives inside `/app` in the bot container, so removing it forces the next request to re-run the challenge and refresh the cache:

```bash
kubectl exec -n marketplace-bot-prod deploy/marketplace-bot -- \
  rm -f /app/.ozon_cookies.json
```

If you want the cookies to survive pod restarts you can mount a small PVC or hostPath volume and set `OZON_COOKIE_PATH` accordingly.

## Rollback

Via ArgoCD UI:
1. Open application
2. Go to "History"
3. Select previous version
4. Click "Rollback"

Via CLI:

```bash
kubectl rollout undo deployment/marketplace-bot -n marketplace-bot-prod
```

## Maintenance

### Update application

Push changes to `main` branch. ArgoCD will auto-sync within 3 minutes.

Force sync:

```bash
kubectl patch application marketplace-bot-prod -n argocd --type merge \
  -p '{"operation":{"sync":{"revision":"HEAD"}}}'
```

### Scale deployment

```bash
kubectl scale deployment marketplace-bot -n marketplace-bot-prod --replicas=2
```

### Update secrets

```bash
kubectl delete secret bot-secrets -n marketplace-bot-prod
kubectl create secret generic bot-secrets -n marketplace-bot-prod \
  --from-literal=BOT_TOKEN='new_token' \
  --from-literal=POSTGRES_PASSWORD='new_password'
kubectl rollout restart deployment/marketplace-bot -n marketplace-bot-prod
kubectl rollout restart deployment/postgres -n marketplace-bot-prod
```

## Remote Access

For remote `kubectl` access from local machine:

```bash
# On server
sudo cat /etc/rancher/k3s/k3s.yaml

# On local machine
mkdir -p ~/.kube
nano ~/.kube/config
# Paste content, change server: https://<server-ip>:6443

kubectl get nodes
```

## Security Notes

- Secrets stored in Kubernetes, not in Git
- Images pulled from GHCR (private by default)
- PostgreSQL not exposed externally (ClusterIP service)
- Use strong passwords for production
- Regular backups recommended

## CI/CD Integration

GitHub Actions workflows:

- `.github/workflows/ci.yml`: Test, lint, build Docker image
- `.github/workflows/deploy-pr-to-dev.yaml`: Auto-deploy PRs to dev
- `.github/workflows/deploy-k3s-argocd.yaml`: Manual production deployment

## Further Reading

- [K3s Documentation](https://docs.k3s.io/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Kustomize Documentation](https://kubectl.docs.kubernetes.io/references/kustomize/)
