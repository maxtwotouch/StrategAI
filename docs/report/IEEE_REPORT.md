# StrategAI: Integrating Large Language Models and Diffusion Transformers for AI-Driven Strategy Game Development

**Abstract**—Strategy game development faces two persistent bottlenecks: AI behavior authoring, where hand-crafted decision systems become brittle and labor-intensive as complexity grows, and asset creation, where manual pixel art production scales poorly with game scope. This paper presents StrategAI, a full-stack strategy game that addresses both challenges by integrating generative AI technologies. Three AI civilizations—Mongolia under Genghis Khan, Egypt under Cleopatra, and India under Gandhi—are controlled by GPT-5.4-mini via OpenAI's tool-use API. Each AI emits high-level strategic intents through a novel abstraction layer that decouples LLM reasoning from deterministic game mechanics, preventing direct game-state manipulation while preserving strategic agency. Concurrently, a self-hosted asset server generates top-down medieval pixel-art assets on demand using FLUX.2 Klein 4B Distilled, a 4-billion-parameter Diffusion Transformer, orchestrated through ComfyUI with a four-layer prompt architecture separating workflow configuration, style constraints, semantic descriptions, and assembly logic. A custom-trained LoRA adapter, produced through a systematic 3×2 experiment matrix evaluating caption detail against rank configuration on a curated 100-image dataset, enforces consistent top-down perspective and medieval architectural styling via a trigger token. The system degrades gracefully through four fallback tiers when AI services are unavailable. Generation times of 2.5–6 seconds on a Blackwell RTX 6000 and 3.5–7 seconds on an RTX 3090 suggest workstation GPUs can support near-interactive generative asset pipelines. We detail the architectural decisions, integration patterns, and engineering lessons from building this multi-agent generative AI system, providing a reference implementation for developers incorporating language models and diffusion transformers into interactive applications.

**Index Terms**—Large Language Models, Diffusion Transformers, Game AI, Asset Generation, LoRA Fine-Tuning, Tool Use, Multi-Agent Systems, Procedural Content Generation

---

## I. INTRODUCTION

The last five years have witnessed a dramatic transformation in what generative AI systems can produce. Large Language Models (LLMs) now reason about strategy, negotiate diplomatically, and invoke external tools with structured outputs. Diffusion Transformers (DiTs) generate high-quality images from natural language descriptions with remarkable prompt adherence. Yet practical systems that combine these modalities into cohesive, playable applications remain rare. Most existing integrations either place LLMs in sandbox environments without competitive rules, or use diffusion models for concept art rather than production game assets with specific technical constraints.

StrategAI is a full-stack strategy game—a Civilization-style 4X (explore, expand, exploit, exterminate) experience played on a square grid—that demonstrates how these technologies can work together in a single, functional system. The game features three AI civilizations, each controlled by an LLM with a distinct strategic persona, and generates all visual assets on demand using a DiT model running on workstation-class GPU hardware. The entire system is open-source and self-hosted, with no dependency on proprietary cloud services for asset generation.

### A. Motivation

Independent game developers face two structural challenges that generative AI is uniquely positioned to address.

First, authoring competitive AI opponents traditionally requires behavior trees, finite state machines, or utility-based AI systems. These approaches demand extensive manual authoring—designers must anticipate every strategic scenario and encode appropriate responses. As game complexity grows, the behavior tree becomes exponentially harder to maintain, and scripted AI inevitably exhibits exploitable patterns that players learn to circumvent. An LLM that reasons about strategy in natural language could, in principle, adapt to novel situations without requiring every contingency to be pre-scripted.

Second, asset creation is the dominant cost in game development. A single strategy game might require hundreds of distinct visual assets across terrain types, building styles, unit classes, and leader portraits. Manual pixel art production for this volume of content is measured in artist-months. Procedural generation techniques—noise functions, grammar systems, constraint solvers—can produce variation but rarely achieve the visual quality and stylistic coherence of hand-crafted art. Generative image models have matured to the point where they can produce production-quality outputs, but integrating them into a reliable, automated pipeline with consistent style and perspective remains an engineering challenge.

StrategAI addresses both bottlenecks simultaneously: LLMs for strategic reasoning and diplomacy, and DiTs for on-demand pixel-art generation. The system demonstrates that these technologies are not merely research curiosities but practical tools accessible on consumer-grade hardware.

### B. Problem Statement

This work investigates three interconnected research questions:

1. Can LLMs serve as autonomous strategic agents in a rule-bound competitive game, making decisions that are both strategically coherent and persona-consistent, without direct access to game state manipulation?

2. Can diffusion models generate consistent, production-quality pixel-art assets across multiple asset families on workstation GPU hardware, meeting technical constraints such as transparent backgrounds, consistent perspective, and appropriate resolution?

3. Can these two AI modalities be integrated into a cohesive, playable system with graceful degradation when either AI service is unavailable?

### C. Contributions

This paper makes the following contributions:

1. **Intent-based LLM abstraction**: A layered architecture that decouples strategic reasoning (LLM-emitted intents) from tactical execution (deterministic Python resolution), enabling LLMs to control game entities without coordinate-level manipulation or rule validation.

2. **Four-layer prompt architecture**: A systematic approach to generative asset prompting that separates workflow configuration, style templates, semantic descriptions, and assembly logic across independently maintainable layers, producing consistent outputs across six asset families.

3. **Three-stage identity-preserving leader portrait pipeline**: An img2img generation system that maintains character identity across splash art, profile portraits, and action scenes through carefully calibrated denoising parameters.

4. **LoRA fine-tuning methodology**: A complete style-adaptation pipeline with a 3×2 experiment matrix evaluating caption detail against LoRA rank, trained on a curated 100-image dataset, with systematic evaluation of perspective consistency, style adherence, and trigger-token gating.

5. **Graceful degradation system**: A four-tier fallback architecture—generative, static, placeholder, and built-in—that ensures the game remains functional regardless of AI service availability.

6. **Reference implementation**: A fully functional, open-source codebase demonstrating practical patterns for multi-modal generative AI integration.

### D. Paper Organization

Section II reviews related work in game AI, procedural content generation, model adaptation, and multi-agent systems. Section III presents the overall system architecture and technology rationale. Section IV details the LLM-driven strategic AI, including the intent abstraction, persona system, and memory management. Section V describes the generative asset pipeline, including the four-layer prompt architecture and leader portrait system. Section VI covers the LoRA fine-tuning methodology and experimental results. Section VII discusses frontend integration and user experience. Section VIII evaluates system performance and AI behavior quality. Section IX examines ethical considerations. Section X discusses limitations and future work. Section XI concludes.

---

## II. RELATED WORK

### A. Game AI and Large Language Models

Traditional game AI relies on hand-crafted decision systems. Behavior trees [12] provide hierarchical task decomposition with clear execution semantics but require designers to anticipate every strategic branch. Finite state machines offer predictable transitions between discrete behavioral modes but scale poorly as the number of states grows combinatorially with game complexity. Utility-based AI systems evaluate candidate actions through weighted scoring functions, enabling more nuanced decision-making, but the weight tuning process is labor-intensive and the resulting behaviors can be opaque to designers [13].

The emergence of capable LLMs has prompted a wave of research into language-model-driven game agents. Park et al. [1] introduced generative agents—simulated characters that remember, reflect, and plan through natural language reasoning—but their system operated in a sandbox environment (a Sims-style village) without competitive gameplay or rule enforcement. Wang et al. [2] developed Voyager, an LLM-powered agent that autonomously explores Minecraft through self-generated skill libraries and iterative code generation, establishing LLMs as capable of open-ended exploration. Schick et al. [3] demonstrated with Toolformer that language models can teach themselves to invoke external tools via API calls—a capability that directly motivates our intent-based tool-use architecture.

StrategAI differs from prior work in two fundamental ways. First, our LLMs operate as competitive strategic agents in a rule-bound environment with explicit victory conditions, fog of war, and adversarial opponents—a substantially harder setting than cooperative or sandbox environments. Second, our intent-based abstraction addresses a well-documented LLM weakness: while language models excel at high-level reasoning, they struggle with precise numerical calculations, spatial logic, and rule compliance. By separating strategic intent from tactical execution, we leverage LLM strengths while maintaining deterministic game mechanics.

### B. Procedural Content Generation

Procedural Content Generation (PCG) has a long history in games, from the procedural dungeons of Rogue [4] to the vast procedurally generated universes of No Man's Sky [5]. Togelius et al. [15] surveyed the landscape of PCG for games, establishing taxonomies of generation techniques and design integration patterns. Traditional PCG techniques—Perlin noise [14] for terrain, L-systems and shape grammars for structures, constraint solvers for level design—produce functional but aesthetically limited results. They excel at generating variation within parameterized spaces but struggle to produce content that matches the visual quality of hand-crafted assets.

