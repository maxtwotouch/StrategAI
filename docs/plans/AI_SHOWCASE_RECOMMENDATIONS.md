# AI Showcase Recommendations — Future UI Enhancements

> **Purpose**: This document describes potential UI enhancements that could make the AI technologies more visible to users. These are **recommendations for future work**, not part of the current deliverable. The AI showcase for the INF-3600 report is documented in the academic paper itself.

---

## Overview

StrategAI uses four cutting-edge AI technologies that are currently invisible to end users. While the academic report thoroughly documents these technologies, the game UI does not surface them. This document outlines potential enhancements to make the AI more visible, should the project continue beyond the course deliverable.

---

## Current State: AI is Invisible

### What Users See Today
- AI civilizations make decisions, but users only see the outcomes (unit movements, city founding, diplomatic messages)
- Assets are generated on-demand, but users don't know they're AI-generated
- LoRA fine-tuning enforces style consistency, but users don't see the training process
- Diplomacy chat uses LLMs, but messages look like scripted text

### What's Missing
- No indication that AI decisions are LLM-generated
- No visibility into the AI's "thought process" (which intents were called)
- No "AI-generated" labels on assets
- No showcase of the LoRA training or experiment matrix
- No link to published HuggingFace models/dataset

---

## Recommendation 1: AI Decision Log Panel

### Concept
Add a panel showing the last N AI decisions with intent names, arguments, and timestamps.

### Implementation Sketch
- **Backend**: Add `GET /games/{id}/ai-log` endpoint returning structured decision history
- **Storage**: In-memory ring buffer (last 50 decisions per game)
- **Frontend**: Right-rail panel with color-coded intent types (military=red, diplomatic=blue, economic=green)
- **Data**: `civ_id`, `turn`, `intent_name`, `intent_args`, `timestamp`, `reasoning` (if available)

### Example UI
```
🤖 AI Intent Log (last 10 decisions)
─────────────────────────────────────
🏹 Mongol Empire → engage(target=Egypt)     Turn 5
🗣️ Egypt → speak(to=Mongol, kind=threat)    Turn 5
🔬 India → research(tech="Iron Working")    Turn 4
🏗️ Rome → build(unit="Settler")             Turn 4
```

### Value
- Makes LLM decision-making visible
- Demonstrates the 9-intent abstraction layer
- Shows that AI civs have distinct strategies (different intent distributions)

