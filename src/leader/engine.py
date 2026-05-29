"""Leader generation orchestrator.

Routes splash/profile/action requests through the ComfyUI pipeline,
maintains character consistency via img2img reference images,
and persists everything through LeaderRegistry + AssetStore + AssetRecord.

Resolution, denoise, steps, cfg, sampler, scheduler, model paths, LoRA
strength, and SaveImage prefix are all baked into the workflow JSONs.
The engine only injects: positive_prompt, seed, and
(for profile/action) the reference image + LoadImage filename.

All generation methods are **async** and can be awaited directly from
FastAPI endpoints -- no thread-pool required.
"""
from __future__ import annotations
import logging
import os
import secrets
import time
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.comfyui_client import ComfyUIClient
from src.config import settings, BASE_DIR
from src.database import SessionLocal, AssetRecord
from .models import LeaderRequest, LeaderResponse
from .prompts import build_prompt, build_multi_action_prompt
from .registry import LeaderRegistry, generate_leader_id
from src.storage import store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _try_remove_asset(filename: str) -> None:
    """Best-effort cleanup of an orphaned image file after a DB failure."""
    try:
        path = os.path.join(BASE_DIR, settings.paths.output_dir, os.path.basename(filename))
        if os.path.isfile(path):
            os.unlink(path)
            logger.warning("Cleaned up orphaned asset: %s", filename)
    except Exception as exc:
        logger.error("Failed to clean up orphaned asset %s: %s", filename, exc)


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

        # 3. Seed — use cryptographically secure random unless caller provides one
        seed = req.seed if req.seed is not None else secrets.randbits(31)

        # 4. Workflow path
        wf_path = str(Path(settings.leader_workflow_dir) / "leader_splash.json")

        # 5. Run — only inject what changes per request
        start = time.time()
        img = await self._client.generate(
            wf_path,
            positive_prompt=prompt,
            seed=seed,
        )

        # 6. Save to AssetStore
        filename = f"{leader_id}_splash.png"
        store.save_image(filename, img)

        # 7. Persist AssetRecord + LeaderRecord in one transaction
        #    Uses context manager for auto-rollback on exception.
        try:
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="leader_splash",
                    character_name=req.leader_name,
                    generation_mode="comfyui",
                ))
                LeaderRegistry.register(
                    leader_id=leader_id,
                    leader_name=req.leader_name,
                    leader_description=req.leader_description,
                    archetype=req.archetype,
                    culture=req.culture,
                    time_of_day=req.time_of_day,
                    mood=req.mood,
                    splash_image_filename=filename,
                    splash_seed=seed,
                    splash_prompt=prompt,
                    session=db,
                )
                db.commit()
        except Exception:
            # Clean up orphaned image file if DB persist fails
            _try_remove_asset(filename)
            raise

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
        seed = req.seed if req.seed is not None else leader.splash_seed

        # 3. Upload reference image — with path traversal protection
        ref_base = Path(os.path.join(BASE_DIR, settings.paths.leader_reference_dir)).resolve()
        ref_filename = os.path.basename(leader.reference_filename)
        ref_path = (ref_base / ref_filename).resolve()
        if not str(ref_path).startswith(str(ref_base)):
            raise RuntimeError(
                f"Reference image path escapes directory: {leader.reference_filename}"
            )
        if not ref_path.exists():
            raise RuntimeError(f"Reference image missing: {ref_path}")
        try:
            ref_img = Image.open(ref_path).convert("RGBA")
        except Exception as exc:
            raise RuntimeError(
                f"Failed to open reference image at {ref_path}: {exc}"
            ) from exc
        await self._client.upload_reference_image(ref_img, leader.reference_filename)

        # 4. Build prompt
        prompt = build_prompt(req)

        # 5. Workflow path
        wf_path = str(Path(settings.leader_workflow_dir) / "leader_profile.json")

        # 6. Run — inject prompt, seed, and reference image filename
        start = time.time()
        img = await self._client.generate(
            wf_path,
            positive_prompt=prompt,
            seed=seed,
            ref_image_filename=leader.reference_filename,
        )

        # 7. Save
        filename = f"{req.leader_id}_profile.png"
        store.save_image(filename, img)

        # 8. Persist AssetRecord + update LeaderRecord in one transaction
        try:
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="leader_profile",
                    base_image_id=leader.splash_image_id,
                    character_name=req.leader_name,
                    generation_mode="comfyui",
                ))
                LeaderRegistry.record_profile(req.leader_id, filename, session=db)
                db.commit()
        except Exception:
            _try_remove_asset(filename)
            raise

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
        seed = req.seed if req.seed is not None else leader.splash_seed

        # 3. Upload reference image — with path traversal protection
        ref_base = Path(os.path.join(BASE_DIR, settings.paths.leader_reference_dir)).resolve()
        ref_filename = os.path.basename(leader.reference_filename)
        ref_path = (ref_base / ref_filename).resolve()
        if not str(ref_path).startswith(str(ref_base)):
            raise RuntimeError(
                f"Reference image path escapes directory: {leader.reference_filename}"
            )
        if not ref_path.exists():
            raise RuntimeError(f"Reference image missing: {ref_path}")
        try:
            ref_img = Image.open(ref_path).convert("RGBA")
        except Exception as exc:
            raise RuntimeError(
                f"Failed to open reference image at {ref_path}: {exc}"
            ) from exc
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
            seed=seed,
            ref_image_filename=leader.reference_filename,
        )

        # 7. Save
        filename = f"{req.leader_id}_action_{uuid.uuid4().hex[:6]}.png"
        store.save_image(filename, img)

        # 8. Persist AssetRecord + update LeaderRecord in one transaction
        try:
            with SessionLocal() as db:
                db.add(AssetRecord(
                    id=filename,
                    asset_family="leader_action",
                    base_image_id=leader.splash_image_id,
                    character_name=req.leader_name,
                    generation_mode="comfyui",
                ))
                LeaderRegistry.record_action(req.leader_id, filename, session=db)
                db.commit()
        except Exception:
            _try_remove_asset(filename)
            raise

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

    async def generate_multi_action(
        self,
        req: LeaderRequest,
        leader_ids: list[str],
    ) -> LeaderResponse:
        """Generate a multi-leader action scene with multiple leaders via ComfyUI.

        Loads all leader records, builds a composite prompt from their
        descriptions, and generates a single action image.
        """
        t0 = time.time()

        # Load all leader records
        leader_names = []
        leader_descriptions = []
        for lid in leader_ids:
            leader = LeaderRegistry.get(lid)
            if not leader:
                raise ValueError(
                    f"Leader '{lid}' not found. Generate a splash first."
                )
            leader_names.append(leader.leader_name)
            leader_descriptions.append(leader.leader_description)

        # Build composite prompt
        prompt = build_multi_action_prompt(req, leader_descriptions, leader_names)

        # Workflow path — use the standard action workflow
        wf_path = str(Path(settings.leader_workflow_dir) / "leader_action.json")

        # Run
        seed = req.seed if req.seed is not None else secrets.randbits(31)
        img = await self._client.generate(
            wf_path,
            positive_prompt=prompt,
            seed=seed,
        )

        # Save
        asset_id = str(uuid.uuid4())
        filename = f"leader_multi_{asset_id}_action.png"
        store.save_image(filename, img)

        # Persist AssetRecord
        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_action",
                character_name=", ".join(leader_names),
                generation_mode="comfyui",
            ))
            db.commit()

        elapsed = int((time.time() - t0) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="action",
            leader_name=", ".join(leader_names),
            leader_id=asset_id,
            leader_ids=leader_ids,
            leader_names=leader_names,
            seed=seed,
            generation_mode="comfyui",
            prompt_used=prompt,
            resolution=f"{img.width}x{img.height}",
            generation_time_ms=elapsed,
        )


