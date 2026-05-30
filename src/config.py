import os
from enum import Enum

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

# Resolve paths relative to the project root (one level up from src/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env into os.environ so that pydantic-settings' env_settings source
# can pick up overrides (the built-in dotenv_settings source does not merge
# dict fields like generation.modes correctly).
_dotenv_path = os.path.join(BASE_DIR, ".env")
if os.path.isfile(_dotenv_path):
    load_dotenv(_dotenv_path)

# ---------------------------------------------------------------------------
#  Nested configuration models (mirrors config.yaml structure)
# ---------------------------------------------------------------------------


class ComfyUISettings(BaseModel):
    """Connection settings for the external ComfyUI inference server(s).

    Single-node (backward-compatible):
        ``base_url`` is used directly, ``nodes`` is empty.

    Multi-node (load-balanced):
        ``nodes`` is a list of ComfyUI server URLs.  The load-balancer
        picks the node with the shortest queue (pending + running) and
        transparently retries on a different node on failure.

    All nodes are assumed homogeneous — same models, LoRAs, storage.
    """
    base_url: str = "http://127.0.0.1:8188"
    nodes: list[str] = Field(default_factory=list)
    timeout: int = Field(default=300, gt=0, description="Per-request timeout in seconds")
    health_check_interval: int = Field(default=30, gt=0, description="Seconds between re-pinging unhealthy nodes")
    max_retries: int = Field(default=3, ge=0, description="Max nodes to try per generation before failing")

    def get_urls(self) -> list[str]:
        """Return the list of ComfyUI server URLs to connect to.

        If ``nodes`` is non-empty it is used directly; otherwise
        ``base_url`` is wrapped in a single-element list for backward
        compatibility.
        """
        return self.nodes if self.nodes else [self.base_url]


class PathSettings(BaseModel):
    """Output and reference directories, relative to the project root."""
    output_dir: str = "generated_assets"
    splash_dir: str = "splash_assets"
    static_tiles_dir: str = "static_tiles"
    leader_reference_dir: str = "leader_references"
    font_path: str = Field(
        default="",
        description="Optional absolute path to a .ttf or .ttc font for placeholder labels. "
                    "Leave empty to auto-detect from common system locations.",
    )


class GenerationSettings(BaseModel):
    """Per-family generation mode routing."""
    modes: dict[str, str] = Field(default_factory=lambda: {
        "structure": "comfyui",
        "object": "comfyui",
        "terrain": "comfyui",
        "leader": "comfyui",
        "unit": "comfyui",
    })
    default_mode: str = "comfyui"


class LeaderSettings(BaseModel):
    """Prompt and behaviour settings for the leader pipeline.

    Flux2 Klein does not use negative prompts — this block is kept
    for future configuration needs.
    """
    pass


class ServerSettings(BaseModel):
    """HTTP server configuration."""
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="CORS allowed origins.  The default allows local development. "
                    "Set to specific domains in production.  Using ['*'] is a "
                    "security risk — the server will emit a warning at startup.",
    )
    max_request_body_mb: int = Field(
        default=10,
        gt=0,
        le=100,
        description="Maximum request body size in megabytes (1–100).",
    )
    assets_url_prefix: str = Field(
        default="/assets",
        description="URL prefix for serving generated assets.",
    )
    cache_max_entries: int = Field(
        default=1000,
        gt=0,
        le=100_000,
        description="Maximum number of images held in the in-memory LRU cache. "
                    "Reduce if RAM is constrained (e.g. 100).  Set higher for "
                    "faster repeated reads at the cost of memory.",
    )
    cache_max_mb: int = Field(
        default=500,
        gt=0,
        le=16384,
        description="Maximum memory (MB) for the in-memory image cache. "
                    "Images are evicted when either this limit or cache_max_entries is exceeded.",
    )
    api_key: str = Field(
        default="",
        description="Optional static API key for authentication.  When set, "
                    "all requests must include the header ``X-API-Key: <key>``. "
                    "Leave empty to disable authentication (development default).",
    )


class DeploymentMode(str, Enum):
    """Deployment environment — controls which safety checks are enforced."""
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class RateLimitSettings(BaseModel):
    """Per-endpoint rate limiting configuration.

    Uses a simple token-bucket algorithm.  Limits are enforced globally
    (across all clients), NOT per-IP.  For per-IP limits, place a reverse
    proxy (nginx/Caddy) in front of the service.
    """
    post_rps: float = Field(
        default=2.0, gt=0,
        description="Max POST (generation) requests per second globally.",
    )
    get_rps: float = Field(
        default=50.0, gt=0,
        description="Max GET (read) requests per second globally.",
    )
    burst_size: int = Field(
        default=5, ge=1,
        description="Max burst size for POST endpoints before throttling.",
    )
    enabled: bool = Field(
        default=True,
        description="Set to false to disable rate limiting (e.g., in tests).",
    )


# ---------------------------------------------------------------------------
#  Top-level Settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Application configuration.

    Load order (later sources win):
      1. Pydantic defaults (above)
      2. ``config.yaml`` — version-controlled, primary source of truth
      3. Environment variables
      4. ``.env`` file — deployment-specific overrides (highest priority)

    Use ``__`` as the nesting delimiter in ``.env`` / env vars.
    Example: ``COMFYUI__BASE_URL=http://10.0.0.5:8188``
    """

    model_config = SettingsConfigDict(
        yaml_file="config.yaml",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = Field(
        default="",
        description="Database connection URL.  Leave empty to use the default "
                    "SQLite database at the project root (tilemap.db).  For "
                    "PostgreSQL: postgresql://user:pass@host:5432/dbname",
    )
    mode: DeploymentMode = Field(
        default=DeploymentMode.DEVELOPMENT,
        description="Deployment environment. 'production' enables stricter "
                    "safety checks (CORS must be explicit, database must be "
                    "PostgreSQL, etc.).",
    )
    comfyui: ComfyUISettings = Field(default_factory=ComfyUISettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    leader: LeaderSettings = Field(default_factory=LeaderSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)

    # ------------------------------------------------------------------
    #  Derived structural paths (never overridable — always relative to src/)
    # ------------------------------------------------------------------

    @property
    def workflow_dir(self) -> str:
        """Directory containing ComfyUI workflow JSON templates."""
        return os.path.join(BASE_DIR, "workflows")

    @property
    def leader_workflow_dir(self) -> str:
        """Directory containing leader-specific workflow JSONs."""
        return os.path.join(BASE_DIR, "workflows", "leader")

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def get_mode(self, asset_family: str) -> str:
        """Resolve generation mode for a family, falling back to default."""
        return self.generation.modes.get(asset_family, self.generation.default_mode)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )


# ---------------------------------------------------------------------------
#  Singleton + ensure directories
# ---------------------------------------------------------------------------

settings = Settings()

# Ensure output directories exist
os.makedirs(os.path.join(BASE_DIR, settings.paths.output_dir), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, settings.paths.splash_dir), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, settings.paths.static_tiles_dir), exist_ok=True)
os.makedirs(settings.workflow_dir, exist_ok=True)
os.makedirs(settings.leader_workflow_dir, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, settings.paths.leader_reference_dir), exist_ok=True)
