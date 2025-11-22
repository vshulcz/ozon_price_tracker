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
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 3. Create secrets
kubectl create secret generic bot-secrets -n ozon-bot-prod \
  --from-literal=BOT_TOKEN='your_telegram_bot_token' \
  --from-literal=POSTGRES_PASSWORD='your_db_password'

# 4. Deploy application
kubectl apply -f k8s/argocd/application-prod.yaml

# 5. Monitor deployment
kubectl get pods -n ozon-bot-prod
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

### 2. ArgoCD Installation

Install ArgoCD:

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
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
kubectl create secret generic bot-secrets -n ozon-bot-prod \
  --from-literal=BOT_TOKEN='your_prod_bot_token' \
  --from-literal=POSTGRES_PASSWORD='secure_password'

# Development
kubectl create secret generic bot-secrets -n ozon-bot-dev \
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
kubectl get pods -n ozon-bot-prod
kubectl get pods -n ozon-bot-dev
```

View logs:

```bash
kubectl logs -f deployment/ozon-bot -n ozon-bot-prod
kubectl logs -f deployment/postgres -n ozon-bot-prod
```

## Architecture

```
GitHub Repository (main branch)
    ↓
ArgoCD (polls every 3 min)
    ↓
K3s Cluster
    ├── Namespace: ozon-bot-prod
    │   ├── PostgreSQL (PVC: 5Gi)
    │   └── Bot (resources: 512Mi-1Gi)
    └── Namespace: ozon-bot-dev
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
- `AUTO_MIGRATE`: Auto-run Alembic migrations (default: true)
- `PRICE_CHECK_HOURS`: Hours for price checks (default: 9,15,21)
- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database user

## Database Management

### Backup

```bash
kubectl exec -n ozon-bot-prod deployment/postgres -- \
  pg_dump -U admin price_tracker_bot > backup-$(date +%Y%m%d).sql
```

### Restore

```bash
kubectl cp backup.sql -n ozon-bot-prod postgres-pod:/tmp/restore.sql
kubectl exec -n ozon-bot-prod postgres-pod -- \
  psql -U admin -d price_tracker_bot -f /tmp/restore.sql
```

### Connect via DBeaver

```bash
# Port-forward PostgreSQL
kubectl port-forward -n ozon-bot-prod svc/postgres 5433:5432

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
kubectl logs -f -l app=ozon-bot -n ozon-bot-prod

# Events
kubectl get events -n ozon-bot-prod --sort-by='.lastTimestamp'

# Resource usage
kubectl top pods -n ozon-bot-prod
```

## Troubleshooting

### Pod not starting

```bash
kubectl describe pod -n ozon-bot-prod <pod-name>
kubectl logs -n ozon-bot-prod <pod-name> --previous
```

### ArgoCD sync failed

```bash
kubectl get application ozon-bot-prod -n argocd -o yaml
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller
```

### Database connection issues

```bash
kubectl get pods -n ozon-bot-prod -l app=postgres
kubectl logs -n ozon-bot-prod -l app=postgres
kubectl exec -n ozon-bot-prod postgres-pod -- psql -U admin -l
```

### Image pull errors

Check image exists:

```bash
docker manifest inspect ghcr.io/vshulcz/ozon_price_tracker:latest
```

Verify CI completed:

```bash
gh run list --workflow=ci.yml --limit 5
```

## Rollback

Via ArgoCD UI:
1. Open application
2. Go to "History"
3. Select previous version
4. Click "Rollback"

Via CLI:

```bash
kubectl rollout undo deployment/ozon-bot -n ozon-bot-prod
```

## Maintenance

### Update application

Push changes to `main` branch. ArgoCD will auto-sync within 3 minutes.

Force sync:

```bash
kubectl patch application ozon-bot-prod -n argocd --type merge \
  -p '{"operation":{"sync":{"revision":"HEAD"}}}'
```

### Scale deployment

```bash
kubectl scale deployment ozon-bot -n ozon-bot-prod --replicas=2
```

### Update secrets

```bash
kubectl delete secret bot-secrets -n ozon-bot-prod
kubectl create secret generic bot-secrets -n ozon-bot-prod \
  --from-literal=BOT_TOKEN='new_token' \
  --from-literal=POSTGRES_PASSWORD='new_password'
kubectl rollout restart deployment/ozon-bot -n ozon-bot-prod
kubectl rollout restart deployment/postgres -n ozon-bot-prod
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
