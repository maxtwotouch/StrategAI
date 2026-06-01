# StrategAI Deployment Guide

> **Last Validated: 2026-06-01**

This guide covers running StrategAI's components. The system uses a **separation of concerns** architecture where different components run on different infrastructure based on their resource requirements (see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §1 for the rationale).

> **Why no Docker / containers?** Our deployment environment does not have root access and Docker is not available. The system is designed to run as plain OS processes managed by systemd or a process supervisor. Each subproject is self-contained with its own dependency management — there is intentionally no top-level `requirements.txt` or `Dockerfile`.

> **Why no top-level `requirements.txt`?** Each subproject manages its own dependencies: the backend uses `pyproject.toml` (`pip install -e .`), the asset server uses `requirements.txt`, and the frontend uses `package.json`. A single top-level requirements file would conflate unrelated dependency trees and Python version constraints (3.10+ for assetserver vs 3.11+ for backend).

## Architecture Overview

StrategAI consists of three main deployment tiers:

1. **Game Server** (Backend + Frontend) — CPU-only, handles game logic and user interface
2. **Asset Server** — CPU-only orchestrator, coordinates image generation
3. **ComfyUI Workers** — GPU-accelerated, performs actual diffusion model inference

**Critical:** The Asset Server is **never deployed on the same machine** as the Game Server. It is **colocated** with ComfyUI GPU workers to minimize latency on generation requests.

All components run as plain processes — start them with `uvicorn` (Python) and `npm start` (Node). See the step-by-step sections below.

## Deployment Tiers

### Tier 1: Game Server

**Components:**
- Backend (FastAPI) — Game engine, LLM integration, REST API
- Frontend (Next.js) — User interface, asset resolution

**Hardware Requirements:**
- CPU: 2+ cores
- RAM: 4+ GB
- Storage: 10 GB
- GPU: **Not required**

**Network:**
- Public internet access (for OpenAI API calls)
- Inbound: HTTP/HTTPS (port 80/443)
- Outbound: HTTPS to OpenAI API

### Tier 2: Asset Server

**Components:**
- Asset Server (FastAPI) — Request validation, prompt assembly, caching, storage
- SQLite database — Asset metadata
- File storage — Generated images (`generated_assets/`)

**Hardware Requirements:**
- CPU: 2+ cores
- RAM: 2+ GB
- Storage: 100+ GB (for generated assets)
- GPU: **Not required** (orchestration only)

**Network:**
- Low-latency connection to ComfyUI workers (same datacenter/VPC recommended)
- Inbound: HTTP from Game Server frontend
- Outbound: HTTP/WebSocket to ComfyUI workers

### Tier 3: ComfyUI Workers

**Components:**
- ComfyUI — Diffusion model inference server
- FLUX.2 Klein 4B Distilled — Base model
- LoRA adapters — Style fine-tuning weights

**Hardware Requirements:**
- GPU: NVIDIA with 8+ GB VRAM (RTX 3070/4070 or better)
- CPU: 4+ cores
- RAM: 16+ GB
- Storage: 50+ GB (models + workflows)

**Network:**
- Inbound: HTTP/WebSocket from Asset Server
- No public internet access required

## Step-by-Step Deployment

> **Deployment model:** The simplest and recommended setup runs all components on machines within the same network — the Game Server on one machine, the Asset Server + ComfyUI Workers on another (or the same GPU machine). The tiers above describe the logical separation; physically, the only hard requirement is that the Asset Server has low-latency connectivity to ComfyUI.

### 1. Deploy ComfyUI Workers

**On each GPU node:**

```bash
# Install ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
pip install -r requirements.txt

# Download FLUX.2 Klein 4B Distilled
# (Follow Black Forest Labs instructions for model access)

# Download LoRA adapters from HuggingFace
# https://huggingface.co/stixxert/topdown-medieval-pixelart

# Note: Workflows are JSON API payloads (not ComfyUI custom nodes).
# They stay in the asset server and are read by Python code at runtime.
# See assetserver/workflows/ for the JSON prompt templates.

# Start ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

**Verify:**
```bash
curl http://localhost:8188/system_stats
```

### 2. Deploy Asset Server

**On orchestration node (same network as ComfyUI workers):**

```bash
# Clone repository
git clone https://github.com/your-org/StrategAI.git
cd StrategAI/assetserver

# Create virtual environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env
```

> **Port note:** This guide uses port 8001 as the deployment convention, but the
> code default in `config.yaml` and `src/config.py` is **8000**. To use 8001,
> explicitly set `SERVER__PORT=8001` in `.env` or pass `--port 8001` to uvicorn.

**Required environment variables:**

```bash
# ComfyUI — single node:
COMFYUI__BASE_URL=http://gpu-worker-1:8188

