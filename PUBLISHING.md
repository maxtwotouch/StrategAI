# Publishing Guide — Top-Down Medieval Pixel Art LoRA

This document helps you prepare the final model card and repository for publication on Hugging Face, Civitai, or your preferred model hub.

---

## Model Card Template

When publishing your trained LoRA, include the following sections in your model card:

### Trigger Token

**`<tdmp>`**

Always use the angle brackets. The token is injected automatically during training and must be present at inference to activate the LoRA.

Example prompt:
```
<tdmp> a medieval granary in steampunk industrial style, top-down pixel art 16x16, white background
```

### Base Model

- **4B config**: `black-forest-labs/FLUX.2-klein-4B`
- **9B config**: `black-forest-labs/FLUX.2-klein-9B`

### Training Summary

| Parameter | Value |
|-----------|-------|
| Method | LoRA |
| Rank (linear) | 128 |
| Rank (conv) | 64 |
| Learning rate | 8e-5 |
| Steps | 2500 |
| Optimizer | adamw_8bit |
| Timestep type | weighted |
| Weight decay | 1e-4 |
| Resolution buckets | 512, 768, 1024 (repeated) |
| Scheduler | flowmatch |
| Captions | Natural language with `[trigger]` placeholder — toolkit replaces at train time |

### Intended Use

- Top-down (overhead) medieval/fantasy pixel art assets
- Game development tilesets (structures, backgrounds, props)
- 16×16 and similar small-scale pixel art styles
- Consistent art direction across multiple assets

### Limitations

- Trained on a specific art style; may not generalize to non-pixel-art or non-medieval subjects
- Small dataset size requires careful inference parameter tuning
- Best results with white/isolated backgrounds during training; may need prompt engineering for complex scenes

### Inference Settings

| Setting | Recommended |
|---------|-------------|
| Sampler | FlowMatch |
| Steps | 4–25 |
| Guidance scale | 3–4 |
| LoRA strength | 0.8–1.0 |
| Resolution | 1024×1024 (native), scales down well |

---

## Files to Publish

After training completes, publish:

1. **The `.safetensors` checkpoint** (e.g. `flux2_klein_4b_lora_step_1500.safetensors`)
2. **This repo's `README.md`** (adapted for the model card)
3. **Sample images** from `output/<name>/samples/`
4. **Config reference** (the `config/lora_4b.yaml` or `config/lora_9b.yaml` used)

---

## License Considerations

- The base model (`FLUX.2 Klein`) is gated by Black Forest Labs. Users must accept the license on Hugging Face before downloading.
- Your LoRA weights are your own work. License them as you see fit (e.g. CC-BY-SA 4.0, MIT, or commercial).
- Include a note that the LoRA requires the base model and acceptance of its license.

---

## Example Model Card (Markdown)

```markdown
# Top-Down Medieval Pixel Art — FLUX.2 Klein LoRA

**Trigger:** `<tdmp>`

A LoRA for generating consistent top-down medieval pixel art game assets using FLUX.2 Klein.

## Usage

```
<tdmp> a medieval watchtower in gothic style, top-down pixel art 16x16, white background
```

## Training
- Base: `black-forest-labs/FLUX.2-klein-4B`
- Rank-128 LoRA (64 conv), 2500 steps, natural language captions
- See [training repo](https://github.com/YOURNAME/TopDownMedievalPixelArt-Flux2-Klein-LoRa) for configs and dataset tools

## License
- LoRA weights: [Your License]
- Requires FLUX.2 Klein base model (accept on Hugging Face)
```

---

## Checklist Before Publishing

- [ ] Trained checkpoint saved as `.safetensors`
- [ ] Sample images generated and reviewed for quality
- [ ] Trigger token verified working in inference
- [ ] Model card includes trigger token, base model, and usage examples
- [ ] License chosen and declared
- [ ] No copyrighted or unlicensed training images included in public repo
