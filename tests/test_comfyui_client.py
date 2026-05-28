"""Unit tests for ComfyUI workflow patching (src/comfyui_client.py)."""

import pytest
from src.comfyui_client import _patch_workflow


def _make_workflow():
    """Create a minimal workflow with common node types."""
    return {
        "1": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "Positive Prompt"},
            "inputs": {"text": "original positive"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "Negative Prompt"},
            "inputs": {"text": "original negative"},
        },
        "3": {
            "class_type": "KSampler",
            "inputs": {"seed": 0, "steps": 20, "cfg": 7.0},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 256, "height": 256, "batch_size": 1},
        },
        "5": {
            "class_type": "LoadImage",
            "inputs": {"image": "default.png"},
        },
        "6": {
            "class_type": "LoadImage",
            "_meta": {"title": "Reference Image"},
            "inputs": {"image": "default_ref.png"},
        },
        "7": {
            "class_type": "VAEDecode",
            "inputs": {"samples": []},
        },
    }


class TestPatchClipTextEncode:
    """Tests for CLIPTextEncode patching."""

    def test_positive_prompt(self):
        """Node with title containing 'positive' → inputs['text'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, positive_prompt="new positive")
        assert result["1"]["inputs"]["text"] == "new positive"

    def test_negative_prompt(self):
        """Node with title containing 'negative' → inputs['text'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, negative_prompt="new negative")
        assert result["2"]["inputs"]["text"] == "new negative"

    def test_negative_default_when_none(self):
        """When negative_prompt is None, uses _COMMON_NEGATIVE."""
        wf = _make_workflow()
        result = _patch_workflow(wf, negative_prompt=None)
        assert "blurry" in result["2"]["inputs"]["text"]

    def test_positive_not_set_when_none(self):
        """When positive_prompt is None, original text preserved."""
        wf = _make_workflow()
        result = _patch_workflow(wf, positive_prompt=None)
        assert result["1"]["inputs"]["text"] == "original positive"


class TestPatchKSampler:
    """Tests for KSampler patching."""

    def test_seed_set(self):
        """inputs['seed'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, seed=42)
        assert result["3"]["inputs"]["seed"] == 42

    def test_random_seed_when_none(self):
        """seed=None → random seed generated."""
        wf = _make_workflow()
        result = _patch_workflow(wf, seed=None)
        assert isinstance(result["3"]["inputs"]["seed"], int)
        assert 0 <= result["3"]["inputs"]["seed"] <= 2**32 - 1


class TestPatchEmptyLatentImage:
    """Tests for EmptyLatentImage patching."""

    def test_width_height_set(self):
        """inputs['width'], inputs['height'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, width=512, height=512)
        assert result["4"]["inputs"]["width"] == 512
        assert result["4"]["inputs"]["height"] == 512

    def test_not_set_when_none(self):
        """When width/height is None, original values preserved."""
        wf = _make_workflow()
        result = _patch_workflow(wf, width=None, height=None)
        assert result["4"]["inputs"]["width"] == 256
        assert result["4"]["inputs"]["height"] == 256


class TestPatchLoadImage:
    """Tests for LoadImage patching."""

    def test_uploaded_filename(self):
        """Node ID in uploaded_filenames → inputs['image'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, uploaded_filenames={"5": "uploaded_test.png"})
        assert result["5"]["inputs"]["image"] == "uploaded_test.png"

    def test_reference_image(self):
        """_meta.title contains 'reference' + ref_image_filename → inputs['image'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, ref_image_filename="ref_leader.png")
        assert result["6"]["inputs"]["image"] == "ref_leader.png"

    def test_reference_not_set_without_filename(self):
        """No ref_image_filename → reference node unchanged."""
        wf = _make_workflow()
        result = _patch_workflow(wf, ref_image_filename=None)
        assert result["6"]["inputs"]["image"] == "default_ref.png"


class TestPatchExtraOverrides:
    """Tests for extra_overrides."""

    def test_arbitrary_node_override(self):
        """Arbitrary node_id → inputs updated."""
        wf = _make_workflow()
        result = _patch_workflow(wf, extra_overrides={"7": {"samples": ["overridden"]}})
        assert result["7"]["inputs"]["samples"] == ["overridden"]


class TestPatchPreservesUnrelated:
    """Tests that unrelated nodes are unchanged."""

    def test_unrelated_nodes_unchanged(self):
        """Non-targeted nodes unchanged."""
        wf = _make_workflow()
        result = _patch_workflow(wf, positive_prompt="new")
        # Node 7 (VAEDecode) should be unchanged
        assert result["7"]["inputs"]["samples"] == []
        # Node 3 (KSampler) steps should be unchanged
        assert result["3"]["inputs"]["steps"] == 20

