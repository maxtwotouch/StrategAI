# StrategAI Agent System

This directory contains the multi-agent system for StrategAI, an INF-3600 Generative AI student project. The system supports both **GitHub Copilot** and **Claude Code** harnesses.

## Architecture Overview

```
Root Orchestrator (cross-project coordination)
├─ Planner (implementation planning & task decomposition)
├─ AI Showcase (report/presentation generation)
├─ Research (read-only exploration)
├─ Integration Tester (cross-project validation)
├─ Backend Specialist
│  └─ backend/.github/agents/
│     ├─ Orchestrator
│     ├─ Game Engine
│     └─ LLM Integration
├─ Frontend Specialist
│  └─ frontend/.github/agents/
│     ├─ Orchestrator
│     └─ UI Engineer
├─ Asset Server (existing)
│  └─ assetserver/.github/agents/
│     ├─ Orchestrator
│     ├─ Implementation
│     ├─ API Designer
│     ├─ Planner
│     ├─ Research
│     ├─ Test Engineer
│     ├─ Code Reviewer
│     ├─ Documentation Engineer
│     ├─ Database Architect
│     ├─ Workflow Engineer
│     └─ Security Auditor
└─ Dataset/Training (existing)
   └─ dataset-gen-train/.github/agents/
      ├─ Orchestrator
      ├─ Training
      ├─ Dataset
      ├─ Publishing
      └─ Code Quality
```

## Agent Roster

### Root-Level Agents (`.github/agents/`)

| Agent | File | Purpose | When to Use |
|-------|------|---------|-------------|
| **Orchestrator** | `orchestrator.agent.md` | Cross-project coordination | Multi-subproject features, integration work |
| **Planner** | `planner.agent.md` | Implementation planning | Architecture design, task decomposition, complex features |
| **AI Showcase** | `ai-showcase.agent.md` | Report/presentation generation | Documenting AI/ML aspects for student report |
| **Research** | `research.agent.md` | Read-only exploration | Understanding codebase, tracing data flow |
| **Integration Tester** | `integration-tester.agent.md` | Cross-project validation | API contracts, asset manifest resolution |
| **Backend** | `backend.agent.md` | Backend specialist | Game engine, LLM integration, API |
| **Frontend** | `frontend.agent.md` | Frontend specialist | Next.js UI, state management, assets |

### Subproject Agents

#### Backend (`backend/.github/agents/`)

| Agent | File | Purpose |
|-------|------|---------|
| **Orchestrator** | `orchestrator.agent.md` | Backend task coordination |
| **Game Engine** | `game-engine.agent.md` | Pure functional engine, combat, economy |
| **LLM Integration** | `llm-integration.agent.md` | OpenAI tool-use, diplomacy, personas |

#### Frontend (`frontend/.github/agents/`)

| Agent | File | Purpose |
|-------|------|---------|
| **Orchestrator** | `orchestrator.agent.md` | Frontend task coordination |
| **UI Engineer** | `ui-engineer.agent.md` | React components, state, API integration |

#### Asset Server (`assetserver/.github/agents/`)

11 specialist agents covering implementation, API design, testing, code review, documentation, database, workflows, and security. See `assetserver/.github/agents/` for details.

#### Dataset/Training (`dataset-gen-train/.github/agents/`)

5 specialist agents covering training, dataset generation, publishing, and code quality. See `dataset-gen-train/.github/agents/` for details.

## Cross-Harness Compatibility

### GitHub Copilot

**Format**: `.agent.md` files with YAML frontmatter

**Location**: `.github/agents/` (root and subprojects)

**Invocation**: 
- Automatic: Copilot selects agents based on task context
- Manual: Use `@agent-name` in chat

**Example**:
```
@Orchestrator Add a new unit type across backend, frontend, and asset server
```

### Claude Code

**Format**: `AGENTS.md` files (Markdown with structured sections)

**Location**: Root and each subproject

**Invocation**:
- Automatic: Claude reads `AGENTS.md` for project context
- Manual: Reference agent names in conversation

**Example**:
```
Use the Orchestrator agent to coordinate adding a new unit type
```

## Delegation Patterns

### Cross-Project Task