### Complexity
- **Backend**: ~200 lines (new endpoint + storage + wiring into `OpenAIGoalSource`)
- **Frontend**: ~300 lines (new panel + API integration + styling)
- **Risk**: Low (additive, doesn't change game logic)

---

## Recommendation 2: AI-Generated Asset Badges

### Concept
Add subtle "AI" badges to generated assets (leader portraits, structures) with tooltips showing generation metadata.

### Implementation Sketch
- **Frontend**: Overlay badge on asset images (toggleable via settings)
- **Tooltip**: Show model name, prompt excerpt, generation time
- **Loading screen**: Expand "Conjuring world art…" to show model name and asset type

### Example UI
```
[Leader Portrait]
  └─ Bottom-right corner: "AI" badge (semi-transparent)
  └─ Hover tooltip:
     🤖 AI-Generated
     Model: FLUX.2 Klein 4B Distilled
     Prompt: "top-down medieval ruler, pixel art, 32x32..."
```

### Value
- Makes generative AI visible
- Demonstrates the four-layer prompt architecture
- Shows that assets are not hand-crafted

### Complexity
- **Frontend**: ~150 lines (badge component + tooltip + CSS)
- **Risk**: Very low (purely cosmetic)

---

## Recommendation 3: Diplomacy AI Indicators

### Concept
Add indicators to the diplomacy panel showing that messages are LLM-generated and visualizing relationship trends.

### Implementation Sketch
- **Message badge**: "🤖 AI" next to AI civ messages
- **Relationship trend**: Arrow indicator (↗ Improving / ↘ Deteriorating / → Stable) based on last 3 turns
- **Mood label**: Color-coded pill (Hostile/Wary/Neutral/Friendly/Allied) based on relationship score

### Example UI
```
Diplomacy with Mongol Empire
─────────────────────────────
Relationship: -45 (Hostile) ↘ Deteriorating
Mood: 🔴 Hostile

Messages:
  🤖 Mongol Empire: "Your borders encroach on our territory..."
  You: "We seek peaceful coexistence."
  🤖 Mongol Empire: "Words are wind. Withdraw your settlers."
```

### Value
- Makes diplomatic AI visible
- Demonstrates persistent conversation memory
- Shows relationship scoring system

### Complexity
- **Frontend**: ~200 lines (badge + trend calculation + mood label)
- **Risk**: Very low (purely cosmetic)

---

## Recommendation 4: AI Showcase / "About" Section

### Concept
Create a dedicated section (modal or page) explaining the 4 AI technologies with links to HuggingFace.

### Implementation Sketch
- **Access**: Button in start screen or settings menu
- **Content**: 4 technology cards with icons, descriptions, key features
- **Links**: HuggingFace model/dataset, GitHub repo
- **Technical details**: Expandable section with model specs, training info

### Example UI
```
The AI That Powers StrategAI
═════════════════════════════

🧠 LLM-Driven Civilizations
   AI leaders powered by GPT-4 make strategic decisions
   using 9 intent types (expand, engage, research, etc.)
   Key: Intent-based abstraction — LLMs think in high-level
   strategies, engine resolves to deterministic actions

🗣️ Diplomatic AI
   Free-form diplomacy chat with AI leaders who remember
   conversations and adjust relationships
   Key: Persistent memory + relationship scoring creates
   emergent alliances and rivalries

🎨 Generative Pixel Art
   On-demand asset generation using FLUX.2 Klein 4B
   Distilled (Diffusion Transformer) via ComfyUI
   Key: Four-layer prompt architecture ensures consistent
   quality across 6 asset families

🎭 LoRA Style Adaptation
   Custom LoRA fine-tuning on 100 medieval pixel art images
   enforces consistent top-down style
   Key: Trigger token <tdp> activates style without affecting
   non-game assets
   [View on HuggingFace →]
```

### Value
- Educates users about the AI technologies
- Provides links to published models/dataset
- Demonstrates academic contribution

### Complexity
- **Frontend**: ~400 lines (new component + modal + styling)
- **Risk**: Very low (purely informational)

---

## Recommendation 5: AI Behavior Visualization

### Concept
Add visualizations showing AI behavior patterns (intent distributions, strategic diversity, emergent behaviors).

### Implementation Sketch
- **Intent distribution chart**: Bar chart showing frequency of each intent type per civ
- **Strategic diversity**: Comparison across civs (e.g., "Mongol Empire uses `engage` 40% of the time")
- **Emergent behaviors**: Highlight notable events (coalitions, revenge, betrayals)

### Example UI
```
AI Behavior Analysis
════════════════════

Intent Distribution (last 20 turns):
  Mongol Empire:  ████████ engage (40%)
                  ████ expand (20%)
                  ██ scout (10%)
                  ██ research (10%)
                  █ speak (5%)
                  █ other (15%)

  Egypt:          ██████ research (30%)
                  ████ build (20%)
                  ███ expand (15%)
                  ██ engage (10%)
                  ██ speak (10%)
                  █ other (15%)

Emergent Behaviors:
  • Turn 12: Mongol Empire and Rome formed alliance against Egypt
  • Turn 18: Egypt declared war on Mongol Empire (revenge for Turn 8 attack)
```

### Value
- Demonstrates strategic diversity
- Shows emergent behaviors (coalitions, revenge)
- Provides evidence for report claims

### Complexity
- **Backend**: ~100 lines (aggregate intent statistics)
- **Frontend**: ~500 lines (chart component + visualization)
- **Risk**: Medium (requires data collection over multiple turns)

---

## Recommendation 6: LoRA Training Visualization

### Concept
Add a visualization showing the LoRA training process, experiment matrix, and before/after comparisons.

### Implementation Sketch
- **Training diagram**: Show the 6-experiment matrix (3×2 grid)
- **Before/after slider**: Compare base model output vs. LoRA-enhanced output
- **Loss curves**: Show training progress (if logs available)
- **Dataset samples**: Show 5-10 example images from the training dataset

### Example UI
```
LoRA Fine-Tuning Experiment Matrix
════════════════════════════════════

Caption Detail × LoRA Rank:
              Low Rank (4)    High Rank (16)
Detailed      [image]         [image]
Minimal       [image]         [image]
Ultra-minimal [image]         [image]

Best checkpoint: detailed_high @ step 1800

Before/After Comparison:
  [slider: base model ←→ LoRA-enhanced]
  Prompt: "top-down medieval castle, pixel art, 32x32"

Dataset: 100 curated images from OpenGameArt (CC-BY)
Training: ~2 hours on RTX 3090, ~12 GB VRAM
```

### Value
- Demonstrates the most academically rigorous component
- Shows systematic experimentation
- Links to published HuggingFace models

### Complexity
- **Frontend**: ~600 lines (visualization component + image slider)
- **Data**: Requires training logs and comparison images
- **Risk**: Medium (requires additional assets)

---

## Priority Ranking

If implementing these recommendations, we suggest this order:

1. **AI Showcase Section** (Recommendation 4) — Highest value, lowest risk, purely informational
2. **AI-Generated Asset Badges** (Recommendation 2) — Makes generative AI visible, very low risk
3. **Diplomacy AI Indicators** (Recommendation 3) — Makes diplomatic AI visible, very low risk
4. **AI Decision Log Panel** (Recommendation 1) — Most complex but highest educational value
5. **AI Behavior Visualization** (Recommendation 5) — Requires data collection, medium complexity
6. **LoRA Training Visualization** (Recommendation 6) — Requires additional assets, medium complexity

---

## For the INF-3600 Report

The academic report (IEEE_REPORT.md / IEEE_REPORT_COMPLETE.tex) thoroughly documents all four AI technologies:

- **Section IV**: LLM-Driven AI Civilizations (intent abstraction, persona system, rolling memory)
- **Section V**: Diffusion Transformer Asset Pipeline (ComfyUI, FLUX2 Klein 4B, four-layer prompts)
- **Section VI**: LoRA Fine-Tuning (experiment matrix, training methodology, results)
- **Section VII**: Frontend Integration (asset resolution, graceful degradation)
- **Section IX**: Ethical Considerations (bias, environmental cost, copyright)

The report includes:
- Architecture diagrams (Figures 1-5)
- Example prompts and responses
- Performance benchmarks (generation time, cache hit rate)
- Test coverage statistics
- Links to published HuggingFace models and dataset

**The AI showcase is complete in the documentation. UI enhancements are optional future work.**

---

## Conclusion

These recommendations would make the AI technologies more visible to end users, but they are **not required** for the INF-3600 course deliverable. The academic report and supporting documentation already provide a comprehensive showcase of the AI contributions.

If the project continues beyond the course, implementing these enhancements would:
- Improve user understanding of the AI systems
- Provide better demonstrations for presentations
- Generate evidence for report claims (e.g., strategic diversity, emergent behaviors)
- Link users to published models and datasets

For now, the documentation-only approach is appropriate for the course deliverable.
