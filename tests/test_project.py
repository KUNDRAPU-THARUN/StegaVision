from __future__ import annotations

import math
import struct
import tempfile
import unittest
from base64 import b64decode
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from app import MAX_UPLOAD_BYTES, OUTPUT_DIR, UPLOAD_DIR, app
from backend import dct_steganography, image_analysis, image_metrics, lsb_steganography, steganalysis


class StegaVisionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.temp_path = Path(self.temporary_directory.name)
        self.client = app.test_client()
        self.previous_testing = app.config.get("TESTING", False)
        app.config["TESTING"] = True
        self.addCleanup(self._restore_testing)

    def _restore_testing(self) -> None:
        app.config["TESTING"] = self.previous_testing

    def save_image(self, pixels: np.ndarray, name: str, image_format: str = "PNG") -> Path:
        path = self.temp_path / name
        Image.fromarray(pixels).save(path, format=image_format)
        return path

    @staticmethod
    def upload_data(path: Path, field_name: str = "image", filename: str | None = None):
        return {field_name: (BytesIO(path.read_bytes()), filename or path.name)}

    @staticmethod
    def image_bytes(pixels: np.ndarray, image_format: str = "PNG") -> bytes:
        buffer = BytesIO()
        Image.fromarray(pixels).save(buffer, format=image_format)
        return buffer.getvalue()

    def track_output(self, filename: str) -> Path:
        path = OUTPUT_DIR / filename
        self.addCleanup(path.unlink, missing_ok=True)
        return path


