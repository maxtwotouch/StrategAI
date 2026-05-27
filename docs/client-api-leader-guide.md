# Implementation Plan: Civ Leader Art Service — Single Instance

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Single Machine                       │
│                                                          │
│  ┌──────────────────┐       ┌────────────────────────┐  │
│  │   FastAPI Server  │──────▶│   ComfyUI Instance     │  │
│  │   Port 8000       │       │   Port 8188            │  │
│  │                    │◀─────│                        │  │
│  │  • Prompt Engine   │       │   • flux1-dev-fp8      │  │
│  │  • Workflow Mutator│       │   • t5xxl_fp8          │  │
│  │  • Leader Registry │       │   • Hyper-SD LoRA      │  │
│  │  • Output Serving  │       │   • ~18GB VRAM total   │  │
│  └──────────────────┘       └────────────────────────┘  │
│                                                          │
│  /opt/civ-leader-api/          /opt/comfyui/             │
│  /opt/comfyui/models/          /opt/comfyui/output/      │
│  /opt/comfyui/input/                                    │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Directory Layout

```
/opt/
├── comfyui/
│   ├── main.py                          # ComfyUI entry point
│   ├── venv/                            # Python environment
│   ├── models/
│   │   ├── unet/
│   │   │   └── flux1-dev-fp8.safetensors       # ~12GB
│   │   ├── clip/
│   │   │   ├── t5xxl_fp8_e4m3fn.safetensors    # ~5GB
│   │   │   └── clip_l.safetensors               # ~250MB
│   │   ├── vae/
│   │   │   └── ae.safetensors                   # ~330MB
│   │   └── loras/
│   │       └── Hyper-FLUX.1-dev-8steps-lora.safetensors  # ~750MB
│   ├── output/                          # Generated images
│   ├── input/                           # Reference images for img2img
│   └── custom_nodes/
│       ├── ComfyUI-Manager/
│       ├── ComfyUI_IPAdapter_plus/
│       ├── ComfyUI-KJNodes/
│       ├── rgthree-comfy/
│       └── efficiency-nodes-comfyui/
│
└── civ-leader-api/
    ├── main.py                          # FastAPI app
    ├── config.py                        # Constants, enum maps, templates
    ├── models.py                        # Pydantic request/response schemas
    ├── prompt_engine.py                 # Prompt assembly
    ├── workflow_mutator.py              # Workflow JSON manipulation
    ├── comfyui_client.py                # HTTP client for ComfyUI
    ├── leader_registry.py               # Leader ID → reference image
    ├── workflows/
    │   └── civ_leader_assets.json       # The single workflow
    ├── tests/
    │   └── test_integration.py
    └── requirements.txt
```

---

## 2. Phase 1: Base System & ComfyUI Installation

### 2.1 GPU Driver & CUDA

```bash
# Ubuntu 22.04 / 24.04
sudo apt update
sudo apt install nvidia-driver-550 -y
sudo reboot

# Verify
nvidia-smi

# CUDA toolkit
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install cuda-toolkit-12-4 -y
```

### 2.2 ComfyUI

```bash
cd /opt
git clone https://github.com/comfyanonymous/ComfyUI.git comfyui
cd comfyui

python3 -m venv venv
source venv/bin/activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

# Custom nodes
cd custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git
git clone https://github.com/kijai/ComfyUI-KJNodes.git
git clone https://github.com/rgthree/rgthree-comfy.git
git clone https://github.com/jags111/efficiency-nodes-comfyui.git

for d in */; do
    [ -f "${d}requirements.txt" ] && pip install -r "${d}requirements.txt"
done
```

### 2.3 Model Downloads

```bash
cd /opt/comfyui/models

# --- UNet (fp8 — fits 24GB VRAM) ---
mkdir -p unet
cd unet
wget -O flux1-dev-fp8.safetensors \
  https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-dev-fp8.safetensors

# --- Text Encoders ---
cd /opt/comfyui/models/clip
wget -O t5xxl_fp8_e4m3fn.safetensors \
  https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors
wget -O clip_l.safetensors \
  https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors

# --- VAE ---
cd /opt/comfyui/models/vae
wget -O ae.safetensors \
  https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors

# --- Hyper-SD LoRA ---
cd /opt/comfyui/models/loras
wget -O Hyper-FLUX.1-dev-8steps-lora.safetensors \
  https://huggingface.co/ByteDance/Hyper-SD/resolve/main/Hyper-FLUX.1-dev-8steps-lora.safetensors
```

### 2.4 Verify ComfyUI Starts

```bash
cd /opt/comfyui
source venv/bin/activate
python main.py --listen 0.0.0.0 --port 8188 --highvram
```

Open `http://<ip>:8188` in a browser. Build the workflow below manually, test it, then export as API JSON.

---

## 3. Phase 2: The Workflow

### 3.1 Node Specification

Build this in ComfyUI desktop. One workflow handles all three asset types.