Deep learning approaches to PCG initially focused on Generative Adversarial Networks (GANs), which demonstrated the ability to generate game levels and textures, but training instability and mode collapse limited practical adoption. Variational Autoencoders (VAEs) offered more stable training but produced characteristically blurry outputs unsuitable for the crisp edges required by pixel art.

Diffusion models [6], [7] have emerged as the state-of-the-art for image generation, offering high-quality, diverse outputs with strong prompt adherence. Peebles and Xie [8] advanced this paradigm by replacing the U-Net backbone with a pure Transformer architecture, creating Diffusion Transformers (DiTs) that exhibit superior scaling behavior. Liu et al. [9] proposed rectified flow, an alternative to score-based diffusion that learns straight-line trajectories for substantially faster sampling—a technique adopted by the FLUX model family that powers our asset pipeline. However, the application of diffusion models to production game assets remains limited. Most existing work focuses on concept art generation rather than assets with specific technical requirements: transparent backgrounds, consistent perspective, tileable textures, and appropriate resolution for game engines.

StrategAI addresses these requirements through a multi-stage pipeline combining DiT-based generation with post-processing (background removal, Lanczos resizing) and a structured prompt system that enforces asset specifications across six families with diverse technical constraints.

### C. Model Adaptation and LoRA

Full fine-tuning of large diffusion models—updating all 4 billion parameters of FLUX.2 Klein 4B, for example—is computationally prohibitive for independent developers, requiring hundreds of gigabytes of VRAM and days or weeks of training time. Parameter-Efficient Fine-Tuning (PEFT) methods address this by training a small number of additional parameters while keeping the base model frozen.

Low-Rank Adaptation (LoRA), introduced by Hu et al. [10], injects trainable low-rank decomposition matrices into the attention and convolution layers of a frozen model. At inference time, the base weights and LoRA weights are combined, enabling the adapted model to produce stylistically shifted outputs. LoRA adapters typically represent 0.1–1% of the base model's parameter count, making them storage-efficient (hundreds of megabytes rather than gigabytes) and trainable on a single GPU in hours rather than days.

Prior work on LoRA for diffusion models has primarily focused on character consistency, specific artist styles, or object concepts. Our contribution is threefold: (1) we apply LoRA to the FLUX.2 Klein 4B DiT architecture, a newer model family with rectified flow formulation and distilled inference, rather than the more commonly used U-Net-based Stable Diffusion; (2) we systematically evaluate the interaction between caption detail level and LoRA rank through a 3×2 experiment matrix, providing empirical guidance for practitioners; and (3) we validate trigger-token gating through style-leakage testing, confirming that the adapter's influence is appropriately scoped to its intended domain.

### D. Multi-Agent Systems

Multi-agent systems (MAS) in games have traditionally employed homogeneous agents with shared decision logic [17]. Heterogeneous MAS, where agents exhibit different behavioral tendencies or pursue different goals, are more complex to implement but enable richer, more naturalistic interactions.

StrategAI implements heterogeneous AI agents through persona-based prompting—a technique unique to LLM-driven agents. Each AI civilization receives a distinct character description that shapes its strategic decision-making while sharing the same underlying intent system and game engine. This approach achieves behavioral diversity without requiring separate AI implementations for each civilization, and the personas can be modified or extended by editing natural language descriptions rather than rewriting decision logic.

---

## III. SYSTEM OVERVIEW

### A. High-Level Architecture

StrategAI comprises four principal components connected through well-defined service contracts. The Backend implements the game engine and LLM integration in Python using FastAPI. The Frontend, built with Next.js and React, renders the game state through an SVG-based map and manages all user interaction. The Asset Server, a separate FastAPI service, orchestrates ComfyUI-based image generation using FLUX.2 Klein 4B Distilled. The Training Pipeline, built on the Ostris AI Toolkit, produces the LoRA adapters that enforce a consistent top-down perspective across all generated assets.

A critical architectural principle governs cross-service communication: the Frontend mediates all interaction between services. The Backend and Asset Server never communicate directly. When the game state changes, the Frontend queries the Backend for updated state, determines which assets are needed, and requests them from the Asset Server independently. This mediation pattern simplifies each service's responsibilities and enables independent development, testing, and deployment of each component. (See Fig. 1 for a diagram of the system architecture and cross-service data flows.)

The game engine itself is organized into four layers that process decisions sequentially. At the top, the Strategic layer—the LLM, receiving a fog-filtered JSON view of the game world—emits high-level intents through OpenAI's tool-use API. These intents flow down to the Operations layer, a set of deterministic Python functions that translate each intent into concrete goals, diplomatic actions, and production directives by querying the current game state for unit positions, distances, and rule constraints. The Tactical layer receives these goals and resolves them further: it runs A* pathfinding for movement goals, computes combat outcomes, and determines valid city-founding locations. Finally, the Validator layer checks every proposed action against the game rules—verifying turn order, movement budgets, diplomatic preconditions, and resource constraints—before any state mutation occurs. The Engine applies only validated actions, producing a new immutable GameState.

The key principle throughout this pipeline is that the LLM never accesses GameState directly. Every LLM intent passes through operations resolution, tactical execution, and rule validation before any state change. This four-layer separation ensures that strategic reasoning (where LLMs excel) is cleanly decoupled from tactical bookkeeping and rule enforcement (where deterministic code is necessary).

### B. Technology Choices

Several technology decisions shaped the system's capabilities and constraints. Each was made with explicit awareness of the trade-offs involved.

**FLUX.2 Klein 4B Distilled** was selected as the image generation model over alternatives including Stable Diffusion XL and the larger FLUX.2 Klein 9B. Four criteria drove this choice. First, its Apache 2.0 license permits both research and commercial use without restrictions, a hard requirement for game asset generation. Second, FP8 quantization reduces its VRAM footprint to approximately 8.4 GB, fitting within the memory budget of workstation GPUs. Third, its 4-step distilled inference—achieved through rectified flow distillation from a 50-step teacher model—enables generation times that approach interactivity. Fourth, its DiT architecture with a Qwen 3 4B text encoder provides superior prompt adherence compared to CLIP-based models, which is essential for precise game asset descriptions. Like all FLUX.2-family models, it does not support negative prompts—a consequence of classifier-free guidance being baked into the model weights during training rather than applied at inference time—so all prompt templates use positive-only, affirmative language.

**GPT-5.4-mini** was selected for strategic AI reasoning based on its tool-use capability, which enables structured intent emission through OpenAI's function-calling interface, its 128K token context window, which accommodates game state serialization alongside rolling memory of past decisions and diplomatic exchanges, its strategic reasoning quality relative to smaller models, and its production-grade API infrastructure with graceful error handling.

**ComfyUI** serves as the inference orchestration layer, providing a node-graph workflow system with HTTP and WebSocket APIs that enable programmatic control from the Asset Server [21]. Its modular architecture—where models, samplers, VAEs, and post-processing nodes are composed as directed graphs stored in version-controlled JSON—makes it well-suited to the multi-stage pipelines required by our asset families.

### C. Data Flow

The system operates through three primary data flows corresponding to its main functions.

The gameplay loop proceeds as follows. A human player submits an action through the Frontend, which sends it to the Backend API. The Backend validates the action against game rules and, if valid, applies it to produce a new GameState. When the human player ends their turn, the Backend iterates over AI civilizations, serializing each one's fog-filtered local view into JSON, sending it to GPT-5.4-mini with the system prompt and conversation history, receiving tool calls representing intents, and resolving those intents into validated actions through the engine layers. The final GameState is serialized and returned to the Frontend for rendering.

The asset generation flow is initiated by the Frontend after receiving updated game state. The Frontend's asset manifest resolver determines which assets are needed—terrain tiles for visible tiles, unit sprites for deployed units, structure sprites for city buildings, and leader portraits for diplomatic interactions—and fans out requests to the Asset Server. Each request triggers a ComfyUI workflow execution: the workflow JSON is patched with the appropriate prompt (assembled from the four-layer architecture), a cryptographic seed is generated, and FLUX.2 Klein 4B Distilled performs 4-step distilled inference. The output image is post-processed (resized, sharpened, background-removed as needed), stored atomically, and its URL returned to the Frontend for display.

The training data flow is offline and unidirectional. A curated dataset of 100 top-down medieval pixel-art images is captioned at three detail levels. The Ostris AI Toolkit trains six LoRA variants against a frozen FLUX.2 Klein 4B base model, producing adapter weights that are deployed to the Asset Server's ComfyUI models directory and loaded at inference time when the trigger token is present in a prompt.

---

## IV. LLM-DRIVEN GAME AI

The Backend implements three AI civilizations, each controlled by GPT-5.4-mini through OpenAI's tool-use API. This section describes the architectural decisions that make this integration robust: the intent-based abstraction that decouples reasoning from execution, the nine intent types that constitute the LLM's action vocabulary, the persona system that produces distinct strategic behaviors, and the memory management that maintains coherence across turns.

