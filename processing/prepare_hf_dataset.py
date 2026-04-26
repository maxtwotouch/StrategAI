#!/usr/bin/env python3
"""Prepare a PNG + JSON sidecar dataset for Hugging Face imagefolder publishing.

Output layout:
- <out_dir>/images/*.png
- <out_dir>/metadata.jsonl
- (optional) <out_dir>/metadata/*.json (trimmed sidecars)
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import shutil
import zlib
from pathlib import Path
from typing import Iterable


DEFAULT_EXTRA_FIELDS = ["asset_family", "domain", "object_class"]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_KEY_PROMPT = "prompt"


def detect_paths(dataset_root: Path) -> tuple[Path, Path]:
    direct_meta = dataset_root / "metadata"
    direct_images = dataset_root / "images"
    generated_meta = dataset_root / "generated" / "metadata"
    generated_images = dataset_root / "generated" / "images"

    if direct_meta.is_dir() and direct_images.is_dir():
        return direct_meta, direct_images
    if generated_meta.is_dir() and generated_images.is_dir():
        return generated_meta, generated_images
    raise FileNotFoundError(f"Could not locate metadata/images directories under: {dataset_root}")


def iter_metadata_files(metadata_dir: Path) -> Iterable[Path]:
    return sorted(metadata_dir.glob("*.json"))


def resolve_image_path(metadata: dict, image_dir: Path) -> Path:
    image_path = metadata.get("image_path", "")
    if image_path:
        candidate = image_dir.parent / image_path
        if candidate.exists():
            return candidate
        candidate = image_dir / Path(image_path).name
        if candidate.exists():
            return candidate

    image_id = metadata.get("id", "")
    if image_id:
        candidate = image_dir / f"{image_id}.png"
        if candidate.exists():
            return candidate
    return image_dir / "unknown.png"


def pick_caption(metadata: dict) -> str:
    # Prefer compact captions when available, then fallback to caption/prompt.
    for key in ("lora_caption", "caption", "positive_prompt"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _iter_chunks_tolerant(png_bytes: bytes) -> list[tuple[bytes, bytes]]:
    if not png_bytes.startswith(PNG_SIGNATURE):
        raise ValueError("Not a PNG file")

    pos = len(PNG_SIGNATURE)
    chunks: list[tuple[bytes, bytes]] = []
    while pos < len(png_bytes):
        if pos + 8 > len(png_bytes):
            break
        length = struct.unpack(">I", png_bytes[pos : pos + 4])[0]
        chunk_type = png_bytes[pos + 4 : pos + 8]
        data_start = pos + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(png_bytes):
            break
        chunk_data = png_bytes[data_start:data_end]
        chunks.append((chunk_type, chunk_data))
        pos = crc_end
        if chunk_type == b"IEND":
            break
    return chunks


def read_png_text_fields(image_path: Path, wanted_keys: set[str]) -> dict[str, str]:
    payload = image_path.read_bytes()
    found: dict[str, str] = {}
    for chunk_type, chunk_data in _iter_chunks_tolerant(payload):
        if chunk_type == b"tEXt":
            marker = chunk_data.find(b"\x00")
            if marker <= 0:
                continue
            key = chunk_data[:marker].decode("latin-1", errors="ignore")
            if key in wanted_keys:
                value = chunk_data[marker + 1 :].decode("latin-1", errors="ignore")
                found[key] = value
        elif chunk_type == b"zTXt":
            marker = chunk_data.find(b"\x00")
            if marker <= 0 or marker + 2 > len(chunk_data):
                continue
            key = chunk_data[:marker].decode("latin-1", errors="ignore")
            if key not in wanted_keys:
                continue
            comp_method = chunk_data[marker + 1]
            if comp_method != 0:
                continue
            compressed = chunk_data[marker + 2 :]
            try:
                value = zlib.decompress(compressed).decode("utf-8", errors="ignore")
            except Exception:
                continue
            found[key] = value
        elif chunk_type == b"iTXt":
            marker = chunk_data.find(b"\x00")
            if marker <= 0:
                continue
            key = chunk_data[:marker].decode("latin-1", errors="ignore")
            if key not in wanted_keys:
                continue
            payload = chunk_data[marker + 1 :]
            if len(payload) < 2:
                continue
            compressed_flag = payload[0]
            compression_method = payload[1]
            rest = payload[2:]
            for _ in range(2):
                sep = rest.find(b"\x00")
                if sep == -1:
                    rest = b""
                    break
                rest = rest[sep + 1 :]
            if not rest:
                continue
            try:
                if compressed_flag == 1 and compression_method == 0:
                    value = zlib.decompress(rest).decode("utf-8", errors="ignore")
                else:
                    value = rest.decode("utf-8", errors="ignore")
            except Exception:
                continue
            found[key] = value
    return found


def extract_positive_prompt_from_embedded_prompt(raw_prompt_field: str) -> str:
    raw = (raw_prompt_field or "").strip()
    if not raw:
        return ""

    try:
        workflow = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if not isinstance(workflow, dict):
        return raw

    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") != "CLIPTextEncode":
            continue
        inputs = node.get("inputs", {})
        if isinstance(inputs, dict) and isinstance(inputs.get("text"), str):
            return inputs["text"].strip()

    return raw


def resolve_generated_prompt_text(metadata: dict, image_path: Path) -> str:
    meta_prompt = metadata.get("positive_prompt")
    if isinstance(meta_prompt, str) and meta_prompt.strip():
        return meta_prompt.strip()

    png_fields = read_png_text_fields(image_path, {PNG_KEY_PROMPT})
    return extract_positive_prompt_from_embedded_prompt(png_fields.get(PNG_KEY_PROMPT, ""))


def link_or_copy(src: Path, dst: Path, mode: str) -> None:
    if dst.exists():
        dst.unlink()

    if mode == "symlink":
        os.symlink(src, dst)
        return

    if mode == "hardlink":
        try:
            os.link(src, dst)
            return
        except OSError:
            # Fallback to copy if hardlink is not possible (filesystem boundary, permissions, etc).
            pass

    shutil.copy2(src, dst)


def parse_extra_fields(extra_fields_raw: str) -> list[str]:
    if not extra_fields_raw.strip():
        return []
    return [field.strip() for field in extra_fields_raw.split(",") if field.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Hugging Face imagefolder-ready dataset export.")
    parser.add_argument(
        "dataset_roots",
        nargs="+",
        type=Path,
        help="One or more source dataset roots (processed in the order provided).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Export directory. Default: <dataset_root>/hf_ready",
    )
    parser.add_argument(
        "--link-mode",
        choices=["copy", "hardlink", "symlink"],
        default="hardlink",
        help="How images are placed in output/images.",
    )
    parser.add_argument(
        "--extra-fields",
        default=",".join(DEFAULT_EXTRA_FIELDS),
        help="Comma-separated metadata fields to keep in metadata.jsonl in addition to id/file_name/text.",
    )
    parser.add_argument(
        "--caption-source",
        choices=["generated_prompt", "metadata_caption"],
        default="generated_prompt",
        help="Text source used for metadata `text` and image-sidecar `.txt` captions.",
    )
    parser.add_argument(
        "--linearize-ids",
        dest="linearize_ids",
        action="store_true",
        help="Emit sequential IDs and filenames in export order (default: enabled).",
    )
    parser.add_argument(
        "--keep-source-ids",
        dest="linearize_ids",
        action="store_false",
        help="Preserve source IDs as output IDs/filenames.",
    )
    parser.set_defaults(linearize_ids=True)
    parser.add_argument(
        "--linear-id-width",
        type=int,
        default=7,
        help="Zero-pad width for sequential IDs when --linearize-ids is enabled.",
    )
    parser.add_argument(
        "--include-source-id",
        action="store_true",
        help="Include original source id in metadata rows as `source_id`.",
    )
    parser.add_argument(
        "--write-trimmed-sidecars",
        action="store_true",
        help="Write minimal JSON sidecars to <out_dir>/metadata/.",
    )
    parser.add_argument(
        "--write-captions-txt",
        dest="write_captions_txt",
        action="store_true",
        help="Write LoRA caption .txt files next to exported images (default: enabled).",
    )
    parser.add_argument(
        "--skip-captions-txt",
        dest="write_captions_txt",
        action="store_false",
        help="Disable writing caption .txt files next to exported images.",
    )
    parser.set_defaults(write_captions_txt=True)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail immediately on missing/corrupt rows. Default behavior skips bad rows and reports them.",
    )
    parser.add_argument(
        "--fail-on-missing-image",
        action="store_true",
        help="Treat missing image files as hard errors instead of intentional skips.",
    )
    parser.add_argument(
        "--fail-on-duplicate-id",
        action="store_true",
        help="Fail when duplicate ids would overwrite files in output/images.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_roots = [root.resolve() for root in args.dataset_roots]
    if len(dataset_roots) > 1 and args.out_dir is None:
        raise ValueError("--out-dir is required when merging multiple dataset roots")

    base_root = dataset_roots[0]
    out_dir = (args.out_dir.resolve() if args.out_dir else (base_root / "hf_ready").resolve())

    sources: list[tuple[Path, Path, Path]] = []
    for root in dataset_roots:
        metadata_dir, image_dir = detect_paths(root)
        sources.append((root, metadata_dir, image_dir))

    out_images = out_dir / "images"
    out_meta_jsonl = out_dir / "metadata.jsonl"
    out_sidecars = out_dir / "metadata"

    out_images.mkdir(parents=True, exist_ok=True)
    if args.write_trimmed_sidecars:
        out_sidecars.mkdir(parents=True, exist_ok=True)

    extra_fields = parse_extra_fields(args.extra_fields)

    converted = 0
    skipped = 0
    skipped_missing_images = 0
    captions_txt_written = 0
    prompt_caption_fallbacks = 0
    errors: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    per_root: list[dict[str, object]] = []

    with out_meta_jsonl.open("w", encoding="utf-8") as metadata_jsonl:
        for root, metadata_dir, image_dir in sources:
            root_converted = 0
            root_skipped = 0
            root_missing = 0
            for meta_path in iter_metadata_files(metadata_dir):
                try:
                    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                    image_path = resolve_image_path(metadata, image_dir)
                    if not image_path.exists():
                        if args.fail_on_missing_image:
                            raise FileNotFoundError(f"Image not found for metadata: {meta_path.name}")
                        skipped += 1
                        skipped_missing_images += 1
                        root_skipped += 1
                        root_missing += 1
                        continue

                    source_id = str(metadata.get("id") or image_path.stem)
                    if args.linearize_ids:
                        image_id = f"{converted + 1:0{args.linear_id_width}d}"
                    else:
                        image_id = source_id
                    if image_id in seen_ids:
                        message = f"Duplicate id encountered: {image_id}"
                        if args.fail_on_duplicate_id:
                            raise ValueError(message)
                        skipped += 1
                        root_skipped += 1
                        errors.append({"file": str(meta_path), "error": message})
                        continue
                    seen_ids.add(image_id)

                    out_image_name = f"{image_id}.png"
                    dst_image_path = out_images / out_image_name
                    link_or_copy(image_path, dst_image_path, args.link_mode)

                    if args.caption_source == "generated_prompt":
                        caption_text = resolve_generated_prompt_text(metadata, image_path)
                        if not caption_text:
                            caption_text = pick_caption(metadata)
                            prompt_caption_fallbacks += 1
                    else:
                        caption_text = pick_caption(metadata)

                    row = {
                        "id": image_id,
                        "file_name": f"images/{out_image_name}",
                        "text": caption_text,
                    }
                    if args.include_source_id:
                        row["source_id"] = source_id
                    for field in extra_fields:
                        if field in metadata:
                            row[field] = metadata[field]
                            continue

                        generation = metadata.get("generation", {})
                        if isinstance(generation, dict) and field in generation:
                            row[field] = generation[field]

                    metadata_jsonl.write(json.dumps(row, ensure_ascii=False) + "\n")

                    if args.write_captions_txt:
                        caption_txt_path = dst_image_path.with_suffix(".txt")
                        caption_txt_path.write_text(caption_text + "\n", encoding="utf-8")
                        captions_txt_written += 1

                    if args.write_trimmed_sidecars:
                        sidecar_path = out_sidecars / f"{image_id}.json"
                        sidecar_path.write_text(json.dumps(row, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

                    converted += 1
                    root_converted += 1
                except Exception as exc:  # noqa: BLE001
                    skipped += 1
                    root_skipped += 1
                    errors.append({"file": str(meta_path), "error": str(exc)})
                    if args.strict:
                        raise
            per_root.append(
                {
                    "dataset_root": str(root),
                    "metadata_source": str(metadata_dir),
                    "images_source": str(image_dir),
                    "converted": root_converted,
                    "skipped": root_skipped,
                    "skipped_missing_images": root_missing,
                }
            )

    report = {
        "dataset_roots": [str(root) for root in dataset_roots],
        "output_dir": str(out_dir),
        "merged_roots": len(dataset_roots),
        "link_mode": args.link_mode,
        "converted": converted,
        "skipped": skipped,
        "skipped_missing_images": skipped_missing_images,
        "captions_txt_written": captions_txt_written,
        "write_captions_txt": args.write_captions_txt,
        "caption_source": args.caption_source,
        "linearize_ids": args.linearize_ids,
        "linear_id_width": args.linear_id_width,
        "include_source_id": args.include_source_id,
        "prompt_caption_fallbacks": prompt_caption_fallbacks,
        "per_root": per_root,
        "errors": len(errors),
    }
    (out_dir / "prepare_hf_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if errors:
        with (out_dir / "prepare_hf_errors.jsonl").open("w", encoding="utf-8") as f:
            for item in errors:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(json.dumps(report, indent=2))
    return 1 if (errors and args.strict) else 0


if __name__ == "__main__":
    raise SystemExit(main())

