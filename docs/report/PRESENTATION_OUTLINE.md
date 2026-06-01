# StrategAI Oral Presentation - Complete Slide Deck

**Duration**: 7-8 minutes presentation + questions  
**Format**: All team members must participate  
**Focus**: AI/ML innovations and course concept application

---

## Slide 1: Title & Team (30 seconds)

**Visual**: 
- StrategAI logo/title
- Team member names and roles
- Background: Screenshot of game with AI-generated assets

**Bullet Points**:
- StrategAI: AI-Driven Civilization Strategy Game
- INF-3600 Generative AI Project
- Team: [Names and roles]

**Speaker Notes** (30 seconds):
"Good morning. We're team [name], and we built StrategAI - a Civilization-style strategy game where AI civilizations are controlled by Large Language Models and game assets are generated on-demand using Diffusion Transformers. Our team consists of [introduce members and their primary contributions]. Today we'll show you how we integrated multiple generative AI technologies into a cohesive, playable game."

**Transition**: "Let's start with the problem we're solving."

---

## Slide 2: Motivation & Problem (45 seconds)

**Visual**:
- Split screen: Left side shows "Problem" with icons (GPU, dollar sign, complexity), Right side shows "Solution" with checkmarks
- Key statistic: "Workstation GPU: 14-16 GB VRAM (FP8)"

**Bullet Points**:
- **Problem**: Independent developers lack access to advanced AI
  - Computational constraints (24+ GB VRAM required)
  - Integration complexity (multiple AI systems)
  - Cost barriers (cloud APIs, recurring fees)
- **Solution**: Demonstrate feasibility on consumer hardware
  - GPT-5.4-mini for strategic reasoning
  - FLUX.2 Klein 4B Distilled for asset generation
  - Real-time performance: 2.5-6 seconds per asset (Blackwell RTX 6000)

**Speaker Notes** (45 seconds):
"Independent game developers face two fundamental challenges when trying to incorporate advanced AI. First, computational constraints - state-of-the-art models often require enterprise-grade hardware with 24+ gigabytes of VRAM, far exceeding typical development budgets. Second, integration complexity - combining multiple AI systems like language models and image generators requires careful architectural design.

Our solution demonstrates that these challenges can be overcome. By selecting appropriately-sized models - GPT-5.4-mini for reasoning and FLUX.2 Klein 4B Distilled for generation - and implementing robust system design, we achieve real-time performance on workstation hardware with 14 to 16 gigabytes of VRAM using FP8 precision. Asset generation takes only 2.5 to 6 seconds on a Blackwell RTX 6000, or 3.5 to 7 seconds on an RTX 3090, enabling near-interactive gameplay."

**Transition**: "Let me show you the system architecture that makes this possible."

---

## Slide 3: System Architecture (60 seconds)

**Visual**:
- **Fig. 1**: System architecture diagram showing four components
- Technology stack labels on each component
- Data flow arrows with protocol labels

**Bullet Points**:
- **Four components**:
  - Backend: Python/FastAPI, game engine, LLM integration
  - Frontend: Next.js, React, SVG rendering
  - Asset Server: FastAPI, ComfyUI, FLUX.2 Klein 4B Distilled
  - Training Pipeline: Ostris AI Toolkit, LoRA fine-tuning
- **Data flow**:
  - User actions → Backend API → Game state updates
  - LLM decisions → Intent resolution → Deterministic execution
  - Asset requests → ComfyUI → Generated images
- **Key insight**: Microservices enable independent scaling

**Speaker Notes** (60 seconds):
"Our system follows a microservices architecture with four primary components. The backend, built with Python and FastAPI, implements a pure functional game engine with immutable state and integrates GPT-5.4-mini for AI decision-making. The frontend, using Next.js and React, renders the game state through an SVG-based hex map and coordinates asset loading.

The asset server is a separate FastAPI service that generates pixel-art assets on-demand using ComfyUI and FLUX.2 Klein 4B Distilled - a 4-billion parameter Diffusion Transformer. Finally, our training pipeline uses the Ostris AI Toolkit to fine-tune LoRA adapters that adapt the base model to our specific visual style.

The key architectural insight is that these components communicate through well-defined APIs, enabling independent scaling and deployment. The backend handles game logic, the asset server handles generation, and they can be scaled separately based on demand.

A third AI modality---OpenAI TTS---generates an epic voiced narration at
game start. When the player clicks "Begin Campaign," the frontend constructs
a personalized campaign script, the backend calls OpenAI's TTS API with
theatrical narrator instructions, and the generated voiceover plays over
ducked ambient music."

