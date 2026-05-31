# Deployment Guide — Medieval Pixel Art Image Service

Step-by-step guide for deploying the service in a production environment.

---

## Pre-Deployment Checklist

Complete every item before exposing the service to the internet.

### Security (MUST DO)

- [ ] **Set `DEPLOYMENT_MODE=production`** — enables strict safety checks (CORS must be explicit, schema mismatches are fatal, `DATABASE_RESET` is blocked).
- [ ] **Generate a strong API key** — use `openssl rand -hex 32` and set `SERVER__API_KEY=<value>`. Without this, the API is open to anyone.
- [ ] **Tighten CORS origins** — set `SERVER__CORS_ORIGINS` to your frontend's exact origin(s). Never use `["*"]` in production.
- [ ] **Place a reverse proxy in front** — nginx or Caddy for TLS termination and per-IP rate limiting. The built-in rate limiter is **global**, not per-IP.
- [ ] **Bind to localhost** — set `SERVER__HOST=127.0.0.1` if only the reverse proxy needs direct access.
- [ ] **Use HTTPS** — terminate TLS at the reverse proxy. Never expose the service over plain HTTP.

### Infrastructure

- [ ] **ComfyUI server provisioned** — see [comfyui-setup-guide.md](comfyui-setup-guide.md) for step-by-step instructions. Flux2 Klein models must be loaded.
- [ ] **GPU VRAM sufficient** — Flux2 Klein 4B requires ~8 GB VRAM at FP8. Ensure the ComfyUI host has adequate GPU memory.
- [ ] **Disk space** — generated PNGs accumulate in `generated_assets/`. Monitor disk usage and set up a cleanup cron job if needed.
- [ ] **Network connectivity** — the FastAPI server must be able to reach the ComfyUI server on its HTTP port (default 8188).

### Configuration

This service uses a **config layering** pattern:

| Layer | File | Purpose |
|-------|------|---------|
| **Defaults** | `config.yaml` (version-controlled) | Canonical defaults and structure for every setting. Commit changes here when adding new config keys. |
| **Overrides** | `.env` (per-deployment, git-ignored) | **Only** values that differ from `config.yaml` defaults. Typically just `COMFYUI__BASE_URL`. |
| **Testing preset** | `.env.testing` | Drop-in replacement that sets all generation modes to `placeholder` for ComfyUI-free testing. |

**Rule**: If a value in `.env` equals the `config.yaml` default, it doesn't belong in `.env`. The `.env` file should be minimal — in most deployments, only `COMFYUI__BASE_URL` needs an override.

**Naming convention**: Use `__` (double underscore) to target nested keys.

| `.env` variable | Maps to `config.yaml` path |
|-----------------|---------------------------|
| `COMFYUI__BASE_URL` | `comfyui.base_url` |
| `COMFYUI__TIMEOUT` | `comfyui.timeout` |
| `SERVER__CORS_ORIGINS` | `server.cors_origins` |
| `GENERATION__MODES__STRUCTURE` | `generation.modes.structure` |
| `RATE_LIMIT__POST_RPS` | `rate_limit.post_rps` |

- [ ] **Set `COMFYUI__BASE_URL`** — typically the ONLY override needed. Point to the production ComfyUI server.
- [ ] **Review generation modes** — only override `GENERATION__MODES__*` if a family should use something other than the `config.yaml` default (`comfyui`).
- [ ] **Database** — `DATABASE_URL` defaults to SQLite at the project root. Only override if using a different path. SQLite WAL mode is enabled automatically.
- [ ] **Disable warmup if VRAM-constrained** — set `COMFYUI__WARMUP_ENABLED=false` if the ComfyUI GPU can't spare VRAM for an extra generation at startup.
- [ ] **Review all `.env` overrides** — compare against `config.yaml` defaults. Only override what's truly different in production.

---

## Step-by-Step Deployment

### 1. Clone and Install

