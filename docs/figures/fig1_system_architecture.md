# Figure 1: System Architecture Overview

**Caption**: System architecture showing four primary components and data flow between backend game engine, frontend UI, asset generation server, and LoRA training pipeline.

```mermaid
graph TB
    %% ── Styling ──
    classDef backend fill:#2563eb,color:#fff,stroke:#1d4ed8,stroke-width:2px
    classDef frontend fill:#16a34a,color:#fff,stroke:#15803d,stroke-width:2px
    classDef assetserver fill:#ea580c,color:#fff,stroke:#c2410c,stroke-width:2px
    classDef training fill:#7c3aed,color:#fff,stroke:#6d28d9,stroke-width:2px
    classDef external fill:#6b7280,color:#fff,stroke:#4b5563,stroke-width:2px,stroke-dasharray: 5 5
    classDef storage fill:#f59e0b,color:#1c1917,stroke:#d97706,stroke-width:2px

    %% ── External Services ──
    openai["🧠 OpenAI API<br/>GPT-4 / tool-use<br/>(LLM Strategic Reasoning)"]
    comfyui["🎨 ComfyUI Workers<br/>FLUX2 Klein 4B Distilled<br/>(DiT Inference)"]
    huggingface["🤗 HuggingFace Hub<br/>stixxert/topdown-medieval-pixelart<br/>stixxert/strategai-lora"]

    %% ── Backend ──
    subgraph backend_box["  BACKEND  |  Python 3.11+ · FastAPI · port :8000  "]
        direction TB
        api["REST API Layer<br/>14 endpoints"]
        engine["Game Engine<br/>Pure Functional · Frozen Dataclasses<br/>339+ tests"]
        llm_int["LLM Integration<br/>openai_goals.py · 9 intent tools<br/>Per-leader personas · Rolling memory"]
        store["In-Memory GameStore<br/>Threading lock"]
        api --> engine
        engine --> llm_int
        engine --> store
    end

    %% ── Frontend ──
    subgraph frontend_box["  FRONTEND  |  Next.js 15 · React 19 · TypeScript · SVG  "]
        direction TB
        ui["Game UI<br/>HexMap.tsx · Panels · Chat"]
        state_mgmt["State Management<br/>useState + useRef + useMemo"]
        asset_lib["Asset Resolution<br/>assetManifest.ts<br/>Fallback: colors/glyphs/initials"]
        ui --> state_mgmt
        ui --> asset_lib
    end

    %% ── Asset Server ──
    subgraph assetserver_box["  ASSET SERVER  |  Python 3.10+ · FastAPI · port :8001  "]
        direction TB
        asset_api["REST API<br/>6 asset families · 35 endpoints"]
        prompt_engine["4-Layer Prompt Assembly<br/>Workflow → Template → Enum → Assembly"]
        gen_engine["Generation Engine<br/>txt2img · img2img · ImageStitch<br/>3 modes: comfyui / static / placeholder"]
        lb["ComfyUI Load Balancer<br/>Multi-node · LRU cache"]
        asset_api --> prompt_engine
        prompt_engine --> gen_engine
        gen_engine --> lb
    end

    %% ── Training Pipeline ──
    subgraph training_box["  DATASET / TRAINING  |  Python 3.10+ · Ostris AI Toolkit  "]
        direction TB
        dataset["Dataset Curation<br/>100 images · 3 caption variants<br/>Top-down medieval pixel art"]
        lora_train["LoRA Fine-Tuning<br/>6-experiment matrix<br/>3 caption × 2 rank levels"]
        publish["HF Publishing<br/>Dataset + LoRA models<br/>Apache 2.0 licensed"]
        dataset --> lora_train --> publish
    end

    %% ── Data Flows ──
    ui <==>|"REST API<br/>Game state · User actions · Chat"| api
    asset_lib -->|"HTTP POST<br/>Asset generation requests"| asset_api
    asset_api -->|"PNG images<br/>Generated assets"| asset_lib
    llm_int <==>|"Tool-use API<br/>Intents + Serialized state"| openai
    lb -->|"HTTP/WebSocket<br/>Workflow execution"| comfyui
    publish -->|"LoRA weights<br/>&lt;tdp&gt; trigger"| gen_engine
    publish -.->|"Published models"| huggingface

    %% ── Key Annotation ──
    note["⚠️ Backend does NOT directly<br/>call Asset Server.<br/>Frontend mediates all<br/>asset requests."]

    %% ── Apply classes ──
    class backend_box,api,engine,llm_int,store backend
    class frontend_box,ui,state_mgmt,asset_lib frontend
    class assetserver_box,asset_api,prompt_engine,gen_engine,lb assetserver
    class training_box,dataset,lora_train,publish training
    class openai,comfyui,huggingface,note external
```

## Key Points

| Component | Tech Stack | Role |
|-----------|-----------|------|
| **Backend** | Python 3.11+, FastAPI, OpenAI API | Game engine, LLM-driven AI civs, REST API |
| **Frontend** | Next.js 15, React 19, TypeScript, SVG | Game UI, hex map rendering, asset integration |
| **Asset Server** | Python 3.10+, FastAPI, ComfyUI, FLUX2 Klein 4B Distilled | On-demand generative pixel art |
| **Training Pipeline** | Python 3.10+, Ostris AI Toolkit | LoRA fine-tuning for top-down medieval style |

## Data Flow Summary

1. **Frontend ↔ Backend**: Bidirectional REST API — game state queries, user actions, diplomacy chat
2. **Frontend → Asset Server**: HTTP POST requests for asset generation (leader, unit, structure, terrain, background tile)
3. **Asset Server → Frontend**: PNG image responses (generated sprites, portraits, tiles)
4. **Backend → OpenAI**: Tool-use API calls — LLM receives serialized game state, emits intents
5. **Asset Server → ComfyUI**: HTTP/WebSocket workflow execution requests
6. **Training → Asset Server**: LoRA weights (`.safetensors`) consumed by ComfyUI at inference time

## Critical Design Decision

The **backend never directly calls the asset server**. The frontend mediates all asset requests. This separation keeps the game engine pure (no I/O to image generation services) and allows the frontend to implement graceful degradation (comfyui → static → placeholder → built-in fallbacks) independently.