# ComfyUI — multi-node (JSON array, overrides BASE_URL):
# COMFYUI__NODES=["http://gpu1:8188","http://gpu2:8188"]

# Database (default: sqlite:///tilemap.db)
DATABASE_URL=sqlite:///tilemap.db

# Storage paths (all relative to project root)
PATHS__OUTPUT_DIR=generated_assets
PATHS__STATIC_TILES_DIR=static_tiles

# Server bind
SERVER__HOST=0.0.0.0
SERVER__PORT=8001

# Optional: API key for authentication
SERVER__API_KEY=your-secret-key-here
```

> **Naming convention:** The asset server uses `__` (double underscore) as the
> nested delimiter for environment variables.
> Example: `SERVER__PORT` → `settings.server.port`.
> See `assetserver/.env.example` for the full reference.

**Start server:**
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8001
```

**Verify:**
```bash
curl http://localhost:8001/health
curl http://localhost:8001/modes
```

### 3. Deploy Game Server

**On game server node:**

#### Backend

```bash
cd StrategAI/backend

# Create virtual environment
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Configure environment
cp .env.example .env
nano .env
```

**Required environment variables:**

```bash
# OpenAI API (required for AI civilizations)
OPENAI_API_KEY=sk-...
```

> **Note:** The LLM model (`gpt-5.4-mini`) and temperature (`0.7`) are
> **hardcoded** in `backend/app/engine/openai_goals.py` (lines 471–473).
> They cannot be overridden via environment variables. Only `OPENAI_API_KEY`
> is configurable. See `backend/.env.example` for all available options.

**Start backend:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Verify:**
```bash
curl http://localhost:8000/health
```

#### Frontend

```bash
cd StrategAI/frontend

# Install dependencies
npm install

# Configure environment
cat > .env.local <<EOF
NEXT_PUBLIC_API_URL=http://game-server:8000
NEXT_PUBLIC_ASSET_API_URL=http://asset-server:8001
EOF

# Build and start
npm run build
npm start
```

**Verify:**
- Open browser to `http://game-server:3000`
- Create a test game
- Verify AI civilizations make decisions
- Verify assets generate (if Asset Server is reachable)

### 4. Configure Networking

**Firewall rules:**

| Source | Destination | Port | Protocol | Purpose |
|--------|-------------|------|----------|---------|
| Internet | Game Server | 80/443 | HTTP/HTTPS | User access |
| Game Server | Asset Server | 8001 | HTTP | Asset requests (8000 by code default; 8001 recommended) |
| Asset Server | ComfyUI Workers | 8188 | HTTP/WS | Generation requests |
| Game Server | OpenAI API | 443 | HTTPS | LLM calls |

**CORS configuration:**

Backend (`backend/app/main.py`):
```python
# NOTE: The default CORS setting is allow_origins=["*"] (wide open).
# For production, restrict to your frontend domain:
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://game-server:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Asset Server (`assetserver/src/main.py` — configured via `config.yaml` or `.env`):
```python
# Default: cors_origins=["http://localhost:3000"] (see config.yaml line 43)
# Override via SERVER__CORS_ORIGINS in .env for production domains.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5. Set Up Reverse Proxy (Optional)

**Nginx configuration for Game Server:**

```nginx
server {
    listen 80;
    server_name strategai.example.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**Nginx configuration for Asset Server:**

```nginx
server {
    listen 80;
    server_name assets.strategai.example.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Increase timeout for generation requests
        proxy_read_timeout 300s;
    }
}
```

## Scaling

The Asset Server's built-in load balancer distributes generation requests across multiple ComfyUI workers using shortest-queue selection. To scale up, add more GPU nodes to the `COMFYUI__NODES` list.

### Caching Strategy

Asset Server caches generated images to reduce GPU load:

- **Cache hit rate:** ~80% in typical gameplay
- **Cache location:** `generated_assets/` directory
- **Cache key:** Hash of prompt + model + LoRA + seed
- **Cache eviction:** LRU (least recently used)

**Optimization:**
- Pre-generate common assets (structures, units) during deployment
- Use static assets for frequently requested items
- Enable browser caching (Cache-Control headers)

## Monitoring

### Health Checks

**Game Server:**
```bash
curl http://game-server:8000/health
```

**Asset Server:**
```bash
curl http://asset-server:8001/health
curl http://asset-server:8001/modes
```

**ComfyUI Workers:**
```bash
curl http://gpu-worker:8188/system_stats
```

Key metrics to watch: backend error rate, asset generation latency, ComfyUI GPU queue depth.

## Security

### Network Security

- **Game Server:** Public-facing, use HTTPS (Let's Encrypt)
- **Asset Server:** Internal-only, no public access
- **ComfyUI Workers:** Internal-only, no public access
- **Firewall:** Restrict inbound traffic to necessary ports only

### Authentication

**Current state:** No authentication (localhost-only)

**For production:**
- Add API key authentication to Asset Server
- Add JWT authentication to Backend
- Use OAuth2 for user authentication

### Rate Limiting

**Asset Server:**
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/generate/structure")
@limiter.limit("10/minute")
async def generate_structure(request: Request, ...):
    ...
```

