# Marketplace Price Tracker Bot

A Telegram bot that tracks marketplace prices (Ozon and Wildberries). Paste a product link, set a target price, and the bot checks prices three times a day and notifies you when the target is reached.

## Quick start (Docker)

```bash
cp .env.example .env   # set BOT_TOKEN and DATABASE_URL
make up && make logs
```

## Usage Flow

1. Tap Add product and send a supported Ozon or Wildberries URL.
2. The bot fetches product title and current price.
3. Enter a target price.
4. The product is stored and appears in Products. You can open its card, edit the target price, open the marketplace page, or go Back.
5. The scheduler runs at 09:00, 15:00 and 21:00 (server time) and updates prices, storing history.
6. When current ≤ target, you receive a deal reached notification with a Remove product button.
7. If later current > target, you receive one deal over notification. Repeated notifications for the same state are suppressed.

## Internationalization

* RU 🇷🇺 and EN 🇬🇧 message dictionaries live in app/i18n.py.
* In bot: settings - choose language.

## Production Deployment

Production deployment guide with K3s and ArgoCD is available in [documentation](docs/README-en.md):

- [🇬🇧 Deployment Guide](docs/DEPLOYMENT-en.md)
- [🇷🇺 Руководство по развёртыванию](docs/DEPLOYMENT.md)

## Notes

* Scraping may violate marketplace T&Cs - use responsibly and at your own risk.
* The project is for educational/demo purposes.
* Try the demo: **[@mpricemonitoring_bot](https://t.me/mpricemonitoring_bot)**

## Monitoring

* The bot exposes [Prometheus](https://prometheus.io/) metrics on `http://<host>:8000/metrics` (host/port are controlled via `METRICS_HOST` and `METRICS_PORT`).
* In Kubernetes a dedicated `Service` with `prometheus.io/*` annotations is created, so Prometheus Operator / ServiceMonitor can scrape it out of the box.
* Set `METRICS_ENABLED=false` to disable the endpoint if you do not plan to collect metrics or autoscale by them.
* When deploying via ArgoCD the bot and monitoring stacks are managed by separate applications: `k8s/argocd/application-{dev,prod}.yaml` deploy the bot itself, while `k8s/argocd/application-monitoring-{dev,prod}.yaml` roll out Prometheus/Grafana (operator CRs). Check the “Prometheus + Grafana via ArgoCD” section in `docs/DEPLOYMENT-en.md` for credentials and access tips.

## Contributing

* PRs are welcome - please run linters/tests locally and add coverage where possible.
* Star the repo ⭐ and share
