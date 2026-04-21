"""In-memory game store. Thread-safe via a single lock.

Deferred Postgres until an API + engine shape is stable.
"""

from __future__ import annotations

import itertools
import threading
from typing import Iterator

from app.engine.models import GameState


class GameStore:
    def __init__(self) -> None:
        self._games: dict[int, GameState] = {}
        self._goal_sources: dict[int, object] = {}
        self._lock = threading.Lock()
        self._ids: Iterator[int] = itertools.count(1)

    def create(self, state: GameState) -> int:
        with self._lock:
            game_id = next(self._ids)
            self._games[game_id] = state
            return game_id

    def get(self, game_id: int) -> GameState:
        with self._lock:
            if game_id not in self._games:
                raise KeyError(game_id)
            return self._games[game_id]

    def put(self, game_id: int, state: GameState) -> None:
        with self._lock:
            if game_id not in self._games:
                raise KeyError(game_id)
            self._games[game_id] = state

    def put_goal_sources(self, game_id: int, goal_sources: object) -> None:
        with self._lock:
            if game_id not in self._games:
                raise KeyError(game_id)
            self._goal_sources[game_id] = goal_sources

    def get_goal_sources(self, game_id: int) -> object:
        with self._lock:
            if game_id not in self._goal_sources:
                raise KeyError(game_id)
            return self._goal_sources[game_id]

    def clear(self) -> None:
        with self._lock:
            self._games.clear()
            self._goal_sources.clear()
            self._ids = itertools.count(1)


store = GameStore()
