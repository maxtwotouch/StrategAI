"""Human-driven goal sources.

Two flavors share the GoalSource Protocol:

* `QueueHumanSource` — pulls Decisions from an injected queue.  Suitable for
  HTTP, websocket, or scripted control.  Does not block; if the queue is
  empty the human passes the turn.

* `CLIHumanSource` — interactive REPL on stdin/stdout.  Useful for trying
  out the loop locally without wiring a frontend.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Callable, Deque

from app.engine.diplomacy import (
    DiplomaticAction,
    MessageKind,
    SendMessage,
    SetStance,
)
from app.engine.executor import (
    AttackUnit,
    FoundCityNear,
    Goal,
    MoveTo,
)
from app.engine.hex import Hex
from app.engine.models import DiplomaticStance
from app.engine.playthrough import Decisions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Queue-backed source — drains injected Decisions
# ---------------------------------------------------------------------------

class QueueHumanSource:
    """Goal source backed by an in-memory queue of Decisions.

    External code (HTTP handler, CLI loop, etc.) calls `submit(decisions)`
    before the engine asks for them.  Each call to `decide()` drains and
    merges all queued Decisions for the requesting civ.
    """

    def __init__(self) -> None:
        self._queues: dict[int, Deque[Decisions]] = {}

    def submit(self, civ_id: int, decisions: Decisions) -> None:
        self._queues.setdefault(civ_id, deque()).append(decisions)

    def decide(self, view: dict, civ_id: int) -> Decisions:
        q = self._queues.get(civ_id)
        if not q:
            return Decisions()
        merged_goals: list[Goal] = []
        merged_dipl: list[DiplomaticAction] = []
        while q:
            d = q.popleft()
            merged_goals.extend(d.goals)
            merged_dipl.extend(d.diplomacy)
        return Decisions(goals=tuple(merged_goals), diplomacy=tuple(merged_dipl))


# ---------------------------------------------------------------------------
# CLI source — text prompt
# ---------------------------------------------------------------------------

_HELP = """\
Commands:
  move <unit_id> <q> <r>           Move a unit toward (q, r)
  found <unit_id> <q> <r> <name>   Send settler to (q, r) and found city
  attack <attacker_id> <target_id> Attack an enemy unit
  msg <to_civ_id> <kind> <text>    Send a diplomatic message
  stance <civ_id> peace|war|alliance   Set diplomatic stance
  view                             Reprint your local view summary
  end                              End your turn (no more orders)
  help                             Show this help
"""


class CLIHumanSource:
    """Interactive stdin/stdout source.  One prompt loop per turn until 'end'."""

    def __init__(
        self,
        input_fn: Callable[[str], str] = input,
        print_fn: Callable[[str], None] = print,
    ) -> None:
        self._input = input_fn
        self._print = print_fn

    def decide(self, view: dict, civ_id: int) -> Decisions:
        self._summary(view, civ_id)
        goals: list[Goal] = []
        dipl: list[DiplomaticAction] = []
        while True:
            try:
                raw = self._input(f"[civ {civ_id} turn {view.get('turn')}] > ").strip()
            except EOFError:
                break
            if not raw:
                continue
            cmd, *args = raw.split()
            cmd = cmd.lower()
            if cmd in ("end", "done", "."):
                break
            if cmd == "help":
                self._print(_HELP)
                continue
            if cmd == "view":
                self._summary(view, civ_id)
                continue
            try:
                parsed = _parse_command(cmd, args)
            except ValueError as e:
                self._print(f"  ! {e}")
                continue
            if parsed is None:
                self._print(f"  ! unknown command: {cmd}")
                continue
            if isinstance(parsed, (MoveTo, FoundCityNear, AttackUnit)):
                goals.append(parsed)
            else:
                dipl.append(parsed)
        return Decisions(goals=tuple(goals), diplomacy=tuple(dipl))

    def _summary(self, view: dict, civ_id: int) -> None:
        self._print(
            f"\n=== Your turn (civ {civ_id}, turn {view.get('turn')}) ==="
        )
        own_units = [u for u in view.get("visible_units", []) if u["owner"] == civ_id]
        own_cities = [c for c in view.get("visible_cities", []) if c["owner"] == civ_id]
        self._print(f"Units: {len(own_units)}  Cities: {len(own_cities)}")
        for u in own_units:
            self._print(
                f"  unit {u['id']:>3} {u['type']:<8} @ ({u['q']:>3},{u['r']:>3})  "
                f"hp={u['health']}/{u['max_health']}  moves={u['moves_remaining']}"
            )
        for c in own_cities:
            self._print(
                f"  city {c['id']:>3} {c['name']:<12} @ ({c['q']:>3},{c['r']:>3})  "
                f"pop={c['population']}"
            )
        inbox = view.get("inbox", [])
        if inbox:
            self._print(f"Inbox ({len(inbox)} messages):")
            for m in inbox[-5:]:
                self._print(
                    f"  [t{m['turn']}] from civ {m['from_civ_id']} "
                    f"({m['kind']}): {m['text']}"
                )
        stances = view.get("diplomatic_stances", [])
        if stances:
            self._print("Stances: " + ", ".join(
                f"civ{s['civ_id']}={s['stance']}" for s in stances
            ))


def _parse_command(cmd: str, args: list[str]) -> Goal | DiplomaticAction | None:
    if cmd == "move":
        unit_id, q, r = int(args[0]), int(args[1]), int(args[2])
        return MoveTo(unit_id=unit_id, target=Hex(q, r))
    if cmd == "found":
        unit_id, q, r = int(args[0]), int(args[1]), int(args[2])
        name = " ".join(args[3:]) or f"City-{unit_id}"
        return FoundCityNear(unit_id=unit_id, target=Hex(q, r), name=name)
    if cmd == "attack":
        return AttackUnit(attacker_id=int(args[0]), target_id=int(args[1]))
    if cmd == "msg":
        to_id, kind = int(args[0]), args[1].lower()
        text = " ".join(args[2:])
        try:
            mk = MessageKind(kind)
        except ValueError as exc:
            raise ValueError(
                f"unknown message kind '{kind}'. valid: "
                + ", ".join(k.value for k in MessageKind)
            ) from exc
        return SendMessage(to_civ_id=to_id, kind=mk, text=text)
    if cmd == "stance":
        target = int(args[0])
        try:
            st = DiplomaticStance(args[1].lower())
        except ValueError as exc:
            raise ValueError(
                f"unknown stance '{args[1]}'. valid: peace, war, alliance"
            ) from exc
        return SetStance(target_civ_id=target, stance=st)
    return None
