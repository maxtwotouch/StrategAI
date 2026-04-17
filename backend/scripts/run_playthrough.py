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

from app.api.game_factory import new_game
from app.engine.human_source import CLIHumanSource, QueueHumanSource
from app.engine.models import Civilization
from app.engine.playthrough import RandomGoalSource, run_playthrough
from app.engine.victory import civ_score


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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a headless Civ playthrough")
    parser.add_argument("--seed", type=int, default=42, help="Map/RNG seed")
    parser.add_argument("--radius", type=int, default=5, help="Map hex radius")
    parser.add_argument("--civs", type=int, default=4, help="Number of civilizations (1-4)")
    parser.add_argument("--no-human", action="store_true", help="Drop the human seat (all AI)")
    parser.add_argument("--turns", type=int, default=50, help="Maximum turns")
    parser.add_argument("--ai", choices=["random", "openai"], default="random",
                        help="Goal source for AI civs")
    parser.add_argument("--human", choices=["cli", "queue", "random"], default="random",
                        help="Goal source for the human seat (random = unattended demo)")
    parser.add_argument("--model", default="gpt-4o-mini", help="OpenAI model (if --ai openai)")
    parser.add_argument("--verbose", "-v", action="store_true", help="DEBUG logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

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
    result = run_playthrough(state, sources, max_turns=args.turns)

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