```
Node #1  — UNETLoader
           unet_name:    flux1-dev-fp8.safetensors
           weight_dtype: fp8

Node #2  — DualCLIPLoader
           clip_name1:   t5xxl_fp8_e4m3fn.safetensors
           clip_name2:   clip_l.safetensors
           type:         flux

Node #3  — VAELoader
           vae_name:     ae.safetensors

Node #4  — LoraLoaderModelOnly
           lora_name:    Hyper-FLUX.1-dev-8steps-lora.safetensors
           strength:     0.75
           model:        ← from UNETLoader

Node #5  — CLIPTextEncode  (title: "PositivePrompt")
           clip:         ← from DualCLIPLoader (clip_name1)
           text:         [SWAPPED PER REQUEST]

Node #6  — CLIPTextEncode  (title: "NegativePrompt")
           clip:         ← from DualCLIPLoader (clip_name1)
           text:         [STATIC NEGATIVE — SWAPPED ONCE]

Node #7  — EmptyFluxLatentImage  (title: "LatentImage")
           width:        [SWAPPED: 1920 or 1024]
           height:       [SWAPPED: 1088 or 1024]
           batch_size:   1

Node #8  — LoadImage  (title: "ReferenceImage")
           image:        [SWAPPED or DISCONNECTED]

Node #9  — VAEEncode  (title: "VAEEncodeIn")
           pixels:       ← from LoadImage
           vae:          ← from VAELoader

Node #10 — KSamplerAdvanced  (title: "KSampler")
           model:        ← from LoraLoaderModelOnly
           positive:     ← from PositivePrompt
           negative:     ← from NegativePrompt
           latent_image: ← from LatentImage  OR  from VAEEncodeIn
           seed:         [SWAPPED]
           control_after_generate: randomize
           steps:        8
           cfg:          1.8
           sampler_name: euler
           scheduler:    beta
           denoise:      [SWAPPED: 1.0 | 0.30 | 0.60]

Node #11 — VAEDecode  (title: "Decode")
           samples:      ← from KSampler
           vae:          ← from VAELoader

Node #12 — SaveImage  (title: "SaveImage")
           images:       ← from VAEDecode
           filename_prefix: [SWAPPED]
```

### 3.2 The One-Image Connection Detail

For **splash mode**: `KSamplerAdvanced.latent_image` receives from `LatentImage` (the empty latent). `ReferenceImage` and `VAEEncodeIn` exist in the graph but have no links — they're inert.

For **profile/action mode**: `KSamplerAdvanced.latent_image` receives from `VAEEncodeIn`. `ReferenceImage` is loaded, encoded through `VAEEncodeIn`, and fed as the initial latent. The `LatentImage` node is still present but disconnected from KSampler. Crucially, even though LatentImage is 1024×1024 and ReferenceImage is 1920×1088 (or vice versa), the VAE encode/decode handles aspect ratio changes natively — the latent gets resized by the KSampler's internal processing.

### 3.3 Workflow Swaps Per Asset Type

| Node | Splash | Profile | Action |
|------|--------|---------|--------|
| PositivePrompt text | splash prompt | profile prompt | action prompt |
| NegativePrompt text | static block | static block | static block |
| LatentImage width | 1920 | 1024 | 1920 |
| LatentImage height | 1088 | 1024 | 1088 |
| ReferenceImage image | *(disconnected)* | `ref_{leader_id}.png` | `ref_{leader_id}.png` |
| KSampler seed | random 14-digit | *(same seed)* | *(same seed)* |
| KSampler denoise | 1.0 | 0.30 | 0.60 |
| KSampler latent_image | from LatentImage | from VAEEncodeIn | from VAEEncodeIn |
| SaveImage prefix | `splash` | `profile` | `action` |

### 3.4 Export as API JSON

In ComfyUI desktop, once the workflow is built and tested:
1. Click the gear icon (Settings) in the top-right toolbar
2. Select **"Save (API Format)"**
3. Save as `/opt/civ-leader-api/workflows/civ_leader_assets.json`

This produces JSON with node IDs that the workflow mutator can target.

---

## 4. Phase 3: API Server Code

### 4.1 `requirements.txt`

```
fastapi==0.115.1
uvicorn[standard]==0.30.6
httpx==0.27.2
pydantic==2.9.2
python-multipart==0.0.12
```

```bash
cd /opt/civ-leader-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4.2 `config.py`

```python
"""All constants, enum injection maps, and prompt templates."""

# --- ComfyUI ---
COMFYUI_URL = "http://localhost:8188"

# --- Models ---
MODEL_CONFIG = {
    "unet": "flux1-dev-fp8.safetensors",
    "clip_t5": "t5xxl_fp8_e4m3fn.safetensors",
    "clip_l": "clip_l.safetensors",
    "vae": "ae.safetensors",
    "hyper_lora": "Hyper-FLUX.1-dev-8steps-lora.safetensors",
    "lora_strength": 0.75,
    "steps": 8,
    "cfg": 1.8,
    "sampler": "euler",
    "scheduler": "beta",
}

# --- Resolution ---
RESOLUTIONS = {
    "splash": (1920, 1088),
    "profile": (1024, 1024),
    "action": (1920, 1088),
}

# --- Denoise ---
DENOISE_MAP = {
    "splash": 1.0,
    "profile": 0.30,
    "action": 0.60,
}

# --- Paths ---
OUTPUT_DIR = "/opt/comfyui/output"
REFERENCE_DIR = "/opt/comfyui/input"
WORKFLOW_PATH = "/opt/civ-leader-api/workflows/civ_leader_assets.json"
REGISTRY_PATH = "/opt/civ-leader-api/leaders.json"

# --- Negative Prompt ---
NEGATIVE_PROMPT = (
    "blurry, low quality, distorted, ugly, deformed face, bad hands, "
    "missing fingers, text, watermark, signature, logo, cartoon, 3D render, "
    "photograph, selfie, modern clothing, jeans, t-shirt, plastic, "
    "oversaturated colors, bad anatomy, extra limbs, cloned face, disfigured, "
    "jpeg artifacts"
)

