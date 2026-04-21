# Game Backlog

This document tracks the missing work to turn the current prototype into a proper playable game.

## Critical Path

- Wire the web app into the real playthrough loop.
  The browser currently mutates raw game state directly instead of submitting a human turn and letting the 3 AI civs actually play theirs.
- Add a backend turn-resolution endpoint.
  It should accept the human's completed turn state, advance AI civs until control returns to the human, and return the updated game state plus a structured turn report.
- Move the web client onto a human-local view.
  The frontend should consume fogged state, inbox, discovered civs, visible tiles, and visible units/cities rather than omniscient map data.

## Turn System

- Define a formal human turn payload.
  It should support unit goals, city directives, research selection, diplomacy actions, and explicit end-turn.
- Add pending-orders support for the human player.
  The player should be able to queue actions before committing the turn.
- Return a turn report after AI resolution.
  Combat results, research completion, production completion, city growth, diplomatic messages, discoveries, and eliminated units should be summarized.
- Enforce turn ownership at the API boundary.
  Human actions should be accepted only when the playthrough engine says it is the human's turn.

## Frontend Playability

- Replace direct state-editing with submit-turn and resolve-turn flow.
- Add unit/city action panels with clear contextual controls.
- Add production queue management.
  Queueing exists; cancel, reorder, and replace should follow.
- Add research progress UI.
  Show current tech, accumulated science, cost, and completion updates.
- Add an inbox and conversation view.
  The player needs both incoming messages and per-civ conversation context.
- Add a turn log / event feed.
  The player must be able to understand what happened during AI turns.
- Improve map controls.
  Add zoom, pan, unit cycling, city cycling, and clearer ownership/selection feedback.

## Core Game Systems

- Implement city border growth / tile ownership.
  This is currently missing and is a major Civ-style system.
- Improve city economy.
  Cities should eventually work owned tiles rather than only their center tile.
- Complete city conquest / siege rules if needed.
- Expand economy depth.
  Gold, culture, upkeep, and maintenance are still minimal.
- Deepen diplomacy rules.
  Treaties, peace resolution, alliance effects, and stronger AI memory are still thin.

## AI / Simulation Quality

- Run AI turns in the web game.
- Add AI production and research behavior.
- Add anti-stall logic for repeated no-op intents.
- Add diplomacy spam suppression and stronger message memory.
- Prevent capability-invalid AI choices.
  Example: civs with no units should not repeatedly choose combat.

## Map / World

- Continue improving map generation quality on larger maps.
- Stress-test starting-position fairness on large maps.
- Make exploration matter under fogged local-view play.
- Add fast map-preview tooling for seed evaluation.

## API / Data Model

- Add a dedicated playthrough/session API layer instead of relying only on low-level action routes.
- Expose structured turn events in API responses.
- Expose local-view payloads for the human player.
- Expose richer production and research progress data.
- Add queue-management endpoints if production is meant to be interactive.

## Testing

- Add integration tests for the full human-plus-3-AI web turn flow.
- Add tests for production queue APIs and diplomacy APIs.
- Add regression tests for AI no-op loops and repeated-message spam.
- Add tests for fogged local-view responses.
- Add large-map generation and start-balance tests.

## Recommended Order

1. Backend turn-resolution endpoint for human plus 3 AI playthrough.
2. Frontend submit-turn flow and turn event log.
3. Human-local-view API instead of omniscient game state.
4. Production queue management and research progress UI.
5. Dialogue inbox and conversation UX.
6. City border / tile ownership system.
7. AI production, research, and anti-stall improvements.

## Current Focus

The first implementation target is the backend turn-resolution flow. The game is not a proper game until the web client is connected to the playthrough engine rather than editing raw state.
