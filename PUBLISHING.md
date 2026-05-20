# Publishing Checklist

Use this checklist before making the repository public or publishing on Hugging Face.

## 1) Repository Hygiene (GitHub)
- [ ] Confirm no secrets are committed (`.env`, API tokens, private paths).
- [ ] Verify `.gitignore` excludes generated artifacts (`runs/`, `eval_samples/`, local IDE files).
- [ ] Add an explicit project `LICENSE` file.
- [ ] Ensure `README.md` quick-start steps run successfully from a clean clone.
- [ ] Ensure CI is green (`.github/workflows/ci.yml`).

## 2) Fine-Tuning Readiness
- [ ] `python -m src.validate_dataset --dataset-root dataset --expected-resolution 1024` returns `status: pass`.
- [ ] `python -m src.smoke_test` completes successfully.
- [ ] `python -m src.preflight_check` has no failed checks on your training machine.
- [ ] Dataset is large enough for your objective (recommended 30+ samples per style bucket).
- [ ] `configs/model_flux2_klein_*.yaml` uses a valid and licensed base model id.

## 3) Hugging Face Dataset Publishing
- [ ] Fill `dataset/README.md` dataset card (summary, intended use, limitations, licensing).
- [ ] Replace `license: other` with your actual license slug.
- [ ] Remove local-machine absolute paths from generated report files if included.
- [ ] Re-run validation and include latest report artifacts only if desired.

## 4) Hugging Face Model Publishing
- [ ] Prepare a model card with:
  - Base model
  - Dataset source and license
  - Training settings (`configs/*.yaml` + run config)
  - Intended use and limitations
- [ ] Include evaluation samples and known failure modes.
- [ ] Add inference examples using your final trigger token/prompt schema.

## 5) Final Sanity Commands
```zsh
python -m src.validate_dataset --dataset-root dataset --expected-resolution 1024
python -m src.smoke_test
python -m src.sync_validation_prompts --run-config configs/run_lora.yaml --max-prompts 6 --max-chars 420
python -m src.train_lora --data-config configs/data.yaml --model-config configs/model_flux2_klein_4b.yaml --run-config configs/run_lora.yaml --run-name release_dry_run --dry-run
```

