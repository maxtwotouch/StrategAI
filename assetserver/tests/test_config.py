"""Unit tests for configuration (src/config.py)."""

import os
import pytest
from src.config import Settings, ComfyUISettings, PathSettings, GenerationSettings, LeaderSettings


class TestConfigDefaults:
    """Test default values and derived properties."""

    def test_default_modes_all_present(self):
        """All expected families have entries in generation.modes."""
        s = Settings()
        expected_families = {
            "structure", "object", "terrain", "background_tile",
            "character_sprite", "leader", "unit", "story", "splash",
            # nature_object is NOT a configured generation mode — it is
            # served exclusively from the static catalog (static_tiles/).
            # This test was failing because nature_object was erroneously
            # expected here.
        }
        actual = set(s.generation.modes.keys())
        missing = expected_families - actual
        extra = actual - expected_families
        assert not missing, f"Missing families: {missing}"
        # Extra families from config/env are acceptable (forward-compat)

    def test_get_mode_known_family(self):
        """settings.get_mode returns the configured mode for a known family."""
        s = Settings()
        mode = s.get_mode("structure")
        # Mode may be overridden by .env; just verify it's a valid mode string
        assert mode in ("comfyui", "static", "placeholder"), f"Invalid mode: {mode}"

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

    def test_leader_settings_empty(self):
        """Leader settings placeholder exists (Flux2 Klein uses no negative prompts)."""
        l = LeaderSettings()
        assert l is not None


class TestConfigOverrides:
    """Test YAML and env var overrides."""

    def test_yaml_override(self, tmp_project_root, monkeypatch):
        """config.yaml values override defaults."""
        monkeypatch.setattr("src.config.BASE_DIR", tmp_project_root)
        # Settings reads config.yaml relative to CWD, so chdir to the temp root
        monkeypatch.chdir(tmp_project_root)
        # Overwrite the config.yaml from tmp_project_root fixture
        with open(os.path.join(tmp_project_root, "config.yaml"), "w") as f:
            f.write("server:\n  host: 127.0.0.1\n  port: 9999\n")

        s = Settings(_env_file="")
        assert s.server.host == "127.0.0.1"
        assert s.server.port == 9999

    def test_env_var_override(self, tmp_project_root, monkeypatch):
        """COMFYUI__BASE_URL env var fills gaps not set by config.yaml."""
        monkeypatch.setattr("src.config.BASE_DIR", tmp_project_root)
        # Chdir so Settings reads config.yaml from tmp_project_root
        monkeypatch.chdir(tmp_project_root)
        monkeypatch.setenv("COMFYUI__BASE_URL", "http://10.0.0.5:8188")

        s = Settings(_env_file="")
        assert s.comfyui.base_url == "http://10.0.0.5:8188"