```Planner (design implementation plan)
         ├─ Research (explore affected code)
         └─ Write plan with phases
              ↓
User → Root Orchestrator (execute plan
         ├─ Research (explore affected code)
         ├─ Backend Specialist (engine changes)
         │  └─ backend/Orchestrator
         │     └─ Game Engine agent
         ├─ Frontend Specialist (UI changes)
         │  └─ frontend/Orchestrator
         │     └─ UI Engineer agent
         ├─ Integration Tester (validate contracts)
         └─ AI Showcase (document for report)
```

### Single-Subproject Task

```
User → Subproject Orchestrator
         ├─ Specialist agent 1
         ├─ Specialist agent 2
         └─ Test/Review agents
```

## Quality Gates

All orchestrators enforce these gates before marking tasks complete:

1. **Tests pass**: Subproject test suites green
2. **Types check**: TypeScript/mypy validation
3. **Conventions followed**: Project-specific rules
4. **No regressions**: Existing functionality intact
5. **Integration valid**: Cross-project contracts match (for multi-subproject tasks)

## Project Conventions

### Universal Rules

- **Seeds**: `secrets.randbits(31)` — never `random`
- **Atomic writes**: temp file + `os.rename` for file I/O
- **Config**: `config.yaml` for defaults, `.env` for overrides

### Backend-Specific

- **Frozen dataclasses**: `@dataclass(frozen=True)` for all state
- **Result types**: `ValidationResult` (Ok/Error), never throw for LLM-facing code
- **Error codes**: Machine-readable strings for LLM feedback

### Asset Server-Specific

- **DB sessions**: `with SessionLocal() as db:` context manager
- **Orphan cleanup**: `_try_remove_asset()` on DB persist failure
- **Async safety**: No blocking calls in async context

### Frontend-Specific

- **State management**: React `useState` + `useRef` + `useMemo`
- **API calls**: All through `lib/api.ts` methods
- **Asset fallback**: Generated → static → color/glyph/initial

## AI Technologies (Course Relevance)

| Component | Technology | Location |
|-----------|-----------|----------|
| **LLM-driven AI civs** | OpenAI tool-use API | `backend/app/engine/openai_goals.py` |
| **Diplomacy chat** | LLM with persistent conversation | `backend/app/engine/diplomacy.py` |
| **Generative pixel art** | ComfyUI + FLUX2 Klein 4B Distilled (DiT) | `assetserver/src/` |
| **Style adaptation** | LoRA fine-tuning | `dataset-gen-train/` |

## Inter-Service Contracts

- **Frontend ↔ Backend**: REST API at `http://localhost:8000`, 16 endpoints
- **Frontend ↔ Asset Server**: Asset manifest via `NEXT_PUBLIC_ASSET_API_URL`
- **Backend ↔ Asset Server**: No direct contract (frontend mediates)
- **Asset Server ↔ Dataset/Training**: Shared ComfyUI + FLUX2 Klein 4B Distilled model

## Documentation

- **Root**: `AGENTS.md` (Claude Code), `README.md` (project overview)
- **Backend**: `backend/AGENTS.md`, `docs/ARCHITECTURE.md`
- **Frontend**: `frontend/AGENTS.md`, `frontend/docs/UI_GUIDE.md`
- **Asset Server**: `assetserver/AGENTS.md`, `assetserver/docs/project-report.md`
- **Dataset/Training**: `dataset-gen-train/AGENTS.md`, `dataset-gen-train/docs/`

## Maintenance

### Adding a New Agent

1. Create `.agent.md` file in appropriate `.github/agents/` directory
2. Use standard frontmatter format (see existing agents)
3. Add to `AGENTS.md` roster table
4. Update this README's architecture diagram
5. Test with both GitHub Copilot and Claude Code

### Updating Agent Behavior

1. Edit the `.agent.md` file
2. Update corresponding `AGENTS.md` section if needed
3. Test with representative tasks
4. Document changes in commit message

### Cross-Project Changes

When modifying inter-service contracts:
1. Use Root Orchestrator to coordinate
2. Update both provider and consumer
3. Run Integration Tester to validate
4. Update `AGENTS.md` contract documentation

## Support

For questions about the agent system:
- Check this README first
- Review `AGENTS.md` for project context
- Consult subproject-specific `AGENTS.md` files
- Use the Research agent for codebase exploration