class StaticLeaderEngine:
    """Generates placeholder PNGs at runtime for the leader pipeline.

    Mirrors LeaderEngine's interface but builds placeholder images
    programmatically via PIL — no disk assets, no system font dependency.
    Uses :func:`PIL.ImageFont.load_default` so it is portable everywhere.

    Resolution matches ComfyUI workflows: splash/profile/action = 1920×1088.
    """

    # Matches EmptyLatentImage dimensions in the leader workflow JSONs
    _W, _H = 1920, 1088

    # Colour palette per action category  ---------------------------------
    _ACTION_COLORS: dict[str, tuple[str, str]] = {
        "military":      ("#8B0000", "#FFD700"),   # dark red / gold
        "diplomatic":    ("#1B3A5C", "#C0C0C0"),   # navy / silver
        "construction":  ("#654321", "#FFD700"),    # brown / gold
        "scientific":    ("#1A3A5C", "#00FFAA"),    # dark blue / teal
        "cultural":      ("#4A0E5C", "#FFB6C1"),    # purple / pink
        "exploration":   ("#2E5A1E", "#87CEEB"),    # forest green / sky blue
        "crisis":        ("#2B2B2B", "#FF4444"),    # dark grey / red
    }

    # --- lazy font (PIL built-in — always available) ---------------------
    _font = None

    @classmethod
    def _get_font(cls) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        if cls._font is None:
            # load_default() always works — no ttf file required
            cls._font = ImageFont.load_default()
        return cls._font

    # --- placeholder builder ---------------------------------------------

    @classmethod
    def _build_placeholder(
        cls,
        label: str,
        sublabel: str = "[LEADER PLACEHOLDER]",
        bg_color: str = "#1A1A2E",
        fg_color: str = "#E0E0E0",
    ) -> Image.Image:
        """Return a labelled RGBA placeholder matching the workflow resolution."""
        img = Image.new("RGBA", (cls._W, cls._H), bg_color)
        draw = ImageDraw.Draw(img)
        font = cls._get_font()

        # Outer and inner borders
        draw.rectangle([6, 6, cls._W - 7, cls._H - 7], outline=fg_color, width=5)
        draw.rectangle([28, 28, cls._W - 29, cls._H - 29], outline=fg_color, width=2)

        # --- centred label ---
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        lx, ly = (cls._W - tw) // 2, (cls._H - th) // 2 - 16

        # drop-shadow so it's legible on any background
        draw.text((lx + 3, ly + 3), label, fill="black", font=font)
        draw.text((lx, ly), label, fill=fg_color, font=font)

        # --- sublabel ---
        bbox2 = draw.textbbox((0, 0), sublabel, font=font)
        tw2, th2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
        draw.text(
            ((cls._W - tw2) // 2, ly + th + 16),
            sublabel,
            fill=fg_color,
            font=font,
        )

        return img

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def generate(self, request: LeaderRequest) -> LeaderResponse:
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
        prompt = build_prompt(req)
        leader_id = generate_leader_id(req.leader_name)
        seed = req.seed if req.seed is not None else secrets.randbits(31)

        start = time.time()

        img = self._build_placeholder(
            label="SPLASH",
            sublabel=f"Leader: {req.leader_name}",
            bg_color="#16213E",
            fg_color="#E94560",
        )

        filename = f"{leader_id}_splash.png"
        store.save_image(filename, img)

        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_splash",
                character_name=req.leader_name,
                generation_mode="static",
            ))
            db.commit()

        LeaderRegistry.register(
            leader_id=leader_id,
            leader_name=req.leader_name,
            leader_description=req.leader_description,
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
            generation_mode="static",
            prompt_used=prompt,
            resolution=f"{img.width}x{img.height}",
            generation_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    async def _generate_profile(self, req: LeaderRequest) -> LeaderResponse:
        if not req.leader_id:
            raise ValueError("leader_id is required for profile assets")
        leader = LeaderRegistry.get(req.leader_id)
        if not leader:
            raise ValueError(
                f"Leader '{req.leader_id}' not found. Generate a splash first."
            )

        seed = req.seed if req.seed is not None else leader.splash_seed
        prompt = build_prompt(req)

        start = time.time()

        img = self._build_placeholder(
            label="PROFILE",
            sublabel=f"Leader: {req.leader_name}",
            bg_color="#0F3460",
            fg_color="#16C79A",
        )

        filename = f"{req.leader_id}_profile.png"
        store.save_image(filename, img)

        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_profile",
                base_image_id=leader.splash_image_id,
                character_name=req.leader_name,
                generation_mode="static",
            ))
            db.commit()

        LeaderRegistry.record_profile(req.leader_id, filename)

        elapsed = int((time.time() - start) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="profile",
            leader_name=req.leader_name,
            leader_id=req.leader_id,
            seed=seed,
            generation_mode="static",
            prompt_used=prompt,
            resolution=f"{img.width}x{img.height}",
            generation_time_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    async def _generate_action(self, req: LeaderRequest) -> LeaderResponse:
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

        seed = req.seed if req.seed is not None else leader.splash_seed
        prompt = build_prompt(req)

        # Pick category-specific colours, fall back to a neutral palette
        bg_color, fg_color = self._ACTION_COLORS.get(
            req.action_category, ("#1A1A2E", "#E0E0E0")
        )

        start = time.time()

        img = self._build_placeholder(
            label=f"ACTION: {req.action_category.upper()}",
            sublabel=f"Leader: {req.leader_name}",
            bg_color=bg_color,
            fg_color=fg_color,
        )

        filename = f"{req.leader_id}_action_{uuid.uuid4().hex[:6]}.png"
        store.save_image(filename, img)

        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_action",
                base_image_id=leader.splash_image_id,
                character_name=req.leader_name,
                generation_mode="static",
            ))
            db.commit()

        # Track action in registry
        LeaderRegistry.record_action(req.leader_id, filename)

        elapsed = int((time.time() - start) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="action",
            leader_name=req.leader_name,
            leader_id=req.leader_id,
            seed=seed,
            generation_mode="static",
            prompt_used=prompt,
            resolution=f"{img.width}x{img.height}",
            generation_time_ms=elapsed,
        )

    async def generate_multi_action(
        self,
        req: LeaderRequest,
        leader_ids: list[str],
    ) -> LeaderResponse:
        """Generate a multi-leader action scene placeholder with multiple leaders."""
        t0 = time.time()

        # Load all leader records
        leader_names = []
        leader_descriptions = []
        for lid in leader_ids:
            leader = LeaderRegistry.get(lid)
            if not leader:
                raise ValueError(
                    f"Leader '{lid}' not found. Generate a splash first."
                )
            leader_names.append(leader.leader_name)
            leader_descriptions.append(leader.leader_description)

        # Build composite prompt
        prompt = build_multi_action_prompt(req, leader_descriptions, leader_names)

        # Pick category-specific colours
        bg_color, fg_color = self._ACTION_COLORS.get(
            req.action_category, ("#1A1A2E", "#E0E0E0")
        )

        img = self._build_placeholder(
            label=f"ACTION: {req.action_category.upper()}",
            sublabel=", ".join(leader_names),
            bg_color=bg_color,
            fg_color=fg_color,
        )

        asset_id = str(uuid.uuid4())
        filename = f"leader_multi_{asset_id}_action.png"
        store.save_image(filename, img)

        with SessionLocal() as db:
            db.add(AssetRecord(
                id=filename,
                asset_family="leader_action",
                character_name=", ".join(leader_names),
                generation_mode="static",
            ))
            db.commit()

        elapsed = int((time.time() - t0) * 1000)

        return LeaderResponse(
            url=f"/assets/{filename}",
            asset_type="action",
            leader_name=", ".join(leader_names),
            leader_id=asset_id,
            leader_ids=leader_ids,
            leader_names=leader_names,
            seed=req.seed if req.seed is not None else secrets.randbits(31),
            generation_mode="static",
            prompt_used=prompt,
            resolution=f"{img.width}x{img.height}",
            generation_time_ms=elapsed,
        )