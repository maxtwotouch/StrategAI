# Figure 4: Three-Stage Leader Portrait Pipeline

**Caption**: Identity-preserving leader portrait generation through three stages with calibrated denoising parameters.

```mermaid
graph LR
    %% ── Styling ──
    classDef stage1 fill:#7c3aed,color:#fff,stroke:#6d28d9,stroke-width:2px
    classDef stage2 fill:#2563eb,color:#fff,stroke:#1d4ed8,stroke-width:2px
    classDef stage3 fill:#16a34a,color:#fff,stroke:#15803d,stroke-width:2px
    classDef seed fill:#f59e0b,color:#1c1917,stroke:#d97706,stroke-width:2px
    classDef artifact fill:#fef3c7,color:#92400e,stroke:#f59e0b,stroke-width:2px
    classDef param fill:#f1f5f9,color:#334155,stroke:#94a3b8,stroke-width:1px

    %% ── Stage 1: Splash Art ──
    subgraph S1["  STAGE 1: SPLASH ART — Establishes Canonical Identity  "]
        direction TB
        s1_workflow["Workflow: leader_splash.json"]
        s1_mode["Mode: txt2img (no reference image)"]
        s1_params["📐 1920×1088 · guidance=3.5 · denoise=1.0<br/>4 steps · euler · simple scheduler"]
        s1_prompt["Prompt template (leader_splash):<br/>'epic cinematic wide composition of {leader_description},<br/>{archetype}, in {culture}, {time_of_day}, {mood},<br/>epic civilization leader splash screen...'"]
        s1_output["🖼️ Output: Cinematic wide-shot portrait<br/>Full-body leader in cultural context<br/>Establishes face, attire, posture"]
        s1_workflow --> s1_mode --> s1_params --> s1_prompt --> s1_output
    end

    %% ── Seed Artifact ──
    subgraph SEED["  IDENTITY SEED  "]
        seed_data["🔑 Seed stored<br/>Splash image + generation seed<br/>becomes canonical reference<br/>for all downstream stages"]
    end

    %% ── Stage 2: Profile Portrait ──
    subgraph S2["  STAGE 2: PROFILE PORTRAIT — Maximum Identity Preservation  "]
        direction TB
        s2_workflow["Workflow: leader_profile.json"]
        s2_mode["Mode: img2img (reference = splash art)"]
        s2_params["📐 512×512 · guidance=8.0 · denoise=0.90<br/>4 steps · euler · simple scheduler"]
        s2_prompt["Prompt template (leader_profile):<br/>'An extremely close-up professional portrait of<br/>{leader_description}, {mood}, face filling the frame,<br/>headpiece and collar visible at the edges...'"]
        s2_output["🖼️ Output: Close-up square portrait<br/>Same face, different framing<br/>Rembrandt-style lighting · shallow DoF"]
        s2_workflow --> s2_mode --> s2_params --> s2_prompt --> s2_output
    end

    %% ── Stage 3: Action Scene ──
    subgraph S3["  STAGE 3: ACTION SCENE — Creative Freedom with Consistency  "]
        direction TB
        s3_workflow["Workflow: leader_action.json"]
        s3_mode["Mode: img2img (reference = splash art)<br/>ImageStitch for multi-leader scenes"]
        s3_params["📐 1920×1088 · guidance=4.5 · denoise=0.85<br/>4 steps · euler · simple scheduler"]
        s3_prompt["Prompt template (leader_action):<br/>'epic cinematic scene depicting {leader_description},<br/>{action_description}, in {culture}, {time_of_day},<br/>{mood}, {action_category}...'"]
        s3_output["🖼️ Output: Dynamic action scene<br/>Same character in narrative context<br/>Consistent face · varied pose · dramatic composition"]
        s3_workflow --> s3_mode --> s3_params --> s3_prompt --> s3_output
    end

    %% ── Flow Arrows ──
    S1 -->|"Splash image + seed"| SEED
    SEED -->|"Reference image"| S2
    SEED -->|"Reference image"| S3

    %% ── Denoise Calibration Scale ──
    subgraph DENOISE["  DENOISE STRENGTH CALIBRATION  "]
        direction LR
        d1["0.80<br/>Too constrained<br/>❌ Rigid · Lacks variety"]
        d2["0.85<br/>Sweet spot<br/>✅ Identity preserved<br/>✅ Creative freedom"]
        d3["0.90<br/>Sweet spot<br/>✅ Strong identity<br/>✅ Framing change"]
        d4["0.95+<br/>Identity loss<br/>❌ Different face<br/>❌ Inconsistent character"]
        d1 --> d2 --> d3 --> d4
    end

    %% ── Key Annotations ──
    note1["🔑 Identity Preservation Strategy:<br/>• Stage 1 establishes the canonical face<br/>• Stages 2 & 3 use img2img from Stage 1<br/>• Denoise 0.85–0.90: high enough for<br/>  composition changes, low enough to<br/>  preserve facial identity<br/>• Same seed reused across stages"]
    note2["🎯 Why 3 Stages?<br/>• Splash: cinematic intro, character design<br/>• Profile: UI portrait, diplomacy screen<br/>• Action: narrative events, comic panels<br/>• Each serves different UI/UX context<br/>  but must show the SAME character"]
```

