from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    AttackRequest,
    FoundCityRequest,
    GameStateOut,
    MoveRequest,
    ResearchRequest,
    state_to_out,
)
from app.api.store import store
from app.engine.city_founding import FoundError, found_city
from app.engine.combat import CombatError, attack
from app.engine.hex import Hex
from app.engine.movement import MoveError, move_unit
from app.engine.research import ResearchError, set_research

router = APIRouter(prefix="/games/{game_id}/actions", tags=["actions"])


def _load(game_id: int):  # type: ignore[no-untyped-def]
    try:
        return store.get(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="game not found")


@router.post("/move", response_model=GameStateOut)
def action_move(game_id: int, req: MoveRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = move_unit(state, req.unit_id, Hex(req.q, req.r))
    except MoveError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/attack", response_model=GameStateOut)
def action_attack(game_id: int, req: AttackRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = attack(state, req.attacker_id, req.defender_id)
    except CombatError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/found", response_model=GameStateOut)
def action_found(game_id: int, req: FoundCityRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = found_city(state, req.unit_id, req.name)
    except FoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/research", response_model=GameStateOut)
def action_research(game_id: int, req: ResearchRequest) -> GameStateOut:
    state = _load(game_id)
    try:
        new_state = set_research(state, req.civ_id, req.tech_id)
    except ResearchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)
