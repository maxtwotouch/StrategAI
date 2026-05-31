# Figures — StrategAI IEEE Report

This directory contains Mermaid diagram source files for the 12 figures referenced in the IEEE academic report. Figures 1–5 are the most critical for defending the AI methodology.

## How to Render Mermaid Diagrams

### Option A: VS Code (Recommended)
1. Install the **Markdown Preview Mermaid Support** extension
2. Open any `.md` file in this directory
3. Press `Ctrl+Shift+V` (or `Cmd+Shift+V`) for preview
4. Mermaid diagrams render automatically

### Option B: GitHub
Push to any GitHub repository — Mermaid diagrams render natively in GitHub's markdown viewer.

### Option C: Online Mermaid Live Editor
1. Go to https://mermaid.live/
2. Copy the mermaid code block from any `.md` file
3. Paste into the editor
4. Export as PNG, SVG, or PDF

### Option D: Export for LaTeX (IEEE Report)
To convert Mermaid diagrams to LaTeX-compatible formats:

```bash
# Install mermaid-cli
npm install -g @mermaid-js/mermaid-cli

# Convert a diagram to PNG (300 DPI for print)
mmdc -i fig1_system_architecture.md -o fig1_system_architecture.png --scale 3

# Convert to PDF (vector)
mmdc -i fig1_system_architecture.md -o fig1_system_architecture.pdf

# Batch convert all figures
for f in fig*.md; do
    mmdc -i "$f" -o "${f%.md}.png" --scale 3
done
```

Then reference in LaTeX:
```latex
\begin{figure}[htbp]
    \centering
    \includegraphics[width=\textwidth]{figures/fig1_system_architecture.png}
    \caption{System architecture showing four primary components and data flow...}
    \label{fig:architecture}
\end{figure}
```

### Option E: Draw.io Integration
For more polished diagrams (if needed for final submission):
1. Export Mermaid to SVG via `mermaid-cli`
2. Import SVG into draw.io (https://app.diagrams.net/)
3. Enhance styling, add annotations
4. Export as PNG (300 DPI) or PDF for LaTeX

## Figure Inventory

| # | File | Title | Key AI Concept |
|---|------|-------|----------------|
| 1 | `fig1_system_architecture.md` | System Architecture Overview | Multi-service AI architecture |
| 2 | `fig2_intent_abstraction.md` | Intent-Based Abstraction Layer | LLM tool-use, agent safety |
| 3 | `fig3_prompt_architecture.md` | Four-Layer Prompt Architecture | Prompt engineering, DiT conditioning |
| 4 | `fig4_leader_pipeline.md` | Three-Stage Leader Pipeline | img2img, identity preservation |
| 5 | `fig5_lora_matrix.md` | LoRA Experiment Matrix | Fine-tuning, evaluation methodology |
| 6 | *(Fig. 6–12 TBD in future iteration)* | Asset Fallback, Fog of War, etc. | Graceful degradation, serialization |

## Design Principles

1. **Mermaid-first**: All diagrams defined in Mermaid syntax for portability and version control
2. **Source-code-accurate**: Every claim in diagrams verified against actual source files (paths and line numbers cited)
3. **Standalone**: Each `.md` file includes a complete caption, explanation, and source file references
4. **Color-coded**: Consistent color scheme across all diagrams:
   - 🟣 Purple: LLM / Strategic AI
   - 🔵 Blue: Backend / Operations / Templates
   - 🟢 Green: Frontend / Enum injection / Selected experiments
   - 🟠 Orange: Asset Server / Assembly / Execution
   - 🔴 Red: Game Engine / Risk areas
   - ⚪ Gray: External services

## Diagram Completeness Checklist

- [x] Fig 1: System Architecture Overview
- [x] Fig 2: Intent-Based Abstraction Layer
- [x] Fig 3: Four-Layer Prompt Architecture
- [x] Fig 4: Three-Stage Leader Pipeline
- [x] Fig 5: LoRA Experiment Matrix
- [ ] Fig 6: Asset Generation Modes & Fallback Strategy (TBD)
- [ ] Fig 7: Game State Serialization & Fog of War (TBD)
- [ ] Fig 8: Diplomacy Chat System (TBD)
- [ ] Fig 9: Frontend Component Tree (TBD)
- [ ] Fig 10: Testing Architecture (TBD)
- [ ] Fig 11: Deployment Architecture (TBD)
- [ ] Fig 12: Ethical AI Framework (TBD)

## Related Documents

- `../FIGURE_DESCRIPTIONS.md` — Full figure descriptions and captions for all 12 figures
- `../IEEE_REPORT.md` — IEEE academic report (markdown)
- `../IEEE_REPORT_COMPLETE.tex` — IEEE academic report (LaTeX)
- `../../ARCHITECTURE.md` — Backend engine architecture
- `../../ASSET_INTEGRATION.md` — Asset service contract and resolution
- `assetserver/docs/pipeline/image-generation-pipeline.md` — DiT mechanics deep-dive
- `dataset-gen-train/docs/experiment-design.md` — LoRA experiment design document