# --- Archetype Injections ---
ARCHETYPE = {
    "warrior_queen": (
        "standing proudly, martial bearing, armor and weapons prominent, "
        "battle-hardened confidence"
    ),
    "warrior_king": (
        "commanding presence, battle-scarred dignity, weapon in hand, "
        "military authority"
    ),
    "philosopher_king": (
        "seated or standing in contemplation, scrolls or scientific instruments "
        "nearby, learned wisdom"
    ),
    "merchant_prince": (
        "calculating gaze, surrounded by symbols of wealth and trade, "
        "shrewd intelligence"
    ),
    "spiritual_leader": (
        "mystical aura, religious or natural symbols, ceremonial pose, "
        "transcendent connection"
    ),
    "diplomat": (
        "open posture, formal court or negotiating setting, measured diplomacy"
    ),
    "tyrant": (
        "imposing dominance, deep shadows, iron grip on throne or weapon, "
        "intimidating power"
    ),
    "visionary": (
        "gazing toward horizon, plans or blueprints in hand, forward-looking ambition"
    ),
}

# --- Culture Injections ---
CULTURE = {
    "ancient_egyptian": (
        "a vast sandstone temple with towering hieroglyph-carved pillars, "
        "gold and lapis lazuli accents, bronze braziers burning incense, "
        "desert beyond colonnades"
    ),
    "classical_greek": (
        "a marble temple with corinthian columns, olive groves on the hillside, "
        "Aegean blue sea in the distance, white stone catching golden light"
    ),
    "roman_imperial": (
        "a grand travertine forum with domes and aqueducts, crimson banners "
        "with gold eagles, paved stone plaza, imperial majesty"
    ),
    "medieval_european": (
        "a stone castle great hall with oak beams, heraldic tapestries, iron "
        "chandeliers, stained glass catching colored light through tall windows"
    ),
    "east_asian_imperial": (
        "a magnificent jade and red lacquer palace interior, silk screens with "
        "landscape paintings, cherry blossoms visible through moon gates, misty "
        "mountains beyond"
    ),
    "mesopotamian": (
        "a mud-brick ziggurat temple complex, bronze and lapis lazuli ornamentation, "
        "reed marshes and twin rivers visible in the distance"
    ),
    "mesoamerican": (
        "a stone step pyramid amid dense jungle, obsidian mirrors, jade ornaments "
        "and quetzal feather adornments, carved stone stelae in the foreground"
    ),
    "nordic_viking": (
        "a timber longhouse with carved dragon posts, fur-draped walls, iron "
        "braziers casting warm light, fjord waters and northern lights through "
        "the smoke hole above"
    ),
    "persian": (
        "a blue-tiled palace overlooking cypress gardens and reflecting pools, "
        "silk curtains billowing in mountain breeze, snow-capped peaks in the distance"
    ),
    "sub_saharan_african": (
        "a grand mud-brick structure with carved wooden beams, gold and ivory "
        "ornaments, baobab trees on the savanna horizon, richly woven textile hangings"
    ),
    "south_asian": (
        "a sandstone temple complex with intricate carvings, lotus ponds reflecting "
        "the architecture, gold jewelry catching warm sunlight, monsoon clouds "
        "gathering dramatically"
    ),
    "islamic_golden_age": (
        "a domed observatory with intricate geometric tile patterns, brass "
        "astrolabes on pedestals, parchment manuscripts on shelves, arabesque "
        "arches framing a star-filled desert sky"
    ),
}

# --- Time of Day Injections ---
TIME_OF_DAY = {
    "dawn": (
        "first light of dawn breaking over the horizon, cool blue shadows "
        "giving way to warm gold, mist rising from the ground"
    ),
    "golden_hour": (
        "low golden sunlight casting long dramatic shadows, warm amber glow "
        "suffusing everything, dust motes dancing in light beams"
    ),
    "midday": (
        "harsh clear sunlight from overhead, strong contrast with deep black "
        "shadows, bright cloudless sky"
    ),
    "twilight": (
        "purple and orange sky at the boundary of day and night, torches and "
        "braziers being lit, the first stars appearing"
    ),
    "night": (
        "deep night with moonlight streaming through openings, warm firelight "
        "from torches and braziers, stars visible overhead"
    ),
    "storm": (
        "dark brooding storm clouds massing overhead, dramatic lightning "
        "illuminating the scene in flashes, wind whipping through"
    ),
}

# --- Mood Injections ---
MOOD = {
    "triumphant": (
        "expression of hard-won victory, proud celebratory atmosphere, head held high"
    ),
    "wise_serene": (
        "expression of profound calm wisdom, peaceful dignified atmosphere, "
        "gentle knowing gaze"
    ),
    "grim_determined": (
        "expression of steely unbreakable resolve, tense charged atmosphere, "
        "jaw set firm"
    ),
    "mystical": (
        "expression of spiritual transcendence, ethereal otherworldly atmosphere, "
        "eyes seeing beyond the visible"
    ),
    "melancholic": (
        "expression of bittersweet reflection, quiet somber atmosphere, heavy "
        "with history and memory"
    ),
    "menacing": (
        "expression of cold calculated power, oppressive intimidating atmosphere, "
        "danger crackling in the air"
    ),
    "hopeful": (
        "expression of optimistic vision, bright aspirational atmosphere, looking "
        "toward possibility"
    ),
    "contemplative": (
        "expression of deep thought, quiet introspective atmosphere, weighing "
        "profound decisions"
    ),
}

