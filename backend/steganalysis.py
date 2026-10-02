"""Basic educational statistics for image LSBs and channel values."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _channel_array(image_path: str | Path) -> tuple[np.ndarray, list[str]]:
	with Image.open(image_path) as image:
		image.load()
		if image.mode in ("1", "L", "I", "F"):
			return np.asarray(image.convert("L"), dtype=np.uint8)[:, :, None], ["grayscale"]
		return np.asarray(image.convert("RGB"), dtype=np.uint8), ["red", "green", "blue"]


def analyze_lsb_distribution(image_path: str | Path) -> dict[str, int | float]:
	"""Count zero and one values across the image's usable intensity-channel LSBs."""
	pixels, _ = _channel_array(image_path)
	least_significant_bits = np.bitwise_and(pixels, 1)
	ones = int(np.count_nonzero(least_significant_bits))
	total = int(least_significant_bits.size)
	zeros = total - ones
	return {
		"lsb_0_count": zeros,
		"lsb_1_count": ones,
		"lsb_0_percentage": (zeros / total * 100.0) if total else 0.0,
		"lsb_1_percentage": (ones / total * 100.0) if total else 0.0,
		"total_analyzed_bits": total,
	}


def analyze_pixel_statistics(image_path: str | Path) -> dict[str, dict[str, float | int]]:
	"""Calculate mean, standard deviation, minimum, and maximum per channel."""
	pixels, channel_names = _channel_array(image_path)
	results: dict[str, dict[str, float | int]] = {}
	for index, name in enumerate(channel_names):
		channel = pixels[:, :, index]
		results[name] = {
			"mean": float(np.mean(channel)),
			"standard_deviation": float(np.std(channel)),
			"minimum": int(np.min(channel)),
			"maximum": int(np.max(channel)),
		}
	return results


def basic_steganalysis(image_path: str | Path) -> dict[str, Any]:
	"""Return neutral, descriptive statistics without claiming detection certainty."""
	distribution = analyze_lsb_distribution(image_path)
	difference = abs(
		float(distribution["lsb_0_percentage"])
		- float(distribution["lsb_1_percentage"])
	)
	if difference <= 5.0:
		observations = ["LSB distribution is relatively balanced."]
	else:
		observations = [
			"LSB values are not evenly distributed; natural image content can produce this pattern."
		]
	observations.append("These statistics describe the image and do not establish whether data is hidden.")
	return {
		"lsb_distribution": distribution,
		"pixel_statistics": analyze_pixel_statistics(image_path),
		"observations": observations,
		"warnings": [
			"Statistical analysis alone cannot definitively detect steganography.",
			"Image content, format conversion, and compression can affect these measurements.",
		],
	}
