#!/usr/bin/env python3
"""
generate_comparison_grid.py — Generate comparison grid images from sampling output.

Takes the organized output from sample_checkpoints.py and generates two
comparison grid figures suitable for the project report:

  1. report_figure.png          — 2 prompts × 4 experiments (caption detail trade-off)
  2. model_card_figure_7x4.png  — 7 rows (incl. base) × 4 prompts (comprehensive comparison)

Usage:
    python scripts/generate_comparison_grid.py
    python scripts/generate_comparison_grid.py --input ./comparison_output/ --output ./comparison_grids/

Dependencies: Pillow (see dataset-gen-train/requirements.txt)
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CELL_SIZE: int = 256
CELL_PADDING: int = 4


LABEL_COLOR: tuple[int, int, int] = (40, 40, 40)
BG_COLOR: tuple[int, int, int] = (255, 255, 255)
PLACEHOLDER_COLOR: tuple[int, int, int] = (200, 200, 200)

# Ordered experiment list used by full-matrix grid
FULL_MATRIX_ROWS: list[str] = [
    "base_model",
    "detailed_high",
    "detailed_low",
    "minimal_high",
    "minimal_low",
    "ultra_high",
    "ultra_low",
]

# Prompt IDs in column order
FULL_MATRIX_COLS: list[str] = ["S1", "S2", "U1", "U2", "T3", "L1"]

# Curated 3×3 report figure (legacy)
REPORT_ROWS: list[str] = ["minimal_high", "ultra_low", "base_model"]
REPORT_COLS: list[str] = ["S1", "U1", "T3"]

# IEEE 4×2 figure: caption detail trade-off spectrum
IEEE_FIGURE_ROWS: list[str] = ["S1", "T3"]  # 2 experiments (was columns)
IEEE_FIGURE_COLS: list[str] = ["base_model", "ultra_low", "minimal_high", "detailed_high"]  # 4 prompts (was rows)

# Model card 6×4 figure: comprehensive comparison
MODEL_CARD_ROWS: list[str] = [
    "base_model",
    "detailed_high",
    "detailed_low",
    "minimal_high",
    "minimal_low",
    "ultra_high",
    "ultra_low",
]
MODEL_CARD_COLS: list[str] = ["S1", "U1", "T3", "L1"]


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate comparison grid images from LoRA checkpoint sampling output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --input ./comparison_output/ --output ./comparison_grids/
        """,
    )
    parser.add_argument(
        "--input",
        default="./sample_figures/",
        help="Input directory containing the sampling output (default: ./sample_figures/)",
    )
    parser.add_argument(
        "--output",
        default="./figures/",
        help="Output directory for grid images (default: ./figures/)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Path & font helpers
# ---------------------------------------------------------------------------

def _resolve_input_dir(raw: str) -> Path:
    """Resolve a CLI path relative to the current working directory."""
    return Path(raw).resolve()


def _load_font(size: int = 16) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a TrueType font for labels; fall back to PIL default bitmap font."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for fp in font_paths:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return ImageFont.ImageFont()


# ---------------------------------------------------------------------------
# Image loading
# ---------------------------------------------------------------------------

def _find_image(input_dir: Path, experiment: str, prompt_id: str) -> Path | None:
    """Find an image file for the given experiment and prompt.

    Checks .png first (sample_checkpoints.py output), then .jpg (existing samples).
    """
    for ext in (".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG"):
        candidate = input_dir / experiment / f"{prompt_id}{ext}"
        if candidate.is_file():
            return candidate
    return None


def _create_placeholder(
    text: str,
    size: int = CELL_SIZE,
    bg: tuple[int, int, int] = PLACEHOLDER_COLOR,
) -> Image.Image:
    """Create a square placeholder cell with centred text."""
    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    font = _load_font(14)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text(
        ((size - text_w) // 2, (size - text_h) // 2),
        text,
        fill=(80, 80, 80),
        font=font,
    )
    return img


def _load_cell_image(
    input_dir: Path,
    experiment: str,
    prompt_id: str,
    cell_size: int = CELL_SIZE,
) -> Image.Image:
    """Load and resize a cell image, returning a placeholder on failure.

    Tries the standard path ``experiment/prompt_id.png`` first, then the
    transposed path ``prompt_id/experiment.png`` so that both regular and
    transposed grids (e.g. the IEEE figure where prompts are rows and
    experiments are columns) resolve correctly.
    """
    path = _find_image(input_dir, experiment, prompt_id)
    if path is None:
        # Try transposed: maybe experiment and prompt_id are swapped
        path = _find_image(input_dir, prompt_id, experiment)
    if path is None:
        warnings.warn(
            f"Missing image: {input_dir / experiment / f'{prompt_id}.[png|jpg]'}"
        )
        return _create_placeholder(f"Missing\n{experiment}/{prompt_id}", cell_size)

    try:
        img = Image.open(path)
        # Handle RGBA images by compositing onto white background
        if img.mode == "RGBA":
            background = Image.new("RGBA", img.size, (255, 255, 255, 255))
            img = Image.alpha_composite(background, img).convert("RGB")
        else:
            img = img.convert("RGB")
        img.thumbnail((cell_size, cell_size), Image.LANCZOS)
        canvas = Image.new("RGB", (cell_size, cell_size), BG_COLOR)
        ox = (cell_size - img.width) // 2
        oy = (cell_size - img.height) // 2
        canvas.paste(img, (ox, oy))
        return canvas
    except Exception as exc:
        warnings.warn(f"Failed to load {path}: {exc}")
        return _create_placeholder(f"Error\n{experiment}/{prompt_id}", cell_size)


# ---------------------------------------------------------------------------
# Base-model (No-LoRA) directory discovery
# ---------------------------------------------------------------------------

def _find_base_model_dir(input_dir: Path) -> Path | None:
    """Look for a base / no-LoRA directory under *input_dir*."""
    candidates = [
        input_dir / "base",
        input_dir / "no_lora",
        input_dir / "base_model",
        input_dir / "no-lora",
        input_dir / "baseline",
    ]
    for cand in candidates:
        if cand.is_dir():
            return cand
    return None


def _load_base_model_cell(input_dir: Path, prompt_id: str) -> Image.Image:
    """Load a cell from the base-model directory, or return a 'No LoRA' placeholder.

    Base model images are stored flat at base_model/{prompt_id}.png (e.g. base_model/S1.png).
    All strength=0 images are identical regardless of which checkpoint is used.
    """
    base_dir = _find_base_model_dir(input_dir)
    if base_dir is not None:
        # Images are stored flat: base_model/S1.png
        for ext in (".png", ".jpg", ".jpeg"):
            candidate = base_dir / f"{prompt_id}{ext}"
            if candidate.is_file():
                try:
                    img = Image.open(candidate)
                    # Handle RGBA images by compositing onto white background
                    if img.mode == "RGBA":
                        background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                        img = Image.alpha_composite(background, img).convert("RGB")
                    else:
                        img = img.convert("RGB")
                    img.thumbnail((CELL_SIZE, CELL_SIZE), Image.LANCZOS)
                    canvas = Image.new("RGB", (CELL_SIZE, CELL_SIZE), BG_COLOR)
                    ox = (CELL_SIZE - img.width) // 2
                    oy = (CELL_SIZE - img.height) // 2
                    canvas.paste(img, (ox, oy))
                    return canvas
                except Exception as exc:
                    warnings.warn(f"Failed to load base-model image {candidate}: {exc}")

    return _create_placeholder("No LoRA", CELL_SIZE, PLACEHOLDER_COLOR)


# ---------------------------------------------------------------------------
# Label formatting
# ---------------------------------------------------------------------------

_compact_label_map: dict[str, str] = {
    "base_model": "Base Model",
    "detailed_high": "Detailed-High",
    "detailed_low": "Detailed-Low",
    "minimal_high": "Minimal-High",
    "minimal_low": "Minimal-Low",
    "ultra_high": "Ultra-High",
    "ultra_low": "Ultra-Low",
}


_prompt_label_map: dict[str, str] = {
    "S1": "Watchtower",
    "S2": "Watermill",
    "U1": "Knight",
    "U2": "Archer",
    "T1": "Hill",
    "T2": "Oak Tree",
    "T3": "Boulder",
    "L1": "Sports Car",
}


def _format_experiment_label(name: str) -> str:
    """Turn a snake_case experiment name into a compact display label."""
    return _compact_label_map.get(name, name.replace("_", " ").title())


def _format_row_label(name: str) -> str:
    """Format a row label — prompt IDs stay as raw IDs, experiments get compact labels."""
    if len(name) == 2 and name[0] in "SUTL" and name[1].isdigit():
        return name  # Keep prompt IDs as raw (S1, U1, T3, L1, etc.)
    return _format_experiment_label(name)


# ---------------------------------------------------------------------------
# Generic grid builder
# ---------------------------------------------------------------------------

def _build_grid(
    rows: Sequence[str],
    cols: Sequence[str],
    input_dir: Path,
    output_path: Path,
    title: str | None = None,
) -> None:
    """Render a labelled grid of cell images and save as PNG.

    Args:
        rows: Experiment / row names (left labels).
        cols: Prompt / column IDs (top labels).
        input_dir: Root of the sampling output tree.
        output_path: Destination path for the grid PNG.
        title: Optional title rendered above the grid.
    """
    n_rows = len(rows)
    n_cols = len(cols)

    # --- Dynamic margin computation ---
    font_label = _load_font(14)

    # Format all row labels once (used for measurement and drawing)
    row_labels = [_format_row_label(r) for r in rows]

    # Measure widest row label to compute LEFT_MARGIN
    temp_img = Image.new("RGB", (1, 1), BG_COLOR)
    temp_draw = ImageDraw.Draw(temp_img)
    max_label_w = 0
    for label in row_labels:
        bbox = temp_draw.textbbox((0, 0), label, font=font_label)
        label_w = bbox[2] - bbox[0]
        if label_w > max_label_w:
            max_label_w = label_w
    LEFT_MARGIN = max_label_w + 10

    # Measure column label height to compute TOP_MARGIN
    sample_col = cols[0] if cols else "X"
    col_bbox = temp_draw.textbbox((0, 0), sample_col, font=font_label)
    col_font_height = col_bbox[3] - col_bbox[1]
    TOP_MARGIN = col_font_height + 8

    canvas_w = LEFT_MARGIN + n_cols * CELL_SIZE + (n_cols - 1) * CELL_PADDING
    canvas_h = TOP_MARGIN + n_rows * CELL_SIZE + (n_rows - 1) * CELL_PADDING

    canvas = Image.new("RGB", (canvas_w, canvas_h), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    # ---- Column labels (centred vertically within TOP_MARGIN) ----
    for ci, col_id in enumerate(cols):
        col_label = _format_experiment_label(col_id)
        x = LEFT_MARGIN + ci * (CELL_SIZE + CELL_PADDING)
        bbox = draw.textbbox((0, 0), col_label, font=font_label)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text(
            (x + (CELL_SIZE - text_w) // 2, (TOP_MARGIN - text_h) // 2),
            col_label,
            fill=LABEL_COLOR,
            font=font_label,
        )

    # ---- Rows ----
    for ri, row_name in enumerate(rows):
        y = TOP_MARGIN + ri * (CELL_SIZE + CELL_PADDING)

        # Row label (right-aligned, vertically centred, near left edge)
        display_label = row_labels[ri]
        bbox = draw.textbbox((0, 0), display_label, font=font_label)
        label_w = bbox[2] - bbox[0]
        label_h = bbox[3] - bbox[1]
        draw.text(
            (LEFT_MARGIN - label_w - 6, y + (CELL_SIZE - label_h) // 2),
            display_label,
            fill=LABEL_COLOR,
            font=font_label,
        )

        for ci, col_id in enumerate(cols):
            x = LEFT_MARGIN + ci * (CELL_SIZE + CELL_PADDING)

            if row_name == "base_model":
                cell_img = _load_base_model_cell(input_dir, col_id)
            else:
                cell_img = _load_cell_image(input_dir, row_name, col_id)

            canvas.paste(cell_img, (x, y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG")
    print(f"   ✅ Saved  {output_path.name}  ({canvas_w}×{canvas_h})")


# ---------------------------------------------------------------------------
# Grid 1: Full 6×5 matrix
# ---------------------------------------------------------------------------

def generate_full_matrix(input_dir: Path, output_dir: Path) -> None:
    """Generate the full 7-experiment (incl. base) × 6-prompt comparison matrix."""
    print("\n📐 Grid 1: Full Matrix (7 experiments (incl. base) × 6 prompts)")
    _build_grid(
        rows=FULL_MATRIX_ROWS,
        cols=FULL_MATRIX_COLS,
        input_dir=input_dir,
        output_path=output_dir / "full_matrix_7x6.png",
        title=None,  # Title will be in LaTeX caption
    )


# ---------------------------------------------------------------------------
# Grid 2: Report figure 3×3
# ---------------------------------------------------------------------------

def generate_report_figure(input_dir: Path, output_dir: Path) -> None:
    """Generate the curated 3×3 report figure."""
    print("\n📐 Grid 2: Report Figure (3 experiments × 3 prompts)")
    _build_grid(
        rows=REPORT_ROWS,
        cols=REPORT_COLS,
        input_dir=input_dir,
        output_path=output_dir / "report_figure_3x3.png",
        title=None,  # Title will be in LaTeX caption
    )


# ---------------------------------------------------------------------------
# Grid 2b: IEEE figure 4×2
# ---------------------------------------------------------------------------

def generate_ieee_figure(input_dir: Path, output_dir: Path) -> None:
    """Generate the IEEE report figure: 4×2 matrix showing caption detail trade-off."""
    print("\n📐 Grid 2b: IEEE Figure (2 prompts × 4 experiments)")
    _build_grid(
        rows=IEEE_FIGURE_ROWS,
        cols=IEEE_FIGURE_COLS,
        input_dir=input_dir,
        output_path=output_dir / "report_figure.png",
        title=None,  # Title will be in LaTeX caption
    )


# ---------------------------------------------------------------------------
# Grid 2c: Model card figure 6×4
# ---------------------------------------------------------------------------

def generate_model_card_figure(input_dir: Path, output_dir: Path) -> None:
    """Generate the model card figure: 7×4 comprehensive comparison (incl. base model)."""
    print("\n📐 Grid 2c: Model Card Figure (7 rows (incl. base) × 4 prompts)")
    _build_grid(
        rows=MODEL_CARD_ROWS,
        cols=MODEL_CARD_COLS,
        input_dir=input_dir,
        output_path=output_dir / "model_card_figure_7x4.png",
        title=None,  # Title will be in LaTeX caption
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    input_dir = _resolve_input_dir(args.input)
    output_dir = _resolve_input_dir(args.output)

    print("🖼️  Comparison Grid Generator")
    print(f"   Input  : {input_dir}")
    print(f"   Output : {output_dir}")

    if not input_dir.is_dir():
        print(f"\n❌ Input directory not found: {input_dir}")
        print("   Run sample_checkpoints.py first to generate comparison images.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        generate_ieee_figure(input_dir, output_dir)
        generate_model_card_figure(input_dir, output_dir)

        print(f"\n🏁 All grids generated in: {output_dir.resolve()}")
        for p in sorted(output_dir.iterdir()):
            if p.suffix == ".png":
                print(f"   • {p.name}")
    except Exception as exc:
        print(f"\n❌ Error generating grids: {exc}")
        raise


if __name__ == "__main__":
    main()