```bash
git clone <repo-url> /opt/medieval-pixel-art
cd /opt/medieval-pixel-art
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure Environment

Create a minimal `.env` with only deployment-specific overrides:

```bash
# .env — production overrides (only what differs from config.yaml defaults)
COMFYUI__BASE_URL=http://10.0.0.5:8188
```

For a more locked-down production setup, add security and binding overrides:

```bash
# .env — full production example
MODE=production
SERVER__HOST=127.0.0.1
SERVER__API_KEY=<openssl rand -hex 32>
SERVER__CORS_ORIGINS='["https://mygame.example.com"]'
COMFYUI__BASE_URL=http://10.0.0.5:8188
```

> **Note**: `SERVER__PORT`, `DATABASE_URL`, and all `GENERATION__MODES__*` settings use their `config.yaml` defaults — they don't need to appear in `.env` unless your deployment differs from the default.

For ComfyUI-free testing, use the pre-built testing preset instead:

```bash
cp .env.testing .env
```

### 3. Verify Configuration

```bash
# Check that config is parsed correctly
python3 -c "from src.config import settings; print(settings.model_dump())"
```

### 4. Run Database Migrations

Migrations run automatically at startup, but you can also run them manually:

```bash
alembic upgrade head
```

### 5. Start the Service

**Development/test** (direct uvicorn):

```bash
uvicorn src.main:app --host 127.0.0.1 --port 8000
```

**Production** (with gunicorn, multiple workers):

```bash
# Not yet configured — single-worker deployment behind a reverse proxy
# is the recommended approach for SQLite.
uvicorn src.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

> **Important**: SQLite serializes all writes. Running multiple worker processes
> increases lock contention. For now, deploy a single worker behind a reverse
> proxy. If you need horizontal scaling, pin sessions to a single backend
> (sticky sessions).

### 6. Verify Health

```bash
curl http://127.0.0.1:8000/health | python3 -m json.tool
```

Expected: `"status": "healthy"` with `"comfyui": "ok"`.

If `"status": "degraded"`, check:
- ComfyUI server is running
- `COMFYUI__BASE_URL` is correct
- Network connectivity between FastAPI and ComfyUI hosts

---

## Reverse Proxy Configuration

### nginx Example

```nginx
# /etc/nginx/sites-available/medieval-pixel-art
upstream pixelart_backend {
    server 127.0.0.1:8000;
}

# Per-IP rate limiting (10 req/s, burst 20)
limit_req_zone $binary_remote_addr zone=pixelart_limit:10m rate=10r/s;

server {
    listen 443 ssl http2;
    server_name pixelart.example.com;

    # TLS
    ssl_certificate     /etc/letsencrypt/live/pixelart.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pixelart.example.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    # Request size limit (match server's max_request_body_mb)
    client_max_body_size 15m;

    # Static asset caching
    location /assets/ {
        proxy_pass http://pixelart_backend;
        proxy_cache static_assets;
        proxy_cache_valid 200 30d;
        proxy_cache_key "$uri";
        add_header X-Cache-Status $upstream_cache_status;
    }

    # API endpoints
    location / {
        limit_req zone=pixelart_limit burst=20 nodelay;
        proxy_pass http://pixelart_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;  # match ComfyUI timeout
        proxy_connect_timeout 10s;
    }
}

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name pixelart.example.com;
    return 301 https://$host$request_uri;
}
```

### Caddy Example (simpler)

```caddyfile
pixelart.example.com {
    reverse_proxy 127.0.0.1:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }

    # Per-IP rate limiting
    rate_limit {
        zone dynamic {
            key {remote_host}
            events 10
            window 1s
        }
    }

    # TLS auto-provisioned via Let's Encrypt
    tls admin@example.com
}
```

---

## TLS Termination

Always terminate TLS at the reverse proxy, not at the FastAPI server.

- **Let's Encrypt**: Use `certbot` (nginx) or Caddy's built-in ACME client for free, auto-renewing certificates.
- **Certificate renewal**: Set up a cron job: `0 3 * * * certbot renew --quiet --post-hook "systemctl reload nginx"`
- **Minimum TLS version**: TLS 1.2 or higher. Disable TLS 1.0/1.1.
- **HSTS**: Add `Strict-Transport-Security` header: `add_header Strict-Transport-Security "max-age=63072000" always;`

---

## ComfyUI Setup Prerequisite

The service **requires** a running ComfyUI server with Flux2 Klein models. See
[docs/comfyui-setup-guide.md](comfyui-setup-guide.md) for full provisioning
instructions.

