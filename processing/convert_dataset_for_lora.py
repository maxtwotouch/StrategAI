#!/usr/bin/env python3
"""Convert dataset metadata into PNG-embedded fields for LoRA fine-tuning.

Primary outputs are written into each PNG as text chunks:
- `asset_family`
- `caption`
- `pixelart_meta` (JSON payload)

Optional compatibility outputs can also be written:
- metadata sidecar JSON updates
- adjacent caption `.txt` files
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


OBJECT_PREFIX_MARKER = "Isolate the object on a plain white background, only focusing on the specified object."
OBJECT_SUFFIX_MARKER = "Pixel art 16x16 for game tile assets"
TILE_PREFIX_MARKER = "No disruptive features or objects touching the outermost pixel edges."
TILE_SUFFIX_MARKER = "Crisp pixel edges, consistent top-down game tile style"

TRIGGER_TOKEN = ""
STRUCTURE_CAMERA_PHRASE = "front view overhead shot"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_KEY_ASSET_FAMILY = "asset_type"
PNG_KEY_CAPTION = "caption"
PNG_KEY_META_JSON = "pixelart_meta"
PNG_KEY_PROMPT = "prompt"
TEXT_CHUNK_TYPES = {b"tEXt", b"zTXt", b"iTXt"}


@dataclass
class MarkerConfig:
    object_prefix: str = OBJECT_PREFIX_MARKER
    object_suffix: str = OBJECT_SUFFIX_MARKER
    tile_prefix: str = TILE_PREFIX_MARKER
    tile_suffix: str = TILE_SUFFIX_MARKER


@dataclass
class ConversionStats:
    scanned: int = 0
    converted: int = 0
    skipped: int = 0
    errors: int = 0


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"\.\.+", ".", text)
    return text.strip(" .")


def parse_templates_file(templates_path: Path) -> MarkerConfig:
    """Load marker strings from templates when available; fallback to defaults."""
    config = MarkerConfig()
    if not templates_path.is_file():
        return config

    content = templates_path.read_text(encoding="utf-8")
    if OBJECT_PREFIX_MARKER in content:
        config.object_prefix = OBJECT_PREFIX_MARKER
    if OBJECT_SUFFIX_MARKER in content:
        config.object_suffix = OBJECT_SUFFIX_MARKER
    if TILE_PREFIX_MARKER in content:
        config.tile_prefix = TILE_PREFIX_MARKER
    if TILE_SUFFIX_MARKER in content:
        config.tile_suffix = TILE_SUFFIX_MARKER
    return config


def extract_between_markers(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start != -1:
        text = text[start + len(start_marker) :]
    end = text.find(end_marker)
    if end != -1:
        text = text[:end]
    return clean_text(text)


def minimize_core_caption(core: str) -> str:
    """Trim style-heavy trailing clauses for compact LoRA captions."""
    if not core:
        return core
    separators = [", featuring", ", with", ", and", ". Composed as", ". composed as"]
    trimmed = core
    lower = core.lower()
    cut_positions = [lower.find(token) for token in separators if lower.find(token) != -1]
    if cut_positions:
        trimmed = core[: min(cut_positions)]
    trimmed = re.sub(r"^16x16 pixel art\s+", "", trimmed, flags=re.IGNORECASE)
    return clean_text(trimmed)


def ensure_structure_camera_phrase(caption: str) -> str:
    """Guarantee structure captions include the canonical camera angle phrase once."""
    normalized = clean_text(caption)
    if STRUCTURE_CAMERA_PHRASE in normalized.lower():
        return normalized

    if normalized.startswith(TRIGGER_TOKEN):
        tail = normalized[len(TRIGGER_TOKEN) :].strip()
        return clean_text(f"{TRIGGER_TOKEN} {STRUCTURE_CAMERA_PHRASE}. {tail}")
    return clean_text(f"{STRUCTURE_CAMERA_PHRASE}. {normalized}")


def build_lora_caption(
    asset_family: str,
    positive_prompt: str,
    fallback_caption: str,
    markers: MarkerConfig,
    detail_level: str,
) -> str:
    source = clean_text(positive_prompt or fallback_caption)
    if not source:
        return TRIGGER_TOKEN

    if asset_family == "background_tile":
        core = extract_between_markers(source, markers.tile_prefix, markers.tile_suffix)
        if not core:
            core = source
        if detail_level == "minimal":
            core = minimize_core_caption(core)
        return clean_text(f"{TRIGGER_TOKEN} seamless medieval tile, {core}")

    core = extract_between_markers(source, markers.object_prefix, markers.object_suffix)
    if not core:
        core = source
    if detail_level == "minimal":
        core = minimize_core_caption(core)
    caption = clean_text(f"{TRIGGER_TOKEN} {core}")
    if asset_family == "structure":
        return ensure_structure_camera_phrase(caption)
    return caption


def infer_asset_family_from_prompt(prompt_text: str, existing_asset_family: str | None = None) -> str:
    if existing_asset_family:
        return existing_asset_family

    prompt = (prompt_text or "").lower()
    tile_markers = [
        "single 16x16 pixel art tile",
        "seamlessly repeated in all directions",
        "perfect seamless tiling",
        "top-down game tile style",
    ]
    if any(marker in prompt for marker in tile_markers):
        return "background_tile"
    return "structure"


def extract_positive_prompt_from_embedded_prompt(raw_prompt_field: str) -> str:
    """Read the actual CLIP text from ComfyUI workflow JSON stored in PNG 'prompt'."""
    raw = (raw_prompt_field or "").strip()
    if not raw:
        return ""

    try:
        workflow = json.loads(raw)
    except json.JSONDecodeError:
        return raw

    if not isinstance(workflow, dict):
        return raw

    # Prefer CLIPTextEncode prompt text (Comfy node 100 in current workflows).
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") != "CLIPTextEncode":
            continue
        inputs = node.get("inputs", {})
        if isinstance(inputs, dict) and isinstance(inputs.get("text"), str):
            return inputs["text"]

    return raw


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
        return image_dir / f"{image_id}.png"
    return image_dir / "unknown.png"


def iter_metadata_files(metadata_dir: Path) -> Iterable[Path]:
    return sorted(metadata_dir.glob("*.json"))


def _make_chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
    length = struct.pack(">I", len(chunk_data))
    crc = struct.pack(">I", zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF)
    return length + chunk_type + chunk_data + crc


def _iter_chunks_tolerant(png_bytes: bytes) -> list[tuple[int, int, bytes, bytes]]:
    """Parse as many valid chunks as possible, stopping before malformed/truncated tail."""
    if not png_bytes.startswith(PNG_SIGNATURE):
        raise ValueError("Not a PNG file")
    pos = len(PNG_SIGNATURE)
    chunks: list[tuple[int, int, bytes, bytes]] = []
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
        chunks.append((pos, crc_end, chunk_type, chunk_data))
        pos = crc_end
        if chunk_type == b"IEND":
            break
    return chunks


def _decode_text_keyword(chunk_type: bytes, chunk_data: bytes) -> str | None:
    if chunk_type not in TEXT_CHUNK_TYPES:
        return None
    marker = chunk_data.find(b"\x00")
    if marker <= 0:
        return None
    return chunk_data[:marker].decode("latin-1", errors="ignore")


def _encode_png_text(key: str, value: str) -> bytes:
    # tEXt fields are Latin-1; we keep values ASCII-safe for maximum compatibility.
    ascii_value = value.encode("ascii", errors="replace").decode("ascii")
    return key.encode("latin-1") + b"\x00" + ascii_value.encode("latin-1")


def embed_png_text_fields(image_path: Path, text_fields: dict[str, str]) -> None:
    payload = image_path.read_bytes()
    chunks = _iter_chunks_tolerant(payload)
    if not chunks:
        raise ValueError("PNG has no readable chunks")
    if chunks[0][2] != b"IHDR":
        raise ValueError("PNG missing IHDR chunk")

    replace_keys = set(text_fields.keys())
    ihdr_end = chunks[0][1]

    text_run_end = ihdr_end
    kept_existing_text_chunks: list[bytes] = []

    for start, end, chunk_type, chunk_data in chunks[1:]:
        if start != text_run_end or chunk_type not in TEXT_CHUNK_TYPES:
            break
        keyword = _decode_text_keyword(chunk_type, chunk_data)
        if not keyword or keyword not in replace_keys:
            kept_existing_text_chunks.append(payload[start:end])
        text_run_end = end

    injected_chunks = bytearray()
    for raw in kept_existing_text_chunks:
        injected_chunks += raw
    for key, value in text_fields.items():
        injected_chunks += _make_chunk(b"tEXt", _encode_png_text(key, value))

    rebuilt = payload[:ihdr_end] + bytes(injected_chunks) + payload[text_run_end:]
    image_path.write_bytes(rebuilt)


def read_png_text_fields(image_path: Path, wanted_keys: set[str]) -> dict[str, str]:
    payload = image_path.read_bytes()
    chunks = _iter_chunks_tolerant(payload)
    found: dict[str, str] = {}
    for _, _, chunk_type, chunk_data in chunks:
        if chunk_type != b"tEXt":
            continue
        marker = chunk_data.find(b"\x00")
        if marker <= 0:
            continue
        key = chunk_data[:marker].decode("latin-1", errors="ignore")
        if key not in wanted_keys:
            continue
        value = chunk_data[marker + 1 :].decode("latin-1", errors="ignore")
        found[key] = value
    return found


def convert_one_metadata_file(
    metadata_path: Path,
    image_dir: Path,
    markers: MarkerConfig,
    detail_level: str,
    write_sidecar_json: bool,
    write_txt: bool,
    dry_run: bool,
) -> Path:
    with metadata_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    asset_family = data.get("asset_family")
    if not asset_family:
        raise ValueError("Missing required field: asset_family")

    lora_caption = build_lora_caption(
        asset_family=asset_family,
        positive_prompt=data.get("positive_prompt", ""),
        fallback_caption=data.get("caption", ""),
        markers=markers,
        detail_level=detail_level,
    )
    image_path = resolve_image_path(data, image_dir)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    png_json = json.dumps(
        {
            "schema_version": 1,
            "id": data.get("id", image_path.stem),
            "asset_family": asset_family,
            "caption": lora_caption,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    text_fields = {
        PNG_KEY_ASSET_FAMILY: asset_family,
        PNG_KEY_CAPTION: lora_caption,
        PNG_KEY_META_JSON: png_json,
    }

    if not dry_run:
        embed_png_text_fields(image_path, text_fields)
        verification = read_png_text_fields(image_path, set(text_fields.keys()))
        if verification.get(PNG_KEY_ASSET_FAMILY) != asset_family:
            raise ValueError("PNG metadata verification failed for asset_family")
        if verification.get(PNG_KEY_CAPTION) != lora_caption:
            raise ValueError("PNG metadata verification failed for caption")

        if write_sidecar_json:
            prior_caption = data.get("caption", "")
            if prior_caption and prior_caption != lora_caption and "original_caption" not in data:
                data["original_caption"] = prior_caption
            data["generation_object_type"] = asset_family
            data["caption"] = lora_caption
            data["lora_caption"] = lora_caption
            with metadata_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=True)
                f.write("\n")

        if write_txt:
            caption_path = image_path.with_suffix(".txt")
            caption_path.parent.mkdir(parents=True, exist_ok=True)
            with caption_path.open("w", encoding="utf-8") as f:
                f.write(lora_caption + "\n")

    return image_path


def convert_one_png_only_file(
    image_path: Path,
    metadata_dir: Path,
    markers: MarkerConfig,
    detail_level: str,
    write_sidecar_json: bool,
    write_txt: bool,
    dry_run: bool,
) -> bool:
    png_fields = read_png_text_fields(
        image_path,
        {PNG_KEY_PROMPT, PNG_KEY_ASSET_FAMILY, PNG_KEY_CAPTION, PNG_KEY_META_JSON},
    )
    positive_prompt = extract_positive_prompt_from_embedded_prompt(png_fields.get(PNG_KEY_PROMPT, ""))
    asset_family = infer_asset_family_from_prompt(positive_prompt, png_fields.get(PNG_KEY_ASSET_FAMILY))
    if not positive_prompt:
        positive_prompt = png_fields.get(PNG_KEY_CAPTION, "")
    if not positive_prompt:
        raise ValueError(f"No prompt/caption metadata found in PNG: {image_path.name}")

    lora_caption = build_lora_caption(
        asset_family=asset_family,
        positive_prompt=positive_prompt,
        fallback_caption=png_fields.get(PNG_KEY_CAPTION, ""),
        markers=markers,
        detail_level=detail_level,
    )

    png_json = json.dumps(
        {
            "schema_version": 1,
            "id": image_path.stem,
            "asset_family": asset_family,
            "caption": lora_caption,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    text_fields = {
        PNG_KEY_ASSET_FAMILY: asset_family,
        PNG_KEY_CAPTION: lora_caption,
        PNG_KEY_META_JSON: png_json,
    }

    if not dry_run:
        embed_png_text_fields(image_path, text_fields)

        verification = read_png_text_fields(image_path, set(text_fields.keys()))
        if verification.get(PNG_KEY_ASSET_FAMILY) != asset_family:
            raise ValueError("PNG metadata verification failed for asset_family")
        if verification.get(PNG_KEY_CAPTION) != lora_caption:
            raise ValueError("PNG metadata verification failed for caption")

        if write_txt:
            caption_path = image_path.with_suffix(".txt")
            caption_path.parent.mkdir(parents=True, exist_ok=True)
            with caption_path.open("w", encoding="utf-8") as f:
                f.write(lora_caption + "\n")

        if write_sidecar_json:
            metadata_path = metadata_dir / f"{image_path.stem}.json"
            payload = {
                "id": image_path.stem,
                "asset_family": asset_family,
                "image_path": f"generated/images/{image_path.name}",
                "caption": lora_caption,
                "positive_prompt": positive_prompt,
                "generation_object_type": asset_family,
                "lora_caption": lora_caption,
            }
            with metadata_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=True)
                f.write("\n")

    return True


def run_for_root(
    dataset_root: Path,
    markers: MarkerConfig,
    detail_level: str,
    write_sidecar_json: bool,
    write_txt: bool,
    dry_run: bool,
) -> ConversionStats:
    stats = ConversionStats()
    metadata_dir, image_dir = detect_paths(dataset_root)
    errors: list[dict[str, str]] = []
    processed_images: set[str] = set()

    for metadata_file in iter_metadata_files(metadata_dir):
        stats.scanned += 1
        try:
            image_path = convert_one_metadata_file(
                metadata_file,
                image_dir,
                markers=markers,
                detail_level=detail_level,
                write_sidecar_json=write_sidecar_json,
                write_txt=write_txt,
                dry_run=dry_run,
            )
            processed_images.add(image_path.name)
            stats.converted += 1
        except Exception as exc:
            stats.errors += 1
            errors.append({"file": str(metadata_file), "error": str(exc)})

    for image_file in sorted(image_dir.glob("*.png")):
        if image_file.name in processed_images:
            continue
        stats.scanned += 1
        try:
            ok = convert_one_png_only_file(
                image_file,
                metadata_dir,
                markers=markers,
                detail_level=detail_level,
                write_sidecar_json=write_sidecar_json,
                write_txt=write_txt,
                dry_run=dry_run,
            )
            if ok:
                stats.converted += 1
            else:
                stats.skipped += 1
        except Exception as exc:
            stats.errors += 1
            errors.append({"file": str(image_file), "error": str(exc)})

    if not dry_run:
        report_path = (metadata_dir.parent / "conversion_report.json").resolve()
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "dataset_root": str(dataset_root),
                    "metadata_dir": str(metadata_dir),
                    "images_dir": str(image_dir),
                    "caption_detail": detail_level,
                    "png_fields": [PNG_KEY_ASSET_FAMILY, PNG_KEY_CAPTION, PNG_KEY_META_JSON],
                    "write_sidecar_json": write_sidecar_json,
                    "write_txt": write_txt,
                    "scanned": stats.scanned,
                    "converted": stats.converted,
                    "skipped": stats.skipped,
                    "errors": stats.errors,
                },
                f,
                indent=2,
                ensure_ascii=True,
            )
            f.write("\n")

        errors_path = (metadata_dir.parent / "conversion_errors.jsonl").resolve()
        if errors:
            with errors_path.open("w", encoding="utf-8") as f:
                for item in errors:
                    f.write(json.dumps(item, ensure_ascii=True) + "\n")
        elif errors_path.exists():
            errors_path.unlink()

    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed LoRA metadata directly into PNG files.")
    parser.add_argument(
        "dataset_roots",
        nargs="+",
        type=Path,
        help="One or more dataset roots (e.g. ./dataset or ./convertive/dataset).",
    )
    parser.add_argument(
        "--templates",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "convertive" / "templates.txt",
        help="Path to prompt templates.txt used for marker-guided caption trimming.",
    )
    parser.add_argument(
        "--caption-detail",
        choices=["minimal", "balanced"],
        default="minimal",
        help="`minimal` trims style-heavy clauses; `balanced` keeps more descriptive detail.",
    )
    parser.add_argument(
        "--write-sidecar-json",
        action="store_true",
        help="Also update sidecar metadata JSON files for compatibility.",
    )
    parser.add_argument(
        "--write-txt",
        action="store_true",
        help="Also write caption `.txt` files next to each image.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and compute captions without writing files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    markers = parse_templates_file(args.templates.resolve())

    total = ConversionStats()
    for root in args.dataset_roots:
        stats = run_for_root(
            root.resolve(),
            markers=markers,
            detail_level=args.caption_detail,
            write_sidecar_json=args.write_sidecar_json,
            write_txt=args.write_txt,
            dry_run=args.dry_run,
        )
        total.scanned += stats.scanned
        total.converted += stats.converted
        total.skipped += stats.skipped
        total.errors += stats.errors
        print(
            f"[{root}] scanned={stats.scanned} converted={stats.converted} "
            f"skipped={stats.skipped} errors={stats.errors}"
        )

    print(
        f"TOTAL scanned={total.scanned} converted={total.converted} "
        f"skipped={total.skipped} errors={total.errors}"
    )

    return 1 if total.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())


