# INF-3600: AI Civilization Game

## Concept

A Civilization-style strategy game where AI agents serve as the leaders of rival civilizations. The player competes against AI-controlled civilizations that have distinct personalities, strategies, and diplomatic behaviors.

## Core Ideas

- **AI-driven opponents**: Each rival civilization is controlled by an AI agent (LLM-backed) rather than scripted game AI
- **Free-form diplomacy**: The player can chat with any AI leader at any time — negotiate alliances, trade deals, threats, or just talk
- **Distinct personalities**: Each AI leader has a unique persona, temperament, and strategic style (e.g., aggressive expansionist, peaceful trader, cunning diplomat)
- **Emergent gameplay**: Because leaders are LLM-driven, interactions and strategies emerge organically rather than following decision trees

## Key Features

### Diplomacy & Chat
- Real-time or turn-based conversations with AI leaders
- Leaders remember past interactions and hold grudges or honor alliances
- Negotiations for trade, peace treaties, joint wars, territorial agreements
- Leaders can lie, bluff, or betray based on their personality

### Civilization Mechanics (Civ-like)
- Resource management (food, production, gold, science, culture)
- City building and expansion
- Technology tree progression
- Military units and combat
- Map exploration (fog of war)

### AI Agent System
- Each AI civilization runs as an independent agent
- Agents have access to their civilization's game state
- Agents make strategic decisions (what to build, where to expand, when to attack)
- Agents interact with each other (not just the player) — forming alliances, declaring wars

## MVP Scope

| Include (MVP) | Defer (Later) |
|---|---|
| Hex grid map (small, ~20x20) | Large procedural maps |
| Cities, units (military + settler) | Religion, espionage, great people |
| Basic resources (food, production, gold) | Luxury/strategic resources, trade routes |
| Tech tree (simplified, ~20 techs) | Full tech tree (70+) |
| War & basic diplomacy (peace/war/alliance) | Complex diplomacy (embargoes, world congress) |
| 3-4 AI civilizations | Dozens of civs |
| Win by domination or score | Cultural, science, diplomatic victories |

## Comic Generation Approach

Two viable paths:

1. **AI image generation** (DALL-E / Stable Diffusion) — generate actual comic panels per turn
2. **Template-based comics** — pre-drawn panel templates + speech bubbles filled by LLM text

**Recommendation:** Start with option 2 (template-based). Faster, cheaper, more consistent in style, avoids latency/cost of image generation per turn. Upgrade to full AI generation later.

### Comic Generation Pipeline

1. **Event Ranker** — pick 3-4 most interesting events from the turn
2. **Narrative Writer** (Claude) — generate panel descriptions and dialogue
3. **Panel Composer** — select templates from pre-drawn asset library, insert character sprites, generate speech bubbles
4. **Display** — show comic strip to player with "Next Turn" button

Event ranking heuristics: War declarations > first contact > wonders built > cities founded > tech breakthroughs > routine production

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | Next.js + React + Pixi.js | Game map rendering (Pixi.js/hex grid), UI panels (React), Comic viewer |
| **Backend** | Python (FastAPI) | Game engine (turn resolution), AI agent orchestration, Comic generation pipeline |
| **AI Layer** | Claude API | Agent personalities, decisions, narration. Image gen API for comics (later) |
| **Data Layer** | PostgreSQL + Redis | PostgreSQL for game state/saves. Redis for turn queue, caching, hot read path |

### Why This Stack

- **Python backend** — best ecosystem for AI/LLM integration, game logic is CPU-light
- **Next.js frontend** — good DX, SSR for initial load, React ecosystem for UI
- **Pixi.js** — performant 2D canvas rendering for the hex map (avoids DOM overhead)
- **PostgreSQL** — relational fits game state well (entities, relationships, history)

## AI Agent Architecture

Each AI leader gets:
- **A personality prompt**: e.g., "You are Genghis Khan. Aggressive, expansionist, values military strength. You distrust neighbors who build cities near your borders."
- **A filtered game state**: Only what they can "see" (fog of war)
- **A structured action schema**: The LLM picks from valid actions (build unit, move unit, declare war, propose alliance, research tech, etc.) — no freeform, prevents hallucinated actions
- **Memory**: Short summary of past turns, diplomatic history, grudges

### Diplomacy Chat System

The AI leaders are fully conversational — the player can freely chat with them at any time.

**Key design points:**

