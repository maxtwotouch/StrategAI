from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import GameStateOut, state_to_out
from app.api.store import store
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
