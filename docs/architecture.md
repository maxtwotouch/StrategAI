# Image Diffusion Service: Production Architecture

## 1. System Overview
The Medieval Pixel Art Image Service is a decoupled, highly scalable web service that provides on-demand generative AI assets, acting as the dynamic engine behind the game's terrain, structures, and storytelling. 

Currently, the system is designed with a **Mock-First** approach to allow immediate frontend/game-engine integration without incurring GPU costs, while maintaining the exact operational contract needed for the final production deployment.

## 2. Core Operational Flow
1. **Request Intake**: `FastAPI` validates incoming payloads (`GenerationRequest`) using strict Pydantic schemas. 
2. **Context Routing**: The Factory (`get_generator`) delegates the request based on the `asset_family` and the environment (`MOCK_GENERATION_ENABLED`).
3. **Asset Processing**:
   - **New Asset**: Standard text-to-image pipeline for characters, structures, or epic scenes. Prompt enrichment occurs transparently on the server (e.g., automatically appending cinematic parameters for story scenes).
   - **Copy-on-Write (CoW)**: For inpainting (e.g., adding water to an existing tile), the system locates the `base_image_id` directly from memory (or disk fallback), duplicates it, iteratively processes masks, and saves it.
4. **Caching & Delivery**: The final asset is immediately stored in a globally accessible in-memory cache for ultra-fast serving, then asynchronously written to disk for persistence. The new asset URL is returned to the client.

## 3. Component Architecture

### A. API Layer (`main.py` & `models.py`)
- **FastAPI**: Handles high-concurrency requests.
- **Pydantic**: Guarantees typed, structural contracts for `asset_family`, CoW references (`base_image_id`), and sequential tile modifications (`inpaints`).

### B. Storage Layer (`storage.py`)
- **AssetStore**: Provides zero-overhead in-memory dict caching to serve images instantly without network roundtrips to S3 or Redis. Falls back to writing/reading from localized disk dynamically.

### C. Compute Layer (`generators.py`)
- **MockGenerator**: Bypass GPU. Simulates generation and localized inpainting perfectly for end-to-end integration tests.
- **Flux2Generator**: Target production worker for terrain/characters. Combines standard checkpoints with custom LoRAs.
- **ZImageTurboGenerator**: Specialized worker strictly dealing with storytelling concepts. Enforces prompt structure behind the scenes.

### D. Feature Engineering (`inpainting.py`)
- Calculates precise A/B bounds masks.
- Manages an internal vocabulary mapping (`get_inpaint_prompt`) to decouple game logic ("water") from prompt engineering ("sparkling blue pixel art river water texture").

## 4. Path to Scaled Execution (Future Production Targets)
Currently, the system is strictly decoupled and utilizes low-overhead in-memory optimization. For large clustered scale, future additions include:
- **Task Queues**: Diffusion generation blocks threads. Eventually implement **Celery + Redis**.
- **Object Storage**: Swap the in-memory/disk singleton cache with **AWS S3 / Cloudflare R2** if deploying load-balanced multi-node servers.
- **GPU Cloud**: Web app hosting separated from GPU inference nodes.