**Transition**: "Now let's dive into the first major AI innovation - how we use LLMs to control AI civilizations."

---

## Slide 4: LLM-Driven Strategic AI (90 seconds) ⭐

**Visual**:
- **Fig. 2**: Intent-based abstraction layer diagram
- Code snippet showing intent dataclass
- Screenshot of AI making a decision

**Bullet Points**:
- **Challenge**: LLMs excel at reasoning but struggle with spatial logic
- **Solution**: Intent-based abstraction
  - LLM emits high-level intents (expand, engage, reinforce)
  - Engine resolves intents into specific actions
  - Deterministic execution ensures rule compliance
- **Nine intent types**: expand, scout, engage, reinforce, speak, adjust_stance, build, research, improve
- **Three AI civilizations** with distinct personas:
  - Genghis Khan: Aggressive expansionist
  - Cleopatra: Diplomatic manipulator
  - Gandhi: Peaceful developer
- **Memory system**: Rolling window of 8 turns + 32 messages

**Speaker Notes** (90 seconds):
"The first major challenge we solved was how to use LLMs to control game entities. Direct control presents several problems - LLMs struggle with spatial reasoning like calculating hex distances, they make arithmetic errors in combat formulas, and they can't reliably enforce game rules.

Our solution is an intent-based abstraction layer. Instead of letting the LLM directly manipulate game state, it emits high-level strategic intents. For example, the LLM might emit an 'engage' intent targeting an enemy civilization. The deterministic engine then resolves this intent into specific actions - it finds military units, selects targets using pathfinding algorithms, and validates all moves against game rules.

We define nine intent types covering all strategic decisions: expand for founding cities, engage for warfare, reinforce for defense, speak for diplomacy, and so on. Each intent is a frozen dataclass with optional parameters.

We implement three AI civilizations, each with a distinct persona that influences decision-making. Genghis Khan is an aggressive expansionist who values conquest. Cleopatra is a diplomatic manipulator who forms alliances and plays factions against each other. Gandhi is a peaceful developer focused on science and culture. These personas are appended to the system prompt, enabling diverse strategic behaviors while sharing the same underlying intent system.

The LLM maintains a rolling memory of the last 8 turns and 32 diplomatic messages, enabling it to adapt strategies and respond to changing conditions."

**Demo** (if time permits):
"Let me show you this in action. [Show game running] Here you can see Genghis Khan deciding to engage Egypt. The LLM emitted an engage intent, and the engine is now resolving it - selecting the closest warrior unit, pathfinding to the Egyptian city, and executing the attack. All of this happens deterministically while the LLM focuses on the strategic decision."

**Transition**: "The second major innovation is our asset generation pipeline using Diffusion Transformers."

---

## Slide 5: Diffusion Transformer Asset Pipeline (90 seconds) ⭐

**Visual**:
- **Fig. 3**: Four-layer prompt architecture diagram
- **Fig. 4**: Three-stage leader pipeline diagram
- Sample generated assets (structure, unit, leader portrait)

**Bullet Points**:
- **Model**: FLUX.2 Klein 4B Distilled
  - 4 billion parameters, FP8 quantization
  - 4-step distilled inference (~1.2 seconds)
  - Apache 2.0 license (commercial use)
- **Four-layer prompt architecture**:
  1. Workflow configuration (ComfyUI JSON)
  2. Style templates (camera framing, quality tags)
  3. Semantic descriptions (enum vocabularies)
  4. Assembly logic (template rendering)
- **Six asset families**: structures, objects, terrain, units, background tiles, leaders
- **Three-stage leader pipeline**:
  - Splash art (1920×1088, denoise=1.0)
  - Profile portrait (512×512, denoise=0.90)
  - Action scene (1920×1088, denoise=0.85)
- **Identity preservation** through calibrated denoising

**Speaker Notes** (90 seconds):
"Our second major innovation is the asset generation pipeline using FLUX.2 Klein 4B Distilled, a Diffusion Transformer with 4 billion parameters. We chose this model for four reasons: Apache 2.0 license enabling commercial use, 8.4 gigabyte VRAM requirement fitting consumer GPUs, 4-step distilled inference achieving 1.2-second generation, and superior prompt adherence from its Qwen 3 text encoder.

The key challenge was achieving consistent output across diverse asset types - structures, objects, terrain, units, background tiles, and leaders. Our solution is a four-layer prompt architecture that separates concerns. Layer 1 is workflow configuration - the ComfyUI JSON defining model selection, sampler settings, and resolution. Layer 2 is style templates - camera framing, quality tags, and LoRA triggers stored in JSON. Layer 3 is semantic descriptions - enum-based vocabularies with hand-crafted prose for each value. Layer 4 is assembly logic that renders templates and validates inputs.