Quick checklist:
- ComfyUI with Flux2 Klein native nodes (`UNETLoader`, `CLIPLoader`, `VAELoader`, `CFGGuider`, `Flux2Scheduler`, `KSamplerSelect`, `SamplerCustomAdvanced`, `EmptyFlux2LatentImage`, `SaveImage`)
- Models: `flux-2-klein-4b-fp8.safetensors`, `qwen_3_4b.safetensors`, `flux2-vae.safetensors`
- Custom nodes as specified in workflow JSONs (e.g., `LoraLoaderModelOnly` for `<tdp>` LoRA)
- Automated setup available via `scripts/setup_comfyui.sh`

---

## Monitoring and Health Checks

### Health Endpoint

Poll `GET /health` every 15–30 seconds.

| Status | Meaning | Alert? |
|--------|---------|--------|
| `healthy` | All components OK | No |
| `degraded` | ComfyUI unreachable; static/placeholder modes still work | After 5 minutes |
| `unhealthy` | Database failure | Immediately |

### Logging

Logs are written to stdout in the format:
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

For production, capture logs with your process manager (systemd journal, Docker log driver, etc.).

Key log events to monitor:
- `Workflow JSONs missing required node types` — ComfyUI missing a custom node
- `Database schema is out of sync` — migration needed
- `ComfyUI unreachable` — GPU server down
- `SQLite busy` (repeated) — write contention; consider reducing worker count

### Metrics to Track

- **Generation latency** (`generation_time_ms` in API responses) — spikes indicate GPU contention or model cold-start
- **Asset count growth** (`registered.*` in `/health`) — plan storage accordingly
- **Error rate** — track 503 (ComfyUI down) vs 429 (rate limited) vs 500 (internal errors)
- **Cache hit rate** — monitor LRU eviction warnings for tuning `SERVER__CACHE_MAX_ENTRIES` / `SERVER__CACHE_MAX_MB`

---

## Backup Strategy for SQLite

### What to Back Up

- **`tilemap.db`** — the SQLite database (all metadata: leader records, asset records, generation history)
- **`generated_assets/`** — all generated PNG files
- **`leader_references/`** — leader reference images used for img2img consistency
- **`.env`** — production configuration

### Backup Method

SQLite `.backup` command is safe while the server is running (thanks to WAL mode):

```bash
# Daily backup via cron
sqlite3 /opt/medieval-pixel-art/tilemap.db ".backup /backups/tilemap-$(date +%Y%m%d).db"
```

Or use `rsync` for file-level backup of all data:

```bash
#!/bin/bash
# backup.sh — run daily via cron
BACKUP_DIR="/backups/medieval-pixel-art/$(date +%Y%m%d-%H%M)"
mkdir -p "$BACKUP_DIR"
sqlite3 /opt/medieval-pixel-art/tilemap.db ".backup $BACKUP_DIR/tilemap.db"
rsync -a /opt/medieval-pixel-art/generated_assets/ "$BACKUP_DIR/generated_assets/"
rsync -a /opt/medieval-pixel-art/leader_references/ "$BACKUP_DIR/leader_references/"
cp /opt/medieval-pixel-art/.env "$BACKUP_DIR/.env"
# Retain last 30 days
find /backups/medieval-pixel-art/ -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;
```

### Restore

```bash
# Stop the service first
systemctl stop medieval-pixel-art

# Restore database
cp /backups/medieval-pixel-art/20260531-0300/tilemap.db /opt/medieval-pixel-art/tilemap.db

# Restore assets
rsync -a /backups/medieval-pixel-art/20260531-0300/generated_assets/ /opt/medieval-pixel-art/generated_assets/
rsync -a /backups/medieval-pixel-art/20260531-0300/leader_references/ /opt/medieval-pixel-art/leader_references/

# Start the service
systemctl start medieval-pixel-art
```

### systemd Unit File Example

```ini
# /etc/systemd/system/medieval-pixel-art.service
[Unit]
Description=Medieval Pixel Art Image Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/medieval-pixel-art
EnvironmentFile=/opt/medieval-pixel-art/.env
ExecStart=/opt/medieval-pixel-art/.venv/bin/uvicorn src.main:app --host 127.0.0.1 --port 8000 --no-access-log
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable --now medieval-pixel-art
```

---

## See Also

- [README.md](../README.md) — Project overview and quickstart
- [architecture.md](architecture.md) — Full system architecture
- [SECURITY.md](SECURITY.md) — Security model and considerations
- [comfyui-setup-guide.md](comfyui-setup-guide.md) — ComfyUI provisioning
- [next_steps.md](next_steps.md) — Future roadmap
