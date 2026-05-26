from PIL import Image, ImageDraw, ImageFilter


def create_inpaint_mask(width: int, height: int, point_a: dict, point_b: dict,
                        blur_radius: int = 0) -> Image.Image:
    """
    Creates a binary mask image where the bounding box between point_a and point_b is white (to be inpainted),
    and everything else is black.

    Args:
        blur_radius: If > 0, applies a Gaussian blur to soften mask edges
                     (reduces harsh rectilinear seams in organic pixel art).
    """
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)

    x1, y1 = min(point_a['x'], point_b['x']), min(point_a['y'], point_b['y'])
    x2, y2 = max(point_a['x'], point_b['x']), max(point_a['y'], point_b['y'])

    draw.rectangle([x1, y1, x2, y2], fill=255)

    if blur_radius > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    return mask


def get_inpaint_prompt(fill_type: str) -> str:
    """
    Translates a generic fill_type (like 'water' or 'gravel_road') into a rich,
    production-ready diffusion model prompt for ComfyUI.
    """
    prompts = {
        "water": "sparkling blue pixel art river water texture, seamless, top-down 2d game",
        "gravel_road": "pixel art grey gravel dirt path, detailed stones, top-down 2d game",
        "grass": "lush green pixel art grass tile, top-down view",
        "dirt": "pixel art brown dirt path, top-down 2d game tile",
        "stone_floor": "pixel art grey stone floor tile, medieval, top-down",
        "lava": "glowing red-orange pixel art lava flow, top-down 2d game",
    }
    return prompts.get(fill_type, f"pixel art {fill_type}, detailed, top-down 2d game asset")
