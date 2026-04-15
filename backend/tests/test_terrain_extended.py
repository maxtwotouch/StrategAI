"""Tests for extended terrain/tile model: features, resources, climate."""

from __future__ import annotations

import pytest

from app.engine.hex import Hex
from app.engine.models import Tile
from app.engine.terrain import (
    Feature,
    Resource,
    ResourceCategory,
    Terrain,
    is_passable,
    resource_info,
    yields_for,
)


@pytest.mark.unit
def test_new_terrain_types_exist() -> None:
    assert Terrain.TUNDRA.value == "tundra"
    assert Terrain.SNOW.value == "snow"


@pytest.mark.unit
def test_new_terrain_has_yields() -> None:
    assert yields_for(Terrain.TUNDRA).food >= 0
    assert yields_for(Terrain.SNOW).food == 0


@pytest.mark.unit
def test_tundra_is_passable_snow_is_not() -> None:
    assert is_passable(Terrain.TUNDRA)
    assert not is_passable(Terrain.SNOW)


@pytest.mark.unit
def test_feature_enum_values() -> None:
    assert Feature.FOREST.value == "forest"
    assert Feature.JUNGLE.value == "jungle"
    assert Feature.MARSH.value == "marsh"


@pytest.mark.unit
def test_resource_categories() -> None:
    assert resource_info(Resource.IRON).category == ResourceCategory.STRATEGIC
    assert resource_info(Resource.GEMS).category == ResourceCategory.LUXURY
    assert resource_info(Resource.WHEAT).category == ResourceCategory.BONUS


@pytest.mark.unit
def test_tile_defaults_preserve_backwards_compat() -> None:
    tile = Tile(coord=Hex(0, 0), terrain=Terrain.GRASSLAND)
    assert tile.elevation == 0.0
    assert tile.moisture == 0.0
    assert tile.temperature == 0.0
    assert tile.resource is None
    assert tile.feature is None
    assert tile.river is False


@pytest.mark.unit
def test_tile_accepts_full_attributes() -> None:
    tile = Tile(
        coord=Hex(1, -1),
        terrain=Terrain.PLAINS,
        elevation=0.6,
        moisture=0.3,
        temperature=0.7,
        resource=Resource.WHEAT,
        feature=Feature.FOREST,
        river=True,
    )
    assert tile.resource is Resource.WHEAT
    assert tile.feature is Feature.FOREST
    assert tile.river is True


@pytest.mark.unit
def test_forest_feature_adds_production() -> None:
    base = yields_for(Terrain.GRASSLAND)
    tile_plain = Tile(coord=Hex(0, 0), terrain=Terrain.GRASSLAND)
    tile_forest = Tile(coord=Hex(0, 0), terrain=Terrain.GRASSLAND, feature=Feature.FOREST)
    from app.engine.terrain import tile_yields

    assert tile_yields(tile_plain) == base
    assert tile_yields(tile_forest).production > base.production


@pytest.mark.unit
def test_river_adds_gold() -> None:
    from app.engine.terrain import tile_yields

    dry = Tile(coord=Hex(0, 0), terrain=Terrain.PLAINS)
    wet = Tile(coord=Hex(0, 0), terrain=Terrain.PLAINS, river=True)
    assert tile_yields(wet).gold > tile_yields(dry).gold


@pytest.mark.unit
def test_wheat_resource_adds_food() -> None:
    from app.engine.terrain import tile_yields

    plain = Tile(coord=Hex(0, 0), terrain=Terrain.PLAINS)
    wheat = Tile(coord=Hex(0, 0), terrain=Terrain.PLAINS, resource=Resource.WHEAT)
    assert tile_yields(wheat).food > tile_yields(plain).food
