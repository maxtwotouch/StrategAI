# Dataset/Training — AI Agent System

This subproject contains the LoRA fine-tuning pipeline for FLUX2 Klein 4B on top-down medieval pixel art.

## Architecture

Fine-tunes FLUX2 Klein 4B on top-down medieval pixel-art style via LoRA (Low-Rank Adaptation). Uses Ostris AI Toolkit for training orchestration. 6-experiment matrix: 3 caption variants × 2 rank levels.

## Directory Structure

| Path | Contents |
|------|----------|
| `src/generation/` | Dataset generation tooling (prompt_generator, dataset_generator, image_metadata, prepare_dataset) |
| `src/training/` | Training tooling (validate, derive captions, extract training set, sync prompts) |
| `config/training/` | 6 training experiment configs (detailed/minimal/ultra_minimal × high/low rank) |
| `config/comfyui/` | 2 ComfyUI workflow API JSONs |
| `config/prompt_templates.json` | Prompt generation templates |
| `dataset/` | Dataset root (hf/, derived/, merge_new/, old/) |
| `dataset/metadata.jsonl` | Source caption metadata (100 images) |
| `dataset/hf/` | Published dataset (PNGs + metadata.jsonl) |
| `dataset/derived/` | Derived caption variants (detailed, minimal, ultra_minimal) |
| `scripts/` | Bash orchestrators (generate_images.sh, train_experiments.sh) |
| `tests/` | pytest unit tests |
| `docs/` | Experiment design, training reference, generation reference |

## AI Technology (Course Relevance)

**LoRA Fine-Tuning**: Low-Rank Adaptation of FLUX2 Klein 4B for style transfer.

**Key architectural decisions**:
- **6-experiment matrix**: 3 caption variants (detailed/minimal/ultra_minimal) × 2 rank levels (high/low)
- **Trigger token**: `<tdp>` injected by Ostris toolkit at training time
- **Curated dataset**: 100 images generated via ComfyUI, manually curated, with 3 caption variants
- **Published dataset**: Available on HuggingFace (`stixxert/topdown-medieval-pixelart`)
- **Ostris AI Toolkit**: Training orchestration, LoRA injection, hyperparameter management

## Pipelines

### Dataset Pipeline (`src/generation/`)

1. Generate images via ComfyUI using prompt templates
2. Manual curation (quality filtering)
3. Derive 3 caption variants (detailed, minimal, ultra_minimal)
4. Prepare HuggingFace dataset format

### Training Pipeline (`src/training/`)

1. Validate dataset integrity
2. Derive captions from metadata
3. Extract training set
4. Sync prompts with Ostris toolkit
5. Launch training via `scripts/train_experiments.sh`

## Conventions

- **Trigger token**: `<tdp>` (the toolkit injects it at training time)
- **Caption format**: natural language sentences, never structured tags
- **Angle phrase**: `top-down view.` (replaced old `Front view overhead elevated medium shot.`)
- **Dataset root**: `dataset/` with subdirs `hf/`, `derived/`, `merge_new/`, `old/`
- **Config locations**: training YAMLs in `config/training/`, ComfyUI workflows in `config/comfyui/`, prompt templates in `config/prompt_templates.json`
- **Config naming**: `lora_4b_{variant}_{rank}.yaml` (e.g., `lora_4b_detailed_high.yaml`)
- **Python modules**: generation tools under `src/generation/`, training tools under `src/training/`
- **Python modules run as**: `python -m src.{generation|training}.{module_name}`
- **Training launched via**: Ostris toolkit: set `OSTRIS_TOOLKIT` env var, then `bash scripts/train_experiments.sh`

## Agent Roster

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| **Orchestrator** | Pipeline coordination | Phase management, validation gates |
| **Training** | LoRA config YAML | Experiment launching, hyperparameter tuning |
| **Dataset** | Image generation | Curation, caption derivation |
| **Publishing** | HuggingFace publishing | Model cards, README |
| **Code Quality** | Tests, linting | Python refactoring |

## Testing

```bash
python -m pytest tests/ -x --tb=short
```

## Quick Start

```bash
# See README.md for full setup
# Dataset generation
bash scripts/generate_images.sh

# Training
export OSTRIS_TOOLKIT=/path/to/ostris/ai-toolkit
bash scripts/train_experiments.sh
```

## Cross-Project Context

- **Asset Server shares**: ComfyUI infrastructure, FLUX2 Klein model, LoRA weights applied at inference
- **Published dataset**: HuggingFace (`stixxert/topdown-medieval-pixelart`) — used by asset server for style consistency
- **Root orchestrator**: For cross-project tasks, delegate to root `.github/agents/orchestrator.agent.md`

## Documentation

- `docs/experiment-design.md` — Master experiment design doc
- `docs/training.md` — Complete LoRA training reference
- `docs/generation.md` — Complete dataset generation reference
- `docs/comfyui-workflows.md` — ComfyUI workflow deep-dive
