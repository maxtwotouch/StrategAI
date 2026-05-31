# Figure 5: LoRA Fine-Tuning Experiment Matrix

**Caption**: Six-experiment matrix evaluating interaction between caption detail level and LoRA rank on model generalization.

```mermaid
graph TB
    %% ── Styling ──
    classDef header fill:#1e293b,color:#fff,stroke:#0f172a,stroke-width:2px
    classDef selected fill:#16a34a,color:#fff,stroke:#15803d,stroke-width:3px
    classDef good fill:#dbeafe,color:#1e40af,stroke:#3b82f6,stroke-width:2px
    classDef warn fill:#fef3c7,color:#92400e,stroke:#f59e0b,stroke-width:2px
    classDef risk fill:#fee2e2,color:#991b1b,stroke:#ef4444,stroke-width:2px
    classDef label fill:#f1f5f9,color:#334155,stroke:#cbd5e1,stroke-width:1px

    %% ── Title Row ──
    corner[" "]:::label
    col1_h["HIGH RANK<br/>Linear: 128 · Conv: 64<br/>~250–350 MB safetensors<br/>High capacity · Overfitting risk"]:::header
    col2_h["LOW RANK<br/>Linear: 64→32 · Conv: 32→16<br/>~50–180 MB safetensors<br/>Low capacity · Better generalization"]:::header

    %% ── Row 1: Detailed ──
    row1_label["DETAILED CAPTIONS<br/>50–100 words<br/>Full descriptions:<br/>materials, palette,<br/>condition, setting<br/><br/>Hypothesis:<br/>Rich text may bind<br/>style to trigger token"]:::label
    cell_dh["🧪 detailed_high<br/>━━━━━━━━━━━━━━━━<br/>LR: 8e-5 · Dropout: 0.05<br/>Steps: 2500<br/>━━━━━━━━━━━━━━━━<br/>✅ In-dist: Excellent fidelity<br/>⚠️ OOD: Medieval artifacts<br/>   on modern subjects<br/>━━━━━━━━━━━━━━━━<br/>Verdict: Style leakage detected.<br/>Model memorized pixel-art style<br/>along with angle concept."]:::risk
    cell_dl["🧪 detailed_low<br/>━━━━━━━━━━━━━━━━<br/>LR: 8e-5 · Dropout: 0.05<br/>Steps: 2500<br/>━━━━━━━━━━━━━━━━<br/>✅ In-dist: Good fidelity<br/>⚠️ OOD: Reduced but present<br/>   style artifacts<br/>━━━━━━━━━━━━━━━━<br/>Verdict: Lower rank helps but<br/>detailed captions still bind style."]:::warn

    %% ── Row 2: Minimal ──
    row2_label["MINIMAL CAPTIONS<br/>20–30 words<br/>Category labels only:<br/>'A medieval [category].'<br/><br/>Hypothesis:<br/>Category signal aids<br/>convergence without<br/>binding style descriptors"]:::label
    cell_mh["🧪 minimal_high<br/>━━━━━━━━━━━━━━━━<br/>LR: 8e-5 · Dropout: 0.1<br/>Steps: 2500<br/>━━━━━━━━━━━━━━━━<br/>✅ In-dist: Good fidelity<br/>✅ OOD: Clean angle transfer<br/>   Minimal style leakage<br/>━━━━━━━━━━━━━━━━<br/>Verdict: Balanced performance.<br/>Category diversity helps, style<br/>mostly isolated from angle."]:::good
    cell_ml["🧪 minimal_low<br/>━━━━━━━━━━━━━━━━<br/>LR: 8e-5 · Dropout: 0.1<br/>Steps: 2500<br/>━━━━━━━━━━━━━━━━<br/>✅ In-dist: Adequate fidelity<br/>✅ OOD: Cleanest angle transfer<br/>   Nearly zero style leakage<br/>━━━━━━━━━━━━━━━━<br/>Verdict: Best generalization.<br/>Low rank + minimal captions =<br/>pure angle concept."]:::good

    %% ── Row 3: Ultra-Minimal ──
    row3_label["ULTRA-MINIMAL<br/>CAPTIONS<br/>5–10 words<br/>All 100 images share<br/>identical caption:<br/>'&lt;tdp&gt; top-down view.'<br/><br/>Hypothesis:<br/>Model MUST learn<br/>everything from pixels"]:::label
    cell_uh["🧪 ultra_high<br/>━━━━━━━━━━━━━━━━<br/>LR: 5e-5 · Dropout: 0.0<br/>Steps: 2500<br/>━━━━━━━━━━━━━━━━<br/>⚠️ In-dist: Inconsistent quality<br/>⚠️ OOD: Erratic, some mode<br/>   collapse on certain subjects<br/>━━━━━━━━━━━━━━━━<br/>Verdict: Identical captions +<br/>high rank → unstable training."]:::warn
    cell_ul["🧪 ultra_low<br/>━━━━━━━━━━━━━━━━<br/>LR: 5e-5 · Dropout: 0.0<br/>Steps: 2500<br/>━━━━━━━━━━━━━━━━<br/>❌ In-dist: Weak angle<br/>❌ OOD: Angle not learned<br/>   Rank too low for concept<br/>━━━━━━━━━━━━━━━━<br/>Verdict: Rank 32 insufficient<br/>to capture spatial camera concept."]:::risk

    %% ── Grid Layout ──
    corner --- col1_h --- col2_h
    row1_label --- cell_dh --- cell_dl
    row2_label --- cell_mh --- cell_ml
    row3_label --- cell_uh --- cell_ul

    %% ── Selected Checkpoint Annotation ──
    selected_box["⭐ SELECTED CHECKPOINT: detailed_high @ step 1800<br/>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br/>Rationale: Best in-distribution fidelity for game asset production.<br/>Style leakage to OOD subjects is acceptable — production use is<br/>always in-distribution (medieval pixel art). Checkpoint 1800 chosen<br/>over 2500 because overfitting signs appeared after step 2000.<br/>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br/>Published: stixxert/strategai-topdown-medieval-style-lora on HuggingFace"]:::selected

    %% ── Key Findings ──
    findings["📊 KEY FINDINGS<br/>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br/>1. Less detailed captions → purer angle concept, better OOD generalization<br/>2. Lower rank → less capacity to memorize style details<br/>3. Best generalization: minimal_low (rank 64/32 + minimal captions)<br/>4. Best production quality: detailed_high @ step 1800 (selected for deployment)<br/>5. Ultra-minimal captions require more training data (100 insufficient)<br/>6. Conv layers essential for spatial camera-angle concept learning"]:::label

    %% ── Connect ──
    cell_dh -.->|"Selected for production"| selected_box
    findings --- cell_dh

    %% ── Apply classes ──
    class corner,col1_h,col2_h,row1_label,row2_label,row3_label label
    class cell_dh selected
    class cell_mh,cell_ml good
    class cell_dl,cell_uh warn
    class cell_ul risk
    class selected_box selected
    class findings label
```