# --- Action Category Injections ---
ACTION_CATEGORY = {
    "military": (
        "dynamic action composition, weapons drawn, battlefield context with "
        "smoke and banners, cavalry and infantry in motion"
    ),
    "diplomatic": (
        "formal court or neutral meeting ground, treaty documents on the table, "
        "multiple parties present, ceremonial exchange unfolding"
    ),
    "construction": (
        "monument or great building in progress, workers on scaffolding, stone "
        "blocks being lifted by cranes, immense civic scale"
    ),
    "scientific": (
        "instruments and scrolls in an observatory or study, moment of breakthrough "
        "discovery, intellectual excitement in the air"
    ),
    "cultural": (
        "ceremony or festival with rich ritual elements, artistic performance "
        "in progress, gathered audience, cultural pageantry"
    ),
    "exploration": (
        "newly discovered territory unfolding before them, map unfurled on a "
        "stone table, scouts pointing ahead, vista of unknown lands"
    ),
    "crisis": (
        "imminent threat approaching, the leader responding to emergency, tense "
        "urgent body language, decisive action required"
    ),
}

# --- Style Tails ---
STYLE_TAIL = (
    "civilization leader splash screen art, rich painterly oil style, "
    "masterpiece composition, dramatic lighting, by Craig Mullins and "
    "Greg Rutkowski, 8K, highly detailed, 16:9 cinematic aspect ratio"
)

PROFILE_TAIL = (
    "civilization leader profile picture, sharp focus on eyes, Rembrandt "
    "lighting, portrait lens 85mm f/1.4, very shallow depth of field, bokeh "
    "background, highly detailed skin texture and pores, 8K, square format"
)

ACTION_TAIL = (
    "civilization game event art, rich painterly oil style, dramatic composition, "
    "consistent character design, highly detailed, 8K, 16:9 cinematic aspect ratio"
)
```

### 4.3 `models.py`

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Literal


class AssetType(str, Enum):
    SPLASH = "splash"
    PROFILE = "profile"
    ACTION = "action"


class Archetype(str, Enum):
    WARRIOR_QUEEN = "warrior_queen"
    WARRIOR_KING = "warrior_king"
    PHILOSOPHER_KING = "philosopher_king"
    MERCHANT_PRINCE = "merchant_prince"
    SPIRITUAL_LEADER = "spiritual_leader"
    DIPLOMAT = "diplomat"
    TYRANT = "tyrant"
    VISIONARY = "visionary"


class Culture(str, Enum):
    ANCIENT_EGYPTIAN = "ancient_egyptian"
    CLASSICAL_GREEK = "classical_greek"
    ROMAN_IMPERIAL = "roman_imperial"
    MEDIEVAL_EUROPEAN = "medieval_european"
    EAST_ASIAN_IMPERIAL = "east_asian_imperial"
    MESOPOTAMIAN = "mesopotamian"
    MESOAMERICAN = "mesoamerican"
    NORDIC_VIKING = "nordic_viking"
    PERSIAN = "persian"
    SUB_SAHARAN_AFRICAN = "sub_saharan_african"
    SOUTH_ASIAN = "south_asian"
    ISLAMIC_GOLDEN_AGE = "islamic_golden_age"


class TimeOfDay(str, Enum):
    DAWN = "dawn"
    GOLDEN_HOUR = "golden_hour"
    MIDDAY = "midday"
    TWILIGHT = "twilight"
    NIGHT = "night"
    STORM = "storm"


class Mood(str, Enum):
    TRIUMPHANT = "triumphant"
    WISE_SERENE = "wise_serene"
    GRIM_DETERMINED = "grim_determined"
    MYSTICAL = "mystical"
    MELANCHOLIC = "melancholic"
    MENACING = "menacing"
    HOPEFUL = "hopeful"
    CONTEMPLATIVE = "contemplative"


class ActionCategory(str, Enum):
    MILITARY = "military"
    DIPLOMATIC = "diplomatic"
    CONSTRUCTION = "construction"
    SCIENTIFIC = "scientific"
    CULTURAL = "cultural"
    EXPLORATION = "exploration"
    CRISIS = "crisis"


class GenerateRequest(BaseModel):
    asset_type: AssetType
    leader_name: str = Field(
        max_length=100,
        description="Human-readable leader name, e.g. 'Cleopatra VII'"
    )
    leader_description: str = Field(
        min_length=50, max_length=800,
        description=(
            "Physical description: age, build, skin tone, hair, eyes, "
            "distinctive features (scar, tattoo, jewelry), clothing materials "
            "and colors, expression and bearing. No camera directions or style words."
        )
    )
    archetype: Archetype
    culture: Culture
    time_of_day: TimeOfDay
    mood: Mood
    leader_id: Optional[str] = Field(
        default=None,
        description=(
            "Required for profile and action assets. "
            "The leader_id returned from a previous splash generation."
        )
    )
    action_category: Optional[ActionCategory] = Field(
        default=None,
        description="Required for action scenes only."
    )
    action_description: Optional[str] = Field(
        default=None, max_length=800,
        description=(
            "What is happening in this scene. Single moment, single action. "
            "Required for action scenes only."
        )
    )


class GenerateResponse(BaseModel):
    status: Literal["completed", "failed"]
    asset_type: AssetType
    leader_name: str
    leader_id: str
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    seed: Optional[int] = None
    generation_time_ms: Optional[int] = None
    resolution: Optional[str] = None
    prompt_used: Optional[str] = None
    error: Optional[str] = None


class LeaderInfo(BaseModel):
    leader_id: str
    leader_name: str
    splash_filename: str
    created_at: str
```

### 4.4 `prompt_engine.py`