This separation enables consistency - all assets follow the same style guidelines - and maintainability - style changes require editing only Layer 2.

For leader portraits, we implemented a three-stage pipeline with identity preservation. Stage 1 generates splash art at 1920 by 1088 resolution with full denoising, establishing the canonical character appearance. Stage 2 creates a profile portrait using img2img from the splash with denoise 0.90, preserving facial identity while changing framing. Stage 3 generates action scenes with denoise 0.85, allowing creative freedom while maintaining recognizability.

The denoise parameter is critical - we found through experimentation that values above 0.95 cause identity loss, while values below 0.80 prevent meaningful composition changes. The sweet spot of 0.85 to 0.90 balances reference preservation with creative freedom."

**Demo** (if time permits):
"Let me show you asset generation in real-time. [Trigger generation] Here I'm requesting a medieval barracks in Norman Romanesque style. Within 1.2 seconds, we get this pixel-art asset with transparent background, consistent perspective, and proper style. Now let's generate a leader portrait for Cleopatra. [Show three-stage pipeline] The splash establishes her identity, the profile preserves her features in close-up, and the action scene shows her in a dramatic moment while remaining recognizable."

**Transition**: "But the base model doesn't naturally produce top-down perspective assets. That's where LoRA fine-tuning comes in."

---

## Slide 6: LoRA Fine-Tuning (60 seconds) ⭐

**Visual**:
- **Fig. 5**: Six-experiment matrix diagram
- Sample outputs showing before/after LoRA application
- Trigger token example: `<tdp> top-down view.`

**Bullet Points**:
- **Goal**: Adapt FLUX.2 Klein 4B Distilled to consistent top-down perspective
- **Dataset**: 100 curated medieval pixel-art images
  - Generated via ComfyUI pipeline
  - Manually curated for quality
  - Three caption detail levels
- **Six-experiment matrix**:
  - 3 caption levels: detailed, minimal, ultra-minimal
  - 2 LoRA ranks: high (128), low (64)
- **Key finding**: Less detailed captions improve generalization
  - Forces abstract concept learning
  - Reduces overfitting to specific features
- **Result**: `<tdp>` trigger token enforces top-down perspective

**Speaker Notes** (60 seconds):
"While FLUX.2 Klein 4B Distilled provides strong base capabilities, it doesn't naturally produce assets with consistent top-down perspective. Our solution is LoRA fine-tuning using a curated dataset of 100 medieval pixel-art images.

LoRA - Low-Rank Adaptation - enables efficient fine-tuning by training only 0.1 to 1 percent of parameters. Instead of modifying all 4 billion weights, we train small decomposition matrices totaling about 250 megabytes. This requires only 12 gigabytes of VRAM and 2 hours of training, compared to 100 gigabytes and weeks for full fine-tuning.

We systematically evaluated the interaction between caption design and LoRA rank through a six-experiment matrix. We tested three caption detail levels - detailed with 50 to 100 words, minimal with 20 to 30 words, and ultra-minimal with 5 to 10 words - crossed with two rank levels - high with 128 dimensions and low with 64 dimensions.

The key finding was that less detailed captions improve generalization to unseen asset types. Detailed captions cause the model to memorize specific features from training data, while minimal captions force it to learn abstract concepts like perspective and style. The ultra-minimal plus low-rank configuration showed the strongest generalization, successfully enforcing top-down perspective even for modern objects like cars and spaceships that weren't in the training data.

At inference time, we activate the LoRA using the trigger token 'tdp' followed by the angle phrase 'top-down view', which reliably produces assets with consistent overhead perspective."

**Transition**: "Let's look at how all of this comes together in the evaluation."

---

## Slide 7: Evaluation & Results (45 seconds)

**Visual**:
- **Fig. 10**: Test coverage bar chart
- Performance metrics table
- Screenshot of AI civilizations with diverse behaviors

**Bullet Points**:
- **Performance**:
  - Asset generation: 2.5-6 seconds (Blackwell RTX 6000); 3.5-7s (RTX 3090)
  - API response: <100ms (cached), 2-5s (generation)
  - Cache hit rate: ~80% (reduces generation load)
- **Test coverage**: 886 tests, ~80% aggregate
  - Backend: 315 tests, 85% coverage
  - Asset Server: 547 tests, 82% coverage
  - Frontend: 35 tests, 70% coverage
  - Training: 35 tests, 90% coverage
- **AI behavior quality**:
  - Diverse strategies aligned with personas
  - Emergent diplomatic interactions
  - Adaptive responses to game conditions
