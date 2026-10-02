"""Flask application and secure API endpoints for StegaVision."""

from __future__ import annotations

import base64
import math
import uuid
import os


from collections.abc import Callable
from pathlib import Path
from typing import Any

from flask import Flask, abort, g, jsonify, render_template, request, send_from_directory, url_for
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.utils import secure_filename

from backend import dct_steganography, image_analysis, image_metrics, lsb_steganography, steganalysis

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "webp"}
MAX_UPLOAD_BYTES = 16 * 1024 * 1024

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


def _api_error(message: str, status: int = 400):
	return jsonify({"success": False, "error": message}), status


def _save_upload(*field_names: str) -> tuple[Path, str]:
	uploaded: FileStorage | None = next(
		(request.files.get(field) for field in field_names if request.files.get(field)), None
	)
	if uploaded is None or not uploaded.filename:
		raise ValueError("Please upload an image file.")
	safe_original_name = secure_filename(uploaded.filename)
	extension = Path(safe_original_name).suffix.lower().lstrip(".")
	if not safe_original_name or extension not in ALLOWED_EXTENSIONS:
		raise ValueError("Unsupported image format. Use PNG, JPG, JPEG, BMP, or WEBP.")

	saved_name = f"{uuid.uuid4().hex}.{extension}"
	saved_path = UPLOAD_DIR / saved_name
	uploaded.save(saved_path)
	temporary_uploads = getattr(g, "temporary_uploads", None)
	if temporary_uploads is None:
		temporary_uploads = []
		g.temporary_uploads = temporary_uploads
	temporary_uploads.append(saved_path)
	try:
		with Image.open(saved_path) as image:
			image.verify()
		with Image.open(saved_path) as image:
			image.load()
	except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
		saved_path.unlink(missing_ok=True)
		raise ValueError("The uploaded file is not a valid or supported image.") from error
	return saved_path, safe_original_name


def _save_output_name() -> tuple[str, Path]:
	filename = f"{uuid.uuid4().hex}.png"
	return filename, OUTPUT_DIR / filename


def _capacity_api(calculator: Callable[[Path], dict[str, int]]):
	try:
		uploaded_path, _ = _save_upload("image", "file")
		with Image.open(uploaded_path) as image:
			width, height = image.size
		return jsonify(
			{
				"success": True,
				"width": width,
				"height": height,
				"capacity": calculator(uploaded_path),
			}
		)
	except ValueError as error:
		return _api_error(str(error))
	except HTTPException:
		raise
	except Exception:
		app.logger.exception("Unexpected image capacity error")
		return _api_error("Image capacity could not be calculated.", 500)


def _json_metrics(metrics: dict[str, float]) -> dict[str, float | str]:
	return {
		name: ("Infinity" if math.isinf(value) else value)
		for name, value in metrics.items()
	}


@app.get("/")
def index():
	return render_template("index.html")


@app.get("/lsb")
def lsb_page():
	return render_template("lsb.html")


@app.get("/dct")
def dct_page():
	return render_template("dct.html")


@app.get("/analysis")
def analysis_page():
	return render_template("analysis.html")


@app.get("/steganalysis")
def steganalysis_page():
	return render_template("steganalysis.html")


@app.get("/about")
def about_page():
	return render_template("about.html")


@app.post("/api/lsb/encode")
def lsb_encode_api():
	uploaded_path: Path | None = None
	try:
		uploaded_path, _ = _save_upload("image", "file")
		message = request.form.get("message", "")
		if message == "":
			raise ValueError("Please enter a message to encode.")
		capacity = lsb_steganography.calculate_capacity(uploaded_path)
		filename, output_path = _save_output_name()
		lsb_steganography.encode_lsb(uploaded_path, output_path, message)
		metrics = image_metrics.compare_images(uploaded_path, output_path)
		return jsonify(
			{
				"success": True,
				"message": "Message encoded successfully.",
				"output_filename": filename,
				"download_url": url_for("download_output", filename=filename),
				"capacity": capacity,
				"metrics": _json_metrics(metrics),
			}
		)
	except ValueError as error:
		return _api_error(str(error))
	except HTTPException:
		raise
	except Exception:
		app.logger.exception("Unexpected LSB encoding error")
		return _api_error("The image could not be encoded due to an unexpected error.", 500)


@app.post("/api/lsb/capacity")
def lsb_capacity_api():
	return _capacity_api(lsb_steganography.calculate_capacity)


@app.post("/api/lsb/decode")
def lsb_decode_api():
	try:
		uploaded_path, _ = _save_upload("image", "file")
		return jsonify({"success": True, "message": lsb_steganography.decode_lsb(uploaded_path)})
	except ValueError as error:
		return _api_error(str(error))
	except HTTPException:
		raise
	except Exception:
		app.logger.exception("Unexpected LSB decoding error")
		return _api_error("The image could not be decoded due to an unexpected error.", 500)


@app.post("/api/dct/encode")
def dct_encode_api():
	try:
		uploaded_path, _ = _save_upload("image", "file")
		message = request.form.get("message", "")
		if message == "":
			raise ValueError("Please enter a message to encode.")
		capacity = dct_steganography.calculate_dct_capacity(uploaded_path)
		filename, output_path = _save_output_name()
		dct_steganography.encode_dct(uploaded_path, output_path, message)
		metrics = image_metrics.compare_images(
			uploaded_path,
			output_path,
			crop_processed_dct_padding=True,
		)
		return jsonify(
			{
				"success": True,
				"message": "Message encoded successfully.",
				"output_filename": filename,
				"download_url": url_for("download_output", filename=filename),
				"preview_url": url_for("preview_output", filename=filename),
				"capacity": capacity,
				"metrics": _json_metrics(metrics),
			}
		)
	except ValueError as error:
		return _api_error(str(error))
	except HTTPException:
		raise
	except Exception:
		app.logger.exception("Unexpected DCT encoding error")
		return _api_error("The image could not be encoded due to an unexpected error.", 500)


