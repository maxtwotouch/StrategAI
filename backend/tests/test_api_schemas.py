from __future__ import annotations

from app.api.schemas import state_to_out
from app.engine.diplomacy import DiplomaticMessage, MessageKind
from app.engine.hex import Hex
from app.engine.models import City, Civilization, GameMap, GameState, Tile, Unit, UnitType
from app.engine.terrain import Terrain


def _tile(coord: Hex) -> Tile:
    return Tile(coord=coord, terrain=Terrain.GRASSLAND)


def _state() -> GameState:
    civs = (
        Civilization(id=0, name="Human", leader_name="Leader", is_human=True),
        Civilization(id=1, name="Known", leader_name="Known Leader", is_human=False),
        Civilization(id=2, name="Unknown", leader_name="Unknown Leader", is_human=False),
    )
    human_unit = Unit(
        id=1,
        owner=0,
        type=UnitType.WARRIOR,
        location=Hex(0, 0),
        health=20,
        moves_remaining=2,
    )
    known_unit = Unit(
        id=2,
        owner=1,
        type=UnitType.WARRIOR,
        location=Hex(1, 0),
        health=20,
        moves_remaining=2,
    )
    unknown_unit = Unit(
        id=3,
        owner=2,
        type=UnitType.WARRIOR,
        location=Hex(5, 5),
        health=20,
        moves_remaining=2,
    )
    known_city = City(id=10, owner=1, name="Known City", location=Hex(1, 0))
    unknown_city = City(id=11, owner=2, name="Unknown City", location=Hex(5, 5))
    return GameState(
        turn=3,
        map=GameMap(
            radius=6,
            tiles={
                Hex(0, 0): _tile(Hex(0, 0)),
                Hex(1, 0): _tile(Hex(1, 0)),
                Hex(5, 5): _tile(Hex(5, 5)),
            },
        ),
        civs=civs,
        cities=(known_city, unknown_city),
        units=(human_unit, known_unit, unknown_unit),
        tile_owner={
            Hex(0, 0): 99,
            Hex(1, 0): known_city.id,
            Hex(5, 5): unknown_city.id,
        },
        messages=(
            DiplomaticMessage(
                from_civ_id=1,
                to_civ_id=0,
                turn=1,
                kind=MessageKind.CHAT,
                text="hello",
            ),
            DiplomaticMessage(
                from_civ_id=2,
                to_civ_id=2,
                turn=1,
                kind=MessageKind.CHAT,
                text="secret",
            ),
        ),
    )


def test_state_to_out_filters_to_player_knowledge():
    out = state_to_out(7, _state())

    assert out.known_civ_ids == [1]
    assert [civ.id for civ in out.civs] == [0, 1]
    assert {unit.id for unit in out.units} == {1, 2}
    assert {city.id for city in out.cities} == {10}
    assert {(entry.q, entry.r) for entry in out.tile_owner} == {(0, 0), (1, 0)}
    assert [(message.from_civ_id, message.to_civ_id) for message in out.messages] == [(1, 0)]
    assert [standing.civ_id for standing in out.standings] == [1, 0]
