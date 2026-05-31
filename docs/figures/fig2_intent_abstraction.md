# Figure 2: Intent-Based LLM Abstraction Layer

**Caption**: Two-layer architecture separating strategic LLM reasoning from deterministic tactical execution through intent-based abstraction.

```mermaid
graph TD
    %% ── Styling ──
    classDef llmLayer fill:#7c3aed,color:#fff,stroke:#6d28d9,stroke-width:2px
    classDef intentLayer fill:#2563eb,color:#fff,stroke:#1d4ed8,stroke-width:2px
    classDef opsLayer fill:#16a34a,color:#fff,stroke:#15803d,stroke-width:2px
    classDef execLayer fill:#ea580c,color:#fff,stroke:#c2410c,stroke-width:2px
    classDef engineLayer fill:#dc2626,color:#fff,stroke:#b91c1c,stroke-width:2px
    classDef annotation fill:#fef3c7,color:#92400e,stroke:#f59e0b,stroke-width:1px,stroke-dasharray: 3 3
    classDef intentBox fill:#dbeafe,color:#1e40af,stroke:#3b82f6,stroke-width:1px

    %% ── LAYER 1: LLM Strategic Reasoning ──
    subgraph L1["  STRATEGIC LAYER — LLM (OpenAI tool-use API)  "]
        direction TB
        sysprompt["📋 System Prompt<br/>BASE_SYSTEM_PROMPT + Persona<br/>(Genghis / Cleopatra / Gandhi)"]
        localview["👁️ Fog-Filtered Local View<br/>serialize.local_view(state, civ_id)<br/>visible_tiles · visible_units · known_civs"]
        memory["🧠 Rolling Memory<br/>Last 8 turns of intents<br/>Last 32 diplomatic messages"]
        llm["🤖 LLM (GPT-4)<br/>Receives: system prompt + local view + memory<br/>Reasoning: strategic goals, diplomacy, threats"]
        sysprompt --> llm
        localview --> llm
        memory --> llm
    end

    %% ── LAYER 2: Intent Emission ──
    subgraph L2["  INTENT LAYER — 9 High-Level Tool Calls  "]
        direction LR
        i1["🏗️ expand<br/>Found new city"]
        i2["🔭 scout<br/>Explore unknown"]
        i3["⚔️ engage<br/>Wage war on civ"]
        i4["🛡️ reinforce<br/>Defend position"]
        i5["💬 speak<br/>Diplomatic message"]
        i6["🤝 adjust_stance<br/>Set peace/war/alliance"]
        i7["🏭 build<br/>Queue unit production"]
        i8["📚 research<br/>Set research tech"]
        i9["🔧 improve<br/>Build tile improvement"]
    end

    %% ── LAYER 3: Operations Resolution ──
    subgraph L3["  OPERATIONS LAYER — Deterministic Python  "]
        direction TB
        resolve["⚙️ resolve_intents()<br/>operations.py"]
        goals["Intent → Goals<br/>Expand → FoundCityNear<br/>Engage → DeclareWar + AttackUnit<br/>Scout → MoveTo(edge of fog)"]
        diplomacy["Intent → Diplomacy<br/>Speak → SendMessage<br/>AdjustStance → SetStance"]
        directives["Intent → Directives<br/>Build → EnqueueUnit<br/>Research → SetResearching<br/>Improve → BuildImprovement"]
        resolve --> goals
        resolve --> diplomacy
        resolve --> directives
    end

    %% ── LAYER 4: Tactical Execution ──
    subgraph L4["  TACTICAL LAYER — Deterministic Python  "]
        direction TB
        executor["🏃 executor.py<br/>Goals → Primitive Actions"]
        pathfinding["A* Pathfinding<br/>hex.py · axial coords"]
        combat["Combat Resolution<br/>combat.py · melee math"]
        validation["Rule Validation<br/>Occupancy · movement budget · preconditions"]
        executor --> pathfinding
        executor --> combat
        executor --> validation
    end

    %% ── LAYER 5: Game Engine ──
    subgraph L5["  GAME ENGINE — Pure Functional · Frozen Dataclasses  "]
        direction TB
        apply["✅ Apply Actions → New GameState<br/>dataclasses.replace() — immutable mutations"]
        state["📦 GameState<br/>map · civs · cities · units · diplomacy · visibility"]
        apply --> state
    end

    %% ── Flow Arrows ──
    llm -->|"Tool calls<br/>(no unit IDs, no raw coords)"| L2
    L2 -->|"Intent dataclasses"| resolve
    goals --> executor
    diplomacy --> executor
    directives --> executor
    executor --> apply

    %% ── Side Annotations ──
    note1["🔒 LLM NEVER touches<br/>GameState directly.<br/>Only sees serialized JSON<br/>via serialize.py"]
    note2["✅ All actions validated<br/>before execution.<br/>Machine-readable error codes<br/>for LLM feedback."]
    note3["🎲 Deterministic, reproducible.<br/>Same seed → same map,<br/>same outcomes.<br/>secrets.randbits(31)"]

    %% ── Example Trace ──
    subgraph example["  EXAMPLE: Engage Intent → Actions  "]
        direction LR
        e1["LLM calls:<br/>engage(target_civ_id=2)"]
        e2["Resolves to:<br/>DeclareWar(civ_id=2)<br/>+ MoveTo(unit_id=5, Hex(3,4))<br/>+ AttackUnit(unit_5, unit_8)"]
        e3["Engine validates:<br/>✓ War declared<br/>✓ Unit 5 has moves<br/>✓ Unit 8 in range<br/>→ Apply damage"]
        e1 --> e2 --> e3
    end

    %% ── Apply classes ──
    class L1,sysprompt,localview,memory,llm llmLayer
    class L2,i1,i2,i3,i4,i5,i6,i7,i8,i9 intentLayer
    class L3,resolve,goals,diplomacy,directives opsLayer
    class L4,executor,pathfinding,combat,validation execLayer
    class L5,apply,state engineLayer
    class note1,note2,note3 annotation
    class example,e1,e2,e3 annotation
```

