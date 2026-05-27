"""Static asset catalog -- scans static_tiles/ and resolves PNGs by family and subtype."""

import os
import random
from collections import defaultdict

from .config import settings, BASE_DIR

_VALID_STRUCTURE_SUBTYPES = {"fortification", "production", "civilian", "religious"}
_VALID_UNIT_DIRECTIONS = {"s", "n", "e", "w"}


class StaticCatalog:
    """Scans static_tiles/ on init and builds an in-memory lookup.

    Families with subtypes (structure):
        _catalog["structure"]["fortification"] = [full_path_1, full_path_2, ...]
        _catalog["structure"][None]           = [all PNGs across all subtypes]

    Families without subtypes (background_tile, nature_object, character_sprite):
        _catalog["background_tile"]["water"] = [full_path_water]
        _catalog["background_tile"]["grass"] = [full_path_grass]
        _catalog["nature_object"][None]      = [tree.png, boulder.png]

    Unit family (directional sprites — flat naming archer_s.png, archer_n.png):
        _unit_catalog["archer"]["s"] = [full_path_south]
        _unit_catalog["archer"]["n"] = [full_path_north]  (may be absent → falls back to "s")
    """

    def __init__(self, root_dir: str | None = None):
        self.root_dir = root_dir or os.path.join(BASE_DIR, settings.paths.static_tiles_dir)
        self._catalog: dict[str, dict[str | None, list[str]]] = defaultdict(dict)
        self._unit_catalog: dict[str, dict[str, list[str]]] = defaultdict(dict)
        self._scan()

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def resolve_tile(self, tile_type: str) -> str | None:
        """Return a random file path for a background tile type, or None.

        When multiple PNGs exist for the same tile type (e.g. grass_1.png,
        grass_2.png) a random one is picked so clients get variety.
        """
        entries = self._catalog.get("background_tile", {}).get(tile_type, [])
        return random.choice(entries) if entries else None

    def list_tile_types(self) -> list[str]:
        """Return available background tile types that have at least one PNG."""
        family = self._catalog.get("background_tile", {})
        return sorted(k for k, v in family.items() if k is not None and v)

    def list_structure_subtypes(self) -> list[str]:
        """Return structure subtypes that have at least one PNG."""
        family = self._catalog.get("structure", {})
        return sorted(
            k for k, v in family.items()
            if k is not None and isinstance(k, str) and k in _VALID_STRUCTURE_SUBTYPES and v
        )

    def resolve_random(self, family: str, subtype: str | None = None) -> str | None:
        """Return a random PNG path for a family + optional subtype, or None.

        For structure: if subtype is given, picks from that subtype folder.
                      If subtype is None, picks from all subtypes merged.
        For other families: ignores subtype, picks from the flat list.
        """
        catalog = self._catalog.get(family, {})

        if family == "structure" and subtype is not None:
            entries = catalog.get(subtype, [])
        else:
            entries = catalog.get(None, [])

        if not entries:
            return None
        return random.choice(entries)

    def has_any(self, family: str) -> bool:
        """Return True if the family has any static PNGs at all."""
        catalog = self._catalog.get(family, {})
        return any(v for v in catalog.values() if v)

    def resolve_unit(self, unit_type: str, direction: str) -> str | None:
        """Return a file path for a unit type + direction, or None.

        Falls back to the south-facing (front) sprite if the requested
        direction doesn't have a dedicated PNG.
        """
        entries = self._unit_catalog.get(unit_type, {}).get(direction, [])
        if entries:
            return random.choice(entries)
        # Fall back to south-facing
        south_entries = self._unit_catalog.get(unit_type, {}).get("s", [])
        return random.choice(south_entries) if south_entries else None

    def list_unit_types(self) -> list[str]:
        """Return unit types that have at least one south-facing PNG."""
        return sorted(k for k, v in self._unit_catalog.items() if v.get("s"))

    def has_unit_type(self, unit_type: str) -> bool:
        """Return True if this unit type has at least a south-facing PNG."""
        return bool(self._unit_catalog.get(unit_type, {}).get("s"))

    # ------------------------------------------------------------------
    #  Private
    # ------------------------------------------------------------------

    def _scan(self) -> None:
        """Walk static_tiles/ and populate the catalog."""
        if not os.path.isdir(self.root_dir):
            return

        for entry in sorted(os.listdir(self.root_dir)):
            family_path = os.path.join(self.root_dir, entry)
            if not os.path.isdir(family_path):
                continue

            family = entry  # folder name = asset family

            if family == "structure":
                self._scan_structure(family_path)
            elif family == "background_tile":
                self._scan_flat_named(family_path, family)
            elif family == "unit":
                self._scan_unit(family_path)
            elif family in ("nature_object", "character_sprite"):
                self._scan_flat_unnamed(family_path, family)

    def _scan_structure(self, path: str) -> None:
        """Structure has subfolders (fortification/, production/, etc.)."""
        all_pngs: list[str] = []
        for sub in sorted(os.listdir(path)):
            sub_path = os.path.join(path, sub)
            if not os.path.isdir(sub_path):
                continue
            pngs = self._list_pngs(sub_path)
            if sub in _VALID_STRUCTURE_SUBTYPES:
                self._catalog["structure"][sub] = pngs
            all_pngs.extend(pngs)
        if all_pngs:
            self._catalog["structure"][None] = all_pngs

    def _scan_flat_named(self, path: str, family: str) -> None:
        """Flat folder where filename = type key (background_tile).

        Supports multiple variants per tile type via numeric suffixes:
        ``grass_1.png``, ``grass_2.png`` → both stored under key ``"grass"``.
        Plain names like ``water.png`` work as before.
        """
        for fname in sorted(os.listdir(path)):
            if not fname.lower().endswith(".png"):
                continue
            base = os.path.splitext(fname)[0]  # "grass_1" or "water"
            # Strip trailing _N suffix to group variants under one key
            key = base.rsplit("_", 1)[0] if "_" in base else base
            full = os.path.join(path, fname)
            self._catalog[family].setdefault(key, []).append(full)

    def _scan_flat_unnamed(self, path: str, family: str) -> None:
        """Flat folder where any PNG is a valid random pick."""
        pngs = self._list_pngs(path)
        if pngs:
            self._catalog[family][None] = pngs

    def _scan_unit(self, path: str) -> None:
        """Flat folder: ``archer_s.png``, ``archer_n.png``, ``scout_s.png``, etc.

        Parses ``{unit_type}_{direction}.png`` and stores under
        ``_unit_catalog[unit_type][direction]``.
        """
        for fname in sorted(os.listdir(path)):
            if not fname.lower().endswith(".png"):
                continue
            base = os.path.splitext(fname)[0]  # e.g. "archer_s"
            parts = base.rsplit("_", 1)
            if len(parts) != 2:
                continue
            unit_type, direction = parts[0], parts[1]
            if direction not in _VALID_UNIT_DIRECTIONS:
                continue
            full = os.path.join(path, fname)
            self._unit_catalog.setdefault(unit_type, {}).setdefault(direction, []).append(full)

    @staticmethod
    def _list_pngs(dirpath: str) -> list[str]:
        return sorted(
            os.path.join(dirpath, f)
            for f in os.listdir(dirpath)
            if f.lower().endswith(".png")
        )


# Singleton
catalog = StaticCatalog()