**Backend:**
- Rate limit OpenAI API calls per game
- Prevent abuse (e.g., creating 1000 games)

### Data Protection

- **Game state:** Stored in memory (lost on restart)
- **Generated assets:** Stored on disk (backup regularly)
- **User data:** Minimal (player names only)
- **OpenAI API:** No PII sent (game state only)

## Backup & Recovery

### Backup Strategy

**Game Server:**
- No persistent state (game state in memory)
- Backup configuration files (`.env`)

**Asset Server:**
- Backup SQLite database daily
- Backup `generated_assets/` directory weekly
- Use incremental backups (rsync)

**ComfyUI Workers:**
- Backup model files (or re-download)
- Backup custom workflows

### Recovery Procedure

**Asset Server failure:**
1. Restore SQLite database from backup
2. Restore `generated_assets/` from backup
3. Restart Asset Server
4. Verify health check

**ComfyUI Worker failure:**
1. Restart ComfyUI process
2. Verify system stats endpoint
3. Asset Server load balancer will route to healthy workers

**Game Server failure:**
1. Restart backend and frontend
2. Active games will be lost (state in memory)
3. Consider adding Redis for game state persistence

## Troubleshooting

### Common Issues

**Issue:** Asset generation fails with timeout

**Solution:**
- Check ComfyUI worker health: `curl http://gpu-worker:8188/system_stats`
- Check Asset Server logs for errors
- Increase timeout in nginx config (`proxy_read_timeout 300s`)
- Check GPU utilization (may be overloaded)

**Issue:** AI civilizations don't make decisions

**Solution:**
- Verify `OPENAI_API_KEY` is set
- Check backend logs for OpenAI API errors
- Verify network connectivity to `api.openai.com`
- Check OpenAI API usage/quota

**Issue:** Frontend can't connect to backend

**Solution:**
- Verify `NEXT_PUBLIC_API_URL` is correct
- Check CORS configuration in backend
- Verify firewall allows traffic on port 8000
- Check backend health: `curl http://backend:8000/health`

**Issue:** Assets don't load in frontend

**Solution:**
- Verify `NEXT_PUBLIC_ASSET_API_URL` is correct
- Check CORS configuration in Asset Server
- Verify Asset Server health: `curl http://asset-server:8001/health`
- Check browser console for CORS errors

**Issue:** ComfyUI out of memory

**Solution:**
- Reduce batch size in ComfyUI config
- Use FP8 quantization (reduces VRAM from 16GB to 8.4GB)
- Add more GPU workers
- Check for memory leaks (restart ComfyUI periodically)

## Deployment Checklist

- [ ] ComfyUI workers deployed and healthy
- [ ] Asset Server deployed and connected to ComfyUI workers
- [ ] Game Server (backend + frontend) deployed
- [ ] Environment variables configured correctly
- [ ] CORS configured for frontend domain
- [ ] Firewall rules allow necessary traffic
- [ ] Health checks passing for all components
- [ ] Test game created successfully
- [ ] AI civilizations making decisions
- [ ] Assets generating correctly
- [ ] Monitoring and logging configured
- [ ] Backup strategy in place
- [ ] Security review completed
- [ ] Load testing performed (if production)

## Support

For issues not covered in this guide:

- **Documentation:** See `docs/` directory for detailed guides
- **Asset Server:** See `assetserver/DEPLOYMENT.md` for asset-specific deployment
- **Security:** See `assetserver/SECURITY.md` for security considerations
- **Issues:** Open GitHub issue with logs and configuration

## References

- [Architecture Overview](docs/ARCHITECTURE.md) — System architecture and separation-of-concerns rationale
- [Asset Server Deployment](assetserver/DEPLOYMENT.md) — Detailed asset server guide
- [ComfyUI Setup](assetserver/docs/architecture/comfyui-setup-guide.md) — ComfyUI installation
- [Load Balancer](assetserver/docs/architecture/load-balancer.md) — Multi-worker configuration
- [Security](assetserver/SECURITY.md) — Security considerations