- **Persistent conversation threads** — each leader remembers your full chat history with them. "You promised me peace 10 turns ago" should be possible.
- **Personality bleeds into everything** — a warlike leader is terse and threatening; a scholarly one is verbose and proposes research pacts. The system prompt defines tone, vocabulary, priorities, and even lying/trustworthiness tendencies.
- **Chat can trigger game actions** — if the player negotiates a trade deal in chat and the AI agrees, the agent calls a tool (propose_trade) which the game engine validates and executes. Conversation has mechanical consequences.
- **AI leaders talk to each other** — between turns, AI civs can initiate diplomacy with each other (shorter, summarized exchanges). These show up in the comic or turn log.
- **Deception is possible** — an untrustworthy leader's system prompt might say: "You may agree to peace deals you intend to break. You may lie about your military strength."

### Context Window Strategy

1. Keep last ~20 messages in full
2. Summarize older messages into a "diplomatic memory" block
3. Always inject current game state (resources, military strength, relations) fresh each call
4. AI-to-AI diplomacy uses shorter exchanges (3-5 messages max, then summarize outcome)

### Leader Chat Tools

```python
LEADER_CHAT_TOOLS = [
    {"name": "propose_trade", "params": {"offer": {...}, "request": {...}, "duration_turns": int}},
    {"name": "declare_war"},
    {"name": "offer_peace", "params": {"terms": str}},
    {"name": "offer_alliance"},
    {"name": "share_intel", "params": {"info": str, "truthful": bool}},  # truthful hidden from player
    {"name": "make_demand", "params": {"demand": str, "or_else": str}},
    {"name": "reject_proposal"},
]
```

## Data Model (Core)

```
Game
├── id, name, turn_number, status, settings
│
├── Map
│   └── Tile[] (q, r hex coords, terrain, resource, owner, improvements)
│
├── Civilization[]
│   ├── id, name, leader_name, personality_prompt, is_human
│   ├── gold, science, culture
│   ├── known_techs[]
│   ├── cities[]
│   │   ├── name, location, population, production_queue[]
│   │   └── buildings[]
│   └── units[]
│       ├── type, location, health, moves_remaining
│       └── orders (move_to, attack, fortify, settle)
│
├── DiplomaticRelation[]
│   ├── civ_a, civ_b, status (peace/war/alliance)
│   └── history[] (events that shaped the relationship)
│
├── ConversationThread[] (per leader-pair: player↔AI, AI↔AI)
│   └── messages[], summaries[]
│
└── TurnLog[]
    ├── turn_number
    ├── events[] (unit_moved, city_founded, war_declared, tech_researched...)
    └── comic_panels[] (generated comic for this turn)
```

## Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (Next.js)                          │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────┐ │
│  │  Game Map     │  │  Diplomacy   │  │  Comic     │  │  Game UI  │ │
│  │  (Pixi.js)   │  │  Chat Panel  │  │  Viewer    │  │  Panels   │ │
│  └──────────────┘  └──────────────┘  └────────────┘  └───────────┘ │
│                                                                      │
│              REST/WS API      SSE (chat stream)       REST API       │
└──────────────────────────────────────────────────────────────────────┘
                                 │
═════════════════════════════════╪═══════════════════════════════════════
                                 │
┌────────────────────────────────┼──────────────────────────────────────┐
│                        BACKEND (FastAPI)                              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                        API Layer                                │ │
│  │  /game    /game/{id}/chat/{civ}    /game/{id}/turn    /comic    │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────┐  ┌─────────────────┐  ┌────────────────────┐   │
│  │  Game Engine   │  │  Agent System   │  │  Comic Pipeline   │   │
│  │  - Map gen     │  │  - Leader mgr   │  │  - Event ranker   │   │
│  │  - Turn loop   │  │  - Chat handler │  │  - Narrator       │   │
│  │  - Combat      │  │  - Decision eng │  │  - Panel composer │   │
│  │  - Production  │  │  - Memory mgr   │  │  - Asset selector │   │
│  │  - Tech tree   │  │  - Diplomacy    │  │                   │   │
│  │  - Validation  │  │  - AI↔AI talks  │  │                   │   │
│  └────────────────┘  └─────────────────┘  └────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Service Layer: GameService | AgentService | ComicService      │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                                 │
═════════════════════════════════╪═══════════════════════════════════════
                                 │
