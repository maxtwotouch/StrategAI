# Publishing a Flux2 Klein LoRA

This is the shortest path from a working dataset to a published LoRA on Hugging Face / Civitai / GitHub.

---

## 0. Before you start

- You've already run `python -m src.validate_dataset` and it passes with `status: pass`.
- You've run `./scripts/smoke_test.sh` and it passes.
- You have the Ostris ai-toolkit installed and `ai-toolkit --version` works.
- **⚠️ Compatibility caveat:** The generated `ostris_train.yaml` config contains field names that are a best-guess approximation of the ai-toolkit schema. Before a full training run, test with a 2-image dry run (`--dataset-size 2 --skip-size-check` without `--dry-run`). If the toolkit rejects unknown keys, the field mapping lives in `src/common.py:build_ostris_training_payload()`. Adjust and retest.
- You have a Hugging Face account (or wherever you're publishing).

---

## 1. Pick your model and tune your run config

Edit `config/run_lora.yaml`:

```
num_train_steps: 1500      # Default. Increase for larger datasets (e.g. 3000).
learning_rate: 0.0001      # Start here, rarely needs changing.
lora_rank: 32              # 32 for detail, 16 for smaller files.
validation_prompts: [...]  # 4-8 prompts that match your training caption style.
```

Set your trigger token in `config/data.yaml`:

```yaml
tokens:
  trigger: "<your_token>"   # e.g. "<tmp>", "<medieval-lora>"
  prepend_to_captions: true
```

Pick 4B or 9B:
- `config/model_flux2_klein_4b.yaml` — 16 GB VRAM, easier to run
- `config/model_flux2_klein_9b.yaml` — 48 GB VRAM, higher quality ceiling

---

## 2. Sync your validation prompts from real captions

```zsh
./scripts/sync_validation_prompts.sh --max-prompts 6 --max-chars 420
```

This pulls captions from your dataset and writes them into `run_lora.yaml` with your trigger token prepended. Validation images will match your training style.

---

## 3. Dry-run to inspect what the model will see

```zsh
MODEL_SIZE=4b ./scripts/train_lora.sh --dry-run
```

Open `runs/flux2_klein_lora_v1/metadata.prepared.jsonl` and verify:
- Trigger token is prepended to every caption
- No duplicate tokens
- Captions are under ~420 chars

If anything looks wrong, fix `config/data.yaml` (tokens block) or your source captions.

---

## 4. Train

```zsh
MODEL_SIZE=4b ./scripts/train_lora.sh
```

Let it run. Checkpoints save to `runs/flux2_klein_lora_v1/` every `save_every_steps`.

If you need a smaller stratified sample:

```zsh
MODEL_SIZE=4b ./scripts/train_lora.sh --dataset-size 200 --skip-size-check
```

---

## 5. Pick the best checkpoint

Generate samples from multiple checkpoints:

```zsh
./scripts/run_eval_samples.sh runs/flux2_klein_lora_v1/checkpoint-600
./scripts/run_eval_samples.sh runs/flux2_klein_lora_v1/checkpoint-1200
./scripts/run_eval_samples.sh runs/flux2_klein_lora_v1/checkpoint-1800
./scripts/run_eval_samples.sh runs/flux2_klein_lora_v1/checkpoint-2400
```

Judge by:
- **Style separability** — different styles actually look different
- **Pose stability** — your fixed pose doesn't drift
- **No overfitting** — the model generalizes, doesn't memorize

Usually the best checkpoint is at 60-80% of total steps, not the final one.

---

## 6. Save the winning adapter

```zsh
cp -r runs/flux2_klein_lora_v1/checkpoint-1800 ./flux2-klein-medieval-pixelart-lora
```

Your adapter folder should contain at minimum the LoRA weights file (usually `lora_weights.safetensors` or similar).

---

## 7. Create a model card

Write a `README.md` inside the adapter folder with:

```markdown
# Flux2 Klein — Medieval Pixel Art LoRA

Base model: black-forest-labs/FLUX.2-klein-4B
Trigger token: <tmp>
Trained on: [describe your dataset]
Training steps: 1500
LoRA rank: 32
Learning rate: 0.0001

## Usage

Prompt format:
<tmp> pose:front, subject:medieval granary, style:weathered stone, top-down pixel art 16x16

## Intended use

Top-down medieval pixel art game assets — structures, tiles, and backgrounds.

## Limitations

- Single fixed pose (top-down front view). Cannot generate side views or isometric angles.
- Trained on 16x16 pixel art scale. Larger resolutions may reduce pixel-crispness.
- Requires the trigger token <tmp> to activate.
```

---

## 8. Publish

### Hugging Face

```zsh
huggingface-cli upload your-username/flux2-klein-medieval-pixelart-lora ./flux2-klein-medieval-pixelart-lora .
```

Then:
- Set the base model to `black-forest-labs/FLUX.2-klein-4B` on the model page
- Add the tags: `flux`, `lora`, `pixel-art`, `top-down`, `game-assets`
- Link to your dataset card if you published it

### Civitai

Upload the safetensors file directly. In the description paste your model card. Tag it: `Flux.2 D`, `LoRA`, `Pixel Art`, `Top-Down`, `Concept`.

### GitHub (this repo)

1. Add your trained LoRA weights (or a link to them) to the repo
2. Fill in `dataset/README.md` as your dataset card
3. Push:

```zsh
git add -A
git commit -m "Release: medieval pixel art LoRA"
git push
```

---

## 9. Sanity check before announcing

```zsh
python -m src.validate_dataset --dataset-root dataset --expected-resolution 1024
python -m src.smoke_test
```

Make sure both still pass. Done.
