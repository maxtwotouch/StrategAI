"""Unit tests for configuration (src/config.py)."""

import os
import pytest
from src.config import Settings, ComfyUISettings, PathSettings, GenerationSettings, SplashSettings, LeaderSettings


class TestConfigDefaults:
    """Test default values and derived properties."""

    def test_default_modes_all_present(self):
        """All 10 families have entries in generation.modes defaults."""
        s = Settings()
        expected_families = {
            "background_tile", "structure", "object", "terrain",
            "nature_object", "character_sprite", "story", "splash", "leader", "unit",
        }
        assert set(s.generation.modes.keys()) == expected_families

    def test_get_mode_known_family(self):
        """settings.get_mode('structure') returns 'comfyui' by default."""
        s = Settings()
        assert s.get_mode("structure") == "comfyui"

    def test_get_mode_unknown_family_falls_back_to_default(self):
        """Unknown family returns generation.default_mode."""
        s = Settings()
        assert s.get_mode("nonexistent_family") == s.generation.default_mode

    def test_derived_paths_exist(self):
        """workflow_dir, leader_workflow_dir resolve correctly."""
        s = Settings()
        assert s.workflow_dir.endswith("workflows")
        assert s.leader_workflow_dir.endswith(os.path.join("workflows", "leader"))

    def test_modes_dict_is_mutable(self):
        """You can set settings.generation.modes['structure'] = 'placeholder' at runtime."""
        s = Settings()
        s.generation.modes["structure"] = "placeholder"
        assert s.get_mode("structure") == "placeholder"

    def test_comfyui_defaults(self):
        """ComfyUI settings have expected defaults."""
        c = ComfyUISettings()
        assert c.base_url == "http://127.0.0.1:8188"
        assert c.timeout == 300

    def test_path_defaults(self):
        """Path settings have expected defaults."""
        p = PathSettings()
        assert p.output_dir == "generated_assets"
        assert p.splash_dir == "splash_assets"
        assert p.static_tiles_dir == "static_tiles"
        assert p.leader_reference_dir == "leader_references"

    def test_generation_defaults(self):
        """Generation settings have expected defaults."""
        g = GenerationSettings()
        assert g.default_mode == "comfyui"
        assert g.random_probability == 0.5

    def test_splash_defaults(self):
        """Splash settings have expected defaults."""
        s = SplashSettings()
        assert s.width == 256
        assert s.height == 256

    def test_leader_negative_prompt_not_empty(self):
        """Leader negative prompt is a non-empty string."""
        l = LeaderSettings()
        assert len(l.negative_prompt) > 0
        assert "blurry" in l.negative_prompt


class TestConfigOverrides:
    """Test YAML and env var overrides."""

    def test_yaml_override(self, tmp_project_root, monkeypatch):
        """config.yaml values override defaults."""
        monkeypatch.setattr("src.config.BASE_DIR", tmp_project_root)
        # Settings reads config.yaml relative to CWD, so chdir to the temp root
        monkeypatch.chdir(tmp_project_root)
        # Overwrite the config.yaml from tmp_project_root fixture
        with open(os.path.join(tmp_project_root, "config.yaml"), "w") as f:
            f.write("host: 127.0.0.1\nport: 9999\n")

        s = Settings(_env_file="")
        assert s.host == "127.0.0.1"
        assert s.port == 9999

    def test_env_var_override(self, tmp_project_root, monkeypatch):
        """COMFYUI__BASE_URL env var wins over yaml."""
        monkeypatch.setattr("src.config.BASE_DIR", tmp_project_root)
        monkeypatch.setenv("COMFYUI__BASE_URL", "http://10.0.0.5:8188")

        s = Settings()
        assert s.comfyui.base_url == "http://10.0.0.5:8188"
