"""Unit tests for ComfyUI workflow patching (src/comfyui_client.py)."""

import pytest
from src.comfyui_client import _patch_workflow


def _make_workflow():
    """Create a minimal workflow with actual Flux2 Klein node types used in our JSONs."""
    return {
        "1": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "Positive Prompt"},
            "inputs": {"text": "original positive"},
        },
        "2": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {"noise_seed": 0, "steps": 4, "cfg": 1.0},
        },
        # Actual node type used in our workflow JSONs
        "3": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 256, "height": 256, "batch_size": 1},
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": "default.png"},
        },
        # ComfyUI default title for LoadImage nodes
        "5": {
            "class_type": "LoadImage",
            "_meta": {"title": "Load Image"},
            "inputs": {"image": "default_comfy.png"},
        },
        "6": {
            "class_type": "BasicScheduler",
            "inputs": {"scheduler": "simple", "steps": 4, "denoise": 1.0, "model": ["1", 0]},
        },
        "7": {
            "class_type": "FluxGuidance",
            "inputs": {"guidance": 3.5, "conditioning": ["1", 0]},
        },
        "8": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        "9": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": 12345},
        },
        # Keep old node type for backward compatibility
        "10": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
        "11": {
            "class_type": "Flux2Scheduler",
            "inputs": {"steps": 4, "denoise": 0.5, "model": ["1", 0]},
        },
        "12": {
            "class_type": "CFGGuider",
            "inputs": {"cfg": 1.0, "model": ["1", 0], "positive": ["7", 0], "negative": ["17", 0]},
        },
    }


class TestPatchClipTextEncode:
    """Tests for CLIPTextEncode patching (Flux2 — positive prompt only, no negative)."""

    def test_positive_prompt(self):
        """Positive prompt node → inputs['text'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, positive_prompt="new positive")
        assert result["1"]["inputs"]["text"] == "new positive"

    def test_positive_not_set_when_none(self):
        """When positive_prompt is None, original text preserved."""
        wf = _make_workflow()
        result = _patch_workflow(wf, positive_prompt=None)
        assert result["1"]["inputs"]["text"] == "original positive"


class TestPatchSamplerCustomAdvanced:
    """Tests for SamplerCustomAdvanced patching (Flux2 — noise_seed)."""

    def test_seed_set(self):
        """inputs['noise_seed'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, seed=42)
        assert result["2"]["inputs"]["noise_seed"] == 42

    def test_random_seed_when_none(self):
        """seed=None → random noise_seed generated."""
        wf = _make_workflow()
        result = _patch_workflow(wf, seed=None)
        assert isinstance(result["2"]["inputs"]["noise_seed"], int)
        assert 0 <= result["2"]["inputs"]["noise_seed"] <= 2**32 - 1


class TestPatchLatentImage:
    """Tests for EmptyLatentImage and EmptyFlux2LatentImage patching."""

    def test_empty_latent_image_width_height(self):
        """EmptyLatentImage (actual node type) → width/height set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, width=512, height=512)
        assert result["3"]["inputs"]["width"] == 512
        assert result["3"]["inputs"]["height"] == 512

    def test_empty_flux2_latent_image_width_height(self):
        """EmptyFlux2LatentImage (legacy node type) → width/height set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, width=768, height=768)
        assert result["10"]["inputs"]["width"] == 768
        assert result["10"]["inputs"]["height"] == 768

    def test_not_set_when_none(self):
        """When width/height is None, original values preserved."""
        wf = _make_workflow()
        result = _patch_workflow(wf, width=None, height=None)
        assert result["3"]["inputs"]["width"] == 256
        assert result["3"]["inputs"]["height"] == 256


