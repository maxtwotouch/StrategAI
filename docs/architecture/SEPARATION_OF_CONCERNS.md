# Separation of Concerns: StrategAI Architecture

This document explains the architectural decision to separate StrategAI into three distinct deployment tiers, with particular emphasis on why the Asset Server is **never deployed on the same machine** as the Game Server.

## Overview

StrategAI uses a **three-tier architecture** where each tier runs on infrastructure optimized for its specific workload:

1. **Game Server** (Backend + Frontend) — CPU-only, handles game logic and user interface
2. **Asset Server** — CPU-only orchestrator, coordinates image generation
3. **ComfyUI Workers** — GPU-accelerated, performs diffusion model inference

**Key Principle:** The Asset Server is **colocated** with ComfyUI GPU workers (same datacenter/VPC) but **separated** from the Game Server (different machine, potentially different region).

## Why Separate the Asset Server?

### 1. Resource Isolation

**Problem:** GPU workloads are resource-intensive and can starve other processes.

**ComfyUI Worker Resource Profile:**
- GPU: 100% utilization during generation
- VRAM: 8-16 GB per model instance
- CPU: 4+ cores for preprocessing/postprocessing
- RAM: 16+ GB for model loading
- Disk I/O: High (model loading, image writing)

**Game Server Resource Profile:**
- CPU: 2 cores for game logic, LLM API calls
- RAM: 4 GB for game state, web server
- Network: Moderate (OpenAI API, frontend requests)
- Disk I/O: Low (logs only)

**If colocated:**
- GPU driver overhead consumes CPU cycles needed for game logic
- VRAM allocation competes with system RAM
- Disk I/O from image generation slows database queries
- Game server becomes unresponsive during batch generation

**Solution:** Separate machines ensure each workload gets dedicated resources without interference.

### 2. Latency Optimization

**Problem:** Asset generation involves high-bandwidth, low-latency communication between Asset Server and ComfyUI workers.

**Communication Pattern:**
```
Asset Server → ComfyUI Worker
  1. Upload workflow JSON (10-50 KB)
  2. Upload input images (if img2img) (1-5 MB)
  3. Submit prompt (HTTP POST)
  4. Poll for progress (WebSocket, 10-20 messages)
  5. Download generated image (1-5 MB)
```

**Total data per generation:** 2-10 MB  
**Typical generation time:** 2.5-6 seconds  
**Required latency:** <10ms round-trip for responsive polling

**If Asset Server is remote (e.g., different region):**
- 100-200ms round-trip latency
- Polling becomes inefficient (20 polls × 200ms = 4 seconds overhead)
- Image uploads/downloads slow (high latency × high bandwidth = poor throughput)
- Generation time increases 20-50%

**If Asset Server is colocated (same datacenter):**
- <5ms round-trip latency
- Polling is responsive
- Image transfers fast (local network bandwidth)
- Generation time optimal

**Solution:** Colocate Asset Server with ComfyUI workers to minimize latency on the critical path.

### 3. Cost Optimization

**Problem:** GPU instances are expensive; CPU instances are cheap.

**Pricing Example (AWS, us-east-1, on-demand):**
- Game Server (t3.medium, 2 vCPU, 4 GB RAM): $0.0416/hour = $30/month
- Asset Server (t3.medium, 2 vCPU, 4 GB RAM): $0.0416/hour = $30/month
- ComfyUI Worker (g5.xlarge, 1 GPU, 16 GB RAM): $1.006/hour = $724/month

**If colocated (Game Server + Asset Server + ComfyUI on g5.xlarge):**
- Cost: $1.006/hour = $724/month
- Problem: Paying GPU premium for CPU-only workloads (game logic, orchestration)
- Wasted: $0.964/hour on GPU for tasks that don't need it

**If separated:**
- Game Server (t3.medium): $30/month
- Asset Server (t3.medium): $30/month
- ComfyUI Worker (g5.xlarge): $724/month
- Total: $784/month
- Benefit: Only pay GPU premium for actual GPU work

**Additional savings:**
- Use spot instances for ComfyUI workers (50-70% savings)
- Auto-scale workers based on demand
- Use cheaper CPU instances for orchestration

**Solution:** Separate tiers allow cost-optimized infrastructure for each workload.

### 4. Scalability

**Problem:** Different components scale at different rates.

**Scaling Patterns:**

**Game Server:**
- Scales with number of active games
- Horizontal scaling (multiple instances behind load balancer)
- Stateless (game state in memory or Redis)
- Scale factor: 10-100x