class LSBTests(StegaVisionTestCase):
    def test_capacity_accounts_for_header(self) -> None:
        pixels = np.zeros((32, 32, 3), dtype=np.uint8)
        capacity = lsb_steganography.calculate_capacity(pixels)
        self.assertEqual(capacity["total_bits"], 32 * 32 * 3)
        self.assertEqual(capacity["header_bits"], len(lsb_steganography.MAGIC + struct.pack(">I", 0)) * 8)
        self.assertEqual(capacity["max_message_bytes"], (capacity["total_bits"] - capacity["header_bits"]) // 8)

    def test_round_trip_short_long_and_unicode_messages_and_only_lsb_changes(self) -> None:
        pixels = np.random.default_rng(41).integers(0, 256, (256, 256, 3), dtype=np.uint8)
        source = self.save_image(pixels, "source.png")
        messages = (
            "Hello StegaVision",
            "Digital Image Processing",
            "A longer educational payload: " + "LSB demonstration; " * 40,
            "StegaVision – नमस्ते",
        )
        for index, message in enumerate(messages):
            with self.subTest(message=message[:28]):
                output = self.temp_path / f"lsb-{index}.png"
                lsb_steganography.encode_lsb(source, output, message)
                self.assertEqual(lsb_steganography.decode_lsb(output), message)
                encoded = np.asarray(Image.open(output).convert("RGB"))
                self.assertTrue(np.any(encoded != pixels))
                self.assertTrue(np.all(((encoded ^ pixels) & 0xFE) == 0))

    def test_capacity_overflow_and_invalid_stego_are_friendly(self) -> None:
        small = self.save_image(np.zeros((16, 16, 3), dtype=np.uint8), "small.png")
        with self.assertRaisesRegex(ValueError, "capacity"):
            lsb_steganography.encode_lsb(small, self.temp_path / "too-large.png", "x" * 90)
        with self.assertRaisesRegex(ValueError, "LSB"):
            lsb_steganography.decode_lsb(small)

    def test_api_round_trip_capacity_download_and_upload_cleanup(self) -> None:
        pixels = np.random.default_rng(8).integers(0, 256, (128, 128, 3), dtype=np.uint8)
        source = self.save_image(pixels, "cover.png")
        uploads_before = set(UPLOAD_DIR.iterdir())
        capacity = self.client.post("/api/lsb/capacity", data=self.upload_data(source), content_type="multipart/form-data")
        self.assertEqual(capacity.status_code, 200)
        self.assertEqual(capacity.get_json()["width"], 128)
        self.assertEqual(set(UPLOAD_DIR.iterdir()), uploads_before)

        message = "Hello StegaVision"
        response = self.client.post(
            "/api/lsb/encode",
            data={**self.upload_data(source), "message": message},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.track_output(payload["output_filename"])
        self.assertEqual(set(payload["metrics"]), {"mse", "psnr", "ssim"})
        downloaded = self.client.get(payload["download_url"])
        downloaded_data = downloaded.data
        self.assertEqual(downloaded.status_code, 200)
        self.assertTrue(downloaded_data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn("attachment", downloaded.headers["Content-Disposition"])
        decoded = self.client.post(
            "/api/lsb/decode",
            data={"image": (BytesIO(downloaded_data), "encoded.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(decoded.status_code, 200)
        self.assertEqual(decoded.get_json()["message"], message)
        downloaded.close()
        self.assertEqual(set(UPLOAD_DIR.iterdir()), uploads_before)

    def test_empty_message_and_capacity_errors(self) -> None:
        pixels = np.zeros((128, 128, 3), dtype=np.uint8)
        source = self.save_image(pixels, "cover.png")
        empty = self.client.post(
            "/api/lsb/encode",
            data={**self.upload_data(source), "message": ""},
            content_type="multipart/form-data",
        )
        self.assertEqual(empty.status_code, 400)
        self.assertIn("message", empty.get_json()["error"].lower())
        overflow = self.client.post(
            "/api/lsb/encode",
            data={**self.upload_data(source), "message": "x" * 7000},
            content_type="multipart/form-data",
        )
        self.assertEqual(overflow.status_code, 400)
        self.assertIn("capacity", overflow.get_json()["error"].lower())


class DCTTests(StegaVisionTestCase):
    def test_rgb_short_long_and_unicode_round_trips(self) -> None:
        pixels = np.random.default_rng(12).integers(0, 256, (512, 512, 3), dtype=np.uint8)
        source = self.save_image(pixels, "large.png")
        messages = (
            "Digital Image Processing",
            "StegaVision – नमस्ते",
            "DCT educational payload: " + "frequency coefficients; " * 10,
        )
        for index, message in enumerate(messages):
            with self.subTest(message=message[:25]):
                output = self.temp_path / f"dct-{index}.png"
                dct_steganography.encode_dct(source, output, message)
                self.assertEqual(dct_steganography.decode_dct(output), message)
                encoded = np.asarray(Image.open(output).convert("RGB"))
                self.assertTrue(np.all((encoded >= 0) & (encoded <= 255)))

    def test_capacity_small_image_and_non_multiple_of_eight_padding(self) -> None:
        small = self.save_image(np.zeros((32, 32, 3), dtype=np.uint8), "small.png")
        self.assertEqual(dct_steganography.calculate_dct_capacity(small)["max_message_bytes"], 0)
        with self.assertRaisesRegex(ValueError, "capacity"):
            dct_steganography.encode_dct(small, self.temp_path / "small-stego.png", "x")

        odd_gray = self.save_image(np.random.default_rng(15).integers(0, 256, (105, 107), dtype=np.uint8), "odd.png")
        padded = self.temp_path / "padded.png"
        dct_steganography.encode_dct(odd_gray, padded, "abc")
        with Image.open(padded) as image:
            self.assertEqual(image.size, (112, 112))
        self.assertEqual(dct_steganography.decode_dct(padded), "abc")
        self.assertEqual(dct_steganography.get_dct_original_dimensions(padded), (107, 105))

    def test_supported_formats_round_trip_with_both_methods(self) -> None:
        pixels = np.random.default_rng(23).integers(0, 256, (144, 144, 3), dtype=np.uint8)
        formats = (("png", "PNG"), ("jpg", "JPEG"), ("jpeg", "JPEG"), ("bmp", "BMP"), ("webp", "WEBP"))
        for extension, image_format in formats:
            with self.subTest(format=image_format, extension=extension):
                source = self.temp_path / f"source.{extension}"
                Image.fromarray(pixels).save(source, format=image_format)
                lsb_output = self.temp_path / f"lsb-{extension}.png"
                dct_output = self.temp_path / f"dct-{extension}.png"
                lsb_steganography.encode_lsb(source, lsb_output, "fmt")
                dct_steganography.encode_dct(source, dct_output, "fmt")
                self.assertEqual(lsb_steganography.decode_lsb(lsb_output), "fmt")
                self.assertEqual(dct_steganography.decode_dct(dct_output), "fmt")

    def test_random_images_are_rejected_by_both_decoders(self) -> None:
        random_image = self.save_image(
            np.random.default_rng(37).integers(0, 256, (256, 256, 3), dtype=np.uint8),
            "random.png",
        )
        with self.assertRaisesRegex(ValueError, "LSB"):
            lsb_steganography.decode_lsb(random_image)
        with self.assertRaisesRegex(ValueError, "DCT"):
            dct_steganography.decode_dct(random_image)

    def test_api_capacity_encode_preview_download_decode_and_safe_metrics_crop(self) -> None:
        pixels = np.random.default_rng(18).integers(0, 256, (105, 107, 3), dtype=np.uint8)
        source = self.save_image(pixels, "odd.png")
        capacity = self.client.post("/api/dct/capacity", data=self.upload_data(source), content_type="multipart/form-data")
        self.assertEqual(capacity.status_code, 200)
        self.assertEqual(capacity.get_json()["capacity"]["block_count"], 14 * 14)
        message = "DCT"
        response = self.client.post(
            "/api/dct/encode",
            data={**self.upload_data(source), "message": message},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.track_output(payload["output_filename"])
        self.assertEqual(set(payload["metrics"]), {"mse", "psnr", "ssim"})
        preview = self.client.get(payload["preview_url"])
        self.assertEqual(preview.mimetype, "image/png")
        preview.close()
        download = self.client.get(payload["download_url"])
        download_data = download.data
        self.assertTrue(download_data.startswith(b"\x89PNG\r\n\x1a\n"))
        decoded = self.client.post(
            "/api/dct/decode",
            data={"image": (BytesIO(download_data), "dct.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(decoded.get_json()["message"], message)
        comparison = self.client.post(
            "/api/metrics",
            data={
                "original_image": self.upload_data(source)["image"],
                "processed_image": (BytesIO(download_data), "dct.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(comparison.status_code, 200, comparison.get_json())
        download.close()

    def test_unrelated_rounded_dimensions_are_not_cropped(self) -> None:
        source = self.save_image(np.zeros((105, 107, 3), dtype=np.uint8), "source.png")
        unrelated = self.save_image(np.ones((112, 112, 3), dtype=np.uint8), "unrelated.png")
        response = self.client.post(
            "/api/metrics",
            data={
                "original_image": self.upload_data(source)["image"],
                "processed_image": self.upload_data(unrelated)["image"],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("same dimensions", response.get_json()["error"].lower())


class ImageAnalysisTests(StegaVisionTestCase):
    def test_metadata_rgb_and_grayscale_histograms_and_lsb_plane(self) -> None:
        rgb = np.zeros((10, 12, 3), dtype=np.uint8)
        rgb[:, :, 0] = np.arange(12, dtype=np.uint8)
        rgb[:, :, 1] = 5
        rgb[:, :, 2] = 1
        source = self.save_image(rgb, "rgb.png")
        info = image_analysis.get_image_info(source)
        self.assertEqual((info["width"], info["height"], info["channels"]), (12, 10, 3))
        self.assertEqual(info["format"], "PNG")
        histograms = image_analysis.calculate_histogram(source)
        self.assertEqual(set(histograms), {"red", "green", "blue"})
        self.assertEqual(histograms["red"][7], 10)
        self.assertEqual(sum(histograms["green"]), 120)
        expected_plane = (rgb & 1) * 255
        np.testing.assert_array_equal(image_analysis.generate_lsb_plane(source), expected_plane)

        gray = self.save_image(np.arange(120, dtype=np.uint8).reshape(10, 12), "gray.png")
        gray_histogram = image_analysis.calculate_histogram(gray)["grayscale"]
        self.assertEqual(len(gray_histogram), 256)
        self.assertEqual(sum(gray_histogram), 120)

    def test_difference_image_is_absolute_pixel_difference(self) -> None:
        first = np.zeros((8, 8, 3), dtype=np.uint8)
        second = np.zeros_like(first)
        second[3, 4] = [4, 12, 255]
        original_path = self.save_image(first, "first.png")
        processed_path = self.save_image(second, "second.png")
        difference_path = self.temp_path / "difference.png"
        image_analysis.create_difference_image(original_path, processed_path, difference_path)
        result = np.asarray(Image.open(difference_path).convert("RGB"))
        np.testing.assert_array_equal(result[3, 4], [4, 12, 255])
        self.assertEqual(int(result.sum()), 271)

    def test_analysis_api_returns_original_name_and_real_histogram_plane(self) -> None:
        pixels = np.random.default_rng(21).integers(0, 256, (32, 40, 3), dtype=np.uint8)
        source = self.save_image(pixels, "cover.png")
        response = self.client.post("/api/analyze", data=self.upload_data(source, filename="original cover.png"), content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["image_info"]["filename"], "original_cover.png")
        for channel in ("red", "green", "blue"):
            self.assertEqual(len(payload["histograms"][channel]), 256)
            self.assertEqual(sum(payload["histograms"][channel]), 32 * 40)
        plane_bytes = b64decode(payload["lsb_plane"]["png_base64"])
        with Image.open(BytesIO(plane_bytes)) as plane:
            actual_plane = np.asarray(plane.convert("RGB"))
        np.testing.assert_array_equal(actual_plane, (pixels & 1) * 255)


class MetricsAndSteganalysisTests(StegaVisionTestCase):
    def test_mse_psnr_ssim_identical_modified_and_grayscale_rgb(self) -> None:
        original = np.zeros((16, 16, 3), dtype=np.uint8)
        modified = original.copy()
        modified[4, 5, 0] = 1
        self.assertEqual(image_metrics.calculate_mse(original, original), 0)
        self.assertTrue(math.isinf(image_metrics.calculate_psnr(original, original)))
        self.assertAlmostEqual(image_metrics.calculate_ssim(original, original), 1.0)
        self.assertGreater(image_metrics.calculate_mse(original, modified), 0)
        self.assertGreater(image_metrics.calculate_psnr(original, modified), 0)
        self.assertLessEqual(image_metrics.calculate_ssim(original, modified), 1.0)
        gray = np.zeros((16, 16), dtype=np.uint8)
        color = np.repeat(gray[:, :, None], 3, axis=2)
        self.assertEqual(image_metrics.calculate_mse(gray, color), 0)

    def test_steganalysis_uses_actual_pixels(self) -> None:
        pixels = np.zeros((8, 10, 3), dtype=np.uint8)
        pixels[:, :, 0] = 1
        pixels[:, :, 1] = 2
        pixels[:, :, 2] = 3
        source = self.save_image(pixels, "stats.png")
        expected_ones = int(np.count_nonzero(pixels & 1))
        result = steganalysis.basic_steganalysis(source)
        distribution = result["lsb_distribution"]
        self.assertEqual(distribution["total_analyzed_bits"], pixels.size)
        self.assertEqual(distribution["lsb_1_count"], expected_ones)
        self.assertEqual(distribution["lsb_0_count"] + expected_ones, pixels.size)
        self.assertAlmostEqual(distribution["lsb_0_percentage"] + distribution["lsb_1_percentage"], 100)
        self.assertAlmostEqual(result["pixel_statistics"]["red"]["mean"], 1)
        self.assertEqual(result["pixel_statistics"]["blue"]["maximum"], 3)
        self.assertTrue(result["warnings"])

    def test_metrics_api_identical_mismatch_and_upload_cleanup(self) -> None:
        pixels = np.zeros((32, 32, 3), dtype=np.uint8)
        source = self.save_image(pixels, "source.png")
        uploads_before = set(UPLOAD_DIR.iterdir())
        identical = self.client.post(
            "/api/metrics",
            data={"original_image": self.upload_data(source)["image"], "processed_image": self.upload_data(source, filename="same.png")["image"]},
            content_type="multipart/form-data",
        )
        self.assertEqual(identical.status_code, 200)
        self.assertEqual(identical.get_json()["mse"], 0)
        self.assertEqual(identical.get_json()["psnr"], "Infinity")
        self.assertEqual(set(UPLOAD_DIR.iterdir()), uploads_before)

        smaller = self.save_image(np.zeros((16, 16, 3), dtype=np.uint8), "smaller.png")
        mismatch = self.client.post(
            "/api/metrics",
            data={"original_image": self.upload_data(source)["image"], "processed_image": self.upload_data(smaller)["image"]},
            content_type="multipart/form-data",
        )
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(set(UPLOAD_DIR.iterdir()), uploads_before)


class FlaskApplicationTests(StegaVisionTestCase):
    def test_pages_static_assets_and_supported_image_formats(self) -> None:
        for route in ("/", "/lsb", "/dct", "/analysis", "/steganalysis", "/about"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)
        for asset in ("main.js", "lsb.js", "dct.js", "analysis.js", "steganalysis.js"):
            with self.subTest(asset=asset):
                response = self.client.get(f"/static/js/{asset}")
                self.assertEqual(response.status_code, 200)
                self.assertGreater(len(response.data), 0)
                response.close()
        css = self.client.get("/static/css/style.css")
        self.assertEqual(css.status_code, 200)
        css.close()

        pixels = np.random.default_rng(24).integers(0, 256, (24, 24, 3), dtype=np.uint8)
        for extension, image_format in (("png", "PNG"), ("jpg", "JPEG"), ("bmp", "BMP"), ("webp", "WEBP")):
            with self.subTest(format=image_format):
                response = self.client.post(
                    "/api/analyze",
                    data={"image": (BytesIO(self.image_bytes(pixels, image_format)), f"image.{extension}")},
                    content_type="multipart/form-data",
                )
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertEqual(response.get_json()["image_info"]["width"], 24)

    def test_api_validation_upload_limit_and_download_path_protection(self) -> None:
        missing = self.client.post("/api/lsb/decode", data={}, content_type="multipart/form-data")
        self.assertEqual(missing.status_code, 400)
        unsupported = self.client.post(
            "/api/analyze",
            data={"image": (BytesIO(b"file"), "document.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(unsupported.status_code, 400)
        corrupted = self.client.post(
            "/api/analyze",
            data={"image": (BytesIO(b"not a real png"), "broken.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(corrupted.status_code, 400)
        oversized = self.client.post(
            "/api/analyze",
            data={"image": (BytesIO(b"0" * (MAX_UPLOAD_BYTES + 1)), "large.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(oversized.status_code, 413)
        self.assertEqual(self.client.get("/api/download/..%2Fapp.py").status_code, 404)
        self.assertEqual(self.client.get("/api/preview/..%2Fapp.py").status_code, 404)


if __name__ == "__main__":
    unittest.main()
