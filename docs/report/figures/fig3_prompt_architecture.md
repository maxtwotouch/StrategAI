# Figure 3: Four-Layer Prompt Architecture

**Caption**: Systematic prompt construction through four layers separating workflow configuration, style templates, semantic descriptions, and assembly logic.

```mermaid
graph TB
    %% ── Styling ──
    classDef layer1 fill:#9ca3af,color:#1f2937,stroke:#6b7280,stroke-width:2px
    classDef layer2 fill:#3b82f6,color:#fff,stroke:#2563eb,stroke-width:2px
    classDef layer3 fill:#16a34a,color:#fff,stroke:#15803d,stroke-width:2px
    classDef layer4 fill:#ea580c,color:#fff,stroke:#c2410c,stroke-width:2px
    classDef example fill:#fef3c7,color:#92400e,stroke:#f59e0b,stroke-width:2px
    classDef annotation fill:#fefce8,color:#713f12,stroke:#eab308,stroke-width:1px,stroke-dasharray: 3 3

    %% ── Layer 4: Assembly (top) ──
    subgraph L4["  LAYER 4: Assembly Logic — src/prompt_templates.py  "]
        direction TB
        assemble["🔧 render(family, **kwargs)<br/>Template rendering · Placeholder substitution · Validation"]
        final["📝 Final Prompt String<br/>All {placeholders} resolved<br/>&lt;tdp&gt; token injected for LoRA activation"]
        assemble --> final
    end

    %% ── Layer 3: Enum Injection ──
    subgraph L3["  LAYER 3: Semantic Descriptions — src/*/prompts.py  "]
        direction TB
        enums["📚 Enum Injection Maps<br/>19 classes · 88 hand-crafted prose values"]
        ex_enums["Example enums:<br/>ARCHETYPE: 'warrior_king' → 'commanding presence, battle-scarred dignity...'<br/>CULTURE: 'ancient_egyptian' → 'vast sandstone temple with hieroglyph-carved pillars...'<br/>TIME_OF_DAY: 'golden_hour' → 'warm directional sunlight, long dramatic shadows...'<br/>MOOD: 'determined' → 'resolute expression, unwavering focus, purposeful stance...'"]
        enums --> ex_enums
    end

    %% ── Layer 2: Templates ──
    subgraph L2["  LAYER 2: Style Templates — config/prompt_templates.json  "]
        direction TB
        templates["📋 8 Template Families<br/>structure · object · terrain · unit<br/>background_tile · leader_splash<br/>leader_profile · leader_action"]
        ex_template["Example (structure):<br/>'&lt;tdp&gt; top-down view. The structure is viewed from directly above...<br/>{inner}. Pixel art 16x16 game tile asset, crisp pixel edges,<br/>no anti-aliasing, sharp blocky pixels, centered single asset on white.<br/>Grounded stable perspective, no floating objects.'"]
        templates --> ex_template
    end

    %% ── Layer 1: Workflow (bottom) ──
    subgraph L1["  LAYER 1: Workflow Configuration — workflows/*.json  "]
        direction TB
        workflows["⚙️ 5 ComfyUI Workflow JSONs<br/>txt2img · background_tile · leader_splash<br/>leader_profile · leader_action"]
        params["Per-workflow parameters:<br/>Steps: 4 · Sampler: euler · Scheduler: simple<br/>Guidance: 2.5–8.0 · Denoise: 0.85–1.0<br/>Resolution: 256×256 to 1920×1088<br/>LoRA: &lt;tdp&gt; on game assets, off on leaders"]
        workflows --> params
    end

    %% ── Flow (bottom → top) ──
    L1 -->|"Node graph + params"| L2
    L2 -->|"Templates with {placeholders}"| L3
    L3 -->|"Enum prose + user descriptions"| L4

    %% ── Example Trace (right side) ──
    subgraph trace["  COMPLETE EXAMPLE: 'Medieval Castle' → Final Prompt  "]
        direction TB
        t1["Layer 1: txt2img.json workflow selected<br/>guidance=3.5, denoise=1.0, 1024×1024→256×256"]
        t2["Layer 2: Structure template loaded<br/>&lt;tdp&gt; top-down view. ...{inner}. Pixel art 16x16..."]
        t3["Layer 3: Enum injection<br/>inner = 'sturdy stone castle with four corner towers,<br/>crenellated battlements, central keep with slate roof,<br/>surrounded by curtain walls, iron portcullis at gate'"]
        t4["Layer 4: Assembly<br/>render('structure', inner='sturdy stone castle...')"]
        t5["✅ Final prompt:<br/>'&lt;tdp&gt; top-down view. The structure is viewed from<br/>directly above, showing its roof and layout... sturdy stone<br/>castle with four corner towers, crenellated battlements...<br/>Pixel art 16x16 game tile asset, crisp pixel edges...'"]
        t1 --> t2 --> t3 --> t4 --> t5
    end

    %% ── Annotations ──
    n1["🔑 Separation of Concerns:<br/>• Workflow = inference parameters<br/>• Templates = style & quality tags<br/>• Enums = semantic content<br/>• Assembly = composition logic"]
    n2["🎯 Design Rationale:<br/>• Non-technical artists edit JSON templates<br/>• Python devs manage enum prose<br/>• Workflow engineers tune ComfyUI graphs<br/>• No single person touches all layers"]
    n3["⚠️ FLUX2 Klein 4B Distilled<br/>does NOT support negative prompts.<br/>All templates use positive-only,<br/>affirmative language."]

    %% ── Apply classes ──
    class L1,workflows,params layer1
    class L2,templates,ex_template layer2
    class L3,enums,ex_enums layer3
    class L4,assemble,final layer4
    class trace,t1,t2,t3,t4,t5 example
    class n1,n2,n3 annotation
```