### A. Intent-Based Abstraction

Giving an LLM direct control over game entities—selecting which specific unit to move to which specific coordinate, computing whether an attack would be legal under current diplomatic stance, verifying that a technology's prerequisites are met—would be architecturally unsound. LLMs are probabilistic next-token predictors, not deterministic rule engines. They hallucinate identifiers, miscalculate distances, and propose actions that violate game rules. Even with careful prompting, expecting an LLM to consistently produce valid low-level game commands across hundreds of turns is unrealistic.

Our solution is a layered abstraction that separates strategic reasoning from tactical execution. (This layered abstraction—which the engine further decomposes into operations resolution, tactical execution, and validation sub-layers, as described in §III.A—keeps the LLM focused on high-level goals while deterministic code handles all mechanical bookkeeping.) The Strategic layer, implemented by the LLM, reasons about high-level goals: "Should I expand my territory, engage my neighbor, or consolidate my defenses?" Its output is a set of structured intents—data objects like Engage(target_civ_id=2) or Expand()—that name strategic objectives without specifying how to achieve them.

The Tactical layer, implemented as deterministic Python functions in the Operations module, resolves each intent into concrete goals by querying the current game state. When the LLM emits Engage(target_civ_id=2), the Operations layer automatically checks whether the civilizations are at war (declaring war if not), finds the closest military unit owned by the actor, locates the closest visible enemy unit or city belonging to the target civilization, and emits MoveTo and Attack goals with specific unit identifiers and coordinates. The LLM never selects a unit ID, never computes a grid distance, and never needs to remember the rule that war must be declared before attacking. These responsibilities are handled deterministically by code that cannot hallucinate.

Figure 2 illustrates this layered intent resolution pipeline.

This design represents a deliberate trade-off. The LLM loses the ability to execute fine-grained tactical maneuvers—it cannot order a specific archer to move to a specific hill tile for a flanking bonus. In exchange, it gains robustness: every intent it emits will either produce a valid action or be rejected with a machine-readable error code that it can use to adjust its next decision. For a strategy game where the interesting decisions are strategic (which civilization to attack, where to expand, what technology to prioritize) rather than tactical (exact unit positioning), this trade-off is appropriate.

### B. Intent Types

The system defines nine intent types, each implemented as a frozen dataclass with type-annotated optional parameters. These nine types constitute the complete action vocabulary available to the LLM.

**Expand** instructs the engine to found a new city. The Operations layer identifies an available settler unit and searches for an optimal city site—an unoccupied, passable tile not adjacent to any existing city, prioritizing tiles with high food and production yields. An optional target tile hint can guide the search, but the engine validates any hint and falls back to its own site selection if the hint is invalid.

**Scout** directs a military unit (preferring scouts for their higher movement range) toward unexplored territory. The Operations layer identifies the frontier—tiles at the edge of current visibility—and selects the closest reachable unexplored tile as the movement target.

**Engage** initiates hostilities against another civilization. This is the most mechanically complex intent. The Operations layer checks the current diplomatic stance; if the civilizations are not at war, it emits a war declaration. It then identifies the closest military unit, finds the closest visible enemy unit or city, and generates MoveTo and Attack goals. The LLM simply declares its intention to fight; the engine handles all tactical bookkeeping.

**Reinforce** moves a military unit toward a friendly defensive position—either a specific city or a tile coordinate. If no target is specified, the unit moves toward the civilization's first city.

**Speak** sends a diplomatic message to another leader. The intent carries a message kind (chat, threat, offer_peace, accept_peace, declare_war, propose_alliance, accept_alliance, or reject) and free-form text that the LLM composes in its leader's voice. The engine records the message and updates relationship scores according to fixed deltas defined in the diplomacy module.

**AdjustStance** directly sets the diplomatic stance with another civilization to peace, war, or alliance. This is a unilateral action, distinct from the narrative diplomacy of Speak, and is intended for situations where the LLM wants to make an immediate stance change without composing a message.

**Build** appends a unit to a city's production queue. The Operations layer validates that the requested unit type's technology prerequisite is met (for example, Horseman requires Horseback Riding), selects the specified city or defaults to the first owned city, and emits a QueueProduction directive.

**Research** sets the civilization's active research target. The Operations layer validates that the technology is not already known and that all its prerequisites are satisfied, then emits a StartResearch directive.

**Improve** orders a worker unit to construct a tile improvement—a farm (boosting food on plains or grassland), a mine (boosting production on hills), or a road. The Operations layer selects an idle worker, identifies a legal owned tile matching the improvement type, and emits a BuildImprovement goal.

Each intent carries only semantic, high-level parameters. The LLM specifies target civilization IDs (not unit IDs), hints target tiles (not exact paths), and names technology IDs and unit types from enumerated lists provided in the serialized game view. This constrained vocabulary dramatically reduces the surface area for hallucination while preserving meaningful strategic choice.

### C. Persona System

Three AI civilizations ship with the game, each defined by a civilization name, leader name, strategic traits, and a detailed persona prompt. The persona prompt is appended to a shared base system prompt that defines the game context, available intents, and strategic principles applicable to all AI leaders.

The **base system prompt** establishes the LLM's role as an AI civilization leader, documents the structure of the serialized game state it receives each turn (resources, units, cities, diplomatic relations, fog of war, available technologies, inbox messages, relationship scores), and explains each intent tool's purpose and appropriate use cases. It also encodes strategic principles—expand to two or three cities early, prioritize technologies that unlock military units, monitor diplomatic relationship scores as durable memory—and behavioral rules such as reading feedback from rejected intents and adapting strategy accordingly.

The **persona prompts** layer leader-specific motivations, voice, and constraints on top of this shared foundation. Genghis Khan of Mongolia is characterized as an aggressive expansionist who measures civilization by conquest, remembers every insult, and declares war within two turns of being threatened. His prompt excerpt reads: "Conquest is the only true measure of a civilization. Found cities to fuel armies, then crush your neighbors. You remember every insult. If a leader speaks down to you or threatens you, declare war within two turns." Cleopatra of Egypt is a diplomatic opportunist who plays factions against each other, flatters potential allies, and avoids first strikes unless cornered. Her prompt excerpt reads: "Survive and prosper through clever diplomacy. Play factions against each other. Trade insults with anyone vulgar enough to start them, but always leave a door open for reconciliation if it serves Egypt." Gandhi of India is a peaceful developer who pursues science and culture victories, responds to threats with dignified protest, and welcomes alliances. His prompt excerpt reads: "Pursue victory through science, culture, and patient growth. Avoid aggression where possible. Respond to threats with dignified protest first; only declare war as an absolute last resort to defend your people."

Each persona also includes explicit red lines—behavioral constraints that the LLM is instructed not to cross. Genghis Khan must not propose alliances unprovoked or apologize. Cleopatra must not declare war unless cornered. Gandhi must never attack unprovoked, threaten, or insult. These red lines are not enforced by the engine (the engine would accept any valid intent regardless of persona) but serve as prompt-level guardrails that steer the LLM toward persona-consistent behavior.

The persona system achieves behavioral diversity without requiring separate AI implementations. All three leaders use the same nine intent types, the same Operations layer, and the same game engine. The only difference is the natural language description that shapes their strategic preferences. This design means that adding a new AI civilization requires only writing a new persona prompt—a task measured in minutes rather than the days or weeks needed to script a new behavior tree.

### D. Memory, Context, and Error Handling

LLMs are stateless: each API call is independent, with no inherent memory of previous turns. To enable coherent multi-turn strategic play, the system maintains rolling memory that is injected into the conversation context each turn.

Two logs feed the memory system. The intent log records the last 32 intents emitted by the AI, each annotated with its turn number and a human-readable summary of the outcome (whether the intent was successfully resolved or rejected with a specific error code). The diplomatic message log records the last 32 messages—both sent and received—with sender, recipient, turn number, message kind, and full text. Both logs are filtered to the most recent 8 turns, ensuring that memory remains relevant to the current strategic situation without accumulating stale information from the early game.

This memory serves three purposes. First, it prevents the AI from repeating strategies that the engine has already rejected. When an intent is rejected—for example, a Build intent for a unit whose technology prerequisite is unmet—the rejection reason appears in the following turn's context, and the LLM can adjust. Second, it enables diplomatic continuity: the AI remembers who declared war, who offered peace, and who betrayed an alliance, and can adjust its stance accordingly. Third, it maintains strategic coherence across turns, preventing the erratic goal-switching that can occur when an LLM lacks memory of its own past decisions.

Error resilience is implemented at multiple levels. If the OpenAI API is unreachable or returns an error, the system catches the exception, logs a warning, and returns an empty Decisions object—the AI skips its turn rather than crashing the game. If the API returns a response with malformed tool calls (unparseable JSON, unknown function names, invalid parameter types), the system parses each tool call independently, skipping malformed ones and processing valid ones. If the game state has not been bound to the goal source (a startup edge case), empty decisions are returned. Temperature configuration is omitted for models that do not support it, avoiding API errors from unsupported parameters.

