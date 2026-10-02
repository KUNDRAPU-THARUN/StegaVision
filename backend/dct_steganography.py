"""Block-DCT steganography using coefficient-pair differential modulation."""

from __future__ import annotations

import struct
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

MAGIC = b"DCTV1"
LENGTH_FORMAT = ">I"
DIMENSION_FORMAT = ">II"
HEADER_SIZE = len(MAGIC) + struct.calcsize(LENGTH_FORMAT) + struct.calcsize(DIMENSION_FORMAT)
BLOCK_SIZE = 8
COEFFICIENT_A = (2, 3)
COEFFICIENT_B = (3, 2)
MIN_COEFFICIENT_GAP = 32.0


def _load_bgr(image: str | Path | np.ndarray | Image.Image) -> np.ndarray:
	if isinstance(image, (str, Path)):
		path = Path(image)
		encoded = np.fromfile(path, dtype=np.uint8)
		decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
		if decoded is None:
			raise ValueError("The uploaded file is not a readable color image.")
		return decoded
	if isinstance(image, Image.Image):
		return cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
	array = np.asarray(image)
	if array.ndim == 2:
		return cv2.cvtColor(np.asarray(array, dtype=np.uint8), cv2.COLOR_GRAY2BGR)
	if array.ndim != 3 or array.shape[2] < 3:
		raise ValueError("DCT capacity calculation requires a grayscale or color image.")
	return np.asarray(np.clip(array[:, :, :3], 0, 255), dtype=np.uint8)


def _padded_luminance(bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray, int, int]:
	ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
	height, width = ycrcb.shape[:2]
	pad_bottom = (-height) % BLOCK_SIZE
	pad_right = (-width) % BLOCK_SIZE
	padded = cv2.copyMakeBorder(
		ycrcb,
		0,
		pad_bottom,
		0,
		pad_right,
		cv2.BORDER_REPLICATE,
	)
	return padded[:, :, 0], padded, width, height