**Asset Server:**
- Scales with generation request rate
- Horizontal scaling (multiple instances, shared database)
- Stateless (orchestration only)
- Scale factor: 5-20x

**ComfyUI Workers:**
- Scales with GPU utilization
- Vertical scaling (more powerful GPU) or horizontal (more workers)
- Stateful (model loaded in VRAM)
- Scale factor: 2-10x

**If monolithic:**
- Must scale entire system even if only one component is bottlenecked
- Wastes resources (scaling GPU when only CPU needed)
- Complex (load balancing GPU instances is hard)

**If separated:**
- Scale each tier independently based on actual demand
- Cost-effective (only scale what's needed)
- Simple (load balance CPU instances easily)

**Solution:** Separation enables independent, cost-effective scaling.

### 5. Fault Isolation

**Problem:** GPU workloads are failure-prone (OOM, driver crashes, hardware errors).

**Common GPU Failures:**
- Out of memory (OOM) errors
- CUDA driver crashes
- GPU hardware faults
- Model loading failures
- Thermal throttling

**If colocated:**
- GPU failure crashes entire system (game server + asset server)
- All active games lost
- Recovery requires full system restart
- Single point of failure

**If separated:**
- GPU failure only affects asset generation
- Game server continues running (games playable without new assets)
- Asset server can retry on different worker
- Graceful degradation (use cached assets or placeholders)

**Solution:** Separation provides fault isolation and graceful degradation.

### 6. Security

**Problem:** Different components have different security requirements.

**Game Server Security Profile:**
- Public-facing (internet access)
- Handles user authentication
- Accesses OpenAI API (external service)
- Minimal file system access

**Asset Server Security Profile:**
- Internal-only (no public access)
- Accesses file system (generated assets)
- Communicates with ComfyUI workers (internal network)
- No user authentication needed

**ComfyUI Worker Security Profile:**
- Internal-only (no public access)
- Full GPU access
- Loads model files from disk
- No network access except Asset Server

**If colocated:**
- Attack surface expanded (public-facing + GPU access on same machine)
- Compromised game server = compromised GPU
- Harder to apply principle of least privilege
- Compliance challenges (PCI-DSS, HIPAA)

**If separated:**
- Each tier has minimal attack surface
- Network segmentation (firewalls between tiers)
- Easier to apply security policies
- Compliance-friendly (isolate sensitive workloads)

**Solution:** Separation enables defense-in-depth security.

## Why Colocate Asset Server with ComfyUI?

Given that we're separating the Asset Server from the Game Server, why not also separate it from ComfyUI workers?

### Latency is Critical

**Asset Server ↔ ComfyUI Communication:**
- High frequency (10-100 requests per game session)
- High bandwidth (2-10 MB per request)
- Low latency required (<10ms for responsive polling)

**If Asset Server is remote:**
- Generation time increases 20-50% (latency overhead)
- Polling becomes inefficient (high latency × many polls)
- User experience degrades (slow asset loading)

**If Asset Server is colocated:**
- Generation time optimal (minimal latency)
- Polling responsive (local network)
- User experience smooth (fast asset loading)

### Bandwidth Costs

**If Asset Server is remote:**
- Image transfers cross region/internet boundaries
- Bandwidth costs: $0.01-0.09 per GB (AWS inter-region)
- Typical game: 100-500 MB of generated assets
- Cost per game: $0.001-0.045 (small but adds up)

**If Asset Server is colocated:**
- Image transfers stay within datacenter
- Bandwidth costs: $0 (local network)
- Savings: $0.001-0.045 per game

### Operational Simplicity

**If Asset Server is colocated:**
- Single network to manage (ComfyUI workers + Asset Server)
- Simpler firewall rules (internal-only)
- Easier monitoring (all GPU-related metrics in one place)
- Faster troubleshooting (local network issues easier to diagnose)

## Deployment Topologies

### Topology 1: Single Region (Simple)

```
┌─────────────────────────────────────────────────────────┐
│ Datacenter / Region                                      │
│                                                          │
│  ┌──────────────┐         ┌──────────────────────────┐ │
│  │ Game Server  │────────▶│ Asset Server             │ │
│  │ (Backend +   │         │ (Orchestrator)           │ │
│  │  Frontend)   │         └──────────┬───────────────┘ │
│  └──────────────┘                    │                  │
│                                      │ Low-latency      │
│                                      ▼                  │
│                           ┌──────────────────────────┐ │
│                           │ ComfyUI Worker 1 (GPU)   │ │
│                           │ ComfyUI Worker 2 (GPU)   │ │
│                           │ ComfyUI Worker N (GPU)   │ │
│                           └──────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Use case:** Development, testing, small-scale production

**Pros:**
- Simple networking
- Low latency everywhere
- Easy to manage

**Cons:**
- Limited scalability
- Higher cost if GPU instances expensive in region

### Topology 2: Multi-Region (Production)

```
┌─────────────────────┐         ┌─────────────────────────────────┐
│ Region A            │         │ Region B (GPU-optimized)        │
│                     │         │                                 │
│ ┌──────────────┐   │         │  ┌──────────────────────────┐  │
│ │ Game Server  │───┼─────────┼─▶│ Asset Server             │  │
│ │ (Backend +   │   │  HTTPS  │  │ (Orchestrator)           │  │
│ │  Frontend)   │   │         │  └──────────┬───────────────┘  │
│ └──────────────┘   │         │             │                  │
│                     │         │             │ Low-latency      │
│                     │         │             ▼                  │
│                     │         │  ┌──────────────────────────┐  │
│                     │         │  │ ComfyUI Worker 1 (GPU)   │  │
│                     │         │  │ ComfyUI Worker 2 (GPU)   │  │
│                     │         │  │ ComfyUI Worker N (GPU)   │  │
│                     │         │  └──────────────────────────┘  │
└─────────────────────┘         └─────────────────────────────────┘
```

**Use case:** Production, cost optimization

**Pros:**
- Use GPU-optimized regions (e.g., AWS us-east-1 with G5 instances)
- Game Server in user-proximate region
- Better cost optimization

**Cons:**
- Higher latency between Game Server and Asset Server (mitigated by caching)
- More complex networking

### Topology 3: Hybrid Cloud (Advanced)

```
┌─────────────────────┐         ┌─────────────────────────────────┐
│ Cloud Provider      │         │ On-Premises GPU Cluster         │
│                     │         │                                 │
│ ┌──────────────┐   │         │  ┌──────────────────────────┐  │
│ │ Game Server  │───┼─────────┼─▶│ Asset Server             │  │
│ │ (Backend +   │   │  HTTPS  │  │ (Orchestrator)           │  │
│ │  Frontend)   │   │         │  └──────────┬───────────────┘  │
│ └──────────────┘   │         │             │                  │
│                     │         │             │ Low-latency      │
│                     │         │             ▼                  │
│                     │         │  ┌──────────────────────────┐  │
│                     │         │  │ ComfyUI Worker 1 (GPU)   │  │
│                     │         │  │ ComfyUI Worker 2 (GPU)   │  │
│                     │         │  │ ComfyUI Worker N (GPU)   │  │
│                     │         │  └──────────────────────────┘  │
└─────────────────────┘         └─────────────────────────────────┘
```

**Use case:** High-volume production, existing GPU hardware

**Pros:**
- Use existing GPU hardware (cost-effective)
- Cloud for scalable Game Server
- Best of both worlds

**Cons:**
- Complex networking (VPN/tunneling required)
- Security considerations (cross-network communication)
- Maintenance overhead

## Communication Patterns

### Game Server ↔ Asset Server

**Protocol:** HTTPS (REST API)  
**Frequency:** Low (10-50 requests per game session)  
**Bandwidth:** Low (1-5 MB per request)  
**Latency tolerance:** High (100-200ms acceptable)  
**Authentication:** API key or JWT  
**Encryption:** TLS 1.3

**Why HTTPS?**
- Cross-network communication (potentially cross-region)
- Security (authentication, encryption)
- Standard web protocol (easy to load balance, cache)

### Asset Server ↔ ComfyUI Workers

**Protocol:** HTTP + WebSocket  
**Frequency:** High (10-100 requests per game session)  
**Bandwidth:** High (2-10 MB per request)  
**Latency tolerance:** Low (<10ms required)  
**Authentication:** None (internal network)  
**Encryption:** None (internal network)

**Why HTTP + WebSocket?**
- Low latency (no TLS overhead)
- High bandwidth (local network)
- WebSocket for real-time progress updates
- Simple protocol (easy to debug)

**Why no authentication?**
- Internal network (trusted)
- Performance (no auth overhead)
- Simplicity (no key management)

## Caching Strategy

To mitigate latency between Game Server and Asset Server, we use aggressive caching:

**Cache Location:** Asset Server (`generated_assets/` directory)  
**Cache Key:** Hash of prompt + model + LoRA + seed  
**Cache Hit Rate:** ~80% in typical gameplay  
**Cache Eviction:** LRU (least recently used)

**Benefits:**
- Reduces cross-network traffic (80% of requests served from cache)
- Reduces GPU load (cached assets don't require generation)
- Improves user experience (fast asset loading)

**Optimization:**
- Pre-generate common assets during deployment
- Use CDN for asset delivery (CloudFront, Cloudflare)
- Enable browser caching (Cache-Control headers)

## Trade-offs

### Advantages

✅ **Resource isolation** — No interference between workloads  
✅ **Latency optimization** — Colocate high-bandwidth components  
✅ **Cost optimization** — Use appropriate infrastructure for each workload  
✅ **Scalability** — Scale each tier independently  
✅ **Fault isolation** — GPU failures don't crash game server  
✅ **Security** — Smaller attack surface per tier  
✅ **Operational flexibility** — Deploy tiers in different regions/providers

### Disadvantages

❌ **Complexity** — More components to manage  
❌ **Networking** — Cross-component communication requires configuration  
❌ **Deployment** — Multiple deployment pipelines  
❌ **Monitoring** — Need to monitor multiple tiers  
❌ **Debugging** — Harder to trace requests across tiers

### Mitigations

- **Complexity:** Use infrastructure-as-code (Terraform, CloudFormation)
- **Networking:** Document network topology clearly
- **Deployment:** Automate with CI/CD pipelines
- **Monitoring:** Use centralized logging (ELK, Loki)
- **Debugging:** Use distributed tracing (Jaeger, Zipkin)

## Alternatives Considered

### Alternative 1: Monolithic (All-in-One)

**Description:** Deploy everything on a single GPU instance.

**Pros:**
- Simple deployment
- No networking complexity
- Low latency everywhere

**Cons:**
- Resource contention (GPU starves CPU)
- Expensive (pay GPU premium for CPU work)
- Poor scalability (vertical only)
- Single point of failure

**Verdict:** Rejected — too expensive, poor scalability

### Alternative 2: Serverless (Lambda/Cloud Functions)

**Description:** Deploy game logic as serverless functions.

**Pros:**
- Auto-scaling
- Pay-per-use
- No server management

**Cons:**
- Cold start latency (1-5 seconds)
- Limited execution time (15 minutes max)
- No GPU support (for ComfyUI)
- State management complex

**Verdict:** Rejected — not suitable for long-running games, no GPU support

### Alternative 3: Peer-to-Peer (Decentralized)

**Description:** Distribute game logic across player devices.

**Pros:**
- No server costs
- Decentralized (no single point of failure)
- Privacy (no central data store)

**Cons:**
- Complex synchronization
- Cheating prevention difficult
- Requires player devices to be online
- No AI civilizations (need server for LLM calls)

**Verdict:** Rejected — too complex, doesn't support AI features

## Conclusion

The three-tier architecture with separated Asset Server is the optimal design for StrategAI because:

1. **Resource isolation** prevents GPU workloads from interfering with game logic
2. **Latency optimization** ensures responsive asset generation
3. **Cost optimization** uses appropriate infrastructure for each workload
4. **Scalability** allows independent scaling of each tier
5. **Fault isolation** provides graceful degradation
6. **Security** enables defense-in-depth

The key insight is that **not all components have the same requirements**. By separating components based on their resource profiles, latency requirements, and scaling patterns, we achieve a more efficient, scalable, and reliable system.

The trade-off is increased complexity, but this is mitigated by modern DevOps practices (infrastructure-as-code, CI/CD, centralized monitoring).

## References

- [../DEPLOYMENT.md](../DEPLOYMENT.md) — Step-by-step deployment instructions
- [../../assetserver/DEPLOYMENT.md](../../assetserver/DEPLOYMENT.md) — Detailed asset server guide
- [../../assetserver/docs/architecture/comfyui-setup-guide.md](../../assetserver/docs/architecture/comfyui-setup-guide.md) — ComfyUI installation
- [../../assetserver/docs/architecture/load-balancer.md](../../assetserver/docs/architecture/load-balancer.md) — Multi-worker configuration
- [../../assetserver/SECURITY.md](../../assetserver/SECURITY.md) — Security considerations