┌────────────────────────────────┼──────────────────────────────────────┐
│                         DATA LAYER                                    │
│  ┌───────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │   Claude API  │  │   PostgreSQL    │  │   Redis                 │ │
│  │  - Agent chat │  │  - Game state   │  │  - Turn action queue    │ │
│  │  - Decisions  │  │  - Map data     │  │  - Chat session cache   │ │
│  │  - Narration  │  │  - Chat logs    │  │  - Game state snapshot  │ │
│  └───────────────┘  │  - Turn logs    │  └─────────────────────────┘ │
│                     └─────────────────┘                               │
└───────────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
ai-civilization/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, lifespan
│   │   ├── config.py                # Settings (env vars, defaults)
│   │   ├── database.py              # SQLAlchemy engine, sessions
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   │   ├── game.py
│   │   │   ├── map.py
│   │   │   ├── civilization.py
│   │   │   ├── technology.py
│   │   │   ├── diplomacy.py
│   │   │   ├── conversation.py
│   │   │   └── turn.py
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── routers/                 # API endpoints
│   │   │   ├── games.py
│   │   │   ├── actions.py
│   │   │   ├── turns.py
│   │   │   ├── chat.py             # Diplomacy chat (SSE streaming)
│   │   │   └── comics.py
│   │   ├── engine/                  # Pure game logic (no I/O)
│   │   │   ├── map_generator.py
│   │   │   ├── turn_resolver.py
│   │   │   ├── combat.py
│   │   │   ├── production.py
│   │   │   ├── movement.py
│   │   │   ├── technology.py
│   │   │   ├── fog_of_war.py
│   │   │   ├── victory.py
│   │   │   └── validation.py
│   │   ├── agents/                  # AI civilization system
│   │   │   ├── leader.py
│   │   │   ├── personalities/
│   │   │   ├── decision.py
│   │   │   ├── chat_handler.py
│   │   │   ├── memory.py
│   │   │   ├── tools.py
│   │   │   └── state_serializer.py
│   │   ├── comic/                   # Comic generation pipeline
│   │   │   ├── event_ranker.py
│   │   │   ├── narrator.py
│   │   │   ├── panel_composer.py
│   │   │   └── templates/
│   │   └── services/
│   │       ├── game_service.py
│   │       ├── turn_service.py
│   │       ├── agent_service.py
│   │       └── comic_service.py
│   ├── data/                        # Game data definitions
│   │   ├── tech_tree.json
│   │   ├── units.json
│   │   ├── buildings.json
│   │   └── terrains.json
│   ├── migrations/
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── app/                     # Next.js app router
│   │   ├── components/
│   │   │   ├── game/                # GameMap, HexTile, UnitSprite, FogOverlay
│   │   │   ├── panels/             # CityPanel, TechTree, UnitPanel, Scoreboard
│   │   │   ├── diplomacy/          # ChatPanel, ChatThread, LeaderPortrait
│   │   │   └── comic/              # ComicViewer, ComicPanel, ComicStrip
│   │   ├── hooks/                   # useGame, useChat, useMap, useActions
│   │   ├── lib/                     # api.ts, hex.ts, types.ts
│   │   └── assets/                  # sprites, tiles, leaders, comic templates
│   └── package.json
│
├── docker-compose.yml
└── README.md
```

### Key Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Game engine purity | Engine module has zero I/O — pure functions taking state, returning new state | Testable, deterministic, no side effects |
| AI call parallelism | All AI civs decide concurrently via asyncio.gather | 4 AI civs × 2s each = 2s total, not 8s |
| Chat streaming | SSE (Server-Sent Events), not WebSocket | Simpler, one-direction stream is all we need for chat responses |
| State snapshots | Redis caches current game state; Postgres is source of truth | Fast reads for AI context building; durable saves |
| Conversation memory | Rolling window (20 msgs) + LLM summary of older history | Bounded context window, unbounded conversation length |
| Action validation | Engine validates all actions — AI and human alike | AI can't cheat; invalid LLM output gets rejected gracefully |
| Comic generation | Async — doesn't block turn resolution | Player sees turn results immediately, comic appears shortly after |

## Core Flows

### Turn Resolution

1. Player clicks "End Turn"
2. Validate & queue player actions
3. **AI Decision Phase** (parallel per AI civ):
   - Serialize visible game state (fog-of-war filtered)
   - Run AI↔AI diplomacy (if any)
   - Call Claude → structured actions
   - Validate actions
4. **Resolve all actions** (deterministic order): Movement → Combat → Production → Growth → Research → Diplomacy → Victory check
5. Record TurnEvents
6. Generate comic (async): Rank events → Claude writes narrative → Compose panel strip
7. Return turn results + comic to frontend

### Diplomacy Chat

1. Player sends message → `POST /game/{id}/chat/{civ_id}` (SSE stream)
2. Load conversation thread (last 20 msgs) + diplomatic memory summary
3. Inject current game state snapshot (military balance, resources, borders, treaties)
4. Build system prompt: personality + state + memory + available tools
5. Stream Claude response (text streams to frontend in real-time)
6. If tool called (propose_trade, declare_war) → validate & execute via game engine
7. Save message pair to conversation thread
8. If thread > 20 msgs, summarize oldest batch

## Phased Implementation Plan

### Phase 1: Core Game Engine (Foundation)
- Hex grid map generation (terrain, basic resources)
- Civilization data model (cities, units, resources)
- Turn resolution loop (production, growth, movement, combat)
- Basic unit types: Warrior, Settler, Scout
- City founding and growth mechanics
- Simplified tech tree (~20 techs)
- No AI, no frontend — pure game logic with tests

### Phase 2: Frontend — Map & Game UI
- Pixi.js hex grid renderer
- Camera controls (pan, zoom)
- Tile info panel, city panel, unit panel
- Turn controls (end turn button, turn counter)
- Unit movement (click to select, click to move)
- Basic fog of war rendering
- Connect to backend via REST API

### Phase 3: AI Agents
- Leader personality system (system prompts per civ)
- Game state → LLM prompt serialization (fog-of-war filtered)
- Structured action output (Claude tool use for valid actions)
- Decision loop: each AI civ submits actions per turn
- Basic diplomacy: war/peace declarations, alliance proposals
- AI memory: turn summaries, diplomatic grudges
- **Full conversational diplomacy** — player can chat freely with any AI leader

### Phase 4: Comic Generation
- Event ranking system (score events by "interestingness")
- Narrative writer (Claude generates panel descriptions)
- Template-based comic composer (pre-drawn panels + text overlays)
- Comic viewer component in frontend
- Turn transition flow: resolve → generate comic → display → next turn

### Phase 5: Polish & Gameplay
- Combat balancing
- AI difficulty tuning
- Sound effects / music
- Save/load game
- Multiple map sizes
- Additional unit types and buildings
- Win conditions (domination, score)

### Phase 6: Advanced Features (Post-MVP)
- Full AI image generation for comics (DALL-E/Flux)
- Complex diplomacy (trade, embargoes, joint wars)
- Multiplayer (multiple humans + AI)
- Map editor
- More civilizations and leaders

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| AI agent latency (LLM calls per civ per turn) | HIGH | Parallelize AI decisions; cache/batch; use Haiku for simple decisions |
| AI making invalid/nonsensical moves | HIGH | Structured output with strict action validation; fallback to rule-based AI |
| Comic generation quality/consistency | MEDIUM | Start template-based; curate asset library; iterate on prompts |
| Game balance (AI too strong/weak) | MEDIUM | Tune via difficulty settings; playtest early |
| Scope creep (Civ is enormous) | HIGH | Stick to MVP scope ruthlessly; defer features to Phase 6 |
| Frontend performance (large maps) | MEDIUM | Pixi.js handles this well; viewport culling; keep map small for MVP |

## Viability Assessment

**Strengths:**
- AI leaders you can actually talk to is a genuine innovation — no strategy game has done this well yet
- Diplomacy chat clips are inherently shareable (built-in viral marketing)
- Turn-based format fits LLM latency constraints perfectly
- Comic recaps make every turn shareable

**Challenges:**
- Even the MVP scope is months of work — the game must be fun as a strategy game independent of the AI gimmick
- AI costs: every turn fires multiple LLM calls per AI civ, plus comic narration — needs a monetization model that covers it
- Competing with Civ/Humankind/Old World studios with hundreds of people — can't win on depth
- Art quality needed for commercial success

**Strategic positioning:** Don't compete as a strategy game — position as an "AI diplomacy sandbox with strategy mechanics" where the conversations are the main event and the map is the stage. Lean hard into the AI interaction, keep the strategy layer simple.

## Status

- **Phase**: Planning complete — architecture and tech stack defined
- **Next step**: Begin Phase 1 implementation — game engine, hex map, data models
