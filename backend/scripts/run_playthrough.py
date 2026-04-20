#!/usr/bin/env python3
"""Run a headless playthrough and print a summary.

Examples:
    # 4-civ random AI smoke test
    python -m scripts.run_playthrough --turns 20

    # All civs driven by OpenAI (1 human seat dropped)
    python -m scripts.run_playthrough --no-human --ai openai --turns 15

    # You play Athens, the 3 LLM civs use OpenAI
    python -m scripts.run_playthrough --human cli --ai openai --turns 30
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.api.game_factory import new_game
from app.engine.hex import Hex
from app.engine.human_source import CLIHumanSource, QueueHumanSource
from app.engine.models import Civilization
from app.engine.playthrough import RandomGoalSource, run_playthrough
from app.engine.terrain import Terrain
from app.engine.victory import civ_score


RESET = "\x1b[0m"
BOLD = "\x1b[1m"


def _build_sources(args, civs: tuple[Civilization, ...]):
    """Per-civ goal-source assignment based on CLI flags."""
    sources: dict[int, object] = {}
    for civ in civs:
        if civ.is_human:
            if args.human == "cli":
                sources[civ.id] = CLIHumanSource()
            elif args.human == "queue":
                sources[civ.id] = QueueHumanSource()
            else:  # "random"
                sources[civ.id] = RandomGoalSource(seed=args.seed + civ.id)
        else:
            if args.ai == "openai":
                from app.engine.openai_goals import OpenAIGoalSource
                sources[civ.id] = OpenAIGoalSource(
                    model=args.model, persona=civ.persona,
                )
            else:  # "random"
                sources[civ.id] = RandomGoalSource(seed=args.seed + civ.id)
    return sources


def _print_recent_messages(state, last_n: int = 10) -> None:
    if not state.messages:
        print("  (no diplomatic exchanges)")
        return
    civ_name = {c.id: c.leader_name for c in state.civs}
    for m in state.messages[-last_n:]:
        sender = civ_name.get(m.from_civ_id, f"civ{m.from_civ_id}")
        recipient = civ_name.get(m.to_civ_id, f"civ{m.to_civ_id}")
        print(f"  [t{m.turn}] {sender} → {recipient} ({m.kind.value}): {m.text}")


def _configure_logging(args) -> None:
    level_name = args.log_level.upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise ValueError(f"invalid log level: {args.log_level}")

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if args.log_file:
        log_path = Path(args.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))

    for handler in handlers:
        handler.setFormatter(formatter)

    logging.basicConfig(level=level, handlers=handlers, force=True)


def _tile_char(terrain: Terrain) -> str:
    return {
        Terrain.GRASSLAND: ".",
        Terrain.PLAINS: ",",
        Terrain.DESERT: ":",
        Terrain.TUNDRA: ";",
        Terrain.SNOW: "*",
        Terrain.FOREST: "f",
        Terrain.HILLS: "h",
        Terrain.MOUNTAIN: "^",
        Terrain.OCEAN: "~",
        Terrain.COAST: "=",
    }.get(terrain, "?")


def _ansi_fg_rgb(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def _ansi_bg_rgb(r: int, g: int, b: int) -> str:
    return f"\x1b[48;2;{r};{g};{b}m"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    if len(value) != 6:
        return (220, 220, 220)
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _terrain_bg(terrain: Terrain) -> tuple[int, int, int]:
    return {
        Terrain.GRASSLAND: (76, 153, 84),
        Terrain.PLAINS: (170, 156, 94),
        Terrain.DESERT: (196, 176, 96),
        Terrain.TUNDRA: (126, 136, 124),
        Terrain.SNOW: (226, 235, 239),
        Terrain.FOREST: (42, 100, 56),
        Terrain.HILLS: (120, 98, 78),
        Terrain.MOUNTAIN: (95, 95, 105),
        Terrain.OCEAN: (40, 92, 150),
        Terrain.COAST: (74, 130, 173),
    }.get(terrain, (80, 80, 80))


def _entity_cell(symbol: str, fg: tuple[int, int, int], bg: tuple[int, int, int]) -> str:
    return f"{_ansi_fg_rgb(*fg)}{_ansi_bg_rgb(*bg)}{BOLD} {symbol}{RESET}"


def _terrain_cell(terrain: Terrain) -> str:
    bg = _terrain_bg(terrain)
    return f"{_ansi_fg_rgb(20, 20, 20)}{_ansi_bg_rgb(*bg)} {_tile_char(terrain)}{RESET}"


def _render_ascii_map(state) -> str:
    occupied_units = {u.location: u for u in state.units}
    occupied_cities = {c.location: c for c in state.cities}
    lines: list[str] = []

    for r in range(-state.map.radius, state.map.radius + 1):
        row: list[str] = []
        indent = " " * (state.map.radius - (r + state.map.radius) // 2)
        for q in range(-state.map.radius, state.map.radius + 1):
            coord = Hex(q, r)
            if coord not in state.map:
                row.append("  ")
                continue
            city = occupied_cities.get(coord)
            unit = occupied_units.get(coord)
            if city is not None:
                row.append(f"C{city.owner}")
            elif unit is not None:
                row.append(f"U{unit.owner}")
            else:
                tile = state.map.get(coord)
                assert tile is not None
                row.append(f" {_tile_char(tile.terrain)}")
        lines.append(indent + "".join(row).rstrip())

    legend = "  ".join(f"{civ.id}={civ.leader_name}" for civ in state.civs)
    return "\n".join([
        f"Map at turn {state.turn}",
        *lines,
        f"Legend: {legend}",
        "Symbols: Cn=city owner n, Un=unit owner n",
    ])


def _render_color_map(state) -> str:
    occupied_units = {u.location: u for u in state.units}
    occupied_cities = {c.location: c for c in state.cities}
    civ_by_id = {civ.id: civ for civ in state.civs}
    lines: list[str] = [f"{BOLD}Map at turn {state.turn}{RESET}"]

    for r in range(-state.map.radius, state.map.radius + 1):
        row: list[str] = []
        indent = " " * (2 * max(0, state.map.radius - abs(r)))
        row.append(f"{indent}{BOLD}{r:>3}{RESET} ")
        for q in range(-state.map.radius, state.map.radius + 1):
            coord = Hex(q, r)
            if coord not in state.map:
                row.append("  ")
                continue
            city = occupied_cities.get(coord)
            unit = occupied_units.get(coord)
            tile = state.map.get(coord)
            assert tile is not None
            bg = _terrain_bg(tile.terrain)
            if city is not None:
                civ = civ_by_id[city.owner]
                row.append(_entity_cell("◆", _hex_to_rgb(civ.color), bg))
            elif unit is not None:
                civ = civ_by_id[unit.owner]
                symbol = "●" if unit.type.value != "settler" else "◐"
                row.append(_entity_cell(symbol, _hex_to_rgb(civ.color), bg))
            else:
                row.append(_terrain_cell(tile.terrain))
        lines.append("".join(row).rstrip())

    q_axis = "     " + "".join(f"{q:>2}" for q in range(-state.map.radius, state.map.radius + 1))
    lines.append(f"{BOLD}{q_axis}{RESET}")
    lines.append("")
    lines.append(f"{BOLD}Civs{RESET}")
    for civ in state.civs:
        fg = _ansi_fg_rgb(*_hex_to_rgb(civ.color))
        cities = state.cities_for(civ.id)
        units = state.units_for(civ.id)
        score = civ_score(state, civ)
        kind = "human" if civ.is_human else "ai"
        lines.append(
            f"  {fg}{BOLD}{civ.id}{RESET} {civ.leader_name:<14} "
            f"cities={len(cities):<2} units={len(units):<2} score={score:<3} {kind}"
        )
    lines.append("")
    lines.append("Legend: ◆ city, ● military unit, ◐ settler")
    return "\n".join(lines)


def _render_map(state, style: str) -> str:
    if style == "ascii":
        return _render_ascii_map(state)
    return _render_color_map(state)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a headless Civ playthrough")
    parser.add_argument("--seed", type=int, default=42, help="Map/RNG seed")
    parser.add_argument("--radius", type=int, default=8, help="Map hex radius")
    parser.add_argument("--civs", type=int, default=4, help="Number of civilizations (1-4)")
    parser.add_argument("--no-human", action="store_true", help="Drop the human seat (all AI)")
    parser.add_argument("--turns", type=int, default=50, help="Maximum turns")
    parser.add_argument("--ai", choices=["random", "openai"], default="random",
                        help="Goal source for AI civs")
    parser.add_argument("--human", choices=["cli", "queue", "random"], default="random",
                        help="Goal source for the human seat (random = unattended demo)")
    parser.add_argument("--model", default="gpt-5.4-mini", help="OpenAI model (if --ai openai)")
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Logging verbosity for engine and LLM traces",
    )
    parser.add_argument(
        "--log-file",
        help="Optional path for a detailed simulation log file",
    )
    parser.add_argument(
        "--render-map",
        action="store_true",
        help="Print a simplified ASCII map after each completed turn",
    )
    parser.add_argument(
        "--render-style",
        choices=["color", "ascii"],
        default="color",
        help="Map rendering style for --render-map",
    )
    args = parser.parse_args(argv)

    _configure_logging(args)

    print(f"Generating map: radius={args.radius}, seed={args.seed}, civs={args.civs}")
    state = new_game(
        radius=args.radius,
        seed=args.seed,
        num_civs=args.civs,
        include_human=not args.no_human,
    )

    print("Civilizations:")
    for civ in state.civs:
        kind = "human" if civ.is_human else f"AI ({args.ai})"
        print(f"  civ {civ.id}  {civ.leader_name:<14} of {civ.name:<10}  [{kind}]")

    sources = _build_sources(args, state.civs)
    print(f"Running playthrough (max {args.turns} turns)...")
    if args.render_map:
        print()
        print(_render_map(state, args.render_style))
        print()

    result = run_playthrough(
        state,
        sources,
        max_turns=args.turns,
        turn_observer=(lambda s: print("\n" + _render_map(s, args.render_style) + "\n")) if args.render_map else None,
    )

    print()
    print("=" * 60)
    print("PLAYTHROUGH SUMMARY")
    print("=" * 60)
    print(f"Turns played:     {result.turns_played}")
    print(f"Actions applied:  {result.actions_applied}")
    print(f"Actions rejected: {result.actions_rejected}")

    if result.victory:
        winner = next(c for c in result.final_state.civs if c.id == result.victory.winner_id)
        print(f"Victory:          {result.victory.kind.value} by {winner.leader_name} ({winner.name})")
    else:
        print("Victory:          none (turn limit reached)")

    print()
    print("Final scores:")
    for civ in result.final_state.civs:
        score = civ_score(result.final_state, civ)
        cities = result.final_state.cities_for(civ.id)
        units = result.final_state.units_for(civ.id)
        print(f"  {civ.leader_name:<14}  score={score:3d}  cities={len(cities)}  units={len(units)}")

    print()
    print(f"Final state: turn {result.final_state.turn}, "
          f"{len(result.final_state.cities)} cities, "
          f"{len(result.final_state.units)} units")

    print()
    print(f"Recent diplomacy ({len(result.final_state.messages)} total):")
    _print_recent_messages(result.final_state)


if __name__ == "__main__":
    main()
