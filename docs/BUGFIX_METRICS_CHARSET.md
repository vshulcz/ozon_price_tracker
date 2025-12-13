# Bugfix: Metrics Endpoint Charset Issue

## Problem Description

**Date:** December 13, 2025
**Severity:** Medium (non-critical, affects monitoring only)
**Component:** Prometheus metrics endpoint (`/metrics`)

### Error Message

```
ValueError: charset must not be in content_type argument
```

### Full Stack Trace

```python
File "/app/.venv/lib/python3.12/site-packages/aiohttp/web_protocol.py", line 510, in _handle_request
    resp = await request_handler(request)
File "/app/.venv/lib/python3.12/site-packages/aiohttp/web_app.py", line 569, in _handle
    return await handler(request)
File "/app/app/metrics.py", line 77, in _metrics_handler
    return web.Response(body=payload, content_type=CONTENT_TYPE_LATEST)
File "/app/.venv/lib/python3.12/site-packages/aiohttp/web_response.py", line 650, in __init__
    raise ValueError("charset must not be in content_type argument")
```

### Impact

- ❌ Prometheus scraping fails (returns HTTP 500)
- ❌ Metrics not collected in monitoring system
- ✅ Bot functionality NOT affected (core features work normally)
- ✅ Database operations unaffected
- ✅ User notifications working

---

## Root Cause

### Breaking Change in aiohttp 3.10+

Starting from `aiohttp>=3.10.0`, the `web.Response` constructor requires `charset` to be passed as a **separate parameter**, not embedded in the `content_type` string.

**Previous behavior (aiohttp < 3.10):**
```python
web.Response(body=data, content_type="text/plain; charset=utf-8")  # ✅ OK
```

**New behavior (aiohttp >= 3.10):**
```python
web.Response(body=data, content_type="text/plain; charset=utf-8")  # ❌ Error
web.Response(body=data, content_type="text/plain", charset="utf-8")  # ✅ OK
```

### Our Code Issue

In `app/metrics.py` line 77:

```python
# BEFORE (broken)
async def _metrics_handler(_: web.Request) -> web.Response:
    payload = generate_latest()
    return web.Response(body=payload, content_type=CONTENT_TYPE_LATEST)
```

The `CONTENT_TYPE_LATEST` constant from `prometheus_client` library returns:
```python
"text/plain; version=0.0.4; charset=utf-8"
```

This includes `charset=utf-8` in the string, which violates the new aiohttp requirement.

---

## Solution

### Code Fix

**File:** `app/metrics.py`
**Line:** 77

```python
# AFTER (fixed)
async def _metrics_handler(_: web.Request) -> web.Response:
    payload = generate_latest()
    # aiohttp 3.10+ requires charset to be passed separately, not in content_type
    # CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    return web.Response(
        body=payload,
        content_type="text/plain; version=0.0.4",
        charset="utf-8",
    )
```

### Why This Works

1. **Content-Type header** is set to `text/plain; version=0.0.4` (Prometheus format)
2. **Charset** is passed separately as a parameter to `web.Response`
3. aiohttp internally constructs the correct HTTP header: `Content-Type: text/plain; version=0.0.4; charset=utf-8`

---

## Verification

### Before Fix

```bash
$ curl http://bot-pod:8000/metrics
# Returns: HTTP 500 Internal Server Error
```

Logs show:
```
ValueError: charset must not be in content_type argument
```

### After Fix

```bash
$ curl http://bot-pod:8000/metrics
# HELP marketplace_bot_updates_total Number of Telegram updates processed by type
# TYPE marketplace_bot_updates_total counter
marketplace_bot_updates_total{update_type="message"} 42.0
...
# Returns: HTTP 200 OK with metrics
```

### Testing in Production

```bash
# 1. Port-forward to bot pod
kubectl port-forward -n marketplace-bot-prod pod/marketplace-bot-xxx 8000:8000

# 2. Test metrics endpoint
curl http://localhost:8000/metrics

# 3. Check for errors in logs
kubectl logs -n marketplace-bot-prod pod/marketplace-bot-xxx | grep -i error

# 4. Verify Prometheus can scrape
# Check Prometheus targets page: http://prometheus:9090/targets
```

---

## Deployment

### Option 1: Quick Fix (Manual Deployment)

If you need to deploy immediately:

```bash
# 1. Commit the fix
git add app/metrics.py
git commit -m "fix: metrics endpoint charset compatibility with aiohttp 3.10+"
git push origin main

# 2. Build new image (manual)
docker build -t <registry>/marketplace-bot:latest .
docker push <registry>/marketplace-bot:latest

# 3. Restart pods
kubectl rollout restart deployment/marketplace-bot -n marketplace-bot-prod
kubectl rollout status deployment/marketplace-bot -n marketplace-bot-prod
```

### Option 2: CI/CD Pipeline

The fix will be automatically deployed on next:
- Push to `main` branch → triggers CI build
- ArgoCD sync → deploys to production

```bash
# Just commit and push
git add app/metrics.py
git commit -m "fix: metrics endpoint charset compatibility with aiohttp 3.10+"
git push origin main

# Watch ArgoCD for deployment
argocd app get marketplace-price-tracker-prod
```

---

## Related Issues

### Dependencies

- **aiohttp version:** `>=3.10.0,<4.0` (specified in `pyproject.toml`)
- **prometheus_client version:** Any (the constant `CONTENT_TYPE_LATEST` hasn't changed)

### Similar Issues in Other Projects

This is a common issue when upgrading to aiohttp 3.10+. See:
- [aiohttp changelog](https://docs.aiohttp.org/en/stable/changes.html#aiohttp-3-10)
- Similar pattern should be checked in any code using `web.Response` with content_type containing charset

### Prevention

**Code Review Checklist:**
- [ ] When upgrading aiohttp, check all `web.Response()` calls
- [ ] Ensure `charset` is passed as separate parameter
- [ ] Test metrics endpoint after any aiohttp upgrade
- [ ] Add integration test for `/metrics` endpoint

---

## Monitoring After Fix

### Success Criteria

1. ✅ `/metrics` endpoint returns HTTP 200
2. ✅ No errors in bot logs related to metrics
3. ✅ Prometheus successfully scrapes metrics (check Prometheus UI)
4. ✅ Grafana dashboards show data

### Prometheus Scrape Config

Ensure your Prometheus scrape config includes:

```yaml
scrape_configs:
  - job_name: 'marketplace-bot'
    static_configs:
      - targets: ['marketplace-bot.marketplace-bot-prod.svc.cluster.local:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

---

## Lessons Learned

1. **Breaking changes in dependencies** - Even minor version upgrades can introduce breaking changes
2. **Test monitoring endpoints** - Integration tests should cover `/metrics` endpoint
3. **Dependency pinning** - Consider more strict version constraints for critical dependencies
4. **Monitoring monitoring** - Set up alerts when metrics scraping fails

---

## References

- **aiohttp 3.10 Release Notes:** https://docs.aiohttp.org/en/stable/changes.html
- **Prometheus Python Client:** https://github.com/prometheus/client_python
- **Related PR/Issue:** (add link when created)

---

**Status:** ✅ FIXED
**Fixed By:** Emergency database restore session
**Fixed Date:** December 13, 2025