## Architecture Principles

### Intent Abstraction
The LLM operates at the **strategic** level — it declares *what* it wants to do, never *how* to do it. Intents are semantic and high-level:
- `Expand` — "I want a new city" (engine picks settler + site)
- `Engage` — "Attack Egypt" (engine auto-declares war, picks closest unit + target)
- `Scout` — "Explore unknown territory" (engine picks scout unit + fog edge)

### Why This Decoupling Matters

| Problem | Without Abstraction | With Intent Abstraction |
|---------|-------------------|------------------------|
| **Hallucinated unit IDs** | LLM invents non-existent `unit_id=42` | LLM calls `engage(target_civ_id=2)`, engine finds valid units |
| **War precondition** | LLM forgets to declare war, attacks illegally | `Engage` auto-declares war if needed |
| **Self-targeting** | LLM declares war on itself | Tools reject `target_civ_id == self` |
| **State corruption** | LLM writes directly to GameState | LLM never touches GameState — only reads serialized JSON view |
| **Reproducibility** | Non-deterministic LLM outputs | Deterministic resolution layer ensures same intents → same outcomes |

### Graceful Degradation

If `OPENAI_API_KEY` is missing or API calls fail, the system falls back to `RandomGoalSource` — a deterministic random agent that keeps the game playable. This is implemented in `backend/app/engine/playthrough.py` via the `GoalSource` protocol.

### Key Source Files

| File | Purpose |
|------|---------|
| `backend/app/engine/openai_goals.py` | OpenAI tool-use GoalSource, 9 tool definitions, system prompt builder |
| `backend/app/engine/intents.py` | 9 frozen dataclass Intent types (Expand, Scout, Engage, etc.) |
| `backend/app/engine/operations.py` | `resolve_intents()` — Intent → Goal + DiplomaticAction + Directive |
| `backend/app/engine/serialize.py` | `local_view()` — fog-filtered JSON for LLM consumption |
| `backend/app/engine/executor.py` | Goal → primitive Action resolution with A* pathfinding |
| `backend/app/engine/playthrough.py` | `GoalSource` protocol, `run_playthrough()` headless loop |
