# ComfyUI Setup Guide — TopDownMedievalPixelArt

> **Target audience**: Developers and operators provisioning a ComfyUI server for the
> TopDownMedievalPixelArt generation pipeline.
>
> **Time to complete**: ~20 minutes (mostly download time).
>
> **Auth required**: None — all models are ungated, direct-download.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install ComfyUI](#2-install-comfyui)
3. [Download Models](#3-download-models)
4. [Workflow Setup](#4-workflow-setup)
5. [Verification & Integration](#5-verification--integration)

---

## 1. Prerequisites

### Hardware

| Requirement | Minimum | Recommended |
|---|---|---|
| **GPU VRAM** | 12 GB (RTX 3060, RTX 4070) | 16+ GB (RTX 4090, RTX 5090) |
| **System RAM** | 16 GB | 32 GB |
| **Free disk space** | 30 GB | 50 GB |
| **CUDA** | 12.4+ | 12.6+ |

The Flux2 Klein 4B FP8 model fits in ~8.4 GB VRAM at inference time.
A 12 GB GPU leaves headroom for the OS and ComfyUI itself.

### Software

- **OS**: Linux (recommended) or Windows with WSL2
- **Python**: 3.11 or later
- **Git**: any recent version
- **ComfyUI**: ≥ **0.9.2** (required for Flux2-native node types)

To check your CUDA version:

```bash
nvidia-smi | head -3
```

---

## 2. Install ComfyUI

### 2.1 Clone and set up

```bash
# Choose your install location
COMFYUI_DIR="${COMFYUI_DIR:-$HOME/ComfyUI}"

git clone https://github.com/comfyanonymous/ComfyUI.git "$COMFYUI_DIR"
cd "$COMFYUI_DIR"

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install ComfyUI dependencies
pip install -r requirements.txt
```

### 2.2 First-run smoke test

Start ComfyUI in CPU-only mode to verify the installation before involving
the GPU:

```bash
python main.py --cpu
```

You should see output ending with:

```
Starting server
To see the GUI go to: http://127.0.0.1:8188
```

Press `Ctrl+C` to stop it.  If this fails, check that Python ≥ 3.11 and that
`requirements.txt` installed without errors.

### 2.3 (Optional) Install ComfyUI Manager

ComfyUI Manager provides a web UI for installing custom nodes and models.
It is not required for this pipeline but is helpful for debugging:

```bash
cd "$COMFYUI_DIR/custom_nodes"
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
cd "$COMFYUI_DIR"
# Install Manager's own dependencies
venv/bin/pip install -r custom_nodes/ComfyUI-Manager/requirements.txt
```

---

## 3. Download Models

Three model files are needed.  All are Apache 2.0 licensed and available via
direct download — **no HuggingFace account or access token required**.

### 3.1 Quick-reference table

| Component | Filename | Source Repo | Direct Download URL | ~Size |
|---|---|---|---|---|
| **UNet** | `flux-2-klein-4b-fp8.safetensors` | `black-forest-labs/FLUX.2-klein-4b-fp8` | `https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors` | ~6 GB |
| **Text Encoder** | `qwen_3_4b.safetensors` | `Comfy-Org/vae-text-encorder-for-flux-klein-4b` | `https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-4b/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors` | ~8 GB |
| **VAE** | `flux2-vae.safetensors` | `Comfy-Org/vae-text-encorder-for-flux-klein-4b` | `https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-4b/resolve/main/split_files/vae/flux2-vae.safetensors` | ~320 MB |
| **`<tdp>` LoRA** | TBD | TBD | TBD | TBD |

> **China / slow-network users**: Replace `huggingface.co` with `hf-mirror.com`
> in all URLs above.  The HF Mirror is a community-maintained CDN that proxies
> HuggingFace without rate-limiting.

### 3.2 File placement

Place each file in the correct ComfyUI model subdirectory:

```
ComfyUI/
  models/
    unet/        ← flux-2-klein-4b-fp8.safetensors
    clip/        ← qwen_3_4b.safetensors
    vae/         ← flux2-vae.safetensors
    loras/       ← <tdp> LoRA (TBD)
```

Create the directories if they don't exist:

```bash
mkdir -p "$COMFYUI_DIR/models"/{unet,clip,vae,loras}
```

### 3.3 Download commands

Choose one method per model.  `wget` is the simplest; `huggingface-cli` adds
resume support for unreliable connections.

#### Method A — `wget` (recommended, zero dependencies beyond wget)

```bash
# UNet (~6 GB)
wget -P "$COMFYUI_DIR/models/unet/" \
  "https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors"

# Text encoder (~8 GB)
wget -P "$COMFYUI_DIR/models/clip/" \
  "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-4b/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors"

# VAE (~320 MB)
wget -P "$COMFYUI_DIR/models/vae/" \
  "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-4b/resolve/main/split_files/vae/flux2-vae.safetensors"
```

Add `-c` to resume interrupted downloads:

```bash
wget -c -P "$COMFYUI_DIR/models/unet/" "https://..."
```

#### Method B — `huggingface-cli` (resumable, validates checksums)

```bash
# Install the CLI (one time)
pip install huggingface_hub

# UNet
huggingface-cli download black-forest-labs/FLUX.2-klein-4b-fp8 \
  flux-2-klein-4b-fp8.safetensors --local-dir "$COMFYUI_DIR/models/unet/"

# Text encoder
huggingface-cli download Comfy-Org/vae-text-encorder-for-flux-klein-4b \
  split_files/text_encoders/qwen_3_4b.safetensors --local-dir "$COMFYUI_DIR/models/clip/"

# VAE
huggingface-cli download Comfy-Org/vae-text-encorder-for-flux-klein-4b \
  split_files/vae/flux2-vae.safetensors --local-dir "$COMFYUI_DIR/models/vae/"
```

For the China mirror with `huggingface-cli`:

```bash
export HF_ENDPOINT=https://hf-mirror.com
# then run the same huggingface-cli download commands
```

#### Method C — `curl` (alternative for systems without wget)

```bash
# UNet
curl -L -o "$COMFYUI_DIR/models/unet/flux-2-klein-4b-fp8.safetensors" \
  "https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors"

# Text encoder
curl -L -o "$COMFYUI_DIR/models/clip/qwen_3_4b.safetensors" \
  "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-4b/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors"

# VAE
curl -L -o "$COMFYUI_DIR/models/vae/flux2-vae.safetensors" \
  "https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-4b/resolve/main/split_files/vae/flux2-vae.safetensors"
```

Add `-C -` for resume support with curl.

### 3.4 Verify downloads

Confirm each file exists and has a reasonable size:

```bash
ls -lh "$COMFYUI_DIR/models/unet/flux-2-klein-4b-fp8.safetensors"
# Expected: ~6.0 GB

ls -lh "$COMFYUI_DIR/models/clip/qwen_3_4b.safetensors"
# Expected: ~8.0 GB

ls -lh "$COMFYUI_DIR/models/vae/flux2-vae.safetensors"
# Expected: ~320 MB
```

Files under 1 MB indicate a truncated download — delete and re-download.

---

## 4. Workflow Setup

### 4.1 How workflows are used

This project's FastAPI service loads workflow JSONs from its own `workflows/`
directory and submits them to ComfyUI via the HTTP API at runtime.  You do
**not** need to copy the JSONs into ComfyUI's workflow directory for the
pipeline to function.

However, for **manual testing and debugging** in the ComfyUI web UI, it's
useful to have them available locally.

### 4.2 (Optional) Copy workflows for manual testing

```bash
# From the project root
cp workflows/txt2img.json         "$COMFYUI_DIR/user/default/workflows/"
cp workflows/background_tile.json "$COMFYUI_DIR/user/default/workflows/"
cp workflows/leader/*.json        "$COMFYUI_DIR/user/default/workflows/"
```

Then drag-and-drop a workflow onto the ComfyUI canvas.  If you see red
"missing node" outlines, the required custom nodes are not installed — see
the node type checklist below.

### 4.3 Node type checklist

The following ComfyUI node types must be available (all are built-in with
ComfyUI ≥ 0.9.2):

| Node Type | Purpose | Built-in? |
|---|---|---|
| `UNETLoader` | Loads the Flux2 Klein UNet | ✅ |
| `CLIPLoader` | Loads the Qwen 3 4B text encoder (type=flux2) | ✅ |
| `VAELoader` | Loads the Flux2 VAE | ✅ |
| `CLIPTextEncode` | Encodes the positive prompt | ✅ |
| `EmptyLatentImage` | Creates latent tensor (txt2img) | ✅ |
| `LoadImage` | Loads reference image (img2img) | ✅ |
| `VAEEncode` | Encodes reference image to latent | ✅ |
| `SamplerCustomAdvanced` | Flux2-native sampler | ✅ |
| `FluxGuidance` | Flux2 user-facing guidance control | ✅ |
| `CFGGuider` | Flux2 internal guidance wiring (cfg=1.0) | ✅ |
| `BasicScheduler` | Noise schedule (steps, denoise) | ✅ |
| `KSamplerSelect` | Sampler selector (euler) | ✅ |
| `RandomNoise` | Seeded noise generator | ✅ |
| `VAEDecode` | Decodes latent to image | ✅ |
| `SaveImage` | Saves output PNG | ✅ |
| **`ImageResizeKJv2`** | High-quality resize with Lanczos | ❌ **Custom** — see below |
| **`Image Remove Background (rembg)`** | AI background removal → RGBA | ❌ **Custom** — see below |
| **`ImageStitch`** | Stitches two images side-by-side (leader_action) | ✅ |

### 4.4 Required Custom Nodes

Two custom node packages are required — they are **not** bundled with ComfyUI.

#### Custom Node 1: KJNodes (`ImageResizeKJv2`)

- **Repository:** https://github.com/kijai/ComfyUI-KJNodes
- **Install:**
  ```bash
  cd "$COMFYUI_DIR/custom_nodes"
  git clone https://github.com/kijai/ComfyUI-KJNodes.git
  ```
- **Used by:** All workflows except `leader_splash.json`
- **Purpose:** High-quality image resize with Lanczos interpolation, keep-proportion
  options (`stretch` / `resize`), and device selection (`cpu` / `gpu`).

#### Custom Node 2: rembg (Background Removal)

- **Repository:** https://github.com/Loewen-Hob/rembg-comfyui-node-better
- **Install:**
  ```bash
  cd "$COMFYUI_DIR/custom_nodes"
  git clone https://github.com/Loewen-Hob/rembg-comfyui-node-better.git
  cd "$COMFYUI_DIR"
  venv/bin/pip install rembg[gpu]
  ```
- **Used by:** `txt2img.json` only
- **Purpose:** AI-powered background removal producing clean RGBA output.
  Uses the `u2net` model (~176 MB, downloaded automatically on first use).
- **VRAM:** ~500 MB additional during inference.

> **Note:** The `PixelArtDetector` node referenced in earlier documentation
> is **not present** in the current workflow JSONs.  It is documented in
> `workflow-design-justification.md` for informational purposes only.

---

## 5. Verification & Integration

### 5.1 Start ComfyUI

```bash
cd "$COMFYUI_DIR"
source venv/bin/activate
python main.py
```

Open `http://127.0.0.1:8188` in a browser.  You should see the ComfyUI web UI.

### 5.2 Quick smoke test

1. Drag `workflows/txt2img.json` onto the canvas
2. Type a simple prompt in the `CLIPTextEncode` node, e.g.: `a medieval castle`
3. Click **Queue Prompt**

If the model loads and an image appears, ComfyUI is correctly configured.

### 5.3 Run validation prompts

The project includes 15 pre-built test prompts in
[`docs/validation-prompts.md`](validation-prompts.md).  Copy each prompt into
its corresponding workflow and verify the output looks reasonable.

For automated testing via `curl`:

```bash
# Submit the txt2img workflow with a test prompt
curl -X POST "http://127.0.0.1:8188/prompt" \
  -H "Content-Type: application/json" \
  -d "$(cat workflows/txt2img.json | jq '.prompt')"
```

(Requires `jq` for JSON manipulation.)

### 5.4 Connect the FastAPI service

1. Edit `config.yaml` (or set the `COMFYUI__BASE_URL` env var) to point at
   your ComfyUI server:

   ```yaml
   comfyui:
     base_url: "http://127.0.0.1:8188"   # or your ComfyUI host:port
     timeout: 300
   ```

2. Start the FastAPI service from the project root:

   ```bash
   cd TopDownMedievalPixelArt-Prod
   source .venv/bin/activate
   uvicorn src.main:app --host 0.0.0.0 --port 8000
   ```

3. Verify by hitting a generation endpoint:

   ```bash
   curl -X POST "http://127.0.0.1:8000/structure" \
     -H "Content-Type: application/json" \
     -d '{
       "category": "fortification",
       "subcategory": "wooden",
       "culture": "nordic",
       "condition": "pristine",
       "scale": "small",
       "description": "A wooden watchtower"
     }'
   ```

   A successful response includes `image_id`, `filepath`, and a `url` pointing
   to the generated asset.

### 5.5 Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `503 Service Unavailable` from FastAPI | ComfyUI not running or wrong URL | Check `config.yaml` → `comfyui.base_url`; verify ComfyUI is running at `http://127.0.0.1:8188` |
| ComfyUI shows "missing node" in red | ComfyUI version < 0.9.2 | Upgrade: `git pull` inside ComfyUI dir |
| `UNETLoader` can't find model | File in wrong directory | Verify `flux-2-klein-4b-fp8.safetensors` is in `models/unet/` |
| Out of memory (OOM) | GPU VRAM insufficient | Close other GPU processes; try `--lowvram` flag: `python main.py --lowvram` |
| `wget` 404 error | URL changed upstream | Check the download URLs in [Section 3.1](#31-quick-reference-table) against the source repos |
| Generation produces noise/static | VAE missing or wrong version | Verify `flux2-vae.safetensors` is exactly 320 MB |

---

## 6. Automated Setup Script

For fully automated provisioning, run the included script:

```bash
# From the project root
bash scripts/setup_comfyui.sh

# With custom ComfyUI install location
COMFYUI_DIR=/opt/ComfyUI bash scripts/setup_comfyui.sh

# Using the China mirror
HF_BASE=https://hf-mirror.com bash scripts/setup_comfyui.sh

# Skip ComfyUI installation (models only)
SKIP_COMFYUI=true COMFYUI_DIR=/existing/ComfyUI bash scripts/setup_comfyui.sh

# Dry-run (print what would happen)
bash scripts/setup_comfyui.sh --dry-run
```

The script is **idempotent** — safe to run multiple times.  It skips files
that already exist with the expected size.

---

## Model Provenance

| Component | HuggingFace Repository | License | Maintainer |
|---|---|---|---|
| Flux2 Klein 4B Distilled FP8 | [`black-forest-labs/FLUX.2-klein-4b-fp8`](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8) | Apache 2.0 | Black Forest Labs |
| Qwen 3 4B Text Encoder | [`Comfy-Org/vae-text-encorder-for-flux-klein-4b`](https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-4b) | Apache 2.0 | Comfy Org (comfyanonymous) |
| Flux2 VAE | [`Comfy-Org/vae-text-encorder-for-flux-klein-4b`](https://huggingface.co/Comfy-Org/vae-text-encorder-for-flux-klein-4b) | Apache 2.0 | Comfy Org (comfyanonymous) |

The FP8 quantized UNet is distributed in a separate ungated repository from
the main BF16 weights (`black-forest-labs/FLUX.2-klein-4B`, which requires
terms acceptance).  The text encoder and VAE are packaged by the ComfyUI
organization specifically for ComfyUI compatibility.

---

## 7. Multi-Instance Spawning

For high-throughput deployments on GPU-rich nodes (e.g., Blackwell RTX 6000
with 96 GB VRAM), you can run multiple ComfyUI workers on the same GPU using
the spawn script:

```bash
# Launch 6 instances on ports 8188-8193
bash scripts/spawn_comfyui.sh -n 6 start

# Wait for all to be healthy before printing URLs
bash scripts/spawn_comfyui.sh -n 6 -w start

# Check status
bash scripts/spawn_comfyui.sh status
```

Each Flux2 Klein 4B fp8 instance uses ~14 GB VRAM with headroom, so a 96 GB
GPU can comfortably host 5-6 workers.  The script prints `host:port` URLs
ready for the `comfyui.nodes` config block.

See [DEPLOYMENT.md](../DEPLOYMENT.md#multi-instance-comfyui-on-a-single-gpu)
for full documentation including systemd integration, multi-GPU setups, and
load balancer configuration.

---

## Next Steps

- **LoRA setup**: The `<tdp>` LoRA (used by structure/object/terrain/unit
  pipelines for top-down camera angle) will be documented here once its
  filename and source are confirmed.
- **Multi-instance spawning**: See [§7 Multi-Instance Spawning](#7-multi-instance-spawning)
  above and [DEPLOYMENT.md](../DEPLOYMENT.md#multi-instance-comfyui-on-a-single-gpu).
- **Multi-node**: See [architecture.md](architecture.md) §4 (ComfyUI Client)
  for load-balanced multi-GPU setup.
- **Production**: See [architecture.md](architecture.md) §7 for known issues and
  production guidance.
