"""Image-quality metrics calculated from real image pixel arrays."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity


def _validate_pair(original: np.ndarray, processed: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
	original_array = np.asarray(original)
	processed_array = np.asarray(processed)
	if original_array.ndim == 2 and processed_array.ndim == 3 and processed_array.shape[2] == 3:
		original_array = np.repeat(original_array[:, :, None], 3, axis=2)
	elif processed_array.ndim == 2 and original_array.ndim == 3 and original_array.shape[2] == 3:
		processed_array = np.repeat(processed_array[:, :, None], 3, axis=2)
	if original_array.shape != processed_array.shape:
		raise ValueError("Images must have the same dimensions and channel count for comparison.")
	if original_array.ndim not in (2, 3):
		raise ValueError("Image metrics require grayscale or color image arrays.")
	if original_array.ndim == 3 and original_array.shape[2] not in (1, 3, 4):
		raise ValueError("Image metrics support grayscale, RGB, or RGBA images.")
	return original_array, processed_array


def calculate_mse(original: np.ndarray, processed: np.ndarray) -> float:
	"""Calculate mean squared error over all pixels and channels."""
	first, second = _validate_pair(original, processed)
	difference = first.astype(np.float64) - second.astype(np.float64)
	return float(np.mean(np.square(difference)))


def calculate_psnr(original: np.ndarray, processed: np.ndarray) -> float:
	"""Calculate peak signal-to-noise ratio, returning infinity for identical images."""
	first, second = _validate_pair(original, processed)
	mse = calculate_mse(first, second)
	if mse == 0:
		return math.inf
	if np.issubdtype(first.dtype, np.integer):
		peak = float(np.iinfo(first.dtype).max)
	else:
		peak = max(1.0, float(np.max(first)), float(np.max(second)))
	return float(10.0 * math.log10((peak * peak) / mse))


def calculate_ssim(original: np.ndarray, processed: np.ndarray) -> float:
	"""Calculate structural similarity for grayscale or multichannel images."""
	first, second = _validate_pair(original, processed)
	height, width = first.shape[:2]
	window_size = min(7, height, width)
	if window_size % 2 == 0:
		window_size -= 1
	if window_size < 3:
		raise ValueError("SSIM requires images that are at least 3 pixels wide and high.")
	if np.issubdtype(first.dtype, np.integer):
		data_range = float(np.iinfo(first.dtype).max - np.iinfo(first.dtype).min)
	else:
		data_range = max(1.0, float(max(np.max(first), np.max(second)) - min(np.min(first), np.min(second))))
	return float(
		structural_similarity(
			first,
			second,
			data_range=data_range,
			channel_axis=-1 if first.ndim == 3 and first.shape[2] > 1 else None,
			win_size=window_size,
		)
	)


def _read_image(path: str | Path) -> np.ndarray:
	with Image.open(path) as opened:
		if opened.mode in ("1", "L", "I", "F"):
			return np.asarray(opened.convert("L"), dtype=np.uint8)
		return np.asarray(opened.convert("RGB"), dtype=np.uint8)


def compare_images(
	original_path: str | Path,
	processed_path: str | Path,
	*,
	crop_processed_dct_padding: bool = False,
) -> dict[str, float]:
	"""Load two images and calculate metrics, optionally excluding DCT block padding."""
	original = _read_image(original_path)
	processed = _read_image(processed_path)
	if original.ndim == 2 and processed.ndim == 3 and processed.shape[2] == 3:
		original = np.repeat(original[:, :, None], 3, axis=2)
	elif processed.ndim == 2 and original.ndim == 3 and original.shape[2] == 3:
		processed = np.repeat(processed[:, :, None], 3, axis=2)
	if original.shape != processed.shape and crop_processed_dct_padding:
		original_height, original_width = original.shape[:2]
		processed_height, processed_width = processed.shape[:2]
		expected_height = ((original_height + 7) // 8) * 8
		expected_width = ((original_width + 7) // 8) * 8
		if (processed_height, processed_width) == (expected_height, expected_width):
			processed = processed[:original_height, :original_width]

	return {
		"mse": calculate_mse(original, processed),
		"psnr": calculate_psnr(original, processed),
		"ssim": calculate_ssim(original, processed),
	}
