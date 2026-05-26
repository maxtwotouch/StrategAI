# Inpainting Workflow: ComfyUI vs HuggingFace `diffusers`

When building production-grade generative systems with localized editing (inpainting) such as replacing terrain tiles with water or gravel roads, iterating on workflows is critical. This document outlines how to prototype inpainting with ComfyUI and scale it to production using HuggingFace's `diffusers`.

## 1. Prototyping with ComfyUI
ComfyUI is a powerful node-based interface that lets you build, test, and tune your diffusion pipelines visually. 

### Why ComfyUI for testing?
- **Fast Iteration:** Easily swap models, LoRAs, and prompt parameters.
- **Visual Debugging:** You can see the intermediate representations of masks and latent noise.
- **Node Graph to API:** ComfyUI natively supports exporting your graph as an API JSON, allowing you to script tests without writing a custom Python inference loop initially.

### ComfyUI Inpainting Graph Setup:
1. **Load Image:** Input the raw base terrain background.
2. **Load Mask:** Input the programmatically generated A-B coordinate binary mask.
3. **VAE Encode (for Inpainting):** Merges the latent representation of the source image and mask. 
4. **Conditioning:** Set positive ("clear blue water, pixel art style") and negative ("blur, low res") prompts, attaching your custom trained LoRA.
5. **KSampler:** Generates the filled area inside the masked region, ignoring the rest.
6. **VAE Decode:** Outputs the final composited image.

## 2. Production with HuggingFace `diffusers`
Once the configuration is tuned and proven in ComfyUI, transitioning to HuggingFace `diffusers` directly in Python provides a much lighter, stateless, and scalable production architecture. ComfyUI contains overhead not needed for basic auto-scaling GPU web servers.

### HuggingFace Production Implementation

In a production worker context (e.g. RunPod, Modal, or Celery worker), you run this strictly via the `AutoPipelineForInpainting` or specific Flux inpaint pipelines:

```python
import torch
from diffusers import AutoPipelineForInpainting
from PIL import Image

# Initialize once in the worker's application lifecycle (Global State)
# Wait for exact Flux2 Inpaint implementations or use Stable Diffusion XL as heavily supported backbone
pipeline = AutoPipelineForInpainting.from_pretrained(
    "diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
    torch_dtype=torch.float16,
    variant="fp16"
).to("cuda")

# Optional: Load your pixel-art LoRA
# pipeline.load_lora_weights("path/to/pixel_art_lora.safetensors")

def production_inpaint(image_path: str, mask_path: str, prompt: str) -> Image.Image:
    init_image = Image.open(image_path).convert("RGB")
    mask_image = Image.open(mask_path).convert("RGB")

    # The diffusers library handles the masked inference directly
    out_img = pipeline(
        prompt=prompt,
        image=init_image,
        mask_image=mask_image,
        num_inference_steps=20,
        guidance_scale=8.0,
        strength=0.99  # 1.0 means complete replacement inside the mask
    ).images[0]
    
    return out_img
```

### Key Considerations for Production Inpainting
- **Mask Bleed:** Sometimes simple rectangular A-B bounding boxes produce harsh straight lines in organic pixel art. Apply a slight Gaussian blur to your mask boundaries before passing it to the diffusion model to smooth edges.
- **Consistency:** Passing the original seed along with high `strength` ensures that only the painted area changes, preserving the static parts of your background tile exactly.
