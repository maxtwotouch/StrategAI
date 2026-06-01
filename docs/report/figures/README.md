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

# Batch convert all figures with correct IEEE sizing
./compile_figures.sh
```

### Option E: Draw.io Integration
For more polished diagrams (if needed for final submission):
1. Export Mermaid to SVG via `mermaid-cli`
2. Import SVG into draw.io (https://app.diagrams.net/)
3. Enhance styling, add annotations
4. Export as PNG (300 DPI) or PDF for LaTeX

## IEEE Two-Column Placement

IEEE two-column format imposes strict width constraints:
- **Single-column** figures: max 3.5″ wide, ~9″ tall (with caption). Use `\includegraphics[width=\columnwidth]{...}` inside a `figure` environment.
- **Double-column** figures: max 7.16″ wide. Use `\includegraphics[width=\textwidth]{...}` inside a `figure*` environment.

| Fig | File | Column | Dimensions | LaTeX Command |
|-----|------|--------|------------|---------------|
| 1 | `fig1_system_architecture.pdf` | **double** | 6.8″ × 4.8″ | `\includegraphics[width=\textwidth]{figures/fig1_system_architecture}` in `figure*` |
| 2 | `fig2_intent_abstraction.pdf` | **single** | 3.0″ × 8.0″ | `\includegraphics[width=\columnwidth]{figures/fig2_intent_abstraction}` |
| 3 | `fig3_prompt_architecture.pdf` | **single** | 3.0″ × 6.7″ | `\includegraphics[width=\columnwidth]{figures/fig3_prompt_architecture}` |
| 4 | `fig4_leader_pipeline.pdf` | **double** | 7.0″ × 3.0″ | `\includegraphics[width=\textwidth]{figures/fig4_leader_pipeline}` in `figure*` |
| 5 | `fig5_lora_results.png` | **double** | *(PNG image)* | `\includegraphics[width=\textwidth]{figures/fig5_lora_results}` in `figure*` |
| 6 | `fig6_asset_fallback.pdf` | **single** | 3.0″ × 4.5″ | `\includegraphics[width=\columnwidth]{figures/fig6_asset_fallback}` |
| 7 | *(LaTeX table)* | **single** | *(tabular)* | Included as `tabular` inside `table` environment |

### Example LaTeX Usage

```latex
% Single-column figure
\begin{figure}[htbp]
    \centering
    \includegraphics[width=\columnwidth]{figures/fig2_intent_abstraction.pdf}
    \caption{Intent-based LLM abstraction layer showing the five-stage pipeline from strategic reasoning to rule-enforced game state.}
    \label{fig:intent-abstraction}
\end{figure}

% Double-column figure (spans both columns)
\begin{figure*}[htbp]
    \centering
    \includegraphics[width=\textwidth]{figures/fig1_system_architecture.pdf}
    \caption{System architecture showing four primary components and data flow between frontend, backend, asset server, and training pipeline.}
    \label{fig:architecture}
\end{figure*}
```

## Figure Inventory

| # | File | Title | Key AI Concept |
|---|------|-------|----------------|
| 1 | `fig1_system_architecture.md` | System Architecture Overview | Multi-service AI architecture |
| 2 | `fig2_intent_abstraction.md` | Intent-Based Abstraction Layer | LLM tool-use, agent safety |
| 3 | `fig3_prompt_architecture.md` | Four-Layer Prompt Architecture | Prompt engineering, DiT conditioning |
| 4 | `fig4_leader_pipeline.md` | Three-Stage Leader Pipeline | img2img, identity preservation |
| 5 | `fig5_lora_matrix.md` | LoRA Experiment Matrix | Fine-tuning, evaluation methodology |
| 6 | `fig6_asset_fallback.md` | Asset Fallback Tiers | Graceful degradation |
| 7 | `fig7_ai_behavior.md` | AI Behavior Patterns | Qualitative comparison (LaTeX table) |

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

## Compile Script Configuration

The `compile_figures.sh` script uses per-figure viewport and scale settings tuned for IEEE column widths:

| Fig | Viewport (-w × -H) | Scale | Column |
|-----|---------------------|-------|--------|
| 1 | 1400 × 900 | 2 | double |
| 2 | 800 × 900 | 2 | single |
| 3 | 800 × 900 | 2 | single |
| 4 | 1400 × 900 | 2 | double |
| 6 | 800 × 550 | 2 | single |

Figures 5 (PNG image) and 7 (LaTeX table) are not compiled by this script — they are included directly in the LaTeX source.

## Diagram Completeness Checklist

- [x] Fig 1: System Architecture Overview
- [x] Fig 2: Intent-Based Abstraction Layer
- [x] Fig 3: Four-Layer Prompt Architecture
- [x] Fig 4: Three-Stage Leader Pipeline
- [x] Fig 5: LoRA Experiment Matrix
- [x] Fig 6: Asset Generation Modes & Fallback Strategy
- [x] Fig 7: AI Behavior Patterns (LaTeX table)
- [ ] Fig 8: Diplomacy Chat System (TBD)
- [ ] Fig 9: Frontend Component Tree (TBD)
- [ ] Fig 10: Testing Architecture (TBD)
- [ ] Fig 11: Deployment Architecture (TBD)
- [ ] Fig 12: Ethical AI Framework (TBD)

## Related Documents

- `../FIGURE_DESCRIPTIONS.md` — Full figure descriptions and captions for all 12 figures
- `../REPORT.pdf` — Academic report (PDF)
- `../../ARCHITECTURE.md` — Backend engine architecture
- `../../ASSET_INTEGRATION.md` — Asset service contract and resolution
- `assetserver/docs/pipeline/image-generation-pipeline.md` — DiT mechanics deep-dive
- `dataset-gen-train/docs/experiment-design.md` — LoRA experiment design document