## Prompt Assembly Pipeline

### Layer 1: Workflow Configuration (`workflows/*.json`)
Self-contained ComfyUI node graphs that define the inference pipeline. Each workflow specifies:
- Model loading (UNET, CLIP, VAE, LoRA — split loading architecture)
- Sampler parameters (euler, simple scheduler, 4 steps)
- Guidance scale and denoise strength
- Post-processing (rembg, ImageSharpen for game sprites)
- Reference image inputs (for img2img leader stages)

### Layer 2: Style Templates (`config/prompt_templates.json`)
Jinja2-style templates with `{placeholder}` variables. Contains:
- Camera framing directives (`top-down view`)
- Quality/style tags (`Pixel art 16x16 game tile asset, crisp pixel edges`)
- LoRA trigger token (`<tdp>` for game assets; omitted for leaders/backgrounds)
- Structural constraints (`centered single asset on white`, `no floating objects`)

### Layer 3: Semantic Descriptions (`src/*/prompts.py`)
Hand-crafted enum injection maps providing rich prose per semantic value:
- **19 enums** across 6 asset families: `ARCHETYPE`, `CULTURE`, `TIME_OF_DAY`, `MOOD`, `ACTION_CATEGORY` (leaders); `STRUCTURE_TYPE`, `TERRAIN_TYPE`, etc. (tiles)
- **88 values** total, each with 20–40 words of evocative prose
- Example: `ARCHETYPE['warrior_king']` → `"commanding presence, battle-scarred dignity, weapon in hand, military authority"`

### Layer 4: Assembly Logic (`src/prompt_templates.py`)
Pure composition layer:
- `render(family, **kwargs)` substitutes placeholder values
- `get_placeholders(family)` introspects template expectations (for validation)
- Thread-safe caching of template JSON
- Regex-based placeholder extraction for validation

## Design Rationale

| Principle | Implementation |
|-----------|---------------|
| **Separation of concerns** | Workflow engineers, prompt designers, domain experts, and developers work independently |
| **Consistency across assets** | Same style tags enforced by templates; semantic variation via enums |
| **No hardcoded prompts** | All prompt text lives in JSON; Python contains only assembly logic |
| **Positive-only prompts** | FLUX2 Klein 4B Distilled does not support negative prompts — all language is affirmative |
