"""Unit tests for ComfyUI workflow patching (src/comfyui_client.py)."""

import pytest
from src.comfyui_client import _patch_workflow


def _make_workflow():
    """Create a minimal workflow with Flux2 Klein node types."""
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
        "3": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": 256, "height": 256, "batch_size": 1},
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": "default.png"},
        },
        "5": {
            "class_type": "LoadImage",
            "_meta": {"title": "Reference Image"},
            "inputs": {"image": "default_ref.png"},
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


class TestPatchEmptyFlux2LatentImage:
    """Tests for EmptyFlux2LatentImage patching."""

    def test_width_height_set(self):
        """inputs['width'], inputs['height'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, width=512, height=512)
        assert result["3"]["inputs"]["width"] == 512
        assert result["3"]["inputs"]["height"] == 512

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

    def test_reference_image(self):
        """_meta.title contains 'reference' + ref_image_filename → inputs['image'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, ref_image_filename="ref_leader.png")
        assert result["5"]["inputs"]["image"] == "ref_leader.png"

    def test_reference_not_set_without_filename(self):
        """No ref_image_filename → reference node unchanged."""
        wf = _make_workflow()
        result = _patch_workflow(wf, ref_image_filename=None)
        assert result["5"]["inputs"]["image"] == "default_ref.png"


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
        assert result["5"]["inputs"]["image"] == "default_ref.png"

