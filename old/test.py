#!/usr/bin/env python3
"""
extract_prompts_for_finetune.py

Usage:
  python extract_prompts_for_finetune.py --input path/to/meta.jsonl --outdir ./ft_ready --trigger "<<sks>>" --max_words 20 --val_frac 0.05

Outputs:
  - train.jsonl
  - metadata.jsonl
  - val.jsonl and val_metadata.jsonl (if val_frac > 0)
"""

import argparse
import json
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# -------------------------
# Defaults and heuristics
# -------------------------
DEFAULT_TRIGGER = "<<sks>>"
DEFAULT_VAL_FRAC = 0.05
DEFAULT_MAX_WORDS = 20
RANDOM_SEED = 42

# Patterns derived from the standardized prompts you provided.
# These are intentionally permissive to handle small variations.
STRUCTURE_PATTERN_CANDIDATES = [
    # Capture between the "Isolate the object..." sentence and "Pixel art 16x16"
    r"Isolate the object on a plain white background, only focusing on the specified object\.\s*(?P<inner>.+?)\s*Pixel art 16x16",
    # Capture between "The structure should flow..." and "Pixel art 16x16"
    r"The structure should flow into any inserted background\.\s*(?P<inner>.+?)\s*Pixel art 16x16",
    # Generic: capture between first long procedural block and "Pixel art 16x16"
    r"\.\s*(?P<inner>[^.]{10,200}?)\s*Pixel art 16x16",
]

BACKGROUND_PATTERN_CANDIDATES = [
    # Capture between "16x16 pixel art" and "no rocks" or "Crisp pixel edges"
    r"16x16 pixel art\s*(?P<inner>.+?)\s*no rocks or objects near the edges",
    r"16x16 pixel art\s*(?P<inner>.+?)\s*Crisp pixel edges",
    # Generic: capture between "The entire image must be..." and the next sentence that starts style constraints
    r"The entire image must be one single 16x16 pixel art tile that fully fills the frame with continuous texture\.\s*(?P<inner>.+?)\s*(?:no borders|no disruptive|16x16 pixel art)",
    # Fallback: capture short phrase after "16x16 pixel art"
    r"16x16 pixel art\s*(?P<inner>[^.]{1,120}?)\.",
]

# Pose detection
POSE_KEYWORDS = {
    "overhead": ["<pose_overhead>", "overhead", "top_down", "top-down", "top down", "front view overhead"],
    "front": ["front view", "<pose_front>", "faces the camera straight from the front", "faces the camera"],
    "elevated": ["elevated", "elevated shot"],
    "medium": ["medium shot", "medium"],
}

# Style tokens to include in compact caption if present
STYLE_KEYWORDS = {
    "tile": ["16x16", "16 x 16", "16×16", "tile"],
    "pixel_art": ["pixel art", "pixel_art", "pixel-art"],
    "seamless": ["seamless", "seamless tiling", "perfect seamless"],
    "no_antialias": ["no anti-aliasing", "no anti aliasing", "no antialias"],
    "crisp_edges": ["crisp pixel edges", "crisp edges"],
    "dithering": ["dither", "dithering", "faint dithering"],
}

CATEGORY_KEYWORDS = {
    "background_tile": ["background_tile", "background", "tile", "BG-TILE", "background tile"],
    "structure": ["structure", "building", "wall", "ruin", "arch", "medieval_arch"],
    "object": ["object", "prop", "item", "asset"],
}