```python
"""Assembles final prompts from request fields and enum injection maps."""

from config import (
    ARCHETYPE, CULTURE, TIME_OF_DAY, MOOD, ACTION_CATEGORY,
    STYLE_TAIL, PROFILE_TAIL, ACTION_TAIL,
)
from models import GenerateRequest


def build_splash_prompt(req: GenerateRequest) -> str:
    parts = [
        f"epic cinematic wide composition of {req.leader_description.strip()},",
        ARCHETYPE[req.archetype.value],
        f"in {CULTURE[req.culture.value]}",
        TIME_OF_DAY[req.time_of_day.value],
        MOOD[req.mood.value],
        STYLE_TAIL,
    ]
    return ", ".join(parts)


def build_profile_prompt(req: GenerateRequest) -> str:
    parts = [
        f"professional close-up portrait of {req.leader_description.strip()},",
        "face filling the frame",
        "headpiece and collar visible at the edges of the frame",
        MOOD[req.mood.value],
        PROFILE_TAIL,
    ]
    return ", ".join(parts)


def build_action_prompt(req: GenerateRequest) -> str:
    parts = [
        f"epic cinematic scene depicting {req.leader_description.strip()}",
        req.action_description.strip(),
        f"in {CULTURE[req.culture.value]}",
        TIME_OF_DAY[req.time_of_day.value],
        MOOD[req.mood.value],
        ACTION_CATEGORY[req.action_category.value],
        ACTION_TAIL,
    ]
    return ", ".join(parts)


def build_prompt(req: GenerateRequest) -> str:
    builders = {
        "splash": build_splash_prompt,
        "profile": build_profile_prompt,
        "action": build_action_prompt,
    }
    return builders[req.asset_type.value](req)
```

### 4.5 `workflow_mutator.py`

```python
"""Loads the base workflow JSON and mutates it per request."""

import json
import random
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from config import (
    WORKFLOW_PATH, RESOLUTIONS, DENOISE_MAP, NEGATIVE_PROMPT, OUTPUT_DIR
)
from models import AssetType


class WorkflowMutator:
    def __init__(self):
        with open(WORKFLOW_PATH) as f:
            self._base = json.load(f)
        self._index = self._build_index()

    def _build_index(self) -> Dict[str, str]:
        """Map node titles → node IDs."""
        index = {}
        for nid, node in self._base["nodes"].items():
            title = node.get("title", "")
            if title:
                index[title] = nid
        return index

    def _nid(self, title: str) -> str:
        return self._index[title]

    def build(
        self,
        asset_type: AssetType,
        positive_prompt: str,
        seed: Optional[int] = None,
        reference_image_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        wf = json.loads(json.dumps(self._base))

        if seed is None:
            seed = random.randint(10 ** 14, 10 ** 15 - 1)

        at = asset_type.value
        width, height = RESOLUTIONS[at]
        denoise = DENOISE_MAP[at]

        # --- Positive prompt ---
        wf["nodes"][self._nid("PositivePrompt")]["widgets_values"][0] = positive_prompt

        # --- Negative prompt ---
        wf["nodes"][self._nid("NegativePrompt")]["widgets_values"][0] = NEGATIVE_PROMPT

        # --- Resolution ---
        wf["nodes"][self._nid("LatentImage")]["widgets_values"][0] = width
        wf["nodes"][self._nid("LatentImage")]["widgets_values"][1] = height

        # --- Seed ---
        wf["nodes"][self._nid("KSampler")]["widgets_values"][0] = seed

        # --- Denoise ---
        denoise_widget_idx = self._find_denoise_index(wf)
        wf["nodes"][self._nid("KSampler")]["widgets_values"][denoise_widget_idx] = denoise

        # --- SaveImage prefix ---
        wf["nodes"][self._nid("SaveImage")]["widgets_values"][0] = at

        # --- Reference image path and routing ---
        self._apply_reference(wf, asset_type, reference_image_name)

        return wf

    def _find_denoise_index(self, wf) -> int:
        """Locate the denoise widget in KSamplerAdvanced's widget_values list."""
        node = wf["nodes"][self._nid("KSampler")]
        # KSamplerAdvanced widget order: seed, control_after_gen, steps, cfg,
        # sampler_name, scheduler, denoise
        # We need to be defensive: count widgets or look for a float near 1.0
        for i, w in enumerate(node["widgets_values"]):
            if isinstance(w, (float, int)) and 0 <= w <= 1.5:
                return i
        # Fallback: KSamplerAdvanced denoise is typically index 6
        return 6

    def _apply_reference(
        self,
        wf: dict,
        asset_type: AssetType,
        reference_image_name: Optional[str],
    ):
        """
        For splash: disconnect ReferenceImage → VAEEncodeIn → KSampler.
        For profile/action: connect the chain and set the image.
        """
        ref_nid = int(self._nid("ReferenceImage"))
        enc_nid = int(self._nid("VAEEncodeIn"))
        ksampler_nid = int(self._nid("KSampler"))

        if asset_type == AssetType.SPLASH or reference_image_name is None:
            # Remove all links involving ReferenceImage or VAEEncodeIn
            wf["links"] = [
                l for l in wf["links"]
                if l[0] not in (ref_nid, enc_nid)
                and l[2] not in (ref_nid, enc_nid)
            ]
            # Also ensure KSampler latent_image (input slot 3 in older nodes,
            # or find the latent slot) is left connected only from LatentImage
            latent_nid = int(self._nid("LatentImage"))
            # Remove any link targeting KSampler's latent input
            wf["links"] = [
                l for l in wf["links"]
                if not (l[2] == ksampler_nid and l[3] == 3)
            ]
            # Re-ensure LatentImage → KSampler latent
            wf["links"].append([latent_nid, 0, ksampler_nid, 3])
        else:
            # Enable reference image path
            wf["nodes"][self._nid("ReferenceImage")]["widgets_values"][0] = reference_image_name
            # Remove existing links to KSampler latent input
            wf["links"] = [
                l for l in wf["links"]
                if not (l[2] == ksampler_nid and l[3] == 3)
            ]
            # Build chain: ReferenceImage → VAEEncodeIn → KSampler latent
            wf["links"].append([ref_nid, 0, enc_nid, 0])
            wf["links"].append([enc_nid, 0, ksampler_nid, 3])
```

