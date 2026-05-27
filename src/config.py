import os
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve paths relative to the project root (one level up from src/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- Legacy / general ---
    output_dir: str = os.path.join(BASE_DIR, "generated_assets")
    splash_dir: str = os.path.join(BASE_DIR, "splash_assets")
    host: str = "0.0.0.0"
    port: int = 8000
    splash_width: int = 256
    splash_height: int = 256

    # --- ComfyUI ---
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_timeout: int = 300

    # --- Static assets ---
    static_tiles_dir: str = os.path.join(BASE_DIR, "static_tiles")

    # --- Workflows ---
    workflow_dir: str = os.path.join(os.path.dirname(__file__), "workflows")

    # --- Leader generation ---
    leader_workflow_dir: str = os.path.join(os.path.dirname(__file__), "workflows", "leader")
    leader_reference_dir: str = os.path.join(BASE_DIR, "leader_references")

    # Prompt components (overridable via .env for rapid iteration)
    leader_negative_prompt: str = (
        "blurry, low quality, distorted, ugly, deformed face, bad hands, "
        "missing fingers, text, watermark, signature, logo, cartoon, 3D render, "
        "photograph, selfie, modern clothing, jeans, t-shirt, plastic, "
        "oversaturated colors, bad anatomy, extra limbs, cloned face, disfigured, "
        "jpeg artifacts"
    )

    # --- Per-family generation modes ---
    # Valid per-family: "comfyui" | "static" | "random"
    background_tile_mode: str = "comfyui"
    structure_mode: str = "comfyui"
    nature_object_mode: str = "comfyui"
    character_sprite_mode: str = "comfyui"
    story_mode: str = "comfyui"
    splash_mode: str = "comfyui"
    default_generation_mode: str = "comfyui"
    random_generation_probability: float = 0.5

    def get_mode(self, asset_family: str) -> str:
        """Resolve generation mode for a family, falling back to default."""
        attr = f"{asset_family}_mode"
        return getattr(self, attr, self.default_generation_mode)


settings = Settings()

# Ensure directories exist
os.makedirs(settings.output_dir, exist_ok=True)
os.makedirs(settings.splash_dir, exist_ok=True)
os.makedirs(settings.static_tiles_dir, exist_ok=True)
os.makedirs(settings.workflow_dir, exist_ok=True)
os.makedirs(settings.leader_workflow_dir, exist_ok=True)
os.makedirs(settings.leader_reference_dir, exist_ok=True)