# -------------------------
# Helpers
# -------------------------
def load_inputs(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    items = []
    if p.is_dir():
        for f in sorted(p.iterdir()):
            if f.suffix.lower() == ".json":
                with open(f, "r", encoding="utf8") as fh:
                    try:
                        items.append(json.load(fh))
                    except Exception:
                        fh.seek(0)
                        for line in fh:
                            line = line.strip()
                            if not line:
                                continue
                            items.append(json.loads(line))
    else:
        with open(p, "r", encoding="utf8") as fh:
            text = fh.read().strip()
            # JSONL detection
            if "\n" in text and text.lstrip().startswith("{") and "\n{" in text:
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    items.append(json.loads(line))
            else:
                items.append(json.loads(text))
    return items

def find_category(obj: Dict[str, Any], caption: str) -> str:
    af = (obj.get("asset_family") or obj.get("domain") or "").lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in af:
                return cat
    # fallback to caption scanning
    cap = caption.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in cap:
                return cat
    # default
    return "structure"

def detect_pose(caption: str) -> str:
    c = caption.lower()
    for tag, kws in POSE_KEYWORDS.items():
        for kw in kws:
            if kw in c:
                return tag
    return "overhead"

def detect_style_tokens(caption: str) -> List[str]:
    c = caption.lower()
    found = []
    for tag, kws in STYLE_KEYWORDS.items():
        for kw in kws:
            if kw in c and tag not in found:
                found.append(tag)
    return found

def run_patterns(text: str, patterns: List[str]) -> str:
    if not text:
        return ""
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE | re.DOTALL)
        if m:
            inner = m.groupdict().get("inner") or m.group(0)
            # clean up leading/trailing punctuation and whitespace
            inner = inner.strip()
            inner = re.sub(r"^[\s\.\-:;]+", "", inner)
            inner = re.sub(r"[\s\.\-:;]+$", "", inner)
            # remove trailing tokens like "<pose_overhead>" if accidentally captured
            inner = re.sub(r"<[^>]+>", "", inner).strip()
            return inner
    return ""

def truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(" ,.;:") + "..."

def extract_constraints(original_caption: str, trigger: str) -> str:
    # Remove the extracted inner prompt and keep the long procedural instructions as constraints.
    # Heuristic: find the first procedural marker and return from there to end, else return long remainder.
    markers = [
        "The entire image must be",
        "Isolate the object on a plain white background",
        "No borders",
        "Generate one cohesive tile",
        "No disruptive features",
        "The structure faces the camera",
        "Pixel art 16x16",
        "Crisp pixel edges",
    ]
    s = original_caption or ""
    low = s.lower()
    for m in markers:
        idx = low.find(m.lower())
        if idx != -1:
            return s[idx:].strip()
    # fallback: if caption is long, return everything except the trigger token and tags
    cleaned = re.sub(r"<[^>]+>", " ", s)
    cleaned = cleaned.replace(trigger, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned.split()) > 8:
        return cleaned
    return ""

def build_compact_caption(trigger: str, pose: str, category: str, inner_prompt: str, style_tokens: List[str]) -> str:
    # Compose compact caption: keep trigger, pose, category, inner prompt (short), then style tokens
    parts = [trigger, pose, category]
    if inner_prompt:
        parts.append(inner_prompt)
    # append style tokens deterministically
    if style_tokens:
        parts.extend(style_tokens)
    # join and normalize whitespace
    caption = " ".join([p for p in parts if p]).strip()
    caption = re.sub(r"\s+", " ", caption)
    return caption

