"""Dataset generation pipeline — ComfyUI orchestration, metadata embedding, HF dataset export."""

from src.generation.image_metadata import read_metadata_from_file, embed_metadata_into_file
from src.generation.dataset_generator import main as generate_images
from src.generation.prepare_dataset import main as prepare_dataset

__all__ = [
    "read_metadata_from_file",
    "embed_metadata_into_file",
    "generate_images",
    "prepare_dataset",
]
