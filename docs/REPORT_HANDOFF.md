# Report Handoff for AI Agents

Use this page as the high-level source when writing a project report. It is
intentionally concise and points to the implementation files that justify each
claim.

---

## Executive Summary

StrategAI is a browser-based 4X strategy prototype with a Python/FastAPI
engine and a Next.js/React frontend. The project now supports a complete
human-vs-AI campaign loop: generated maps, fog of war, city founding, city
growth, research, production, diplomacy, combat, AI turns, turn-event
chronicles, generated art, music, and city-level building placement.

The most visible work is the move from a debug-like prototype toward a
playable, reportable game experience:

- AI civilizations have leader personas and take turns through the
  OpenAI-powered intent layer.
- AI-founded cities receive civilization-appropriate names instead of
  placeholder names.
- The UI has a polished war-room layout: map-first center, rails for minimap,
  selection, research, cities, standings, and a collapsible chronicle.
- The asset service provides generated terrain, units, leaders, elevation
  overlays, and structure art, with fallbacks when the service is unavailable.
- Players can drag purchasable structures from the city drawer onto empty
  tiles inside that city's borders.

---

## Current Feature Snapshot

### Backend Game Engine

- Immutable state model with frozen dataclasses in
  `backend/app/engine/models.py`.
- Turn resolution and AI cycling in `backend/app/engine/turn_resolver.py` and
  `backend/app/engine/playthrough.py`.
- City founding in `backend/app/engine/city_founding.py`.
- Deterministic city-name selection in `backend/app/engine/city_names.py`,
  used by AI operations and fallback random AI.
- Production, growth, culture, and border claiming in
  `backend/app/engine/production.py` and `backend/app/engine/borders.py`.
- Queue-built buildings and gold-purchased structure constants in
  `backend/app/engine/buildings.py`.
- Directives for production queues, research, cancellation, and placed
  structures in `backend/app/engine/directives.py`.
- Fog of war and explored tiles in `backend/app/engine/fog_of_war.py`.
- Diplomacy, relationships, truces, and messages in
  `backend/app/engine/diplomacy.py`.
- Score victory in `backend/app/engine/victory.py`.

### Frontend Experience

- Main state owner: `frontend/app/page.tsx`.
- Map renderer: `frontend/components/SquareMap.tsx`, using SVG layers for
  terrain, elevation, borders, fog, cities, placed structures, units, and hit
  zones.
- Styling and HUD polish: `frontend/app/globals.css`.
- Backend DTO/client definitions: `frontend/lib/api.ts`.
- Turn-event diffing for the bottom chronicle and map banner:
  `frontend/lib/turnEvents.ts`.
- Audio intro/ambient playlist and polished mute button:
  `frontend/lib/useAudio.ts` plus `AudioGlyph` in `page.tsx`.

### Generated Assets

- Asset client/proxy: `frontend/lib/assetApi.ts` and
  `frontend/app/api/asset/[...path]/route.ts`.
- Resolver: `frontend/lib/assetManifest.ts`.
- Mapping from game vocabulary to asset-service vocabularies:
  `frontend/lib/assetMapping.ts`.
- Leader mapping and custom leader prompt construction:
  `frontend/lib/leaderMapping.ts`.

The resolver currently pre-generates per-civ unit sprites and per-civ,
per-category structure art. Placed structures use `placedStructureAssets` first
and fall back to the preloaded `assets.structures[civId][category]` URL.

---

## Notable Mechanics to Mention in a Report

- **AI turn loop:** the human acts through immediate API calls, then clicks End
  Turn. The backend advances AI civs until control returns to the human.
- **AI personas:** Mongolia/Genghis, Egypt/Cleopatra, and India/Gandhi have
  distinct prompt personas in `backend/app/api/game_factory.py`.
- **AI city names:** AI settlement no longer uses `City-1-1` style names.
  `city_names.py` provides rosters such as Karakorum, Memphis, and Delhi.
- **Research UI:** available technologies show themed emoji markers for faster
  scanning.
- **Economy:** gold is intentionally simple: flat +5 gold per civilization per
  turn, no unit upkeep, no bankruptcy disbanding.
- **Structure placement:** gold-purchased structures cost 15 gold, grant +2
  production per category owned by a city, and must be dragged onto a passable,
  empty tile inside that city's borders.
- **Chronicle:** the bottom event log summarizes turn changes using frontend
  state diffing.
- **Diplomacy UI:** rival leaders open a full-screen Diplomatic Audience with
  splash art, message history, stance, relationship, and composer.
- **Map polish:** minimap is compact, the mute button is an SVG HUD control,
  the top-left profile portrait is enlarged, and debug Global/Local map mode
  buttons were removed.

---

## Report Structure Recommendation

1. **Problem and goal.** Explain that the project aims to prototype a 4X game
   where AI civilizations are active personalities, not passive scripted NPCs.
2. **Architecture.** Split backend pure engine, FastAPI API, Next.js frontend,
   and external asset service.
3. **Implemented gameplay.** Cover map, units, cities, economy, research,
   production, diplomacy, AI turns, and victory.
4. **AI behavior.** Describe the OpenAI intent layer, deterministic lowering
   into legal actions, fallback random AI, and AI city naming.
5. **Frontend and UX.** Describe war-room layout, map renderer, city drawer,
   diplomacy audience, chronicle, audio, minimap, and polish improvements.
6. **Asset integration.** Explain generated terrain, units, leaders,
   structures, fallbacks, and the same-origin proxy.
7. **Testing and validation.** Mention backend pytest suite and frontend
   TypeScript typecheck.
8. **Limitations and next work.** Cite `GAME_BACKLOG.md`.

---

## Verification Commands

```bash
cd backend && ./.venv/bin/python -m pytest
cd frontend && npm run typecheck
```

Use focused variants while reporting on specific areas:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_directives.py
cd backend && ./.venv/bin/python -m pytest tests/test_playthrough.py
```

---

## Primary Source Map

| Report topic | Primary files |
|---|---|
| Game state model | `backend/app/engine/models.py` |
| AI personas and sources | `backend/app/api/game_factory.py`, `backend/app/engine/openai_goals.py` |
| AI goal lowering | `backend/app/engine/operations.py`, `backend/app/engine/executor.py` |
| AI/city names | `backend/app/engine/city_names.py` |
| City and structure mechanics | `backend/app/engine/buildings.py`, `backend/app/engine/directives.py` |
| API schemas/routes | `backend/app/api/schemas.py`, `backend/app/api/routers/actions.py` |
| Turn loop | `backend/app/engine/turn_resolver.py`, `backend/app/engine/playthrough.py` |
| Frontend war room | `frontend/app/page.tsx`, `frontend/app/globals.css` |
| Map renderer | `frontend/components/SquareMap.tsx` |
| Asset service | `frontend/lib/assetApi.ts`, `frontend/lib/assetManifest.ts`, `frontend/lib/assetMapping.ts` |
| Turn chronicle | `frontend/lib/turnEvents.ts` |