The diplomacy system operates on a parallel track to the intent system. Diplomatic messages are free-form text composed by the LLM in its leader's voice, with the message kind providing categorical structure. Relationship scores range from -100 (maximum hostility) to +100 (maximum alliance), with fixed deltas applied per event type: declaring war costs 50 points, attacking costs 20, threatening costs 10, chatting gains 1, offering peace gains 8, accepting peace gains 25, proposing alliance gains 15, and accepting alliance gains 30. When peace is accepted, a 10-turn truce prevents either party from declaring war. These mechanics create a durable social fabric that the LLM must navigate—aggression has lasting diplomatic consequences, and repairing damaged relationships requires sustained investment.

## V. GENERATIVE ASSET PIPELINE

The Asset Server generates top-down medieval pixel-art assets on demand using FLUX.2 Klein 4B Distilled, orchestrated through ComfyUI. This section describes the model infrastructure, the four-layer prompt architecture that ensures consistency across six asset families, the three-stage leader portrait pipeline that preserves character identity, and the multi-mode generation system that enables graceful degradation.

### A. Model and Infrastructure

FLUX.2 Klein 4B Distilled is a 4-billion-parameter Diffusion Transformer that replaces the convolutional U-Net backbone found in traditional latent diffusion models with a Vision Transformer operating on latent-space patches. This architectural shift has two important consequences. First, the Transformer's global self-attention provides a receptive field that spans the entire latent representation, enabling superior long-range coherence compared to the fixed receptive fields of convolutional models. Second, the DiT architecture exhibits more predictable scaling behavior, having inherited scaling laws from language modeling research.

The model employs rectified flow rather than conventional score-based diffusion. In a rectified flow formulation, the forward process follows a straight-line path from data to noise, and the reverse process follows the same trajectory in reverse. This straight-line geometry enables more efficient distillation: a 4-step student model can learn to approximate the teacher's 50-step trajectory in far fewer steps by taking larger jumps along the straight path, with minimal quality degradation. The practical consequence is that FLUX.2 Klein 4B Distilled achieves generation quality comparable to 50-step models while requiring only 4 inference steps—a roughly twelvefold speedup.

FP8 quantization reduces the model's VRAM footprint from approximately 16 GB to 8.4 GB with minimal perceptual quality loss, making it viable on workstation GPUs such as the RTX 3070 or 4070 class at 8–12 GB. The model uses a Qwen 3 4B text encoder rather than the CLIP encoder common in earlier diffusion models, providing stronger prompt adherence for the precise, technical descriptions required by game asset generation.