def _decode_dct_payload(y_channel: np.ndarray) -> tuple[str, int, int]:
	image_height, image_width = y_channel.shape
	block_count = (image_height // BLOCK_SIZE) * (image_width // BLOCK_SIZE)
	header_bits_count = HEADER_SIZE * 8
	if block_count < header_bits_count:
		raise ValueError("This image is too small to contain a StegaVision DCT header.")

	header = _bits_to_bytes(_extract_bits(y_channel, header_bits_count))
	if not header.startswith(MAGIC):
		raise ValueError("No valid StegaVision DCT payload was found in this image.")
	offset = len(MAGIC)
	message_length = struct.unpack(LENGTH_FORMAT, header[offset : offset + 4])[0]
	offset += 4
	original_width, original_height = struct.unpack(
		DIMENSION_FORMAT,
		header[offset : offset + struct.calcsize(DIMENSION_FORMAT)],
	)
	expected_width = ((original_width + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
	expected_height = ((original_height + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
	if not (0 < original_width and 0 < original_height) or (image_width, image_height) != (
		expected_width,
		expected_height,
	):
		raise ValueError("The DCT image dimension header is corrupted.")

	required_bits = (HEADER_SIZE + message_length) * 8
	if required_bits > block_count:
		raise ValueError("The DCT payload is incomplete or the image has been corrupted.")
	payload_bits = _extract_bits(y_channel, required_bits)[header_bits_count:required_bits]
	try:
		message = _bits_to_bytes(payload_bits).decode("utf-8")
	except UnicodeDecodeError as error:
		raise ValueError("The DCT payload is corrupted and is not valid UTF-8.") from error
	return message, original_width, original_height


def get_dct_original_dimensions(input_path: str | Path) -> tuple[int, int]:
	"""Validate and return dimensions recorded by an encoded StegaVision DCT image."""
	bgr = _load_bgr(input_path)
	y_channel, _, _, _ = _padded_luminance(bgr)
	_, original_width, original_height = _decode_dct_payload(y_channel)
	return original_width, original_height



def calculate_dct_capacity(image: str | Path | np.ndarray | Image.Image) -> dict[str, int]:
	"""Estimate payload capacity from padded 8x8 blocks, one bit per block."""
	bgr = _load_bgr(image)
	height, width = bgr.shape[:2]
	block_count = ((height + BLOCK_SIZE - 1) // BLOCK_SIZE) * (
		(width + BLOCK_SIZE - 1) // BLOCK_SIZE
	)
	header_bits = HEADER_SIZE * 8
	usable_bits = max(0, block_count - header_bits)
	return {
		"block_count": block_count,
		"bits_per_block": 1,
		"total_bits": block_count,
		"header_bits": header_bits,
		"max_message_bits": usable_bits,
		"max_message_bytes": usable_bits // 8,
	}


def _iter_block_coordinates(width: int, height: int):
	for top in range(0, height, BLOCK_SIZE):
		for left in range(0, width, BLOCK_SIZE):
			yield top, left


def _extract_bits(y_channel: np.ndarray, count: int) -> list[int]:
	bits: list[int] = []
	height, width = y_channel.shape
	for top, left in _iter_block_coordinates(width, height):
		block = y_channel[top : top + BLOCK_SIZE, left : left + BLOCK_SIZE].astype(np.float32)
		coefficients = cv2.dct(block)
		bits.append(int(coefficients[COEFFICIENT_A] > coefficients[COEFFICIENT_B]))
		if len(bits) == count:
			break
	return bits


def _bits_to_bytes(bits: list[int]) -> bytes:
	return np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes()


def encode_dct(input_path: str | Path, output_path: str | Path, message: str) -> None:
	"""Embed a UTF-8 message in mid-frequency coefficients of 8x8 luminance blocks."""
	source = Path(input_path)
	destination = Path(output_path)
	if source.resolve() == destination.resolve():
		raise ValueError("The output image must not overwrite the original image.")
	bgr = _load_bgr(source)
	y_channel, ycrcb, original_width, original_height = _padded_luminance(bgr)
	message_bytes = message.encode("utf-8")
	if len(message_bytes) > 0xFFFFFFFF:
		raise ValueError("The message is too large for the DCT header.")
	header = (
		MAGIC
		+ struct.pack(LENGTH_FORMAT, len(message_bytes))
		+ struct.pack(DIMENSION_FORMAT, original_width, original_height)
	)
	payload_bits = np.unpackbits(np.frombuffer(header + message_bytes, dtype=np.uint8))
	capacity = calculate_dct_capacity(bgr)
	if payload_bits.size > capacity["block_count"]:
		raise ValueError(
			f"Message exceeds DCT image capacity: up to {capacity['max_message_bytes']} bytes "
			"can be stored in this image."
		)

	modified_y = y_channel.astype(np.float32)
	padded_height, padded_width = modified_y.shape
	for bit, (top, left) in zip(
		payload_bits.tolist(), _iter_block_coordinates(padded_width, padded_height)
	):
		block = modified_y[top : top + BLOCK_SIZE, left : left + BLOCK_SIZE]
		coefficients = cv2.dct(block.copy())
		first = float(coefficients[COEFFICIENT_A])
		second = float(coefficients[COEFFICIENT_B])
		if (bit == 1 and first - second < MIN_COEFFICIENT_GAP) or (
			bit == 0 and second - first < MIN_COEFFICIENT_GAP
		):
			center = (first + second) / 2.0
			half_gap = MIN_COEFFICIENT_GAP / 2.0
			coefficients[COEFFICIENT_A] = center + half_gap if bit else center - half_gap
			coefficients[COEFFICIENT_B] = center - half_gap if bit else center + half_gap
		modified_y[top : top + BLOCK_SIZE, left : left + BLOCK_SIZE] = cv2.idct(coefficients)

	ycrcb[:, :, 0] = np.clip(np.rint(modified_y), 0, 255).astype(np.uint8)
	stego_bgr = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
	success, encoded_png = cv2.imencode(".png", stego_bgr)
	if not success:
		raise OSError("OpenCV could not encode the DCT stego image as PNG.")
	destination.parent.mkdir(parents=True, exist_ok=True)
	destination.write_bytes(encoded_png.tobytes())


def decode_dct(input_path: str | Path) -> str:
	"""Recover and validate a payload encoded by :func:`encode_dct`."""
	bgr = _load_bgr(input_path)
	y_channel, _, _, _ = _padded_luminance(bgr)
	message, _, _ = _decode_dct_payload(y_channel)
	return message
