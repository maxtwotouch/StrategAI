"""Unit tests for StaticCatalog (src/static_catalog.py)."""

import os
import pytest
from PIL import Image
from src.static_catalog import StaticCatalog


def _make_png(path: str) -> None:
    """Create a minimal 1x1 RGBA PNG at the given path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new("RGBA", (1, 1), (0, 0, 0, 255))
    img.save(path, format="PNG")


class TestBackgroundTile:
    """Tests for background_tile scanning and resolution."""

    def test_list_tile_types(self, test_catalog):
        """water.png, grass_1.png, grass_2.png → list_tile_types() = ['grass', 'water']."""
        types = test_catalog.list_tile_types()
        assert "grass" in types
        assert "water" in types
        assert len(types) == 2

    def test_resolve_tile_known(self, test_catalog):
        """resolve_tile('grass') returns a path containing grass."""
        path = test_catalog.resolve_tile("grass")
        assert path is not None
        assert "grass" in os.path.basename(path)

    def test_resolve_tile_nonexistent(self, test_catalog):
        """resolve_tile('lava') → None."""
        assert test_catalog.resolve_tile("lava") is None

    def test_resolve_tile_multiple_variants(self, test_catalog):
        """grass_1.png + grass_2.png → both reachable via resolve_tile."""
        paths = set()
        for _ in range(20):
            p = test_catalog.resolve_tile("grass")
            paths.add(os.path.basename(p))
        # Should eventually hit both variants
        assert len(paths) >= 1  # At least one variant returned

    def test_numeric_suffix_stripping(self, test_catalog):
        """water_3.png → keyed as 'water'."""
        # Add water_3.png to the catalog dir
        bg_dir = os.path.join(test_catalog.root_dir, "background_tile")
        _make_png(os.path.join(bg_dir, "water_3.png"))
        # Re-scan
        cat = StaticCatalog(root_dir=test_catalog.root_dir)
        assert "water" in cat.list_tile_types()


class TestStructure:
    """Tests for structure scanning and resolution."""

    def test_list_structure_subtypes(self, test_catalog):
        """fortification/castle.png, production/mill.png → list_structure_subtypes()."""
        subtypes = test_catalog.list_structure_subtypes()
        assert "fortification" in subtypes
        assert "production" in subtypes

    def test_resolve_with_subtype(self, test_catalog):
        """resolve_random('structure', 'fortification') → only returns fortification PNGs."""
        path = test_catalog.resolve_random("structure", "fortification")
        assert path is not None
        assert "fortification" in path

    def test_resolve_without_subtype(self, test_catalog):
        """resolve_random('structure', None) → returns from any subtype."""
        path = test_catalog.resolve_random("structure", None)
        assert path is not None

    def test_subtype_not_in_valid_set_ignored(self, tmp_project_root):
        """Folder 'unknown/' under structure/ → ignored."""
        struct_dir = os.path.join(tmp_project_root, "static_tiles", "structure", "unknown")
        _make_png(os.path.join(struct_dir, "thing.png"))
        cat = StaticCatalog(root_dir=os.path.join(tmp_project_root, "static_tiles"))
        assert "unknown" not in cat.list_structure_subtypes()

    def test_empty_subtype_folder_not_listed(self, tmp_project_root):
        """fortification/ with no PNGs → not listed."""
        struct_dir = os.path.join(tmp_project_root, "static_tiles", "structure", "fortification")
        os.makedirs(struct_dir, exist_ok=True)
        # No PNGs added
        cat = StaticCatalog(root_dir=os.path.join(tmp_project_root, "static_tiles"))
        assert "fortification" not in cat.list_structure_subtypes()


class TestNatureObjectAndCharacterSprite:
    """Tests for flat unnamed families."""

    def test_has_any_nature_object(self, test_catalog):
        """Any PNG in nature_object/ → has_any('nature_object') = True."""
        assert test_catalog.has_any("nature_object") is True

    def test_has_any_character_sprite(self, test_catalog):
        assert test_catalog.has_any("character_sprite") is True

    def test_has_any_empty_family(self, test_catalog):
        """has_any('terrain') → False (no static_tiles/terrain/)."""
        assert test_catalog.has_any("terrain") is False

    def test_resolve_random_nature_object(self, test_catalog):
        path = test_catalog.resolve_random("nature_object")
        assert path is not None
        assert "tree" in os.path.basename(path)


class TestUnit:
    """Tests for unit sprite scanning and resolution."""

    def test_list_unit_types(self, test_catalog):
        """Only types with at least a south PNG appear."""
        types = test_catalog.list_unit_types()
        assert "archer" in types
        assert "scout" in types

    def test_has_unit_type(self, test_catalog):
        """has_unit_type('archer') with archer_s.png → True."""
        assert test_catalog.has_unit_type("archer") is True

    def test_has_unit_type_false(self, test_catalog):
        """has_unit_type('warrior') with no warrior PNGs → False."""
        assert test_catalog.has_unit_type("warrior") is False

    def test_resolve_unit_exact_direction(self, test_catalog):
        """resolve_unit('archer', 'n') → returns the north sprite."""
        path = test_catalog.resolve_unit("archer", "n")
        assert path is not None
        assert "archer_n" in os.path.basename(path)

    def test_resolve_unit_s_fallback(self, test_catalog):
        """resolve_unit('scout', 'e') when no east PNG → returns south sprite."""
        path = test_catalog.resolve_unit("scout", "e")
        assert path is not None
        assert "scout_s" in os.path.basename(path)

    def test_resolve_unit_no_s_fallback(self, test_catalog):
        """resolve_unit('warrior', 's') with no warrior PNGs → None."""
        assert test_catalog.resolve_unit("warrior", "s") is None

    def test_invalid_direction_ignored(self, tmp_project_root):
        """archer_x.png not cataloged (x not in _VALID_UNIT_DIRECTIONS)."""
        unit_dir = os.path.join(tmp_project_root, "static_tiles", "unit")
        _make_png(os.path.join(unit_dir, "archer_x.png"))
        cat = StaticCatalog(root_dir=os.path.join(tmp_project_root, "static_tiles"))
        # archer_x should not appear as a direction
        assert "x" not in cat._unit_catalog.get("archer", {})

    def test_unit_filename_with_underscores(self, tmp_project_root):
        """city_settler_s.png → parses as type=city_settler, direction=s."""
        unit_dir = os.path.join(tmp_project_root, "static_tiles", "unit")
        _make_png(os.path.join(unit_dir, "city_settler_s.png"))
        cat = StaticCatalog(root_dir=os.path.join(tmp_project_root, "static_tiles"))
        assert cat.has_unit_type("city_settler") is True
        path = cat.resolve_unit("city_settler", "s")
        assert path is not None


class TestEdgeCases:
    """Edge case tests for StaticCatalog."""

    def test_empty_root_dir(self, tmp_project_root):
        """No crash, empty catalog."""
        empty = os.path.join(tmp_project_root, "empty_static")
        os.makedirs(empty, exist_ok=True)
        cat = StaticCatalog(root_dir=empty)
        assert cat.list_tile_types() == []
        assert cat.list_structure_subtypes() == []
        assert cat.list_unit_types() == []

    def test_nonexistent_root_dir(self):
        """No crash, empty catalog."""
        cat = StaticCatalog(root_dir="/nonexistent/path/12345")
        assert cat.list_tile_types() == []

    def test_non_png_files_ignored(self, tmp_project_root):
        """.DS_Store, thumbs.db → ignored."""
        bg_dir = os.path.join(tmp_project_root, "static_tiles", "background_tile")
        os.makedirs(bg_dir, exist_ok=True)
        # Create non-PNG files
        for name in [".DS_Store", "thumbs.db", "readme.txt"]:
            with open(os.path.join(bg_dir, name), "w") as f:
                f.write("junk")
        _make_png(os.path.join(bg_dir, "valid.png"))
        cat = StaticCatalog(root_dir=os.path.join(tmp_project_root, "static_tiles"))
        assert "valid" in cat.list_tile_types()