class TestPatchLoadImage:
    """Tests for LoadImage patching."""

    def test_uploaded_filename(self):
        """Node ID in uploaded_filenames → inputs['image'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, uploaded_filenames={"4": "uploaded_test.png"})
        assert result["4"]["inputs"]["image"] == "uploaded_test.png"

    def test_comfyui_default_title(self):
        """ComfyUI default 'Load Image' title → ref_image_filename applied."""
        wf = _make_workflow()
        result = _patch_workflow(wf, ref_image_filename="ref_leader.png")
        assert result["5"]["inputs"]["image"] == "ref_leader.png"

    def test_ref_not_set_without_filename(self):
        """No ref_image_filename → LoadImage node unchanged."""
        wf = _make_workflow()
        result = _patch_workflow(wf, ref_image_filename=None)
        assert result["5"]["inputs"]["image"] == "default_comfy.png"


class TestPatchExtraOverrides:
    """Tests for extra_overrides."""

    def test_arbitrary_node_override(self):
        """Arbitrary node_id → inputs updated."""
        wf = _make_workflow()
        result = _patch_workflow(wf, extra_overrides={"5": {"image": "overridden.png"}})
        assert result["5"]["inputs"]["image"] == "overridden.png"


class TestPatchPreservesUnrelated:
    """Tests that unrelated nodes are unchanged."""

    def test_unrelated_nodes_unchanged(self):
        """Non-targeted nodes unchanged."""
        wf = _make_workflow()
        result = _patch_workflow(wf, positive_prompt="new")
        # Node 1 (CLIPTextEncode) should be updated with prompt
        assert result["1"]["inputs"]["text"] == "new"
        # Node 4 (LoadImage) should be unchanged without upload
        assert result["4"]["inputs"]["image"] == "default.png"
        # Node 5 (LoadImage ref) should be unchanged without ref_image_filename
        assert result["5"]["inputs"]["image"] == "default_comfy.png"


class TestPatchBasicScheduler:
    """Tests for BasicScheduler and Flux2Scheduler patching."""

    def test_basic_scheduler_steps_denoise(self):
        """BasicScheduler (actual node type) → steps/denoise set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, steps=8, denoise=0.5)
        assert result["6"]["inputs"]["steps"] == 8
        assert result["6"]["inputs"]["denoise"] == 0.5

    def test_flux2_scheduler_steps_denoise(self):
        """Flux2Scheduler (legacy node type) → steps/denoise set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, steps=8, denoise=0.5)
        assert result["11"]["inputs"]["steps"] == 8
        assert result["11"]["inputs"]["denoise"] == 0.5

    def test_not_set_when_none(self):
        """When steps/denoise is None, original values preserved."""
        wf = _make_workflow()
        result = _patch_workflow(wf, steps=None, denoise=None)
        assert result["6"]["inputs"]["steps"] == 4
        assert result["6"]["inputs"]["denoise"] == 1.0


class TestPatchFluxGuidance:
    """Tests for FluxGuidance patching."""

    def test_guidance_set(self):
        """FluxGuidance node → guidance set from cfg_guidance param."""
        wf = _make_workflow()
        result = _patch_workflow(wf, cfg_guidance=5.0)
        assert result["7"]["inputs"]["guidance"] == 5.0

    def test_guidance_not_set_when_none(self):
        """When cfg_guidance is None, original guidance preserved."""
        wf = _make_workflow()
        result = _patch_workflow(wf, cfg_guidance=None)
        assert result["7"]["inputs"]["guidance"] == 3.5

    def test_cfg_guider_also_patched(self):
        """CFGGuider (internal node) also receives cfg_guidance."""
        wf = _make_workflow()
        result = _patch_workflow(wf, cfg_guidance=2.0)
        assert result["12"]["inputs"]["cfg"] == 2.0


class TestPatchKSamplerSelect:
    """Tests for KSamplerSelect patching."""

    def test_sampler_name_set(self):
        """KSamplerSelect → sampler_name set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, sampler="dpmpp_2m")
        assert result["8"]["inputs"]["sampler_name"] == "dpmpp_2m"

    def test_not_set_when_none(self):
        """When sampler is None, original preserved."""
        wf = _make_workflow()
        result = _patch_workflow(wf, sampler=None)
        assert result["8"]["inputs"]["sampler_name"] == "euler"


class TestPatchRandomNoise:
    """Tests for RandomNoise patching."""

    def test_noise_seed_set(self):
        """RandomNoise → noise_seed set from seed param."""
        wf = _make_workflow()
        result = _patch_workflow(wf, seed=42)
        assert result["9"]["inputs"]["noise_seed"] == 42

    def test_random_seed_when_none(self):
        """seed=None → random noise_seed."""
        wf = _make_workflow()
        result = _patch_workflow(wf, seed=None)
        assert isinstance(result["9"]["inputs"]["noise_seed"], int)
        assert 0 <= result["9"]["inputs"]["noise_seed"] <= 2**32 - 1