### 4.6 `comfyui_client.py`

```python
import time
import httpx
from typing import Dict, Optional


class ComfyUIClient:
    """Thin HTTP client for ComfyUI's REST API."""

    def __init__(self, base_url: str = "http://localhost:8188", timeout: int = 120):
        self.base_url = base_url
        self.timeout = timeout

    async def submit(self, workflow: Dict) -> str:
        """POST /prompt. Returns prompt_id."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as c:
            resp = await c.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow}
            )
            resp.raise_for_status()
            data = resp.json()
            if "prompt_id" not in data:
                raise RuntimeError(f"No prompt_id in response: {data}")
            return data["prompt_id"]

    async def wait(self, prompt_id: str, poll_interval: float = 0.5) -> Dict:
        """Poll /history/{prompt_id} until result or timeout."""
        deadline = time.time() + self.timeout
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as c:
            while time.time() < deadline:
                resp = await c.get(f"{self.base_url}/history/{prompt_id}")
                resp.raise_for_status()
                history = resp.json()
                if prompt_id in history:
                    entry = history[prompt_id]
                    if "outputs" in entry:
                        return entry
                await asyncio.sleep(poll_interval)
        raise TimeoutError(f"Timed out waiting for prompt {prompt_id}")

    async def upload_image(self, data: bytes, filename: str) -> str:
        """Upload a reference image to ComfyUI's input directory."""
        async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as c:
            resp = await c.post(
                f"{self.base_url}/upload/image",
                files={"image": (filename, data, "image/png")},
                data={"type": "input", "overwrite": "true"},
            )
            resp.raise_for_status()
            return resp.json()["name"]

    async def health(self) -> bool:
        """Check if ComfyUI is responsive."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5)) as c:
                resp = await c.get(f"{self.base_url}/system_stats")
                return resp.status_code == 200
        except Exception:
            return False


import asyncio  # needed for sleep in wait()
```

### 4.7 `leader_registry.py`

```python
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict

from config import REGISTRY_PATH, OUTPUT_DIR, REFERENCE_DIR


class LeaderRegistry:
    def __init__(self):
        self._path = Path(REGISTRY_PATH)
        self._leaders: Dict[str, dict] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            self._leaders = json.loads(self._path.read_text())

    def _save(self):
        self._path.write_text(json.dumps(self._leaders, indent=2))

    def register(self, leader_id: str, leader_name: str, splash_filename: str) -> str:
        src = Path(OUTPUT_DIR) / splash_filename
        ref_name = f"ref_{leader_id}.png"
        dst = Path(REFERENCE_DIR) / ref_name
        shutil.copy2(src, dst)

        self._leaders[leader_id] = {
            "leader_id": leader_id,
            "leader_name": leader_name,
            "reference_image": ref_name,
            "splash_filename": splash_filename,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        return ref_name

    def get_reference(self, leader_id: str) -> Optional[str]:
        entry = self._leaders.get(leader_id)
        return entry["reference_image"] if entry else None

    def exists(self, leader_id: str) -> bool:
        return leader_id in self._leaders

    def get(self, leader_id: str) -> Optional[dict]:
        return self._leaders.get(leader_id)

    def list_all(self) -> list:
        return list(self._leaders.values())
```

### 4.8 `main.py`

