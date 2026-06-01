# StrategAI Report Figures — Mermaid Diagrams
#
# Render to PDF with: mmdc -i figures.md -o figures.pdf
# Or individually: mmdc -i fig1-architecture.mmd -o fig1-architecture.pdf
#
# Figures:
#   Fig 1: System Architecture Overview
#   Fig 2: Intent-Based LLM Abstraction Layer
#   Fig 3: Four-Layer Prompt Architecture
#   Fig 4: Three-Stage Leader Portrait Pipeline
#   Fig 5: LoRA Experiment Results → uses existing PNG (not mermaid)

---

## Fig. 1. System Architecture Overview

```mermaid
graph TB
    subgraph Frontend["🖥️ Frontend (Next.js 15 / React 19)"]
        UI[SVG Hex Map<br/>Diplomacy Chat<br/>Asset Display]
    end

    subgraph Backend["⚙️ Backend (Python 3.11 / FastAPI)"]
        API[REST API<br/>16 endpoints]
        Engine[Pure Functional Game Engine<br/>Frozen Dataclasses]
        LLM[LLM Integration Layer<br/>OpenAI Tool-Use API]
        API --> Engine
        LLM --> Engine
    end

    subgraph AssetServer["🎨 Asset Server (FastAPI / ComfyUI)"]
        PromptEng[Prompt Assembly Engine<br/>4-Layer Architecture]
        ComfyUI[ComfyUI Inference<br/>FLUX.2 Klein 4B Distilled]
        Storage[(Asset Store<br/>SQLite + Disk Cache)]
        PromptEng --> ComfyUI
        ComfyUI --> Storage
    end

    subgraph Training["🔬 Training Pipeline (Ostris AI Toolkit)"]
        Dataset[100-Image Curated Dataset]
        LoRA[LoRA Fine-Tuning<br/>6-Experiment Matrix]
        Weights[LoRA Weights<br/>~250 MB .safetensors]
        Dataset --> LoRA
        LoRA --> Weights
    end

    Frontend <-->|"REST JSON<br/>(game state, actions)"| Backend
    Frontend -->|"HTTP POST<br/>(asset requests)"| AssetServer
    AssetServer -->|"PNG Images<br/>(generated assets)"| Frontend
    Weights -->|"Model Deployment"| ComfyUI
    Backend -.->|"No direct contact"| AssetServer

    classDef frontend fill:#1f77b4,color:#fff,stroke:#0d3b66
    classDef backend fill:#2ca02c,color:#fff,stroke:#1a6b1a
    classDef asset fill:#ff7f0e,color:#fff,stroke:#b85900
    classDef training fill:#9467bd,color:#fff,stroke:#6b3f8c

    class Frontend,UI frontend
    class Backend,API,Engine,LLM backend
    class AssetServer,PromptEng,ComfyUI,Storage asset
    class Training,Dataset,LoRA,Weights training
```

**Caption**: System architecture showing four primary components and their data flows. The frontend mediates all communication — the backend game engine and asset server never interact directly.

---

## Fig. 2. Intent-Based LLM Abstraction Layer

```mermaid
flowchart TD
    subgraph Strategic["🧠 Strategic Layer — LLM (OpenAI)"]
        Prompt["System Prompt<br/>+ Game State View<br/>+ Persona<br/>+ Rolling Memory"]
        IntentEmit["Emits Structured Intents<br/>(JSON via Tool-Use API)"]
        Prompt --> IntentEmit
    end

    subgraph Intents["📋 9 Intent Types"]
        I1["Expand: Found city"]
        I2["Scout: Explore territory"]
        I3["Engage: Attack enemy"]
        I4["Reinforce: Defend position"]
        I5["Speak: Diplomacy message"]
        I6["AdjustStance: Set war/peace"]
        I7["Build: Queue unit"]
        I8["Research: Pick technology"]
        I9["Improve: Build on tile"]
    end

    subgraph Resolution["⚡ Intent Resolution (Deterministic)"]
        Ops["resolve_intents()<br/>Intent → Goals + Directives"]
        Example["Example:<br/>Engage(civ_id=2)<br/>↓<br/>DeclareWar + MoveTo + Attack"]
        Ops --> Example
    end

    subgraph Tactical["🎯 Tactical Layer — Game Engine"]
        Path[A* Pathfinding]
        Combat[Combat Resolution]
        Validate[Rule Validation]
        State[Updated GameState<br/>(Immutable / Frozen)]
        Path --> Validate
        Combat --> Validate
        Validate --> State
    end

    Strategic -->|"Intent JSON"| Intents
    Intents -->|"Typed Dataclass"| Resolution
    Resolution -->|"Goals + Actions"| Tactical

    classDef strategic fill:#1f77b4,color:#fff,stroke:#0d3b66
    classDef intent fill:#ff7f0e,color:#fff,stroke:#b85900
    classDef resolution fill:#2ca02c,color:#fff,stroke:#1a6b1a
    classDef tactical fill:#d62728,color:#fff,stroke:#8b0000

    class Strategic,Prompt,IntentEmit strategic
    class Intents,I1,I2,I3,I4,I5,I6,I7,I8,I9 intent
    class Resolution,Ops,Example resolution
    class Tactical,Path,Combat,Validate,State tactical
```

**Caption**: Two-layer architecture separating strategic LLM reasoning from deterministic tactical execution. The LLM emits high-level intents (top); the engine resolves them into validated actions (bottom). The LLM never accesses `GameState` directly.

---

## Fig. 3. Four-Layer Prompt Architecture