## Experiment Design Summary

### The 3×2 Matrix

| | High Rank (128/64) | Low Rank (64/32 or 32/16) |
|---|---|---|
| **Detailed** (50–100 words) | `detailed_high` — Best fidelity, style leakage | `detailed_low` — Good fidelity, reduced leakage |
| **Minimal** (20–30 words) | `minimal_high` — Balanced, good transfer | `minimal_low` — **Best generalization** |
| **Ultra-Minimal** (5–10 words) | `ultra_high` — Unstable, inconsistent | `ultra_low` — Rank too low, concept not learned |

### Caption Detail Levels

| Level | Format | Token Count | Hypothesis |
|-------|--------|-------------|------------|
| **Detailed** | `<tdp> top-down view. [full description — building type, materials, palette, condition, setting]` | 50–100 words | Rich text gives more conditioning signal but risks binding style descriptors |
| **Minimal** | `<tdp> top-down view. A medieval [category].` | 20–30 words | Category labels aid convergence without style binding |
| **Ultra-Minimal** | `<tdp> top-down view.` | 5–10 words | All 100 images identical caption — model must learn from pixels alone |

### Rank Levels

| Level | Linear Rank | Conv Rank | Safetensors Size | Capacity |
|-------|-------------|-----------|-----------------|----------|
| **High** | 128 | 64 | ~250–350 MB | Higher capacity, risk of style memorization |
| **Low** (minimal/detailed) | 64 | 32 | ~120–180 MB | Balanced |
| **Low** (ultra-minimal) | 32 | 16 | ~50–80 MB | May not capture spatial concept |

### Why `detailed_high` @ Step 1800 Was Selected

Despite not having the best OOD generalization, `detailed_high` was selected for production because:

1. **Production use is always in-distribution** — all game assets are medieval pixel art; OOD generalization to cars and spaceships is irrelevant for the game asset pipeline
2. **Best in-distribution fidelity** — detailed captions produce the highest-quality medieval pixel art sprites
3. **Step 1800, not 2500** — overfitting (memorization of individual training assets) became detectable after step ~2000, so the checkpoint before degradation was chosen
4. **Published on HuggingFace** as `stixxert/strategai-topdown-medieval-style-lora`

### Training Infrastructure

| Parameter | Value |
|-----------|-------|
| **Base model** | FLUX2 Klein 4B Distilled (fp8) |
| **Training toolkit** | Ostris AI Toolkit |
| **Optimizer** | AdamW 8-bit |
| **Timestep sampling** | Weighted (flow-matching) |
| **Gradient checkpointing** | Enabled (VRAM optimization) |
| **Checkpoint interval** | Every 200 steps |
| **Total storage** | ~13–14 GB across 6 experiments × 13 checkpoints |
| **VRAM per experiment** | ~15–18 GB |

### Key Source Files

| File | Purpose |
|------|---------|
| `dataset-gen-train/docs/experiment-design.md` | Complete experiment rationale and methodology |
| `dataset-gen-train/config/training/*.yaml` | 6 training experiment configuration files |
| `dataset-gen-train/src/training/derive_captions.py` | Caption variant generation (detailed/minimal/ultra-minimal) |
| `dataset-gen-train/src/generation/prepare_dataset.py` | Dataset card auto-generation with live statistics |
| `dataset-gen-train/src/training/extract_training_set.py` | Training set extraction with trigger token injection |