```python
import uuid
import time
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from config import OUTPUT_DIR, REFERENCE_DIR, RESOLUTIONS
from models import GenerateRequest, GenerateResponse, AssetType, LeaderInfo
from prompt_engine import build_prompt
from workflow_mutator import WorkflowMutator
from comfyui_client import ComfyUIClient
from leader_registry import LeaderRegistry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Civ Leader Art API", version="1.0.0")

mutator = WorkflowMutator()
comfyui = ComfyUIClient()
registry = LeaderRegistry()

app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")


@app.on_event("startup")
async def startup():
    healthy = await comfyui.health()
    if not healthy:
        logger.error("ComfyUI is not reachable at startup")
    else:
        logger.info("ComfyUI connected")


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    # --- Validate ---
    if req.asset_type != AssetType.SPLASH:
        if not req.leader_id:
            raise HTTPException(400, "leader_id required for profile and action assets")
        if not registry.exists(req.leader_id):
            raise HTTPException(404, f"Leader '{req.leader_id}' not found. Generate a splash first.")

    if req.asset_type == AssetType.ACTION:
        if not req.action_category:
            raise HTTPException(400, "action_category required for action assets")
        if not req.action_description:
            raise HTTPException(400, "action_description required for action assets")

    # --- Leader ID ---
    leader_id = req.leader_id or (
        f"leader_{req.leader_name.lower().replace(' ', '_')[:40]}_{uuid.uuid4().hex[:6]}"
    )

    # --- Reference image ---
    ref_name = None
    if req.asset_type != AssetType.SPLASH:
        ref_name = registry.get_reference(leader_id)
        if not ref_name or not (Path(REFERENCE_DIR) / ref_name).exists():
            raise HTTPException(500, f"Reference image missing for leader '{leader_id}'")

    # --- Build prompt ---
    prompt = build_prompt(req)

    # --- Build workflow ---
    workflow = mutator.build(
        asset_type=req.asset_type,
        positive_prompt=prompt,
        reference_image_name=ref_name,
    )

    # --- Submit ---
    start = time.time()

    if ref_name:
        ref_path = Path(REFERENCE_DIR) / ref_name
        try:
            await comfyui.upload_image(ref_path.read_bytes(), ref_name)
        except Exception as e:
            raise HTTPException(502, f"Failed to upload reference image: {e}")

    try:
        prompt_id = await comfyui.submit(workflow)
    except Exception as e:
        raise HTTPException(502, f"ComfyUI submission failed: {e}")

    try:
        result = await comfyui.wait(prompt_id)
    except TimeoutError:
        raise HTTPException(504, "Generation timed out")

    # --- Extract filename ---
    try:
        output_node = list(result["outputs"].values())[0]
        image_info = output_node["images"][0]
        filename = image_info["filename"]
        subfolder = image_info.get("subfolder", "")
    except (KeyError, IndexError) as e:
        raise HTTPException(500, f"Failed to parse ComfyUI output: {e}")

    # --- Register new leader ---
    if req.asset_type == AssetType.SPLASH:
        registry.register(leader_id, req.leader_name, filename)

    # --- Extract seed ---
    seed = workflow["nodes"][mutator._nid("KSampler")]["widgets_values"][0]
    elapsed = int((time.time() - start) * 1000)
    at = req.asset_type.value

    image_url = f"/output/{subfolder}/{filename}" if subfolder else f"/output/{filename}"

    return GenerateResponse(
        status="completed",
        asset_type=req.asset_type,
        leader_name=req.leader_name,
        leader_id=leader_id,
        image_path=str(Path(OUTPUT_DIR) / subfolder / filename if subfolder else Path(OUTPUT_DIR) / filename),
        image_url=image_url,
        seed=seed,
        generation_time_ms=elapsed,
        resolution=f"{RESOLUTIONS[at][0]}x{RESOLUTIONS[at][1]}",
        prompt_used=prompt,
    )


@app.get("/leaders", response_model=list[LeaderInfo])
async def list_leaders():
    return [
        LeaderInfo(**l) for l in registry.list_all()
    ]


@app.get("/leaders/{leader_id}", response_model=LeaderInfo)
async def get_leader(leader_id: str):
    entry = registry.get(leader_id)
    if not entry:
        raise HTTPException(404, f"Leader '{leader_id}' not found")
    return LeaderInfo(**entry)


@app.get("/health")
async def health():
    comfyui_ok = await comfyui.health()
    return {
        "status": "ok" if comfyui_ok else "degraded",
        "comfyui": "connected" if comfyui_ok else "unreachable",
        "leaders_registered": len(registry.list_all()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 5. Phase 4: Productionize

### 5.1 Systemd Services

**`/etc/systemd/system/comfyui.service`**

```ini
[Unit]
Description=ComfyUI
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/comfyui
ExecStart=/opt/comfyui/venv/bin/python main.py --listen 0.0.0.0 --port 8188 --highvram
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/civ-leader-api.service`**

```ini
[Unit]
Description=Civ Leader Art API
After=network.target comfyui.service
Requires=comfyui.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/civ-leader-api
ExecStart=/opt/civ-leader-api/venv/bin/python main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable comfyui civ-leader-api
sudo systemctl start comfyui civ-leader-api
```

### 5.2 Integration Test

```bash
# Health check
curl http://localhost:8000/health

# Generate a splash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "asset_type": "splash",
    "leader_name": "Test Queen",
    "leader_description": "a tall warrior queen with bronze skin and sharp amber eyes, long black hair in tight braids bound with gold rings, wearing engraved bronze scale armor over a crimson linen tunic, a lion-pelt cape fastened at her left shoulder, a healed slash scar across her right cheekbone, expression of calm authority",
    "archetype": "warrior_queen",
    "culture": "ancient_egyptian",
    "time_of_day": "golden_hour",
    "mood": "triumphant"
  }' | python -m json.tool

# Take the leader_id from the response, then:
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "asset_type": "profile",
    "leader_name": "Test Queen",
    "leader_description": "a tall warrior queen with bronze skin and sharp amber eyes, long black hair in tight braids bound with gold rings, healed slash scar across her right cheekbone",
    "leader_id": "LEADER_ID_FROM_SPLASH",
    "archetype": "warrior_queen",
    "culture": "ancient_egyptian",
    "time_of_day": "night",
    "mood": "wise_serene"
  }' | python -m json.tool

# Then action:
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "asset_type": "action",
    "leader_name": "Test Queen",
    "leader_description": "a tall warrior queen with bronze skin and sharp amber eyes, long black hair in tight braids bound with gold rings, wearing engraved bronze scale armor",
    "leader_id": "LEADER_ID_FROM_SPLASH",
    "archetype": "warrior_queen",
    "culture": "ancient_egyptian",
    "time_of_day": "twilight",
    "mood": "grim_determined",
    "action_category": "military",
    "action_description": "standing on horseback at the crest of a hill, cavalry behind her silhouetted against sunset, watching enemy banners lowered in surrender, her bloodied sword resting across her saddle, expression of grim relief"
  }' | python -m json.tool
```

---

## 6. Phase 5: Client Prompt Guide

```
═══════════════════════════════════════════════════════════════════
  CIV LEADER ART API — PROMPT WRITING GUIDE
═══════════════════════════════════════════════════════════════════

ORDER OF OPERATIONS PER LEADER
  1. SPLASH   (generates the canonical reference)
  2. PROFILE  (uses splash as img2img init — same face, close crop)
  3. ACTION   (uses splash as img2img init — new scene, same person)

