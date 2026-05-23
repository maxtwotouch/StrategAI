from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def load_metadata_rows(metadata_path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with metadata_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"Row {line_number} is not a JSON object.")
            rows.append(payload)
    return rows


def write_metadata_rows(metadata_path: Path, rows: List[Dict[str, Any]]) -> None:
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with metadata_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _iter_images(image_dir: Path, extensions: Iterable[str]) -> List[Path]:
    normalized = {ext.lower().lstrip(".") for ext in extensions if ext.strip()}
    if not normalized:
        normalized = {"png", "jpg", "jpeg"}

    images: List[Path] = []
    for path in sorted(image_dir.rglob("*")):
        if path.is_file() and path.suffix.lower().lstrip(".") in normalized:
            images.append(path)
    return images


def load_sidecar_caption_rows(
    dataset_root: Path,
    image_dir: Path,
    caption_extension: str,
    image_extensions: Iterable[str],
    caption_column: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    cap_ext = caption_extension if caption_extension.startswith(".") else f".{caption_extension}"
    images = _iter_images(image_dir=image_dir, extensions=image_extensions)

    for image_path in images:
        caption_path = image_path.with_suffix(cap_ext)
        if not caption_path.exists():
            continue

        text = caption_path.read_text(encoding="utf-8").strip()
        relative_image_path = image_path.resolve().relative_to(dataset_root.resolve())
        image_id = image_path.stem
        parent_rel = image_path.parent.resolve().relative_to(image_dir.resolve())
        asset_family = str(parent_rel) if str(parent_rel) != "." else "__root__"

        rows.append(
            {
                "id": image_id,
                "file_name": str(relative_image_path),
                caption_column: text,
                "asset_family": asset_family,
            }
        )

    return rows


def _compute_group_quotas(group_counts: Dict[str, int], target_size: int) -> Dict[str, int]:
    total = sum(group_counts.values())
    if total == 0:
        raise ValueError("Cannot sample an empty dataset.")
    if target_size > total:
        raise ValueError(f"Requested target size {target_size} exceeds dataset size {total}.")

    ideals: Dict[str, float] = {}
    quotas: Dict[str, int] = {}
    for group, count in group_counts.items():
        ideal = (count / total) * target_size
        quotas[group] = int(ideal)
        ideals[group] = ideal

    assigned = sum(quotas.values())
    remaining = target_size - assigned

    # Largest-remainder allocation keeps ratios close while hitting exact target size.
    ranked = sorted(
        group_counts.keys(),
        key=lambda g: (ideals[g] - quotas[g], group_counts[g], g),
        reverse=True,
    )

    while remaining > 0:
        progressed = False
        for group in ranked:
            if quotas[group] < group_counts[group]:
                quotas[group] += 1
                remaining -= 1
                progressed = True
                if remaining == 0:
                    break
        if not progressed:
            raise ValueError("Failed to allocate sample quotas; check target size and group counts.")

    return quotas


def stratified_sample_rows(
    rows: List[Dict[str, Any]],
    target_size: int,
    stratify_column: str,
    seed: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if target_size <= 0:
        raise ValueError("target_size must be a positive integer.")

    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        raw_value = row.get(stratify_column, "__missing__")
        group = str(raw_value) if raw_value not in (None, "") else "__missing__"
        groups[group].append(row)

    group_counts = {group: len(values) for group, values in groups.items()}
    quotas = _compute_group_quotas(group_counts=group_counts, target_size=target_size)

    rng = random.Random(seed)
    sampled: List[Dict[str, Any]] = []
    for group in sorted(groups.keys()):
        candidates = list(groups[group])
        rng.shuffle(candidates)
        sampled.extend(candidates[: quotas[group]])

    rng.shuffle(sampled)

    sampled_counts = Counter(
        str(row.get(stratify_column, "__missing__") if row.get(stratify_column, "__missing__") not in (None, "") else "__missing__")
        for row in sampled
    )

    report: Dict[str, Any] = {
        "stratify_column": stratify_column,
        "seed": seed,
        "source_total": len(rows),
        "sampled_total": len(sampled),
        "source_counts": dict(sorted(group_counts.items())),
        "sampled_counts": dict(sorted(sampled_counts.items())),
        "sampled_ratios": {
            group: round(sampled_counts[group] / len(sampled), 6) for group in sorted(sampled_counts.keys())
        },
    }

    return sampled, report
