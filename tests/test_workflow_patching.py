"""Unit tests for ComfyUI workflow patching (src/comfyui_client.py).

.. note::
   Workflow JSONs are the single source of truth for all parameters
   except prompt, seed, and input images.  The patcher no longer
   injects guidance, steps, denoise, sampler, or resolution —
   those are baked into the workflow JSON files.
"""

import copy
import pytest
from src.comfyui_client import _patch_workflow


def _make_workflow():
    """Create a minimal workflow with actual node types used in our JSONs.

    Nodes that are baked into the workflow JSON (FluxGuidance, CFGGuider,
    BasicScheduler, KSamplerSelect, EmptyLatentImage — guidance, steps,
    denoise, sampler, resolution) are included for structural correctness
    but are NOT patched at runtime.  Only CLIPTextEncode, SamplerCustomAdvanced,
    LoadImage, and RandomNoise receive runtime injection.
    """
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
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 256, "height": 256, "batch_size": 1},
        },
        "4": {
            "class_type": "LoadImage",
            "inputs": {"image": "default.png"},
        },
        # ComfyUI default title — NOT matched by ref_image_filename
        # (only nodes with "reference" in _meta.title are matched)
        "5": {
            "class_type": "LoadImage",
            "_meta": {"title": "Load Image"},
            "inputs": {"image": "default_comfy.png"},
        },
        # Node with explicit "reference" title — WILL be matched
        "6": {
            "class_type": "LoadImage",
            "_meta": {"title": "Reference Image"},
            "inputs": {"image": "default_ref.png"},
        },
        "7": {
            "class_type": "BasicScheduler",
            "inputs": {"scheduler": "simple", "steps": 4, "denoise": 1.0, "model": ["1", 0]},
        },
        "8": {
            "class_type": "FluxGuidance",
            "inputs": {"guidance": 3.5, "conditioning": ["1", 0]},
        },
        "9": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        "10": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": 12345},
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


class TestPatchLoadImage:
    """Tests for LoadImage patching (uploaded images + reference filename)."""

    def test_uploaded_filename(self):
        """Node ID in uploaded_filenames → inputs['image'] set."""
        wf = _make_workflow()
        result = _patch_workflow(wf, uploaded_filenames={"4": "uploaded_test.png"})
        assert result["4"]["inputs"]["image"] == "uploaded_test.png"

    def test_reference_title_matched(self):
        """Title 'Reference Image' → ref_image_filename applied to that node."""
        wf = _make_workflow()
        result = _patch_workflow(wf, ref_image_filename="ref_leader.png")
        # Node 6 has title "Reference Image" → should be patched
        assert result["6"]["inputs"]["image"] == "ref_leader.png"
        # Node 5 has default "Load Image" title → should NOT be patched
        assert result["5"]["inputs"]["image"] == "default_comfy.png"

    def test_ref_not_set_without_filename(self):
        """No ref_image_filename → LoadImage nodes unchanged."""
        wf = _make_workflow()
        result = _patch_workflow(wf, ref_image_filename=None)
        assert result["5"]["inputs"]["image"] == "default_comfy.png"
        assert result["6"]["inputs"]["image"] == "default_ref.png"


class TestPatchExtraOverrides:
    """Tests for extra_overrides."""

    def test_arbitrary_node_override(self):
        """Arbitrary node_id → inputs updated."""
        wf = _make_workflow()
        result = _patch_workflow(wf, extra_overrides={"5": {"image": "overridden.png"}})
        assert result["5"]["inputs"]["image"] == "overridden.png"


class TestPatchPreservesUnrelated:
    """Tests that unrelated nodes and baked-in parameters are unchanged."""

    def test_unrelated_nodes_unchanged(self):
        """Non-targeted nodes unchanged after patching."""
        wf = _make_workflow()
        result = _patch_workflow(wf, positive_prompt="new")
        # Node 1 (CLIPTextEncode) should be updated
        assert result["1"]["inputs"]["text"] == "new"
        # Node 4 (LoadImage) should be unchanged without upload
        assert result["4"]["inputs"]["image"] == "default.png"
        # Node 5 (LoadImage with "Load Image" title) unchanged without ref match
        assert result["5"]["inputs"]["image"] == "default_comfy.png"

    def test_baked_in_params_not_overridden(self):
        """Guidance, steps, denoise, sampler, resolution are NEVER patched."""
        wf = _make_workflow()
        result = _patch_workflow(wf, seed=42, positive_prompt="test")
        # Baked-in values must remain at their workflow defaults
        assert result["7"]["inputs"]["steps"] == 4  # BasicScheduler
        assert result["7"]["inputs"]["denoise"] == 1.0
        assert result["8"]["inputs"]["guidance"] == 3.5  # FluxGuidance
        assert result["9"]["inputs"]["sampler_name"] == "euler"  # KSamplerSelect
        assert result["12"]["inputs"]["cfg"] == 1.0  # CFGGuider
        assert result["3"]["inputs"]["width"] == 256  # EmptyLatentImage
        assert result["3"]["inputs"]["height"] == 256

    def test_deep_copy_does_not_mutate_original(self):
        """The original workflow dict must not be modified by _patch_workflow."""
        wf = _make_workflow()
        original_text = wf["1"]["inputs"]["text"]
        original_seed = wf["2"]["inputs"]["noise_seed"]

        _patch_workflow(wf, positive_prompt="modified", seed=99999)

        # Original dict must be unchanged
        assert wf["1"]["inputs"]["text"] == original_text
        assert wf["2"]["inputs"]["noise_seed"] == original_seed


class TestPatchRandomNoise:
    """Tests for RandomNoise patching."""

    def test_noise_seed_set(self):
        """RandomNoise → noise_seed set from seed param."""
        wf = _make_workflow()
        result = _patch_workflow(wf, seed=42)
        assert result["10"]["inputs"]["noise_seed"] == 42

    def test_random_seed_when_none(self):
        """seed=None → random noise_seed."""
        wf = _make_workflow()
        result = _patch_workflow(wf, seed=None)
        assert isinstance(result["10"]["inputs"]["noise_seed"], int)
        assert 0 <= result["10"]["inputs"]["noise_seed"] <= 2**32 - 1