Profile and Action calls require the leader_id from the Splash response.


LEADER DESCRIPTION (leader_description)
───────────────────────────────────────
Describe the person. Be specific about materials, not generic.

  INCLUDE:
    • Age, build, skin tone, hair style and color, eye color
    • One distinctive feature (scar, unusual jewelry, tattoo, unique weapon)
    • What they wear — exact materials and colors
    • Expression and bearing

  DO NOT INCLUDE:
    • Camera directions ("close-up", "wide shot")
    • Style words ("epic", "cinematic", "beautiful", "masterpiece")
    • Image quality words ("8K", "highly detailed", "sharp")
    • Setting or background description
    • Atmosphere or lighting words

  BAD (60 chars):
    "a cool warrior queen with awesome armor and epic fantasy vibes"

  GOOD (480 chars):
    "a tall warrior queen with bronze skin and sharp amber eyes, long
     black hair in tight braids bound with gold rings, wearing engraved
     bronze scale armor over a crimson linen tunic, a lion-pelt cape
     fastened at her left shoulder, holding a curved khopesh sword
     point-down, a healed slash scar across her right cheekbone,
     expression of calm authority earned through decades of battle"

  For profile and action calls, you can SHORTEN the description —
  retain the key identifying features (scar, braids, armor material).
  The face reference comes from the splash art via img2img.


ACTION DESCRIPTION (action_description)
───────────────────────────────────────
One moment. One action. Describe what the leader is doing right now.

  INCLUDE:
    • What the leader is physically doing
    • Who or what is around them
    • The emotional register — shown through expression or body language

  DO NOT INCLUDE:
    • Multi-step narratives ("first they planned, then built...")
    • Abstract descriptions ("they are strong and victorious")
    • Re-describing the leader's appearance (already in leader_description)

  BAD:
    "the queen fights a huge battle against many enemies and wins"

  GOOD:
    "standing on horseback at the crest of a hill, cavalry behind her
     silhouetted against sunset, watching enemy banners lowered in
     surrender, her bloodied sword resting across her saddle, expression
     of grim relief rather than celebration, smoke rising from the
     distant battlefield"


ENUM VALUES — PICK ONE FROM EACH CATEGORY
─────────────────────────────────────────

ARCHETYPE          CULTURE                   TIME OF DAY
warrior_queen      ancient_egyptian          dawn
warrior_king       classical_greek           golden_hour
philosopher_king   roman_imperial            midday
merchant_prince    medieval_european         twilight
spiritual_leader   east_asian_imperial       night
diplomat           mesopotamian              storm
tyrant             mesoamerican
visionary          nordic_viking
                   persian
                   sub_saharan_african
                   south_asian
                   islamic_golden_age

MOOD               ACTION CATEGORY
triumphant         military
wise_serene        diplomatic
grim_determined    construction
mystical           scientific
melancholic        cultural
menacing           exploration
hopeful            crisis
contemplative
```

---

## 7. Error Handling

| Scenario | HTTP Code | Message |
|----------|-----------|---------|
| `leader_id` missing for profile/action | 400 | `"leader_id required for profile and action assets"` |
| `leader_id` not found | 404 | `"Leader 'X' not found. Generate a splash first."` |
| `action_category` missing for action | 400 | `"action_category required for action assets"` |
| `action_description` missing for action | 400 | `"action_description required for action assets"` |
| `leader_description` < 50 chars | 422 | Pydantic validation |
| ComfyUI unreachable | 502 | `"ComfyUI submission failed: ..."` |
| Generation timeout (>120s) | 504 | `"Generation timed out"` |
| Reference image missing from disk | 500 | `"Reference image missing for leader 'X'"` |
| ComfyUI error in history | 500 | `"Failed to parse ComfyUI output: ..."` |

---

## 8. Directory Summary

```
/opt/comfyui/                        ComfyUI installation
/opt/comfyui/models/unet/              flux1-dev-fp8.safetensors
/opt/comfyui/models/clip/              t5xxl_fp8_e4m3fn, clip_l
/opt/comfyui/models/vae/               ae.safetensors
/opt/comfyui/models/loras/             Hyper-FLUX.1-dev-8steps-lora
/opt/comfyui/output/                   Generated PNGs
/opt/comfyui/input/                    Reference images (ref_*.png)

/opt/civ-leader-api/                  API server
/opt/civ-leader-api/main.py            FastAPI app
/opt/civ-leader-api/config.py          Constants, enums, templates
/opt/civ-leader-api/models.py          Pydantic schemas
/opt/civ-leader-api/prompt_engine.py   Prompt assembly
/opt/civ-leader-api/workflow_mutator.py Workflow JSON mutation
/opt/civ-leader-api/comfyui_client.py  ComfyUI HTTP client
/opt/civ-leader-api/leader_registry.py Leader tracking
/opt/civ-leader-api/workflows/         civ_leader_assets.json
/opt/civ-leader-api/leaders.json       Registry data file
```

---

## 9. Implementation Checklist

```
□  GPU driver + CUDA installed
□  ComfyUI cloned, venv created, dependencies installed
□  Custom nodes cloned
□  fp8 models downloaded (4 files)
□  ComfyUI starts at port 8188, --highvram
□  Workflow built in ComfyUI desktop and tested manually
□  Workflow exported as API JSON
□  civ-leader-api directory created, venv, dependencies
□  All Python files written (config, models, prompt_engine,
   workflow_mutator, comfyui_client, leader_registry, main)
□  curl splash → profile → action pipeline passes
□  Systemd services created and enabled
□  Client prompt guide delivered
```