## Identity Preservation Mechanism

### The Core Challenge
Generating three different compositions of the same fictional character while maintaining consistent facial identity is non-trivial. Each generation is a stochastic process — without constraints, each stage would produce a different-looking person.

### The Solution: Calibrated img2img
Stages 2 and 3 use **image-to-image (img2img)** generation seeded from the Stage 1 splash art output:

1. **Stage 1 (txt2img, denoise=1.0)**: Full creative freedom. The model generates a novel character from pure noise, guided only by the text prompt. This establishes the **canonical identity**.

2. **Stage 2 (img2img, denoise=0.90)**: The splash art is partially noised then denoised with a new prompt (close-up portrait framing). At denoise=0.90, ~90% of the latent is replaced — enough to change composition from wide-shot to close-up — but ~10% of the original structure persists, preserving facial features.

3. **Stage 3 (img2img, denoise=0.85)**: Similar approach for action scenes. Slightly lower denoise (0.85) provides more structural preservation while still allowing dynamic pose and scene changes.

### Denoise Trade-off

| Denoise | Effect |
|---------|--------|
| **0.80** | Too constrained — output nearly identical to reference; cannot change composition |
| **0.85–0.90** | **Sweet spot** — sufficient structural change for new composition while preserving face |
| **0.95+** | Too much freedom — effectively a new generation; facial identity lost |

### Why Guidance Varies by Stage

| Stage | Guidance | Rationale |
|-------|----------|-----------|
| Splash | 3.5 | Moderate — balances creative expression with prompt adherence |
| Profile | 8.0 | High — strong prompt adherence needed for close-up framing and Rembrandt lighting |
| Action | 4.5 | Moderate-high — allows dynamic composition while maintaining character consistency |

### Multi-Leader Scenes (ImageStitch)
For action scenes featuring two leaders, two separate splash references are fed into the `ImageStitch` node, compositing both characters into a single coherent scene while preserving both identities.

### Key Source Files

| File | Purpose |
|------|---------|
| `assetserver/workflows/leader_splash.json` | txt2img workflow, 1920×1088 cinematic portrait |
| `assetserver/workflows/leader_profile.json` | img2img workflow, 512×512 close-up from splash |
| `assetserver/workflows/leader_action.json` | img2img workflow, 1920×1088 action from splash + ImageStitch |
| `assetserver/config/prompt_templates.json` | `leader_splash`, `leader_profile`, `leader_action` templates |
| `assetserver/src/leader/prompts.py` | Enum injection maps: ARCHETYPE, CULTURE, TIME_OF_DAY, MOOD, ACTION_CATEGORY |
| `assetserver/src/leader/models.py` | `LeaderRequest` Pydantic model with all enum fields |
