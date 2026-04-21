from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import GameStateOut, state_to_out
from app.api.store import store
from app.engine.playthrough import advance_until_human_turn
from app.engine.turn_resolver import end_turn

router = APIRouter(prefix="/games/{game_id}/turn", tags=["turns"])


@router.post("", response_model=GameStateOut)
def advance_turn(game_id: int) -> GameStateOut:
    try:
        state = store.get(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="game not found")
    new_state = end_turn(state)
    store.put(game_id, new_state)
    return state_to_out(game_id, new_state)


@router.post("/resolve", response_model=GameStateOut)
def resolve_ai_turns(game_id: int) -> GameStateOut:
    try:
        state = store.get(game_id)
        goal_sources = store.get_goal_sources(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="game not found")

    human_civ = next((civ for civ in state.civs if civ.is_human), None)
    if human_civ is None:
        raise HTTPException(status_code=400, detail="game has no human civ")

    result = advance_until_human_turn(
        state,
        goal_sources,
        human_civ_id=human_civ.id,
    )
    store.put(game_id, result.final_state)
    return state_to_out(game_id, result.final_state)
