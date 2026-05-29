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
        path = DOCS_DIR / "leader-prompt-guide.md"
        assert path.exists(), f"Missing: {path}"
        return path.read_text()

    def test_archetype_all_in_doc(self, doc_text):
        from src.leader.models import Archetype
        for val in sorted(Archetype.ALL):
            assert val in doc_text, f"ARCHETYPE: '{val}' missing from leader-prompt-guide.md"

    def test_culture_all_in_doc(self, doc_text):
        from src.leader.models import Culture
        for val in sorted(Culture.ALL):
            assert val in doc_text, f"CULTURE: '{val}' missing from leader-prompt-guide.md"

    def test_time_of_day_all_in_doc(self, doc_text):
        from src.leader.models import TimeOfDay
        for val in sorted(TimeOfDay.ALL):
            assert val in doc_text, f"TIME_OF_DAY: '{val}' missing from leader-prompt-guide.md"

    def test_mood_all_in_doc(self, doc_text):
        from src.leader.models import Mood
        for val in sorted(Mood.ALL):
            assert val in doc_text, f"MOOD: '{val}' missing from leader-prompt-guide.md"

    def test_action_category_all_in_doc(self, doc_text):
        from src.leader.models import ActionCategory
        for val in sorted(ActionCategory.ALL):
            assert val in doc_text, f"ACTION_CATEGORY: '{val}' missing from leader-prompt-guide.md"


# ===========================================================================
#  Tile prompt guide
# ===========================================================================


class TestTileDocEnums:
    """Verify tile-prompt-guide.md lists all enum values from tile_models.py."""

    @pytest.fixture(scope="class")
    def doc_text(self) -> str:
        path = DOCS_DIR / "tile-prompt-guide.md"
        assert path.exists(), f"Missing: {path}"
        return path.read_text()

    def test_structure_category_all_in_doc(self, doc_text):
        from src.tile.models import StructureCategory
        for val in sorted(StructureCategory.ALL):
            assert val in doc_text, f"StructureCategory: '{val}' missing from tile-prompt-guide.md"

    def test_structure_style_all_in_doc(self, doc_text):
        from src.tile.models import StructureStyle
        for val in sorted(StructureStyle.ALL):
            assert val in doc_text, f"StructureStyle: '{val}' missing from tile-prompt-guide.md"

    def test_structure_condition_all_in_doc(self, doc_text):
        from src.tile.models import StructureCondition
        for val in sorted(StructureCondition.ALL):
            assert val in doc_text, f"StructureCondition: '{val}' missing from tile-prompt-guide.md"

    def test_structure_scale_all_in_doc(self, doc_text):
        from src.tile.models import StructureScale
        for val in sorted(StructureScale.ALL):
            assert val in doc_text, f"StructureScale: '{val}' missing from tile-prompt-guide.md"

    def test_object_category_all_in_doc(self, doc_text):
        from src.tile.models import ObjectCategory
        for val in sorted(ObjectCategory.ALL):
            assert val in doc_text, f"ObjectCategory: '{val}' missing from tile-prompt-guide.md"

    def test_biome_all_in_doc(self, doc_text):
        from src.tile.models import Biome
        for val in sorted(Biome.ALL):
            assert val in doc_text, f"Biome: '{val}' missing from tile-prompt-guide.md"

    def test_season_all_in_doc(self, doc_text):
        from src.tile.models import Season
        for val in sorted(Season.ALL):
            assert val in doc_text, f"Season: '{val}' missing from tile-prompt-guide.md"

    def test_terrain_category_all_in_doc(self, doc_text):
        from src.tile.models import TerrainCategory
        for val in sorted(TerrainCategory.ALL):
            assert val in doc_text, f"TerrainCategory: '{val}' missing from tile-prompt-guide.md"

    def test_terrain_scale_all_in_doc(self, doc_text):
        from src.tile.models import TerrainScale
        for val in sorted(TerrainScale.ALL):
            assert val in doc_text, f"TerrainScale: '{val}' missing from tile-prompt-guide.md"

    def test_terrain_material_all_in_doc(self, doc_text):
        from src.tile.models import TerrainMaterial
        for val in sorted(TerrainMaterial.ALL):
            assert val in doc_text, f"TerrainMaterial: '{val}' missing from tile-prompt-guide.md"


# ===========================================================================
#  Unit prompt guide
# ===========================================================================


class TestUnitDocEnums:
    """Verify unit-prompt-guide.md lists all enum values from unit_models.py."""

    @pytest.fixture(scope="class")
    def doc_text(self) -> str:
        path = DOCS_DIR / "unit-prompt-guide.md"
        assert path.exists(), f"Missing: {path}"
        return path.read_text()

    def test_unit_type_all_in_doc(self, doc_text):
        from src.unit.models import UnitType
        for val in sorted(UnitType.ALL):
            assert val in doc_text, f"UnitType: '{val}' missing from unit-prompt-guide.md"
