"""Unit tests for inpainting (src/inpainting.py)."""

from PIL import Image
from src.inpainting import create_inpaint_mask, get_inpaint_prompt


class TestCreateInpaintMask:
    """Tests for create_inpaint_mask."""

    def test_dimensions(self):
        """Output size matches input."""
        mask = create_inpaint_mask(64, 64, {"x": 10, "y": 10}, {"x": 30, "y": 30})
        assert mask.size == (64, 64)

    def test_mode(self):
        """Output is 'L' (grayscale)."""
        mask = create_inpaint_mask(64, 64, {"x": 10, "y": 10}, {"x": 30, "y": 30})
        assert mask.mode == "L"

    def test_white_region(self):
        """Pixels inside bbox are 255."""
        mask = create_inpaint_mask(64, 64, {"x": 10, "y": 10}, {"x": 30, "y": 30})
        # Center of bbox should be white
        assert mask.getpixel((20, 20)) == 255

    def test_black_region(self):
        """Pixels outside bbox are 0."""
        mask = create_inpaint_mask(64, 64, {"x": 10, "y": 10}, {"x": 30, "y": 30})
        assert mask.getpixel((0, 0)) == 0
        assert mask.getpixel((63, 63)) == 0

    def test_point_ordering(self):
        """point_a > point_b → bbox still correct (min/max)."""
        mask = create_inpaint_mask(64, 64, {"x": 30, "y": 30}, {"x": 10, "y": 10})
        assert mask.getpixel((20, 20)) == 255

    def test_blur(self):
        """blur_radius=3 → edge pixels are between 0 and 255."""
        mask = create_inpaint_mask(64, 64, {"x": 10, "y": 10}, {"x": 30, "y": 30}, blur_radius=3)
        # Edge pixel should be blurred (not pure 0 or 255)
        val = mask.getpixel((10, 10))
        assert 0 < val < 255

    def test_no_blur_default(self):
        """Default blur_radius=0 → sharp edges."""
        mask = create_inpaint_mask(64, 64, {"x": 10, "y": 10}, {"x": 30, "y": 30})
        # Edge pixel should be exactly 255
        assert mask.getpixel((10, 10)) == 255


class TestGetInpaintPrompt:
    """Tests for get_inpaint_prompt."""

    def test_known_water(self):
        assert "sparkling blue" in get_inpaint_prompt("water")

    def test_known_gravel_road(self):
        assert "grey gravel" in get_inpaint_prompt("gravel_road")

    def test_known_grass(self):
        assert "lush green" in get_inpaint_prompt("grass")

    def test_known_dirt(self):
        assert "brown dirt" in get_inpaint_prompt("dirt")

    def test_known_stone_floor(self):
        assert "grey stone" in get_inpaint_prompt("stone_floor")

    def test_known_lava(self):
        assert "glowing red-orange" in get_inpaint_prompt("lava")

    def test_unknown_fallback(self):
        """Unknown fill_type → generic prompt with the type name."""
        prompt = get_inpaint_prompt("magma")
        assert "pixel art magma" in prompt
        assert "top-down 2d game asset" in prompt

