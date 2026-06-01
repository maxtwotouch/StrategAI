# Static Asset Catalog

> 📘 This document is a supplementary deep-dive for the [Medieval Pixel Art Image Service](../../README.md). For the full project report, see [`project-report.md`](../project-report.md).

---

## 1. Overview

### 1.1 Purpose

The `StaticCatalog` class in `src/static_catalog.py` provides a filesystem-based registry of pre-made PNG assets. It powers:
- **Static generation mode**: When `generation.modes.{family} = "static"`, assets are served from this catalog
- **`GET /catalog` endpoint**: Clients can discover available static assets and valid enum values
- **Graceful degradation**: When ComfyUI is unavailable, the static engines fall back to this catalog before falling further to placeholder mode

### 1.2 Initialisation

The catalog is a **module-level singleton**, scanned once at startup:

```python
# src/static_catalog.py
catalog = StaticCatalog()
```

At initialisation, it walks `static_tiles/` and builds an in-memory lookup structure. No restart is needed to pick up new files — the scan happens at process startup. To add new static assets, place PNGs in the correct directories and restart the service.

### 1.3 In-Memory Structure

```python
class StaticCatalog:
    _catalog: dict[str, dict[str | None, list[str]]]
    # {
    #   "structure": {
    #       "fortification": ["/path/to/static_tiles/structure/fortification/castle.png", ...],
    #       "production": [...],
    #       None: [all PNGs across all subtypes]
    #   },
    #   "background_tile": {
    #       "water": ["/path/to/static_tiles/background_tile/water.png"],
    #       "grass": ["/path/to/static_tiles/background_tile/grass_1.png",
    #                 "/path/to/static_tiles/background_tile/grass_2.png"],
    #       ...
    #   },
    #   "nature_object": {None: ["tree.png", "boulder.png", ...]},
    #   "character_sprite": {None: ["knight.png", "mage.png", ...]},
    # }

    _unit_catalog: dict[str, list[str]]
    # {
    #   "archer": ["/path/to/static_tiles/unit/archer.png"],
    #   "scout": [...],
    #   "settler": [...],
    #   "warrior": [...],
    # }
```

---

## 2. Directory Structure

```
static_tiles/
├── background_tile/          # Flat folder — filename = tile type
│   ├── water.png
│   ├── grass_1.png           # Variant 1
│   ├── grass_2.png           # Variant 2 (random selection)
│   ├── sand.png
│   ├── stone.png
│   └── dirt.png
│
├── structure/                # Subfolder per category
│   ├── fortification/
│   │   ├── castle.png
│   │   └── watchtower.png
│   ├── production/
│   │   └── ...
│   ├── housing/
│   │   └── ...
│   └── sacred/
│       └── ...
│
├── nature_object/            # Flat folder — any PNG is valid
│   ├── tree.png
│   ├── boulder.png
│   └── ...
│
├── character_sprite/         # Flat folder — any PNG is valid
│   ├── knight.png
│   └── ...
│
└── unit/                     # Flat folder — filename stem = unit type
    ├── archer.png
    ├── scout.png
    ├── settler.png
    └── warrior.png
```

### 2.1 Scanning Rules

| Directory | Scanning Method | Key Resolution |
|-----------|----------------|----------------|
| `background_tile/` | `_scan_flat_named()` | Filename stem (minus `_N` suffix) → tile type key |
| `structure/` | `_scan_structure()` | Subfolder name → subtype key (only `fortification`, `production`, `housing`, `sacred`) |
| `nature_object/` | `_scan_flat_unnamed()` | All PNGs → single `None` key (random pick) |
| `character_sprite/` | `_scan_flat_unnamed()` | All PNGs → single `None` key (random pick) |
| `unit/` | `_scan_unit()` | Filename stem → unit type key |

### 2.2 Variant Suffix Convention

For `background_tile/`, multiple PNGs of the same type can be provided with numeric suffixes:

```
grass_1.png   → key "grass"
grass_2.png   → key "grass"
grass_3.png   → key "grass"
```

On resolution, `resolve_tile("grass")` randomly picks one of the three variants, providing visual variety even in static mode.

---

## 3. Resolution Methods

### 3.1 `resolve_tile(tile_type)` → Background Tiles

```python
def resolve_tile(self, tile_type: str) -> str | None:
    """Return a random file path for a background tile type, or None."""
    entries = self._catalog.get("background_tile", {}).get(tile_type, [])
    return random.choice(entries) if entries else None
```

Used by `StaticBackgroundTileEngine` to serve pre-made ground textures.

### 3.2 `resolve_unit(unit_type)` → Unit Sprites

```python
def resolve_unit(self, unit_type: str) -> str | None:
    """Return a file path for a unit type, or None."""
    entries = self._unit_catalog.get(unit_type, [])
    return random.choice(entries) if entries else None
```

Used by `StaticUnitEngine` to serve pre-made character sprites.