- **Asset quality**:
  - Consistent style across families
  - Proper top-down perspective
  - Identity preservation in leaders
- **TTS Demo** (15s): Show narration generation --- highlight narrator instructions as prompt engineering

**Speaker Notes** (45 seconds):
"Our evaluation covers three dimensions: performance, test coverage, and AI behavior quality.

Performance-wise, asset generation takes 1.2 to 4 seconds depending on complexity, with leader portraits taking longest due to the three-stage pipeline. API responses are under 100 milliseconds for cached assets, and we achieve an 80 percent cache hit rate during typical gameplay, significantly reducing generation load.

We implemented comprehensive testing with 886 tests achieving 80 percent aggregate coverage. The backend has 339+ tests including property tests that validate invariants like state immutability. The asset server has 547 tests including concurrency tests for the load balancer. The frontend uses TypeScript strict mode for compile-time validation.

AI behavior quality exceeded our expectations. Each civilization exhibits distinct strategies aligned with its persona - Genghis pursues aggressive expansion, Cleopatra forms diplomatic alliances, Gandhi focuses on peaceful development. We observed emergent behaviors like coalition formation and revenge mechanics that weren't explicitly programmed.

Asset quality is consistent across all six families, with proper top-down perspective enforced by the LoRA and identity preservation working reliably in the leader pipeline."

**Transition**: "Let me conclude with our contributions and future directions."

---

## Slide 8: Conclusions & Future Work (30 seconds)

**Visual**:
- Summary of 6 key contributions
- Future work roadmap
- GitHub repository link

**Bullet Points**:
- **Contributions**:
  1. Intent-based LLM abstraction for game AI
  2. Four-layer prompt architecture for consistent generation
  3. Three-stage identity preservation pipeline
  4. LoRA fine-tuning methodology with systematic evaluation
  5. Graceful degradation patterns for robustness
  6. Reference implementation (open-source)
- **Future work**:
  - Persistent storage (PostgreSQL)
  - Asynchronous generation (Celery + Redis)
  - Multi-agent coordination (coalitions)
  - Quantitative evaluation metrics (FID, CLIP score)
- **Code**: github.com/[username]/StrategAI

**Speaker Notes** (30 seconds):
"In conclusion, StrategAI demonstrates that modern generative AI can be integrated into cohesive game systems accessible to independent developers. Our six key contributions are: the intent-based abstraction enabling LLM control of game entities, the four-layer prompt architecture for consistent asset generation, the three-stage identity preservation pipeline for leader portraits, the LoRA fine-tuning methodology with systematic evaluation, comprehensive graceful degradation patterns, and a complete open-source reference implementation.

Future work includes persistent storage for multi-instance deployment, asynchronous generation with job queues, multi-agent coordination for coalition warfare, and quantitative evaluation metrics like FID and CLIP score.

The complete codebase is available on GitHub. Thank you for your attention, and we're happy to take questions."

**Transition**: "We're now ready for questions."

---

## Q&A Preparation (15-17 minutes remaining)

### Team Roles for Q&A

Assign each team member specific question categories:

**Member 1**: Backend & LLM Integration
- Intent abstraction details
- Game engine architecture
- AI behavior and personas
- Memory system

**Member 2**: Asset Generation & DiT
- FLUX.2 Klein 4B Distilled model selection
- Prompt architecture
- ComfyUI integration
- Leader pipeline

**Member 3**: LoRA Fine-Tuning & Training
- Dataset curation
- Experiment matrix
- Training methodology
- Evaluation approach

**Member 4**: Frontend & Integration
- Asset manifest resolution
- Graceful degradation
- User interface
- System architecture

### Backup Slides (if needed)

**Backup Slide A: Technical Deep Dive - Intent Resolution**
- Detailed algorithm for each intent type
- Code examples showing resolution logic
- Performance characteristics

**Backup Slide B: Technical Deep Dive - ComfyUI Workflow**
- Complete 22-node workflow diagram
- Node-by-node explanation
- Parameter tuning rationale

**Backup Slide C: Technical Deep Dive - LoRA Training**
- Training curves and loss plots
- Sample outputs at different checkpoints
- Hyperparameter sensitivity analysis

**Backup Slide D: Demo Video**
- Pre-recorded 2-minute gameplay video
- Shows AI civilizations interacting
- Demonstrates asset generation in real-time
- Backup if live demo fails

### Common Follow-up Questions

**Q: How do you handle LLM hallucinations or invalid intents?**
A: The intent resolution layer validates all intents before execution. Invalid intents (e.g., targeting non-existent units) are silently dropped. The LLM receives feedback through the `last_turn_feedback` field, helping it avoid repeating failed actions. We also use `tool_choice="required"` to ensure the LLM always emits at least one intent.

