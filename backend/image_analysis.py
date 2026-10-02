"""Image metadata, histogram, bit-plane, and difference-image utilities."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def get_image_info(image_path: str | Path) -> dict[str, int | str]:
	"""Return file and image properties read from the actual image."""
	path = Path(image_path)
	with Image.open(path) as image:
		image.load()
		width, height = image.size
		channels = len(image.getbands())
		mode = image.mode
		if mode == "P":
			color_type = "indexed color"
		elif channels == 1:
			color_type = "grayscale"
		elif "A" in image.getbands():
			color_type = "color with alpha"
		else:
			color_type = "color"
		return {
			"filename": path.name,
			"width": width,
			"height": height,
			"channels": channels,
			"format": image.format or "unknown",
			"mode": mode,
			"file_size_bytes": path.stat().st_size,
			"total_pixels": width * height,
			"color_type": color_type,
		}


def calculate_histogram(image_path: str | Path) -> dict[str, list[int]]:
	"""Return 256-bin intensity histograms for grayscale or RGB channels."""
	with Image.open(image_path) as image:
		image.load()
		if image.mode in ("1", "L", "I", "F"):
			return {"grayscale": [int(value) for value in image.convert("L").histogram()]}
		red, green, blue = image.convert("RGB").split()
		return {
			"red": [int(value) for value in red.histogram()],
			"green": [int(value) for value in green.histogram()],
			"blue": [int(value) for value in blue.histogram()],
		}


def generate_lsb_plane(image_path: str | Path) -> np.ndarray:
	"""Return an 8-bit image where each source LSB is shown as black or white."""
	with Image.open(image_path) as image:
		image.load()
		if image.mode in ("1", "L", "I", "F"):
			pixels = np.asarray(image.convert("L"), dtype=np.uint8)
		else:
			pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
	return np.bitwise_and(pixels, 1).astype(np.uint8) * 255


def create_difference_image(
	original_path: str | Path,
	processed_path: str | Path,
	output_path: str | Path,
) -> None:
	"""Save the absolute per-pixel difference between equal-sized images."""
	with Image.open(original_path) as original_image, Image.open(processed_path) as processed_image:
		original = np.asarray(original_image.convert("RGB"), dtype=np.int16)
		processed = np.asarray(processed_image.convert("RGB"), dtype=np.int16)
	if original.shape != processed.shape:
		raise ValueError("Images must have the same dimensions to create a difference image.")
	difference = np.abs(original - processed).astype(np.uint8)
	destination = Path(output_path)
	destination.parent.mkdir(parents=True, exist_ok=True)
	Image.fromarray(difference, mode="RGB").save(destination, format="PNG")