# -------------------------
# Main conversion
# -------------------------
def convert(items: List[Dict[str, Any]], trigger: str, max_words: int, val_frac: float, seed: int):
    random.seed(seed)
    processed = []
    for obj in items:
        orig_caption = obj.get("caption") or obj.get("positive_prompt") or ""
        # prefer positive_prompt if present
        if obj.get("positive_prompt"):
            orig_caption = obj.get("positive_prompt")
        image_path = obj.get("image_path") or obj.get("image") or obj.get("file") or ""
        if not image_path:
            image_path = obj.get("generation", {}).get("image_path", "")
        category = find_category(obj, orig_caption)
        pose = detect_pose(orig_caption)
        style_tokens = detect_style_tokens(orig_caption)
        extracted = ""
        if category == "background_tile":
            extracted = run_patterns(orig_caption, BACKGROUND_PATTERN_CANDIDATES)
        else:
            extracted = run_patterns(orig_caption, STRUCTURE_PATTERN_CANDIDATES)
        # fallback: try a generic capture of the sentence that contains the main subject
        if not extracted:
            # capture the sentence that contains "pixel art" or the sentence after the trigger
            sentences = re.split(r"\.\s+", orig_caption)
            for s in sentences:
                if "pixel art" in s.lower() or "16x16" in s.lower():
                    # try to extract phrase after "pixel art"
                    m = re.search(r"pixel art\s*(.+)", s, flags=re.IGNORECASE)
                    if m:
                        extracted = m.group(1).strip()
                        break
            if not extracted and len(sentences) > 1:
                # take the middle sentence as fallback
                extracted = sentences[len(sentences)//2].strip()
        extracted = re.sub(r"<[^>]+>", "", extracted).strip()
        extracted_short = truncate_words(extracted, max_words) if extracted else ""
        constraints = extract_constraints(orig_caption, trigger)
        compact_caption = build_compact_caption(trigger, pose, category, extracted_short, style_tokens)
        train_entry = {"image": image_path, "caption": compact_caption}
        meta_entry = {
            "id": obj.get("id"),
            "image_path": image_path,
            "asset_family": obj.get("asset_family"),
            "domain": obj.get("domain"),
            "original_caption": orig_caption,
            "extracted_prompt": extracted,
            "extracted_prompt_short": extracted_short,
            "constraints": constraints,
            "pose_tag": pose,
            "style_tokens": style_tokens,
            "category": category,
            "generation": obj.get("generation", {}),
        }
        processed.append((train_entry, meta_entry))
    # split
    total = len(processed)
    indices = list(range(total))
    random.shuffle(indices)
    val_count = int(total * val_frac)
    val_idx = set(indices[:val_count])
    train_pairs = []
    val_pairs = []
    for i, pair in enumerate(processed):
        if i in val_idx:
            val_pairs.append(pair)
        else:
            train_pairs.append(pair)
    return train_pairs, val_pairs

def write_jsonl(pairs: List[Tuple[Dict, Dict]], train_path: Path, meta_path: Path):
    with open(train_path, "w", encoding="utf8") as tfh, open(meta_path, "w", encoding="utf8") as mfh:
        for t, m in pairs:
            tfh.write(json.dumps(t, ensure_ascii=False) + "\n")
            mfh.write(json.dumps(m, ensure_ascii=False) + "\n")

# -------------------------
# CLI
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="Extract inner prompts from standardized captions and produce fine-tune JSONL.")
    parser.add_argument("--input", "-i", required=True, help="Input JSON / JSONL file or directory of JSON files.")
    parser.add_argument("--outdir", "-o", required=True, help="Output directory.")
    parser.add_argument("--trigger", "-t", default=DEFAULT_TRIGGER, help="Trigger token used in captions.")
    parser.add_argument("--max_words", type=int, default=DEFAULT_MAX_WORDS, help="Max words to keep from extracted prompt in compact caption.")
    parser.add_argument("--val_frac", "-v", type=float, default=DEFAULT_VAL_FRAC, help="Validation fraction (0-1).")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Random seed for splitting.")
    args = parser.parse_args()

    items = load_inputs(args.input)
    if not items:
        print("No metadata items found. Exiting.")
        return

    train_pairs, val_pairs = convert(items, trigger=args.trigger, max_words=args.max_words, val_frac=args.val_frac, seed=args.seed)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    train_path = outdir / "train.jsonl"
    meta_path = outdir / "metadata.jsonl"
    write_jsonl(train_pairs, train_path, meta_path)
    print(f"Wrote {len(train_pairs)} training entries to {train_path}")
    print(f"Wrote {len(train_pairs)} training metadata entries to {meta_path}")

    if val_pairs:
        val_train_path = outdir / "val.jsonl"
        val_meta_path = outdir / "val_metadata.jsonl"
        write_jsonl(val_pairs, val_train_path, val_meta_path)
        print(f"Wrote {len(val_pairs)} validation entries to {val_train_path}")
        print(f"Wrote {len(val_pairs)} validation metadata entries to {val_meta_path}")

    # quick summary
    def tally(pairs):
        poses = {}
        cats = {}
        styles = {}
        for t, m in pairs:
            poses[m["pose_tag"]] = poses.get(m["pose_tag"], 0) + 1
            cats[m["category"]] = cats.get(m["category"], 0) + 1
            for s in m.get("style_tokens", []):
                styles[s] = styles.get(s, 0) + 1
        return poses, cats, styles

    poses, cats, styles = tally(train_pairs + val_pairs)
    print("Summary (all):")
    print(" Pose counts:", poses)
    print(" Categories:", cats)
    print(" Style token counts:", styles)

if __name__ == "__main__":
    main()