@app.post("/api/dct/capacity")
def dct_capacity_api():
	return _capacity_api(dct_steganography.calculate_dct_capacity)


@app.post("/api/dct/decode")
def dct_decode_api():
	try:
		uploaded_path, _ = _save_upload("image", "file")
		return jsonify({"success": True, "message": dct_steganography.decode_dct(uploaded_path)})
	except ValueError as error:
		return _api_error(str(error))
	except HTTPException:
		raise
	except Exception:
		app.logger.exception("Unexpected DCT decoding error")
		return _api_error("The image could not be decoded due to an unexpected error.", 500)


@app.post("/api/analyze")
def analyze_api():
	try:
		uploaded_path, original_filename = _save_upload("image", "file")
		plane = image_analysis.generate_lsb_plane(uploaded_path)
		plane_image = Image.fromarray(plane)
		from io import BytesIO

		buffer = BytesIO()
		plane_image.save(buffer, format="PNG")
		image_info = image_analysis.get_image_info(uploaded_path)
		image_info["filename"] = original_filename
		return jsonify(
			{
				"success": True,
				"image_info": image_info,
				"histograms": image_analysis.calculate_histogram(uploaded_path),
				"lsb_plane": {
					"width": int(plane.shape[1]),
					"height": int(plane.shape[0]),
					"channels": 1 if plane.ndim == 2 else plane.shape[2],
					"png_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
				},
			}
		)
	except ValueError as error:
		return _api_error(str(error))
	except HTTPException:
		raise
	except Exception:
		app.logger.exception("Unexpected image analysis error")
		return _api_error("The image could not be analyzed.", 500)


@app.post("/api/steganalysis")
def steganalysis_api():
	try:
		uploaded_path, _ = _save_upload("image", "file")
		return jsonify({"success": True, **steganalysis.basic_steganalysis(uploaded_path)})
	except ValueError as error:
		return _api_error(str(error))
	except HTTPException:
		raise
	except Exception:
		app.logger.exception("Unexpected steganalysis error")
		return _api_error("The image could not be analyzed.", 500)


@app.post("/api/metrics")
def metrics_api():
	try:
		original_path, _ = _save_upload("original_image", "original")
		processed_path, _ = _save_upload("processed_image", "processed")
		with Image.open(original_path) as original_image, Image.open(processed_path) as processed_image:
			original_dimensions = original_image.size
			processed_dimensions = processed_image.size
		allow_dct_padding_crop = False
		if processed_dimensions != original_dimensions:
			try:
				encoded_dimensions = dct_steganography.get_dct_original_dimensions(processed_path)
				allow_dct_padding_crop = encoded_dimensions == original_dimensions
			except ValueError:
				pass
		metrics = image_metrics.compare_images(
			original_path,
			processed_path,
			crop_processed_dct_padding=allow_dct_padding_crop,
		)
		return jsonify({"success": True, **_json_metrics(metrics)})
	except ValueError as error:
		return _api_error(str(error))
	except HTTPException:
		raise
	except Exception:
		app.logger.exception("Unexpected image metrics error")
		return _api_error("The images could not be compared.", 500)


def _resolve_output_file(filename: str) -> Path:
	if not filename or Path(filename).name != filename or secure_filename(filename) != filename:
		abort(404)
	output_root = OUTPUT_DIR.resolve()
	output_path = (OUTPUT_DIR / filename).resolve()
	if output_path.parent != output_root or not output_path.is_file():
		abort(404)
	return output_path


@app.get("/api/download/<filename>")
def download_output(filename: str):
	_resolve_output_file(filename)
	output_root = OUTPUT_DIR.resolve()
	return send_from_directory(output_root, filename, as_attachment=True, download_name=filename)


@app.get("/api/preview/<filename>")
def preview_output(filename: str):
	_resolve_output_file(filename)
	return send_from_directory(
		OUTPUT_DIR.resolve(),
		filename,
		as_attachment=False,
		mimetype="image/png",
		max_age=0,
	)


@app.teardown_request
def cleanup_temporary_uploads(_error: BaseException | None) -> None:
	for uploaded_path in getattr(g, "temporary_uploads", ()):
		try:
			uploaded_path.unlink(missing_ok=True)
		except OSError:
			app.logger.warning("Could not remove a temporary uploaded image.")


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error: RequestEntityTooLarge):
	return _api_error("Image upload exceeds the 16 MB size limit.", 413)


@app.errorhandler(HTTPException)
def handle_http_error(error: HTTPException):
	if request.path.startswith("/api/"):
		return _api_error(error.description, error.code or 500)
	return error


@app.errorhandler(Exception)
def handle_unexpected_error(error: Exception):
	if isinstance(error, HTTPException):
		return handle_http_error(error)
	app.logger.exception("Unhandled application error")
	if request.path.startswith("/api/"):
		return _api_error("An unexpected server error occurred.", 500)
	return "An unexpected server error occurred.", 500


if __name__ == "__main__":
	app.run(host="127.0.0.1", port=5000, debug=False)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)