**Q: What's the cost of running this system?**
A: GPT-5.4-mini API costs approximately $0.03 per AI turn at current prompt sizes. For a 100-turn game with 3 AI civilizations, that's about $9 total. Asset generation is self-hosted, so costs are limited to electricity and hardware depreciation. The system is significantly cheaper than cloud-based asset generation services.

**Q: How does this compare to traditional game AI?**
A: Traditional game AI uses behavior trees or finite state machines, which require extensive manual authoring and struggle with novel situations. Our LLM-based approach enables emergent behavior and natural language diplomacy without scripting every scenario. The trade-off is higher computational cost and less predictable behavior.

**Q: Could this approach work for other game genres?**
A: Yes, the intent-based abstraction is genre-agnostic. For an RPG, intents might be "explore dungeon", "engage enemy", "rest and heal". For a racing game, intents might be "overtake", "defend position", "pit stop". The key is designing intents that separate strategic reasoning from tactical execution.

**Q: What happens if two AI civilizations have conflicting goals?**
A: The game engine handles conflicts deterministically. If two AIs try to found cities on the same tile, the first to execute wins. If they attack each other, combat resolution follows the same formulas as human vs AI. The diplomatic system enables negotiation, but ultimately the engine enforces outcomes.

**Q: How do you ensure the LoRA doesn't degrade base model quality?**
A: LoRA weights are added to base weights at inference time, not replacing them. We use strength=1.0, meaning full LoRA influence. Lower strengths (0.5-0.8) can blend LoRA with base model for less aggressive style enforcement. We also evaluate on out-of-distribution prompts to ensure the LoRA doesn't break general capabilities.

**Q: What's the biggest limitation of your approach?**
A: The biggest limitation is strategic depth. While AI civilizations exhibit diverse behaviors, they lack long-term planning across many turns. LLMs excel at tactical decisions but struggle with multi-turn strategic goals like "build three cities, then research iron working, then attack". This is an active research area in LLM-based agents.

---

## Presentation Checklist

### Before Presentation
- [ ] Practice full presentation 3+ times with timer
- [ ] Verify all demos work (have backup screenshots)
- [ ] Test projector/display compatibility
- [ ] Prepare backup slides on USB drive
- [ ] Assign Q&A roles to team members
- [ ] Review likely questions and answers
- [ ] Dress professionally
- [ ] Arrive 15 minutes early

### During Presentation
- [ ] Start on time
- [ ] Speak clearly and at moderate pace
- [ ] Make eye contact with audience
- [ ] Use gestures to emphasize key points
- [ ] Monitor time (7-8 minutes strict)
- [ ] Transition smoothly between speakers
- [ ] Thank audience at end

### During Q&A
- [ ] Listen carefully to full question
- [ ] Pause briefly before answering
- [ ] Be honest if you don't know
- [ ] Use specific technical details
- [ ] Connect answers to course concepts
- [ ] Divide questions among team members
- [ ] Keep answers concise (30-60 seconds)
- [ ] Thank questioner after each answer

### After Presentation
- [ ] Thank instructors
- [ ] Ask for feedback
- [ ] Note questions you struggled with
- [ ] Celebrate with team!

---

## Timing Breakdown

| Slide | Duration | Cumulative | Speaker |
|-------|----------|------------|---------|
| 1. Title & Team | 0:30 | 0:30 | Member 1 |
| 2. Motivation | 0:45 | 1:15 | Member 1 |
| 3. Architecture | 1:00 | 2:15 | Member 2 |
| 4. LLM Integration | 1:30 | 3:45 | Member 3 |
| 5. Asset Pipeline | 1:30 | 5:15 | Member 2 |
| 6. LoRA Fine-Tuning | 1:00 | 6:15 | Member 4 |
| 7. Evaluation | 0:45 | 7:00 | Member 1 |
| 8. Conclusions | 0:30 | 7:30 | Member 4 |
| **Total** | **7:30** | **7:30** | **All** |

**Buffer**: 30 seconds for transitions and unexpected delays  
**Target**: Finish at 7:30-8:00 mark

---

## Final Tips

1. **Practice, practice, practice**: The more you rehearse, the more confident you'll be
2. **Know your audience**: Instructors care about course concepts and technical depth
3. **Emphasize AI/ML**: This is a generative AI course - highlight LLMs, DiTs, LoRA
4. **Be honest about limitations**: Shows maturity and understanding
5. **Have fun**: You built something impressive - be proud!

Good luck with your presentation!
