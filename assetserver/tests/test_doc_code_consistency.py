"""Doc-code consistency tests.

Verifies that the client-facing prompt guides list all enum values
that exist in the source code.  Prevents silent doc staleness when
new enum values are added to code but not to docs.
"""

from pathlib import Path

import pytest

DOCS_DIR = Path(__file__).parent.parent / "docs"


# ===========================================================================
#  Leader prompt guide
# ===========================================================================


class TestLeaderDocEnums:
    """Verify leader-prompt-guide.md lists all enum values from leader_models.py."""

    @pytest.fixture(scope="class")
    def doc_text(self) -> str:
        path = DOCS_DIR / "guides" / "leader-prompt-guide.md"
        assert path.exists(), f"Missing: {path}"
        return path.read_text()

    def test_archetype_all_in_doc(self, doc_text):
        from src.leader.models import Archetype
        for member in Archetype:
            assert member.value in doc_text, f"ARCHETYPE: '{member.value}' missing from leader-prompt-guide.md"

    def test_culture_all_in_doc(self, doc_text):
        from src.leader.models import Culture
        for member in Culture:
            assert member.value in doc_text, f"CULTURE: '{member.value}' missing from leader-prompt-guide.md"

    def test_time_of_day_all_in_doc(self, doc_text):
        from src.leader.models import TimeOfDay
        for member in TimeOfDay:
            assert member.value in doc_text, f"TIME_OF_DAY: '{member.value}' missing from leader-prompt-guide.md"

    def test_mood_all_in_doc(self, doc_text):
        from src.leader.models import Mood
        for member in Mood:
            assert member.value in doc_text, f"MOOD: '{member.value}' missing from leader-prompt-guide.md"

    def test_action_category_all_in_doc(self, doc_text):
        from src.leader.models import ActionCategory
        for member in ActionCategory:
            assert member.value in doc_text, f"ACTION_CATEGORY: '{member.value}' missing from leader-prompt-guide.md"


# ===========================================================================
#  Tile prompt guide
# ===========================================================================


class TestTileDocEnums:
    """Verify tile-prompt-guide.md lists all enum values from tile_models.py."""

    @pytest.fixture(scope="class")
    def doc_text(self) -> str:
        path = DOCS_DIR / "guides" / "tile-prompt-guide.md"
        assert path.exists(), f"Missing: {path}"
        return path.read_text()

    def test_structure_category_all_in_doc(self, doc_text):
        from src.tile.models import StructureCategory
        for member in StructureCategory:
            assert member.value in doc_text, f"StructureCategory: '{member.value}' missing from tile-prompt-guide.md"

    def test_structure_style_all_in_doc(self, doc_text):
        from src.tile.models import StructureStyle
        for member in StructureStyle:
            assert member.value in doc_text, f"StructureStyle: '{member.value}' missing from tile-prompt-guide.md"

    def test_structure_condition_all_in_doc(self, doc_text):
        from src.tile.models import StructureCondition
        for member in StructureCondition:
            assert member.value in doc_text, f"StructureCondition: '{member.value}' missing from tile-prompt-guide.md"

    def test_structure_scale_all_in_doc(self, doc_text):
        from src.tile.models import StructureScale
        for member in StructureScale:
            assert member.value in doc_text, f"StructureScale: '{member.value}' missing from tile-prompt-guide.md"

    def test_object_category_all_in_doc(self, doc_text):
        from src.tile.models import ObjectCategory
        for member in ObjectCategory:
            assert member.value in doc_text, f"ObjectCategory: '{member.value}' missing from tile-prompt-guide.md"

    def test_biome_all_in_doc(self, doc_text):
        from src.tile.models import Biome
        for member in Biome:
            assert member.value in doc_text, f"Biome: '{member.value}' missing from tile-prompt-guide.md"

    def test_season_all_in_doc(self, doc_text):
        from src.tile.models import Season
        for member in Season:
            assert member.value in doc_text, f"Season: '{member.value}' missing from tile-prompt-guide.md"

    def test_terrain_category_all_in_doc(self, doc_text):
        from src.tile.models import TerrainCategory
        for member in TerrainCategory:
            assert member.value in doc_text, f"TerrainCategory: '{member.value}' missing from tile-prompt-guide.md"

    def test_terrain_scale_all_in_doc(self, doc_text):
        from src.tile.models import TerrainScale
        for member in TerrainScale:
            assert member.value in doc_text, f"TerrainScale: '{member.value}' missing from tile-prompt-guide.md"

    def test_terrain_material_all_in_doc(self, doc_text):
        from src.tile.models import TerrainMaterial
        for member in TerrainMaterial:
            assert member.value in doc_text, f"TerrainMaterial: '{member.value}' missing from tile-prompt-guide.md"


# ===========================================================================
#  Unit prompt guide
# ===========================================================================


class TestUnitDocEnums:
    """Verify unit-prompt-guide.md lists all enum values from unit_models.py."""

    @pytest.fixture(scope="class")
    def doc_text(self) -> str:
        path = DOCS_DIR / "guides" / "unit-prompt-guide.md"
        assert path.exists(), f"Missing: {path}"
        return path.read_text()

    def test_unit_type_all_in_doc(self, doc_text):
        from src.unit.models import UnitType
        for member in UnitType:
            assert member.value in doc_text, f"UnitType: '{member.value}' missing from unit-prompt-guide.md"