```mermaid
flowchart BT
    subgraph L1["Layer 1: Workflow Configuration"]
        L1D["ComfyUI Node Graph JSON<br/>Model: FLUX.2 Klein 4B Distilled<br/>Sampler: euler · Steps: 4<br/>Resolution: 1024→256<br/>Guidance: 2.5–8.0"]
    end

    subgraph L2["Layer 2: Style Templates"]
        L2D["prompt_templates.json<br/>Camera: 'top-down view.'<br/>Quality: 'Pixel art 16×16, crisp edges'<br/>LoRA trigger: '&lt;tdp&gt;'<br/>Format: 'Isolate on white background'"]
    end

    subgraph L3["Layer 3: Semantic Descriptions"]
        L3D["Enum-Driven Prose<br/>19 enum classes · 88 values<br/>Hand-crafted 20–40 word descriptions<br/>Example: fortification →<br/>'sturdy defensive structure with<br/>crenellated battlements, arrow slits,<br/>thick stone walls, watchtower'"]
    end

    subgraph L4["Layer 4: Assembly Logic"]
        L4D["Template Rendering<br/>Placeholder Substitution<br/>Validation<br/>→ Final Prompt String"]
    end

    L1 -->|"Workflow JSON"| L2
    L2 -->|"Style Template"| L3
    L3 -->|"Semantic Prose"| L4

    subgraph Separation["🔒 Separation of Concerns"]
        S1["HOW to generate<br/>(Layers 1–2)<br/>Locked in version control<br/>Client CANNOT override"]
        S2["WHAT to generate<br/>(Layer 3)<br/>Client selects from<br/>curated vocabulary"]
    end

    classDef layer1 fill:#7f7f7f,color:#fff,stroke:#555
    classDef layer2 fill:#1f77b4,color:#fff,stroke:#0d3b66
    classDef layer3 fill:#2ca02c,color:#fff,stroke:#1a6b1a
    classDef layer4 fill:#ff7f0e,color:#fff,stroke:#b85900
    classDef sep fill:#f5f5f5,color:#333,stroke:#999

    class L1,L1D layer1
    class L2,L2D layer2
    class L3,L3D layer3
    class L4,L4D layer4
    class Separation,S1,S2 sep
```

**Caption**: Systematic prompt construction through four layers. Layers 1–2 (HOW) are locked in version-controlled files — no client request can override style directives. Layer 3 (WHAT) exposes a curated vocabulary of game-design concepts. This design trades API flexibility for guaranteed style consistency across all generated assets.

---

## Fig. 4. Three-Stage Leader Portrait Pipeline

```mermaid
flowchart LR
    subgraph Stage1["Stage 1: Splash Art"]
        S1In["txt2img<br/>1920×1088<br/>guidance=3.5<br/>denoise=1.0"]
        S1Out["🎨 Cinematic Wide Shot<br/>Establishes canonical<br/>character identity"]
        S1In --> S1Out
    end

    subgraph Stage2["Stage 2: Profile Portrait"]
        S2In["img2img ← Splash<br/>512×512<br/>guidance=8.0<br/>denoise=0.90"]
        S2Out["👤 Close-Up Portrait<br/>Same character<br/>Maximum identity preservation"]
        S2In --> S2Out
    end

    subgraph Stage3["Stage 3: Action Scene"]
        S3In["img2img ← Splash<br/>1920×1088<br/>guidance=4.5<br/>denoise=0.85"]
        S3Out["⚔️ Dramatic Action Pose<br/>Same character<br/>Creative freedom + consistency"]
        S3In --> S3Out
    end

    Stage1 -->|"Reference Image<br/>+ Seed Stored"| Stage2
    Stage1 -->|"Reference Image<br/>+ Seed Stored"| Stage3

    subgraph Denoise["⚖️ Denoise Parameter Trade-off"]
        D1["0.80 = Too constrained<br/>No composition changes"]
        D2["0.85–0.90 = Sweet spot<br/>Identity preserved + flexibility"]
        D3["0.95+ = Identity loss<br/>Character becomes unrecognizable"]
    end

    classDef stage1 fill:#1f77b4,color:#fff,stroke:#0d3b66
    classDef stage2 fill:#2ca02c,color:#fff,stroke:#1a6b1a
    classDef stage3 fill:#ff7f0e,color:#fff,stroke:#b85900
    classDef denoise fill:#f5f5f5,color:#333,stroke:#999

    class Stage1,S1In,S1Out stage1
    class Stage2,S2In,S2Out stage2
    class Stage3,S3In,S3Out stage3
    class Denoise,D1,D2,D3 denoise
```

**Caption**: Identity-preserving leader portrait generation through three stages. Stage 1 (txt2img) establishes canonical identity. Stages 2–3 (img2img) use the splash as a reference image with calibrated denoise parameters — high guidance (8.0) for profile preservation, lower (4.5) for creative action scenes. The denoise sweet spot (0.85–0.90) maintains recognizability while allowing composition changes.

---

## Fig. 5. LoRA Fine-Tuning Experiment Results

**This figure uses the existing rendered PNG image** at:
`dataset-gen-train/figures/report_figure.png`

**Caption**: Qualitative comparison of LoRA caption detail strategies. A 2×4 grid showing two prompt subjects (watchtower, boulder) across four conditions: base model without LoRA (unreliable perspective), ultra-minimal captions with low rank (strongest generalization, least detail), minimal captions with high rank (balanced), and detailed captions with high rank (optimal architectural fidelity — deployed variant).