ComfyUI [21] provides the orchestration layer. Workflows are stored as version-controlled JSON node graphs specifying the complete generation pipeline: model loading (separate UNETLoader, CLIPLoader, and VAELoader nodes for the DiT's split architecture), prompt encoding, latent sampling with the euler sampler and simple scheduler at 4 steps, VAE decoding, and optional post-processing nodes. The Asset Server communicates with ComfyUI through its HTTP API, patching prompt text and random seeds into the workflow template, queuing the prompt, monitoring execution via WebSocket (with HTTP polling fallback), and downloading the resulting image. Multi-node load balancing distributes requests across available ComfyUI instances, selecting the node with the shortest queue and transparently retrying on failure.

### B. Four-Layer Prompt Architecture

Generating consistent assets across six families with hundreds of combinatorial variants presents a prompt engineering challenge. Manual, ad-hoc prompt construction produces inconsistent results and couples generation logic to API implementation—any stylistic change requires code modifications. Our solution is a four-layer architecture that separates concerns into independently maintainable layers, delivering consistent output through templated prompt construction while decoupling the asset server API from the underlying prompt structure. (Figure 3 diagrams this four-layer prompt construction process.)

**Layer 1: Workflow Configuration.** The ComfyUI workflow JSON specifies the technical generation parameters that are invariant across prompt variations: model file paths, sampler type and scheduler, inference step count (4), generation resolution (1024×1024), output resolution (256×256 via Lanczos resize), and post-processing configuration. This layer is version-controlled alongside the codebase and validated at Asset Server startup. Changes to the model version, sampling parameters, or post-processing pipeline affect all assets uniformly and require editing only this layer.

**Layer 2: Style Templates.** The prompt templates stored in a centralized JSON configuration file define the stylistic constraints applied to each asset family. For tile assets (structures, objects, terrain, units), the template enforces top-down perspective via the LoRA trigger token `<tdp>` and the angle phrase "top-down view.", specifies pixel-art aesthetics ("crisp pixel edges, no anti-aliasing, sharp blocky pixels"), sets the output format ("isolate on a plain white background, centered single asset on white"), and mandates grounded, stable perspective with no floating objects. For leader portraits, the template uses cinematic language appropriate to splash screens and character portraits, omitting the `<tdp>` trigger since leaders are rendered in a painterly oil style rather than pixel art. For background tiles, the template enforces seamless tiling and omits the LoRA trigger since ground textures do not require top-down perspective styling. This separation means that a style-level change—adjusting the pixel-art sharpness language, modifying the background color, or updating the LoRA trigger phrase—requires editing only this single configuration file, and the change propagates consistently to all assets in the affected families.

**Layer 3: Semantic Descriptions.** A set of enum classes define the combinatorial vocabulary for asset generation, each containing hand-crafted prose descriptions for every enum value. For structures, the four enums are category (fortification, production, housing, sacred), style (Nordic wooden, Anglo-Saxon stone, Norman Romanesque, Gothic, Mediterranean, Slavic timber, Moorish), condition (pristine, weathered, ruined, under construction, fortified), and scale (small, medium, large). For objects, the enums are category (vegetation, geological, rural props, urban props, debris), biome (temperate forest, taiga, desert, swamp, mountain, coastal, grassland), and season (spring, summer, autumn, winter). For terrain elevation features, the enums are category (hill, slope, cliff, ridge, depression), scale (low, medium, high), and material (earthen, sandy, rocky, snowy, muddy). For leaders, the enums are archetype (warrior queen, warrior king, philosopher king, merchant prince, spiritual leader, diplomat, tyrant, visionary), culture (spanning ancient Egyptian through Islamic Golden Age), time of day (from dawn through storm), and mood (from triumphant through contemplative). Each enum value maps to a prose description of 20–40 words that captures its visual essence. For example, the fortification category maps to "a sturdy defensive structure with crenellated battlements, arrow slits, thick stone walls, watchtower, military functionality." This layer is the primary extension point: adding a new architectural style requires only adding one enum value with its prose description, and it becomes available across all asset types that use that enum.

**Layer 4: Assembly Logic.** Python prompt builder functions in each pipeline module (leader, tile, unit) combine the preceding three layers. They load the appropriate style template, select the relevant semantic descriptions based on the client's requested enum values, substitute these descriptions into the template's placeholders using Jinja2-style rendering, and validate that all required placeholders have been filled. The assembled prompt string is then injected into the ComfyUI workflow JSON and submitted for generation. This layer contains no hardcoded style directives or prompt text—all language lives in the JSON templates and enum prose—making it purely mechanical assembly code that rarely needs modification.

This four-layer separation yields several practical benefits. Style consistency is achieved because all assets within a family share the same template. Maintainability is improved because style changes require editing only Layer 2. Extensibility is straightforward because new asset types require only Layer 3 additions. Testability is enhanced because each layer can be validated independently: workflow JSONs are validated against ComfyUI schemas, templates are checked for placeholder completeness, and enum prose is reviewed for visual accuracy.

It is worth noting that FLUX.2-family models do not support negative prompts (see §III.B for the technical reason behind this constraint). All prompt templates therefore use positive-only, affirmative language, describing what should appear rather than what should not. This constraint influenced the template design: rather than instructing the model to avoid isometric angles or side views, the templates positively assert "top-down view" and "grounded stable perspective."

### C. Leader Portrait Pipeline

Leader portraits present a unique challenge: the same character must appear recognizably consistent across three different views—a dramatic full-screen splash image, a close-up profile portrait for UI displays, and an action scene showing the leader in a dynamic pose. A single txt2img generation per view would produce three different-looking characters, since diffusion models have no inherent identity memory across generations.

Our solution is a three-stage img2img pipeline that chains generations to preserve identity. All three stages use the same archetype, culture, time of day, and mood parameters, ensuring thematic consistency.

Figure 4 illustrates the pipeline with calibration sweet spots.

**Stage 1: Splash Art (txt2img).** A full txt2img generation at 1920×1088 resolution (16:9 cinematic aspect ratio) with denoise strength 1.0 establishes the canonical character appearance. The guidance scale is set to 3.5, balancing creative freedom with prompt adherence. The random seed is stored in the database, enabling exact reproduction of any splash art given the same model weights and ComfyUI configuration. This image serves as the reference for all subsequent stages.

**Stage 2: Profile Portrait (img2img from Splash).** The splash art is used as a reference image for a 512×512 square portrait with denoise strength 0.90 and guidance scale 8.0. The high guidance scale maximizes prompt adherence to preserve facial features, attire details, and color palette, while the relatively high denoise strength (close to 1.0) allows the significant composition change from wide cinematic framing to tight close-up. Empirical testing during development revealed that denoise values at or above 0.95 cause identity loss—the generated face no longer resembles the splash art—while values at or below 0.80 prevent meaningful composition changes, resulting in a cropped version of the splash rather than a true portrait. The sweet spot at 0.90 preserves identity while enabling the framing shift.

**Stage 3: Action Scene (img2img with reference stitching).** The splash reference is combined with a fully transparent placeholder via image stitching within ComfyUI, then Lanczos-rescaled to 1920×1088 before VAE encoding. This stitch-then-encode approach produces a single coherent latent---avoiding the boundary artifacts that would arise from encoding two references separately---while the denoise strength of 0.85 and guidance scale of 4.5 allow dramatic compositional changes. For multi-leader scenes, the placeholder is replaced with a second leader's reference image.

The combinatorial variety available through the leader enums is substantial: 8 archetypes × 12 cultures × 6 times of day × 8 moods yields 4,608 possible prompt combinations for each of the three stages. In practice, the game maps each of the three AI leaders and the human player's custom leader to specific archetype-culture combinations, and the time of day and mood are selected to match the game context (a triumphant mood for victory, a grim determined mood for wartime).

### D. Multi-Mode Generation and Post-Processing

The Asset Server supports three generation modes, selectable per asset family through configuration. This design enables the system to function across a spectrum of deployment scenarios, from full GPU-accelerated generation to development environments without any GPU.

**ComfyUI mode** performs full AI generation using FLUX.2 Klein 4B Distilled with the LoRA adapter applied. This is the production mode that produces the highest-quality assets.

**Static mode** serves pre-generated PNG files from a filesystem catalog. These assets were previously generated in ComfyUI mode and cached to disk, providing consistent quality without GPU inference. This mode is useful when the ComfyUI service is unavailable but pre-generated assets exist.

**Placeholder mode** generates simple colored rectangles with text labels using the Python Imaging Library (PIL). These are functional but aesthetically minimal, intended for development and testing without any GPU dependency.

Post-processing follows generation in ComfyUI mode. Images are generated at 1024×1024---the minimum native resolution FLUX.2 Klein 4B supports---and Lanczos-downscaled to 256×256 to minimize storage footprint while preserving the crisp edge definition essential for pixel-art aesthetics. Background removal using a segmentation model produces transparent backgrounds for structures, objects, terrain features, and units; background tiles and leader portraits skip this step since tiles must fill their frame and leader portraits benefit from cinematic backgrounds. All file writes use atomic semantics—writing to a temporary file and then performing an atomic rename—to prevent corruption if the server crashes during generation.

The six asset families span a wide range of combinatorial variety. Structures support 420 possible combinations (4 categories × 7 styles × 5 conditions × 3 scales). Nature objects support 140 combinations (5 categories × 7 biomes × 4 seasons). Terrain elevation features support 75 combinations (5 categories × 3 scales × 5 materials). Units support 4 types (archer, scout, settler, warrior). Background tiles support 5 types (water, grass, sand, stone, dirt). Leader portraits, as discussed, support thousands of combinations through their multi-enum parameter space.

---

## VI. LORA FINE-TUNING FOR STYLE ADAPTATION

While FLUX.2 Klein 4B Distilled provides strong base image generation capabilities, achieving consistent top-down perspective and medieval pixel-art styling across hundreds of generated assets requires model adaptation. Prompt engineering alone on the base model produces unreliable results: the phrase "top-down view" yields a mixture of true orthogonal top-down, isometric, and ¾-overhead perspectives depending on the random seed, and the base model's interpretation of "medieval" drifts between photorealistic, painterly, and cartoonish renderings. For an automated game asset pipeline where every asset on a square grid must share the same camera plane and visual language, this inconsistency is unacceptable.

This section describes our LoRA fine-tuning pipeline: the dataset curation and training configuration, the 3×2 experiment matrix that systematically evaluates the interaction between caption detail and LoRA rank, the evaluation methodology and results, and the deployment of the selected checkpoint to the production asset pipeline.

### A. Dataset and Training Setup

The training dataset consists of 100 top-down medieval pixel-art images at 1024×1024 resolution. These images were generated through a knowledge distillation pipeline: a FLUX.2 [dev] (32B) [22] teacher model with a Multi-Angles LoRA v2 [23] enforced top-down perspective at generation time, producing high-quality images that a FLUX.2 Klein 4B student model would learn to replicate through LoRA fine-tuning. Post-generation processing applied palette quantization to achieve pixel-art aesthetics and background removal for clean subject isolation.

The dataset was manually curated from a larger pool of approximately 150–200 generated
images. Curation criteria included perspective accuracy (strict top-down view with no
isometric or oblique drift), compositional clarity (subject clearly visible and
well-framed), architectural coherence (period-appropriate medieval features without
anachronistic elements), and diversity (representation across structure types including
fortifications, production buildings, housing, and sacred structures). The curated set
is heavily skewed toward structures (97 of 100 images), with only 2 vegetation images
(bramble masses, reed clusters) and 1 terrain image (a jagged boulder). This imbalance
was not intentional—it reflects where the generation pipeline worked well and where it
struggled. Structures came out clean and readable; vegetation blurred into indistinct
masses after pixel-art quantization; rock formations rarely survived the strict top-down
constraint with convincing geometry. Each usable non-structure image required many more
generation attempts, and within a fixed curation budget, the practical outcome was a
structure-dominated dataset. The skew is worth acknowledging because it makes the
evaluation more meaningful: if the LoRA transfers top-down perspective to categories it
barely saw during training, the angle concept has been genuinely isolated from subject
matter.

Each image was captioned at three detail levels to support the experiment matrix. **Detailed captions** (50–100 words) describe materials, architectural features, condition, and context in rich prose. **Minimal captions** (20–30 words) focus on essential characteristics—building type, primary materials, style period. **Ultra-minimal captions** (5–10 words) specify only the asset type and the pixel-art style designation. This three-level design tests a core hypothesis: less text detail may produce less style binding, allowing the LoRA to learn a purer perspective concept that generalizes better to unseen asset types.

The trigger token `<tdp>` (standing for top-down perspective) was chosen to be short, domain-agnostic, and unlikely to appear in natural language. At training time, the Ostris AI Toolkit replaces placeholder tokens in caption sidecar files with `<tdp>`, teaching the model to associate this token with the top-down perspective and medieval architectural style present in the training images. At inference time, the token combined with the phrase "top-down view." activates the LoRA adapter's influence.

All six experiments shared a common training configuration: 2,500 training steps, batch size 1, adamw8bit optimizer with weight decay, flowmatch scheduler with weighted timestep sampling, and checkpoint saves every 200 steps. Training was performed on a Blackwell RTX 6000 GPU with FP8 precision, requiring approximately 15–18 GB of VRAM per experiment and completing in roughly 2 hours per experiment.

### B. Experiment Matrix and Methodology

The experiment matrix follows a 3×2 factorial design: three caption detail levels (detailed, minimal, ultra-minimal) crossed with two LoRA rank configurations (high: linear rank 128, convolution rank 64; low: linear rank 64, convolution rank 32). An additional ultra-low variant (rank 32/16) was trained as an outlier for comparison. This design enables systematic evaluation of how caption granularity and model capacity interact during fine-tuning for perspective-conditioned generation.

The evaluation methodology uses eight validation prompts spanning in-distribution and out-of-distribution subjects. Four in-distribution prompts target medieval structures and objects similar to the training data, testing whether the LoRA faithfully reproduces the learned style. Four out-of-distribution prompts target modern, non-medieval subjects (a sports car, a spaceship, a coffee cup, a suburban house), testing whether the LoRA generalizes the perspective concept beyond its training domain or whether the medieval style inappropriately contaminates semantically distant subjects. All prompts include the trigger token and angle phrase. Each experiment generates samples against all eight prompts at every 200-step checkpoint, producing a rich grid for qualitative comparison.

A critical evaluation is the style-leakage test: a prompt that includes the `<tdp>` trigger token alongside a modern red sports car verifies whether the LoRA's medieval styling contaminates anachronistic subjects when the trigger is active. If the generated sports car remains recognizably modern with glossy red paint and aerodynamic curves despite the active trigger, the LoRA appropriately scopes its influence to perspective enforcement. If medieval architectural features or pixel-art texturing appear, style leakage is present.

### C. Results and Deployed Checkpoint

Prior to LoRA fine-tuning, we evaluated several base models for their ability to produce consistent top-down perspective through prompting alone. Stable Diffusion XL [24], FLUX.1 [dev], and FLUX.2 [dev] [22] all failed to achieve reliable camera positioning---the phrase "top-down view" produced a mixture of orthogonal, isometric, and oblique angles varying unpredictably with the random seed. Even FLUX.2 [dev] augmented with the Multi-Angles LoRA v2 [23] exhibited angle discrepancies across generations, as the adapter was designed for 72 discrete camera positions rather than strict overhead enforcement. Our custom-trained LoRA, by contrast, was optimized specifically for consistent top-down perspective and enforces this constraint reliably across all generated assets, as demonstrated below.

Qualitative evaluation of the complete results grid—six LoRA variants plus base model baseline, evaluated against eight prompts at multiple checkpoints—yields several key findings.

Figure 5 presents a representative sample from this evaluation grid.

**The base model without LoRA cannot reliably enforce top-down perspective.** Text prompts alone, even with the phrase "top-down view.", produce a mixture of perspectives including isometric, ¾-overhead, and oblique angles, with the specific angle varying by random seed. While some individual generations achieve the desired perspective, the hit rate is well below the consistency threshold required for an automated pipeline. This confirms the necessity of fine-tuning.

**All six LoRA variants enforce consistent top-down perspective.** Across in-distribution structures and out-of-distribution units and terrain, every variant reliably produces overhead camera angles. The perspective concept transfers across categories because the geometric properties of "viewed from above" are identical regardless of subject matter.

**Caption detail and rank interact in a fidelity–generalization trade-off.** The detailed-high variant (detailed captions, high rank) achieves maximum in-distribution architectural fidelity—structures rendered with crisp crenellations, visible timber framing, and distinct stone masonry courses—at the cost of slightly reduced out-of-distribution generalization. The ultra-low variant (ultra-minimal captions, lowest rank) achieves the strongest generalization to unseen asset types but produces less architecturally specific structures. The minimal-high variant occupies a middle ground, balancing detail reproduction with generalization capability.

**Training dynamics reveal distinct regimes.** Early checkpoints (steps 500–1,000) produce noisy outputs with inconsistent perspective and weak styling. The sweet spot emerges around steps 1,500–2,000, where perspective consistency and style adherence peak simultaneously. Beyond step 2,200, some experiments exhibit overfitting artifacts: rigid repetition of training-set layouts across different seeds, color palette collapse toward the training distribution's dominant tones, and reduced compositional diversity. These observations confirm that LoRA training for perspective-conditioned generation benefits from early stopping before full convergence.

**Style leakage was evaluated using a trigger-present probe.** The probe includes the `<tdp>` trigger token alongside a semantically distant modern subject—a red sports car. This tests whether the LoRA's medieval styling contaminates anachronistic subjects when the trigger is active. The `detailed-high` variant showed the cleanest separation: glossy red paint, aerodynamic curves, and contemporary design language remained intact with minimal medieval palette shift. In contrast, `ultra-high`, `minimal-low`, and `minimal-high` exhibited subtle art-style mimicry—earthen color tones and faint surface texturing characteristic of the training distribution. This confirms that style leakage exists on a spectrum modulated by caption detail and rank configuration, and that `detailed-high` at step 1,800 provides the best balance of perspective enforcement and domain-appropriate restraint.

**The detailed-high variant at step 1,800 was selected for deployment.** This checkpoint achieves maximum in-distribution architectural fidelity while maintaining acceptable out-of-distribution generalization and avoiding the overfitting artifacts observed at later steps. The deployed LoRA file is 353 MB (high-rank configuration: linear rank 128, convolution rank 64) and loaded at strength 1.0 (full influence) by the ComfyUI workflow. Lower-rank variants in the experiment matrix ranged from 89 MB (ultra-low, rank 32/16) to 177 MB (low, rank 64/32), with file size directly reflecting the rank–capacity–generalization trade-off explored in the 3×2 design. The trigger token `<tdp>` and angle phrase "top-down view." are baked into the Layer 2 style templates for all tile asset families, ensuring automatic activation for every structure, object, terrain, and unit generation.

---

## VII. FRONTEND INTEGRATION

The Next.js frontend binds the Backend game engine and Asset Server into a cohesive player experience. While the frontend does not itself implement AI algorithms, it plays a critical role in the AI integration story: it resolves game entities to generative assets, implements graceful degradation when AI services are unavailable, and provides the diplomatic interface through which players interact with LLM-driven AI leaders.

### A. Asset Resolution and Graceful Degradation

When the game state updates, the frontend's asset manifest resolver determines which generative assets are needed and fans out requests to the Asset Server. Mapping tables translate game entities to asset server parameters: the 10 engine terrain types are collapsed onto 5 background tile types (grass, stone, sand, water, dirt), 7 unit types map to 4 asset server unit categories (archer, scout, settler, warrior), and each AI leader's traits map to architectural styles for their civilization's structures.

The resolver implements four-tier fallback, attempted in order. Tier 1 requests full AI-generated assets from the Asset Server in ComfyUI mode—the highest quality, requiring GPU inference. If the Asset Server is unreachable, Tier 2 falls back to static pre-generated PNG files served from the Asset Server's filesystem catalog, providing consistent quality without GPU dependency. If static assets are unavailable, Tier 3 uses placeholder mode—colored rectangles with text labels generated by the Python Imaging Library, functional but aesthetically minimal. If the Asset Server is completely unreachable, Tier 4 provides built-in fallbacks: color-coded tiles from a hardcoded terrain color palette, Unicode glyph characters for units, and initial letters for leader portraits. This four-tier design ensures the game remains playable—with progressively reduced visual quality—regardless of which AI services are available.

### B. Diplomatic Interface

The diplomacy system provides a chat-based interface where human players compose free-text messages to AI leaders, select a message type (chat, threat, offer peace, declare war, propose alliance), and receive LLM-generated responses in the leader's characteristic voice. The AI's response reflects its persona, the current diplomatic relationship score, and the conversation history.

The relationship tracking display shows each AI leader's stance (peace, war, or alliance), a numeric relationship score from -100 to +100 with a color-coded indicator, and a history of recent diplomatic events with their associated relationship deltas. This transparency helps players understand the consequences of their diplomatic choices—declaring war costs 50 relationship points with all civilizations that have met the target, while offering and accepting peace builds trust over time.

---

Having described all system components, we now evaluate their integrated performance and output quality.

## VIII. EVALUATION

We evaluate StrategAI across three dimensions: system performance, AI behavior quality, and asset quality. Where quantitative measurements are available, we report them with appropriate caveats about methodology. Where only qualitative assessment is possible, we describe observed patterns and acknowledge the limitations of subjective evaluation.

### A. System Performance

LLM decision latency is the dominant factor in turn-processing time. Each AI civilization's turn requires a round-trip to the OpenAI API: the serialized game state (approximately 2,000–4,000 tokens of prompt context plus conversation history and memory logs) is sent, and the LLM responds with one to five function calls comprising roughly 100–500 tokens of output. This round-trip typically takes 2–4 seconds per AI civilization, making it the pacing bottleneck for AI turns. This latency is acceptable for turn-based gameplay, where players expect a brief pause between their turn and the next, but would be prohibitive for real-time applications.

Asset generation times were informally observed during development rather than measured through systematic benchmarking. On a Blackwell RTX 6000 with FP8 precision, simple assets (background tiles, small structures) generated in approximately 2.5–4 seconds, while complex leader portraits required 4–6 seconds. On an RTX 3090, the range shifted upward to approximately 3.5–7 seconds. These observations should be interpreted as rough guidance rather than rigorous performance data; generation time varies substantially with prompt complexity, random seed, and GPU load. An estimated cache hit rate based on expected gameplay patterns—where terrain types, common structures, and unit types repeat across turns—suggests that caching substantially reduces redundant generation in practice, but this estimate has not been empirically validated through instrumented measurement.

Frontend rendering performance was observed to maintain 60 frames per second on maps of up to approximately 1,000 visible tiles with SVG-based rendering. The use of React's memoization for tile components and SVG's native efficiency for flat-color geometric shapes contributes to this performance profile.

### B. AI Behavior Quality

Qualitative observation of AI civilization behavior across multiple playthroughs reveals distinct strategic patterns aligned with the designed personas.

Genghis Khan consistently pursued aggressive expansion: early military unit production, rapid declaration of war on encountered civilizations, and sustained military pressure. His behavior exhibited the designed vindictiveness—civilizations that threatened or insulted him were targeted for war within one to two turns, consistent with his persona prompt's instruction to remember every insult.

Cleopatra pursued diplomatic strategies: forming alliances, playing factions against each other through selective messaging, and avoiding direct military confrontation unless her civilization was directly threatened or an overwhelming advantage presented itself. Her diplomatic messages exhibited the warm, witty tone described in her persona, with flattery directed at potential allies and mockery reserved for rivals.

Gandhi prioritized peaceful development: early investment in technology research, minimal military production beyond basic defense, and active pursuit of alliances and trade relationships. When threatened, his diplomatic responses reflected the principled protest language of his persona before any military response.

Emergent behaviors—strategies not explicitly programmed but arising from the LLM's reasoning—included opportunistic attacks on weakened neighbors, the formation of defensive alliances against an aggressive Mongolia, and revenge behavior where Genghis Khan would declare war on civilizations that had previously attacked him, even after extended periods of peace.

Observed limitations include occasional repetition of strategies that the engine had previously rejected (partially mitigated by the memory system surfacing rejection feedback), suboptimal city placement in edge cases where the site selection algorithm's preferences diverged from strategically ideal locations, and difficulty coordinating simultaneous multi-unit attacks—a consequence of the intent abstraction preventing the LLM from issuing coordinated tactical orders. We acknowledge the absence of quantitative metrics for AI behavior quality; the observations reported here are qualitative and subjective, based on developer playtesting rather than controlled user studies.

### C. Asset Quality

Visual inspection of generated assets across the six families reveals several patterns.

Style consistency is achieved across asset families: structures, objects, terrain features, and units all exhibit the same pixel-art aesthetic with crisp edges, limited color palettes, and consistent lighting. The LoRA adapter's enforcement of top-down perspective is reliable—generated assets consistently show the subject from directly above, with appropriate occlusion and layout for the overhead view.

The 420 possible structure combinations produce visually distinct results. Fortifications are rendered with battlements and arrow slits; production buildings with workshops and forges; housing with residential architectural features; sacred structures with appropriate religious architectural vocabulary. The seven architectural styles produce meaningfully different visual outputs: Nordic wooden structures differ visibly from Moorish arched designs, which differ from Gothic stone cathedrals.

Leader portraits preserve character identity across the three pipeline stages. A leader generated with a specific archetype and culture combination in the splash stage produces a recognizable profile portrait and action scene—facial features, skin tone, hair style, and attire remain consistent. This identity preservation is achieved through the img2img pipeline's use of the splash art as reference, with the denoise parameters calibrated to allow compositional change while preserving facial identity.

We acknowledge the absence of automated quantitative metrics for asset quality. Metrics such as Fréchet Inception Distance (FID), CLIP score, or DINO similarity could provide objective quality measures but were not implemented in this phase of the project. The quality assessment presented here is based on qualitative visual inspection by the development team.

---

## IX. ETHICAL CONSIDERATIONS

The integration of generative AI technologies into interactive entertainment raises ethical considerations spanning bias, environmental impact, intellectual property, and reproducibility. This section examines each concern in the context of StrategAI's specific design choices and honestly assesses the limitations of the mitigations employed.

### A. Bias in Generated Content

StrategAI employs three AI civilizations modeled after historical figures: Genghis Khan, Cleopatra, and Gandhi. While these figures were selected to create recognizable and strategically diverse archetypes, the use of culturally specific historical figures carries inherent risks of stereotyping and reductive characterization. LLMs trained on internet-scale corpora have been shown to amplify stereotypes related to nationality, gender, and ethnicity [11], and the persona prompts, while carefully written to emphasize respectful depiction, are mitigations layered on top of a base model whose training distribution may contain biased representations. The system does not implement explicit bias detection or output filtering for LLM-generated diplomatic text, relying instead on the persona prompt to steer generation toward respectful territory.

The diffusion-based asset pipeline introduces additional representation concerns. Crawford and Paglen [18] have documented how training dataset composition shapes the politics of machine learning systems, and the curated training dataset of 100 medieval pixel-art images is dominated by European medieval architectural styles—Gothic cathedrals, timber-framed houses, Norman stone castles—which means generated assets for non-European civilizations may exhibit stylistic incongruity. An Egyptian civilization under Cleopatra might receive structures that inadvertently blend Middle Eastern motifs with European medieval elements, or leader portraits that default to Western facial feature distributions present in the base model's training data. This is an acknowledged limitation of the current dataset composition, and future iterations should include culturally diverse training data spanning the architectural traditions represented by all playable civilizations.

### B. Environmental Impact

The computational demands of generative AI carry measurable environmental costs. Asset generation using FLUX.2 Klein 4B Distilled consumes approximately 0.21–0.58 watt-hours per image on workstation GPUs, based on observed generation times and typical GPU power draw. The LoRA training process required approximately 2 hours per experiment on a Blackwell RTX 6000, totaling approximately 12 GPU-hours for the complete 3×2 experiment matrix. These figures are modest compared to large-scale model training runs, which can consume thousands of megawatt-hours, but the inference costs accumulate as the system scales to many users and many game sessions.

Several design decisions mitigate environmental impact [16]. FP8 quantization halves the model's VRAM requirement and correspondingly reduces inference energy. The four-tier fallback system enables operators to select the most energy-appropriate generation mode for their deployment context, including a zero-GPU placeholder mode for development. Caching reduces redundant generation of identical asset configurations. The rolling memory window of 8 turns prevents unbounded growth of LLM context, constraining token consumption per API call.

LLM API calls constitute the second energy source, though their footprint is indirect since computation occurs on OpenAI's infrastructure. Over a typical 100-turn game with three AI civilizations, cumulative token processing is estimated at 600,000–1,500,000 tokens. While individual API calls have modest energy footprints, aggregate usage across many game sessions is non-trivial.

### C. Copyright and Intellectual Property

The legal status of AI-generated content remains unsettled across jurisdictions. Three intellectual property concerns intersect in this system.

First, the training dataset for the LoRA adapter was generated using FLUX.2 [dev] (32B) as a teacher model and curated by the StrategAI team. The generated images are synthetic—they do not reproduce any specific copyrighted work—but the legal status of training a model on synthetic data derived from another model's outputs exists in uncertain legal territory. The teacher model's license (non-commercial) imposes restrictions that flow through to derivative works, though the extent to which LoRA weights trained on synthetic outputs constitute a derivative work is unresolved.

Second, the copyright status of AI-generated game assets is unclear. Under current guidance from the U.S. Copyright Office, works created entirely by artificial intelligence without sufficient human creative input are not eligible for copyright protection [19]. Hertzmann [20] explores the broader philosophical question of whether computational systems can produce works meriting the designation of art, a debate with direct implications for generative game assets. The StrategAI asset pipeline involves substantial human creative choices—designing the four-layer prompt architecture, authoring hand-crafted semantic descriptions for each asset variant, curating the training dataset, selecting model configurations, and calibrating denoise parameters—but the actual pixel values of each generated image are determined by the diffusion model's stochastic sampling process. Whether this level of human involvement satisfies the originality requirement for copyright protection is uncertain. For game developers considering generative asset pipelines, this uncertainty represents a practical risk.

Third, model weights carry their own licensing terms. FLUX.2 Klein 4B Distilled is released under the Apache 2.0 license, which permits both research and commercial use with minimal restrictions. This was a deliberate selection criterion: the larger FLUX.2 Klein 9B model carries a non-commercial license incompatible with the project's goal of demonstrating commercially viable game development tools. The custom-trained LoRA adapter weights inherit license restrictions from the base model.

### D. Reproducibility

Reproducibility is a cornerstone of scientific research, yet generative AI systems pose significant challenges to reproducible experimentation. StrategAI addresses these partially through several design decisions, though fundamental limitations remain.

The Asset Server uses cryptographically strong random seeds (32-bit values from Python's secrets module) stored in the database alongside generated assets. The Backend uses a deterministic PRNG seeded from map generation parameters for reproducible map layouts. Given the same model weights and ComfyUI configuration, any generated image can be exactly reproduced by re-submitting the stored seed. The LoRA training pipeline fixed random seeds across all six experiments, ensuring that differences between configurations are attributable to the experimental variables rather than stochastic variation. The complete codebase, curated dataset, and trained LoRA weights are publicly available under open-source licenses.

However, a critical reproducibility limitation stems from the LLM integration. GPT-5.4-mini is accessed through OpenAI's API as a cloud service, not as a downloadable, version-pinned model. OpenAI periodically updates model snapshots, and these updates can change model behavior even when the same prompt and parameters are provided. An AI civilization that pursued a particular strategy in one month might behave differently when tested against a later model snapshot. This means that LLM behavior reported in this paper may not be exactly reproducible by future researchers. The intent-based abstraction partially mitigates this by constraining LLM behavior to nine predefined actions, limiting the surface area of potential behavioral drift. However, the specific strategic choices made within those constraints are influenced by the LLM's evolving reasoning patterns and cannot be guaranteed to replicate.

The use of cloud-hosted LLM APIs also introduces an availability dependency. OpenAI's pricing, rate limits, and model deprecation schedules are outside the project's control. Future work could explore locally hosted, open-weight models as drop-in replacements that would provide full reproducibility and independence from external services.

---

## X. LIMITATIONS AND FUTURE WORK

### A. Architectural Limitations

The current system architecture has several constraints that limit deployment scalability. The Backend uses an in-memory game store with a threading lock, which restricts deployment to a single process and prevents horizontal scaling across multiple server instances. A database-backed store with session-level isolation would enable multi-instance deployment.

The Asset Server holds HTTP connections open for the duration of image generation—typically 2–7 seconds—which limits concurrent request throughput. An asynchronous job queue with progress notifications would decouple request acceptance from generation completion, improving perceived responsiveness and enabling better resource utilization.

The Frontend mediates all cross-service communication. While this mediation pattern simplifies each service's responsibilities, it creates a single point of coordination and increases frontend complexity. A service mesh or message bus could reduce this coupling in a production deployment.

### B. AI Limitations

The LLM-driven AI exhibits several behavioral limitations. Multi-turn strategic planning—where the AI pursues a goal requiring coordinated actions across several turns—is limited. The LLM reasons reactively, responding to the current game state, rather than proactively pursuing long-term objectives. This is a fundamental limitation of stateless LLM inference: even with rolling memory, the model lacks the persistent planning state that human players maintain.

AI civilizations act independently with no coalition logic. While bilateral alliances are supported through the diplomacy system, there is no mechanism for three civilizations to coordinate a joint military campaign, divide territory, or negotiate multi-party agreements. Multi-agent coordination remains an open research challenge.

Human players can, with experience, learn to exploit AI behavioral patterns. The memory system mitigates the most obvious exploits—an AI that has been betrayed will not immediately trust the betrayer again—but does not eliminate subtler forms of exploitation such as baiting the AI into unfavorable engagements or manipulating its expansion priorities through feints.

### C. Future Directions

Several directions would extend this work. Persistent storage using PostgreSQL would enable game state persistence, multi-instance deployment, and long-running campaigns. Locally hosted open-weight LLMs would eliminate the cloud API dependency, providing full reproducibility and removing per-token costs. Multi-agent coalition logic would enrich diplomatic gameplay by enabling coordinated AI behavior. Automated quantitative evaluation metrics—FID and CLIP score for asset quality, win-rate analysis for AI behavior, user studies for player experience—would replace the current reliance on qualitative assessment. Expanded asset types including character animations, environmental sound effects, and UI elements would broaden the generative pipeline's scope. Procedural narrative generation using LLMs to produce historical chronicles based on game events would add a unique storytelling dimension to each playthrough.

---

## XI. CONCLUSION

StrategAI demonstrates that generative AI technologies—Large Language Models for strategic reasoning and Diffusion Transformers for asset generation—can be integrated into a cohesive, functional game system on workstation-grade hardware. Three architectural patterns underpin this integration.

First, intent-based abstraction bridges the gap between LLM reasoning and game-engine execution. By constraining LLM output to nine high-level intents and resolving those intents through deterministic operations, the system leverages language models' strategic reasoning capabilities while maintaining the rule compliance and numerical precision that games require. The LLM never selects unit identifiers, never computes grid distances, and never validates game rules—responsibilities that remain with deterministic code—yet retains meaningful strategic agency over expansion, warfare, diplomacy, and development.

Second, the four-layer prompt architecture combined with LoRA fine-tuning enables consistent, on-demand asset generation across six diverse families. The separation of workflow configuration, style templates, semantic descriptions, and assembly logic makes the prompt system maintainable and extensible, while the LoRA adapter—trained through a systematic 3×2 experiment matrix on a curated 100-image dataset—enforces the perspective and style consistency that automated pipelines require. The trigger token mechanism provides selective control, ensuring the adapter's influence activates only for tile assets while leaving leader portraits and background tiles unaffected.

Third, graceful degradation through four-tier fallback ensures the system remains functional regardless of AI service availability. From full GPU-accelerated generation down to built-in color codes and glyph characters, the game degrades progressively rather than failing catastrophically.

The limitations are real: cloud API dependency undermines reproducibility, qualitative evaluation lacks the rigor of quantitative metrics, and the single-instance architecture constrains deployment. But the integration patterns demonstrated here—intent abstraction, layered prompt engineering, parameter-efficient fine-tuning, and multi-tier fallback—provide a practical roadmap for independent developers seeking to harness generative AI in their own projects. As models continue to improve in quality, speed, and efficiency, these patterns will only become more accessible and more powerful.

---

## REFERENCES

[1] J. S. Park, J. C. O'Brien, C. J. Cai, M. R. Morris, P. Liang, and M. S. Bernstein, "Generative agents: Interactive simulacra of human behavior," in *Proc. 36th Annual ACM Symposium on User Interface Software and Technology (UIST)*, 2023.

[2] G. Wang, Y. Xie, Y. Jiang, A. Mandlekar, C. Xiao, Y. Zhu, L. Fan, and A. Anandkumar, "Voyager: An open-ended embodied agent with large language models," in *Proc. NeurIPS*, 2023.

[3] T. Schick, J. Dwivedi-Yu, R. Dessì, R. Raileanu, M. Lomeli, L. Zettlemoyer, N. Cancedda, and T. Scialom, "Toolformer: Language models can teach themselves to use tools," in *Proc. NeurIPS*, 2023.

[4] M. Toy, G. Wichman, K. Arnold, and J. Lane, *Rogue*, Version Unix. 1980.

[5] Hello Games, "No Man's Sky," 2016.

[6] J. Ho, A. Jain, and P. Abbeel, "Denoising diffusion probabilistic models," in *Proc. NeurIPS*, 2020.

[7] R. Rombach, A. Blattmann, D. Lorenz, P. Esser, and B. Ommer, "High-resolution image synthesis with latent diffusion models," in *Proc. IEEE/CVF Conf. Computer Vision and Pattern Recognition (CVPR)*, 2022.

[8] W. Peebles and S. Xie, "Scalable diffusion models with transformers," in *Proc. IEEE/CVF Int. Conf. Computer Vision (ICCV)*, 2023.

[9] X. Liu, C. Gong, and Q. Liu, "Flow straight and fast: Learning to generate and transfer data with rectified flow," in *Proc. ICLR*, 2023.

[10] E. J. Hu, Y. Shen, P. Wallis, Z. Allen-Zhu, Y. Li, S. Wang, L. Wang, and W. Chen, "LoRA: Low-rank adaptation of large language models," in *Proc. ICLR*, 2022.

[11] E. M. Bender, T. Gebru, A. McMillan-Major, and S. Shmitchell, "On the dangers of stochastic parrots: Can language models be too big?," in *Proc. ACM Conf. Fairness, Accountability, and Transparency (FAccT)*, 2021, pp. 610–623.

[12] C. Simpson, "Behavior trees for AI: How they work," *Gamasutra*, 2014.

[13] S. Rabin, *Game AI Pro: Collected Wisdom of Game AI Professionals*. CRC Press, 2013.

[14] K. Perlin, "An image synthesizer," *ACM SIGGRAPH Computer Graphics*, vol. 19, no. 3, pp. 287–296, 1985.

[15] J. Togelius, G. N. Yannakakis, K. O. Stanley, and C. Browne, "Search-based procedural content generation: A taxonomy and survey," *IEEE Trans. Comput. Intell. AI Games*, vol. 3, no. 3, pp. 172–186, 2011.

[16] E. Strubell, A. Ganesh, and A. McCallum, "Energy and policy considerations for deep learning in NLP," in *Proc. ACL*, 2019, pp. 3645–3650.

[17] M. Wooldridge, *An Introduction to MultiAgent Systems*. John Wiley & Sons, 2009.

[18] K. Crawford and T. Paglen, "Excavating AI: The politics of images in machine learning training sets," 2019. [Online]. Available: https://excavating.ai

[19] P. Samuelson, "Generative AI meets copyright," *Science*, vol. 381, no. 6654, pp. 158–161, 2023.

[20] A. Hertzmann, "Can computers create art?," *Arts*, vol. 7, no. 2, 2018.

[21] ComfyUI, "ComfyUI: A powerful and modular Stable Diffusion GUI and backend," 2023. [Online]. Available: https://github.com/comfyanonymous/ComfyUI

[22] Black Forest Labs, "FLUX.2: Frontier visual intelligence," Blog post, Nov. 2025. [Online]. Available: https://bfl.ai/blog/flux-2

[23] lovis93, "Flux-2-Multi-Angles-LoRA-v2: 72 camera angle positions for FLUX.2," LoRA adapter, 2025. [Online]. Available: https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2

[24] D. Podell, Z. English, K. Lacey, A. Blattmann, T. Dockhorn, J. Müller, J. Penna, and R. Rombach, "SDXL: Improving latent diffusion models for high-resolution image synthesis," in *Proc. 12th Int. Conf. Learning Representations (ICLR)*, 2024.
