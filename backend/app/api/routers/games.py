from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.game_factory import build_goal_sources, new_game
from app.api.schemas import CreateGameRequest, GameStateOut, state_to_out
from app.api.store import store

router = APIRouter(prefix="/games", tags=["games"])


@router.post("", response_model=GameStateOut)
def create_game(req: CreateGameRequest) -> GameStateOut:
    state = new_game(radius=req.radius, seed=req.seed, human_name=req.human_name)
    game_id = store.create(state)
    store.put_goal_sources(game_id, build_goal_sources(state))
    return state_to_out(game_id, state)


@router.get("/{game_id}", response_model=GameStateOut)
def get_game(game_id: int) -> GameStateOut:
    try:
        state = store.get(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="game not found")
    return state_to_out(game_id, state)
