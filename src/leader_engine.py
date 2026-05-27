"""Leader generation orchestrator.

Routes splash/profile/action requests through the ComfyUI pipeline,
maintains character consistency via img2img reference images,
and persists everything through LeaderRegistry + AssetStore + AssetRecord.

Resolution, denoise, steps, cfg, sampler, scheduler, model paths, LoRA
strength, and SaveImage prefix are all baked into the workflow JSONs.
The engine only injects: positive_prompt, seed, negative_prompt, and
(for profile/action) the reference image + LoadImage filename.

All generation methods are **async** and can be awaited directly from
FastAPI endpoints -- no thread-pool required.
"""

import logging
import random
import time
import uuid
from pathlib import Path

from PIL import Image

from .comfyui_client import ComfyUIClient
from .config import settings
from .database import SessionLocal, AssetRecord
from .leader_models import LeaderRequest, LeaderResponse
from .leader_prompts import build_prompt
from .leader_registry import LeaderRegistry, generate_leader_id
from .storage import store

logger = logging.getLogger(__name__)


class LeaderEngine:
    """Orchestrates the splash → profile → action pipeline."""

    def __init__(self, client: ComfyUIClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def generate(self, request: LeaderRequest) -> LeaderResponse:
        """Route to the correct handler based on ``asset_type``."""
        handlers: dict[str, str] = {
            "splash":  "_generate_splash",
            "profile": "_generate_profile",
            "action":  "_generate_action",
        }
        handler_name = handlers[request.asset_type]
        handler = getattr(self, handler_name)
        return await handler(request)

    # ------------------------------------------------------------------
    # Splash
    # ------------------------------------------------------------------

    async def _generate_splash(self, req: LeaderRequest) -> LeaderResponse:
        # 1. Build prompt
        prompt = build_prompt(req)

        # 2. Generate leader_id
        leader_id = generate_leader_id(req.leader_name)

        # 3. Seed
        seed = req.seed or random.randint(10**14, 10**15 - 1)

        # 4. Workflow path
        wf_path = str(Path(settings.leader_workflow_dir) / "leader_splash.json")

        # 5. Run — only inject what changes per request
        start = time.time()
        img = await self._client.generate(
            wf_path,
            positive_prompt=prompt,
            negative_prompt=settings.leader_negative_prompt,
            seed=seed,
        )

        # 6. Save to AssetStore
        filename = f"{leader_id}_splash.png"
        store.save_image(filename, img)

        # 7. Persist AssetRecord
        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_splash",
                character_name=req.leader_name,
                generation_mode="comfyui",
            ))
            db.commit()

        # 8. Register leader (copies splash → reference dir)
        LeaderRegistry.register(
            leader_id=leader_id,
            leader_name=req.leader_name,
            archetype=req.archetype,
            culture=req.culture,
            time_of_day=req.time_of_day,
            mood=req.mood,
            splash_image_filename=filename,
            splash_seed=seed,
            splash_prompt=prompt,
        )

        elapsed = int((time.time() - start) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="splash",
            leader_name=req.leader_name,
            leader_id=leader_id,
            seed=seed,
            generation_mode="comfyui",
            prompt_used=prompt,
            resolution=f"{img.width}x{img.height}",
            generation_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    async def _generate_profile(self, req: LeaderRequest) -> LeaderResponse:
        # 1. Validate
        if not req.leader_id:
            raise ValueError("leader_id is required for profile assets")
        leader = LeaderRegistry.get(req.leader_id)
        if not leader:
            raise ValueError(
                f"Leader '{req.leader_id}' not found. Generate a splash first."
            )

        # 2. Seed: use canonical unless overridden
        seed = req.seed or leader.splash_seed

        # 3. Upload reference image
        ref_path = Path(settings.leader_reference_dir) / leader.reference_filename
        if not ref_path.exists():
            raise RuntimeError(f"Reference image missing: {ref_path}")
        ref_img = Image.open(ref_path).convert("RGBA")
        await self._client.upload_reference_image(ref_img, leader.reference_filename)

        # 4. Build prompt
        prompt = build_prompt(req)

        # 5. Workflow path
        wf_path = str(Path(settings.leader_workflow_dir) / "leader_profile.json")

        # 6. Run — inject prompt, seed, negative prompt, and reference image filename
        start = time.time()
        img = await self._client.generate(
            wf_path,
            positive_prompt=prompt,
            negative_prompt=settings.leader_negative_prompt,
            seed=seed,
            ref_image_filename=leader.reference_filename,
        )

        # 7. Save
        filename = f"{req.leader_id}_profile.png"
        store.save_image(filename, img)

        # 8. Persist AssetRecord
        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_profile",
                base_image_id=leader.splash_image_id,
                character_name=req.leader_name,
                generation_mode="comfyui",
            ))
            db.commit()

        # 9. Update registry
        LeaderRegistry.record_profile(req.leader_id, filename)

        elapsed = int((time.time() - start) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="profile",
            leader_name=req.leader_name,
            leader_id=req.leader_id,
            seed=seed,
            generation_mode="comfyui",
            prompt_used=prompt,
            resolution=f"{img.width}x{img.height}",
            generation_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    async def _generate_action(self, req: LeaderRequest) -> LeaderResponse:
        # 1. Validate
        if not req.leader_id:
            raise ValueError("leader_id is required for action assets")
        if not req.action_category:
            raise ValueError("action_category is required for action assets")
        if not req.action_description:
            raise ValueError("action_description is required for action assets")

        leader = LeaderRegistry.get(req.leader_id)
        if not leader:
            raise ValueError(
                f"Leader '{req.leader_id}' not found. Generate a splash first."
            )

        # 2. Seed
        seed = req.seed or leader.splash_seed

        # 3. Upload reference image
        ref_path = Path(settings.leader_reference_dir) / leader.reference_filename
        if not ref_path.exists():
            raise RuntimeError(f"Reference image missing: {ref_path}")
        ref_img = Image.open(ref_path).convert("RGBA")
        await self._client.upload_reference_image(ref_img, leader.reference_filename)

        # 4. Build prompt
        prompt = build_prompt(req)

        # 5. Workflow path
        wf_path = str(Path(settings.leader_workflow_dir) / "leader_action.json")

        # 6. Run
        start = time.time()
        img = await self._client.generate(
            wf_path,
            positive_prompt=prompt,
            negative_prompt=settings.leader_negative_prompt,
            seed=seed,
            ref_image_filename=leader.reference_filename,
        )

        # 7. Save
        filename = f"{req.leader_id}_action_{uuid.uuid4().hex[:6]}.png"
        store.save_image(filename, img)

        # 8. Persist AssetRecord
        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_action",
                base_image_id=leader.splash_image_id,
                character_name=req.leader_name,
                generation_mode="comfyui",
            ))
            db.commit()

        # 9. Update registry
        LeaderRegistry.record_action(req.leader_id, filename)

        elapsed = int((time.time() - start) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="action",
            leader_name=req.leader_name,
            leader_id=req.leader_id,
            seed=seed,
            generation_mode="comfyui",
            prompt_used=prompt,
            resolution=f"{img.width}x{img.height}",
            generation_time_ms=elapsed,
        )
