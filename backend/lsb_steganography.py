"""Least Significant Bit image steganography."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, UnidentifiedImageError

MAGIC = b"STEGAV1"
LENGTH_FORMAT = ">I"
HEADER_SIZE = len(MAGIC) + struct.calcsize(LENGTH_FORMAT)


def _rgb_array(image: str | Path | Image.Image | np.ndarray) -> np.ndarray:
	if isinstance(image, (str, Path)):
		with Image.open(image) as opened:
			return np.asarray(opened.convert("RGB"), dtype=np.uint8)
	if isinstance(image, Image.Image):
		return np.asarray(image.convert("RGB"), dtype=np.uint8)
	array = np.asarray(image)
	if array.ndim == 2:
		array = np.repeat(array[:, :, None], 3, axis=2)
	if array.ndim != 3 or array.shape[2] < 3:
		raise ValueError("Capacity calculation requires a grayscale or color image.")
	return np.asarray(np.clip(array[:, :, :3], 0, 255), dtype=np.uint8)


def calculate_capacity(image: str | Path | Image.Image | np.ndarray) -> dict[str, int]:
	"""Return total RGB LSB capacity and maximum message size after the header."""
	rgb = _rgb_array(image)
	total_bits = int(rgb.shape[0] * rgb.shape[1] * 3)
	header_bits = HEADER_SIZE * 8
	usable_bits = max(0, total_bits - header_bits)
	return {
		"total_bits": total_bits,
		"total_bytes": total_bits // 8,
		"header_bits": header_bits,
		"max_message_bits": usable_bits,
		"max_message_bytes": usable_bits // 8,
	}


def encode_lsb(input_path: str | Path, output_path: str | Path, message: str) -> None:
	"""Embed a UTF-8 message in the RGB channel LSBs and save a PNG image."""
	source = Path(input_path)
	destination = Path(output_path)
	if source.resolve() == destination.resolve():
		raise ValueError("The output image must not overwrite the original image.")
	try:
		with Image.open(source) as opened:
			rgb = np.asarray(opened.convert("RGB"), dtype=np.uint8)
	except (OSError, UnidentifiedImageError) as error:
		raise ValueError("The uploaded file is not a readable image.") from error

	message_bytes = message.encode("utf-8")
	if len(message_bytes) > 0xFFFFFFFF:
		raise ValueError("The message is too large for the StegaVision header.")
	payload = MAGIC + struct.pack(LENGTH_FORMAT, len(message_bytes)) + message_bytes
	payload_bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
	capacity = calculate_capacity(rgb)
	if payload_bits.size > capacity["total_bits"]:
		raise ValueError(
			f"Message exceeds image capacity: up to {capacity['max_message_bytes']} bytes "
			"can be stored in this image."
		)

	stego = rgb.copy()
	flat = stego.reshape(-1)
	flat[: payload_bits.size] = (flat[: payload_bits.size] & 0xFE) | payload_bits
	destination.parent.mkdir(parents=True, exist_ok=True)
	Image.fromarray(stego, mode="RGB").save(destination, format="PNG")


def decode_lsb(input_path: str | Path) -> str:
	"""Extract and validate a StegaVision LSB payload from an image."""
	try:
		with Image.open(input_path) as opened:
			rgb = np.asarray(opened.convert("RGB"), dtype=np.uint8)
	except (OSError, UnidentifiedImageError) as error:
		raise ValueError("The uploaded file is not a readable image.") from error

	flat = rgb.reshape(-1)
	header_bits = HEADER_SIZE * 8
	if flat.size < header_bits:
		raise ValueError("This image is too small to contain a StegaVision LSB header.")
	header = np.packbits(flat[:header_bits] & 1).tobytes()
	if not header.startswith(MAGIC):
		raise ValueError("No valid StegaVision LSB payload was found in this image.")

	message_length = struct.unpack(LENGTH_FORMAT, header[len(MAGIC) : HEADER_SIZE])[0]
	required_bits = (HEADER_SIZE + message_length) * 8
	if required_bits > flat.size:
		raise ValueError("The LSB payload is incomplete or the image has been corrupted.")
	message_bits = flat[header_bits:required_bits] & 1
	message_bytes = np.packbits(message_bits).tobytes()
	try:
		return message_bytes.decode("utf-8")
	except UnicodeDecodeError as error:
		raise ValueError("The LSB payload is corrupted and is not valid UTF-8.") from error