### 3.3 `resolve_random(family, subtype=None)` → General

```python
def resolve_random(self, family: str, subtype: str | None = None) -> str | None:
    """Return a random PNG path for a family + optional subtype."""
    catalog = self._catalog.get(family, {})

    if family == "structure" and subtype is not None:
        entries = catalog.get(subtype, [])  # Specific subtype folder
    else:
        entries = catalog.get(None, [])     # Flat list

    return random.choice(entries) if entries else None
```

Used by `StaticTileEngine` for structures (with subtype filtering) and objects (flat random pick).

### 3.4 Introspection Methods

| Method | Returns | Used By |
|--------|---------|---------|
| `list_tile_types()` | `list[str]` — available background tile types | `GET /catalog` |
| `list_structure_subtypes()` | `list[str]` — structure subtypes with PNGs | `GET /catalog` |
| `list_unit_types()` | `list[str]` — unit types with PNGs | `GET /catalog` |
| `has_any(family)` | `bool` — whether any PNGs exist for a family | Mode dispatch fallback |
| `has_unit_type(unit_type)` | `bool` — whether a specific unit type has PNGs | Unit resolution fallback |

---

## 4. Adding New Static Assets

### 4.1 File Naming Conventions

| Asset Family | Naming Rule | Example |
|-------------|-------------|---------|
| Background tile | `{type}.png` or `{type}_{N}.png` | `water.png`, `grass_1.png`, `grass_2.png` |
| Structure | `{any_name}.png` in `{subtype}/` subfolder | `structure/fortification/castle.png` |
| Nature object | `{any_name}.png` | `nature_object/tree.png` |
| Character sprite | `{any_name}.png` | `character_sprite/knight.png` |
| Unit | `{unit_type}.png` | `unit/archer.png` |

### 4.2 Requirements

- **Format**: PNG only (`.png` extension, case-insensitive)
- **Colour space**: RGBA recommended for transparency support
- **Size**: Should match game asset size (256×256 for tiles, 128×128 effective)
- **Placement**: Must be in the correct directory for automatic discovery
- **No restart needed**: Files are scanned at startup only; restart the service to pick up new assets

### 4.3 Step-by-Step

```bash
# 1. Place PNGs in the correct directory
cp my_custom_castle.png static_tiles/structure/fortification/

# 2. Restart the service
# The catalog scans at startup — new files will be available immediately
```

### 4.4 Valid Structure Subtypes

Only these four subfolder names are recognised in `static_tiles/structure/`:

| Subtype | Description |
|---------|-------------|
| `fortification` | Defensive structures — castles, walls, watchtowers |
| `production` | Industrial buildings — workshops, mills, forges |
| `housing` | Residential buildings — houses, cottages |
| `sacred` | Religious buildings — temples, churches, shrines |

Other subfolder names in `static_tiles/structure/` are silently ignored.

---

## 5. Fallback Chain

The static engine follows a specific fallback chain:

```
1. StaticCatalog.resolve_*()  →  Return static PNG
2. If no match found           →  Generate placeholder (PIL rectangle + label)
```

Placeholder generation is always available — it has zero filesystem dependencies beyond Pillow. This means the static engine **never fails** — it always returns an image, even if no static PNGs are installed.

---

## 6. Powers `GET /catalog`

The `GET /catalog` endpoint aggregates information from the static catalog and the enum definitions:

```json
{
  "background_tile": {
    "static": ["water", "grass", "sand", "stone", "dirt"],
    "enum_values": ["water", "grass", "sand", "stone", "dirt"]
  },
  "structure": {
    "static": {
      "fortification": 2,
      "production": 1,
      "housing": 3,
      "sacred": 1
    },
    "enum_values": {
      "category": ["fortification", "production", "housing", "sacred"],
      "style": ["nordic_wooden", "anglo_saxon_stone", "norman_romanesque", ...],
      "condition": ["pristine", "weathered", "ruined", "under_construction", "fortified"],
      "scale": ["small", "medium", "large"]
    }
  },
  "nature_object": {
    "static": 5,
    "enum_values": {
      "category": ["vegetation", "geological", "rural_props", "urban_props", "debris"],
      "biome": ["temperate_forest", "taiga", "desert", ...],
      "season": ["spring", "summer", "autumn", "winter"]
    }
  },
  "unit": {
    "static": ["archer", "scout", "settler", "warrior"],
    "enum_values": ["archer", "scout", "settler", "warrior"]
  },
  "terrain": {
    "static": [],
    "enum_values": {
      "category": ["hill", "slope", "cliff", "plateau", "valley"],
      "scale": ["low", "medium", "high"],
      "material": ["grassy", "rocky", "sandy", "snowy", "barren"]
    }
  }
}
```

The `"static"` field shows what's actually available on disk; the `"enum_values"` field shows what the API accepts. Clients can use this to discover what they can request without getting 422 validation errors.
