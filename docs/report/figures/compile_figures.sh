#!/usr/bin/env bash
# =============================================================================
# compile_figures.sh — Render Mermaid diagrams to individual PDFs
#
# Usage:
#   ./compile_figures.sh          # compile all 5 mermaid figures
#   ./compile_figures.sh 1 4      # compile only fig1 and fig4
#   ./compile_figures.sh --clean  # remove output directory
#
# Security: File whitelist prevents path traversal.
# Puppeteer: Uses .puppeteerrc.json for --no-sandbox (required in containers).
#
# Output:  docs/report/figures/pdf/fig1_system_architecture.pdf ... fig6.pdf
#
# IEEE Column Constraints:
#   Single-column max: 3.5" wide, ~9" tall (with caption)
#   Double-column max: 7.16" wide (figure* environment)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/pdf"
PUPPETEER_CONFIG="$SCRIPT_DIR/.puppeteerrc.json"

# --- File whitelist (only mermaid-compilable figures) ---
declare -A ALLOWED=(
  [1]="fig1_system_architecture.md"
  [2]="fig2_intent_abstraction.md"
  [3]="fig3_prompt_architecture.md"
  [4]="fig4_leader_pipeline.md"
  [6]="fig6_asset_fallback.md"
)

# --- Per-figure rendering config ---
# -w : viewport width (CSS px): 1400 for double-col, 800 for single-col
# -H : viewport height (CSS px): 900 for most, 600 for short figures
# -s : scale factor (devicePixelRatio): 2 for all
declare -A FIG_WIDTH=(
  [1]=1400  [2]=800  [3]=800  [4]=1400  [6]=800
)
declare -A FIG_HEIGHT=(
  [1]=900   [2]=900   [3]=900  [4]=900   [6]=550
)
declare -A FIG_SCALE=(
  [1]=2     [2]=2     [3]=2    [4]=2     [6]=2
)
declare -A FIG_COL=(
  [1]="double"  [2]="single"  [3]="single"  [4]="double"  [6]="single"
)

# --- Non-mermaid figures (documented for reference, not compiled) ---
# Fig 5: fig5_lora_matrix.md — PNG image, include directly in LaTeX
# Fig 7: fig7_ai_behavior.md — LaTeX table, include directly in LaTeX

clean_output() { rm -rf "$OUTPUT_DIR"; echo "Removed $OUTPUT_DIR"; }

compile_one() {
  local num="$1"
  infile="${ALLOWED[$num]}"
  basename="${infile%.md}"
  local outfile="$OUTPUT_DIR/${basename}.pdf"
  local w="${FIG_WIDTH[$num]}"
  local H="${FIG_HEIGHT[$num]}"
  local s="${FIG_SCALE[$num]}"
  col="${FIG_COL[$num]}"

  [[ -f "$SCRIPT_DIR/$infile" ]] || { echo "FAIL fig${num}: '$infile' not found" >&2; return 1; }

  printf "  fig%-2d %-40s → %-40s [%6s col, %4s×%-4s scale %s] " \
    "$num" "$infile" "${basename}.pdf" "$col" "$w" "$H" "$s"
  if mmdc -i "$SCRIPT_DIR/$infile" -o "$outfile" -b white -w "$w" -H "$H" -s "$s" --pdfFit -p "$PUPPETEER_CONFIG" 2>/dev/null; then
    echo "✓"
  else
    echo "✗ FAILED"
    return 1
  fi
}

# --- Args ---
if [[ $# -eq 0 ]]; then
  FIGS=(1 2 3 4 6)
else
  case "$1" in
    --clean|-c) clean_output; exit 0 ;;
    *) FIGS=("$@") ;;
  esac
fi

for f in "${FIGS[@]}"; do
  [[ -n "${ALLOWED[$f]:-}" ]] || { echo "Invalid figure: $f (allowed: ${!ALLOWED[*]})" >&2; exit 1; }
done

mkdir -p "$OUTPUT_DIR"

echo "=== Compiling ${#FIGS[@]} figure(s) → $OUTPUT_DIR/ ==="
echo ""

FAILED=0
for f in "${FIGS[@]}"; do compile_one "$f" || ((FAILED++)); done

echo ""
echo "=== Summary ==="
echo ""

# Print column placement summary
printf "  %-6s %-45s %-8s %s\n" "Fig" "File" "Column" "LaTeX"
printf "  %-6s %-45s %-8s %s\n" "---" "----" "------" "-----"
for f in "${FIGS[@]}"; do
  infile="${ALLOWED[$f]}"
  basename="${infile%.md}"
  col="${FIG_COL[$f]}"
  if [[ "$col" == "double" ]]; then
    cmd='\includegraphics[width=\textwidth]{figures/'"${basename}"'}  % figure*'
  else
    cmd='\includegraphics[width=\columnwidth]{figures/'"${basename}"'}'
  fi
  printf "  %-6s %-45s %-8s %s\n" "$f" "${basename}.pdf" "$col" "$cmd"
done
echo ""

if [[ $FAILED -eq 0 ]]; then
  # Rename mmdc output from *-1.pdf to *.pdf
for f in "$OUTPUT_DIR"/*-1.pdf; do
  [[ -f "$f" ]] && mv "$f" "${f%-1.pdf}.pdf" 2>/dev/null
done

echo "Done: ${#FIGS[@]} figure(s) → $OUTPUT_DIR/"
  ls -lh "$OUTPUT_DIR"/*.pdf 2>/dev/null || true
else
  echo "$FAILED figure(s) failed" >&2
  exit 1
fi
