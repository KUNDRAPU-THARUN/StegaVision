"use strict";

(() => {
	const byId = (id) => document.getElementById(id);
	const chartObservers = new WeakMap();

	function validateHistogram(values, label) {
		if (!Array.isArray(values) || values.length !== 256 || values.some((value) => !Number.isFinite(Number(value)) || Number(value) < 0)) {
			throw new Error(`The server returned invalid ${label} histogram data.`);
		}
		return values.map(Number);
	}

	function drawHistogram(container, series, description) {
		if (!container || !series.length) {
			throw new Error("Histogram chart container or channel data is missing.");
		}
		chartObservers.get(container)?.disconnect();
		const canvas = document.createElement("canvas");
		canvas.className = "histogram-canvas";
		canvas.setAttribute("role", "img");
		container.replaceChildren(canvas);
		container.setAttribute("aria-label", description);
		const observer = typeof ResizeObserver === "function" ? new ResizeObserver(paint) : null;
		if (observer) {
			chartObservers.set(container, observer);
			observer.observe(container);
		}

		function paint() {
			const cssWidth = Math.max(280, container.clientWidth || 640);
			const cssHeight = Math.max(170, container.clientHeight || 250);
			const scale = Math.max(1, window.devicePixelRatio || 1);
			canvas.width = Math.round(cssWidth * scale);
			canvas.height = Math.round(cssHeight * scale);
			canvas.style.width = "100%";
			canvas.style.height = `${cssHeight}px`;
			const context = canvas.getContext("2d");
			if (!context) {
				throw new Error("This browser could not create a histogram canvas.");
			}
			context.setTransform(scale, 0, 0, scale, 0, 0);
			context.clearRect(0, 0, cssWidth, cssHeight);
			context.fillStyle = "#fbfcfc";
			context.fillRect(0, 0, cssWidth, cssHeight);

			const margin = { left: 58, right: 17, top: series.length > 1 ? 42 : 20, bottom: 35 };
			const plotWidth = Math.max(1, cssWidth - margin.left - margin.right);
			const plotHeight = Math.max(1, cssHeight - margin.top - margin.bottom);
			const maximum = Math.max(1, ...series.flatMap((item) => item.values));
			context.font = '11px "Segoe UI", sans-serif';
			context.textBaseline = "middle";
			context.lineWidth = 1;
			for (let tick = 0; tick <= 4; tick += 1) {
				const fraction = tick / 4;
				const y = margin.top + plotHeight * (1 - fraction);
				const count = Math.round(maximum * fraction);
				context.strokeStyle = "#e3ebe9";
				context.beginPath();
				context.moveTo(margin.left, y);
				context.lineTo(cssWidth - margin.right, y);
				context.stroke();
				context.fillStyle = "#53666b";
				context.textAlign = "right";
				context.fillText(count.toLocaleString(), margin.left - 8, y);
			}

			const intensities = [0, 64, 128, 192, 255];
			context.fillStyle = "#53666b";
			context.textAlign = "center";
			intensities.forEach((intensity) => {
				const x = margin.left + (intensity / 255) * plotWidth;
				context.strokeStyle = "#cbd8d5";
				context.beginPath();
				context.moveTo(x, margin.top + plotHeight);
				context.lineTo(x, margin.top + plotHeight + 4);
				context.stroke();
				context.fillText(String(intensity), x, cssHeight - 18);
			});
			context.save();
			context.translate(13, margin.top + plotHeight / 2);
			context.rotate(-Math.PI / 2);
			context.fillStyle = "#34474b";
			context.textAlign = "center";
			context.fillText("Pixel count", 0, 0);
			context.restore();

			if (series.length > 1) {
				let legendX = margin.left;
				context.textAlign = "left";
				series.forEach((item) => {
					context.fillStyle = item.color;
					context.fillRect(legendX, 16, 14, 3);
					context.fillStyle = "#34474b";
					context.fillText(item.label, legendX + 19, 18);
					legendX += item.label.length > 5 ? 82 : 72;
				});
			}

			series.forEach((item) => {
				context.beginPath();
				context.strokeStyle = item.color;
				context.lineWidth = series.length > 1 ? 1.5 : 1.8;
				item.values.forEach((value, index) => {
					const x = margin.left + (index / 255) * plotWidth;
					const y = margin.top + plotHeight - (value / maximum) * plotHeight;
					if (index === 0) {
						context.moveTo(x, y);
					} else {
						context.lineTo(x, y);
					}
				});
				context.stroke();
			});

			context.fillStyle = "#34474b";
			context.textAlign = "center";
			context.fillText("Intensity (0–255)", margin.left + plotWidth / 2, cssHeight - 4);
		}

		paint();
	}

	function renderImageInfo(info, selectedFile) {
		if (!info || typeof info !== "object") {
			throw new Error("The server did not return image information.");
		}
		const rows = [
			["Filename", selectedFile?.name || info.filename],
			["Format", info.format],
			["Width", `${Number(info.width).toLocaleString()} px`],
			["Height", `${Number(info.height).toLocaleString()} px`],
			["Channels", info.channels],
			["Mode", info.mode],
			["File size", window.StegaVision.formatBytes(Number(info.file_size_bytes))],
			["Total pixels", Number(info.total_pixels).toLocaleString()],
			["Color type", info.color_type],
		];
		const body = byId("imageInfo");
		body.replaceChildren();
		rows.forEach(([label, value]) => {
			const row = document.createElement("tr");
			const heading = document.createElement("th");
			const cell = document.createElement("td");
			heading.scope = "row";
			heading.textContent = String(label);
			cell.textContent = value == null ? "Unavailable" : String(value);
			row.append(heading, cell);
			body.append(row);
		});
		const caption = byId("analysisPreviewCaption");
		if (caption) {
			caption.textContent = `${Number(info.width).toLocaleString()} × ${Number(info.height).toLocaleString()} px · ${info.format || "Image"}`;
		}
	}

	function renderHistograms(histograms) {
		if (!histograms || typeof histograms !== "object") {
			throw new Error("The server did not return histogram data.");
		}
		const rgbSection = byId("rgbHistogram")?.closest(".chart-section");
		const graySection = byId("grayscaleHistogramSection");
		const hasRgb = ["red", "green", "blue"].every((name) => Array.isArray(histograms[name]));
		if (hasRgb) {
			if (rgbSection) {
				rgbSection.hidden = false;
			}
			if (graySection) {
				graySection.hidden = true;
			}
			const colors = { red: "#a94b35", green: "#24796e", blue: "#3e7591" };
			const series = ["red", "green", "blue"].map((name) => ({
				label: name[0].toUpperCase() + name.slice(1),
				color: colors[name],
				values: validateHistogram(histograms[name], name),
			}));
			const pixelCount = series[0].values.reduce((total, count) => total + count, 0);
			const description = `RGB histograms calculated from ${pixelCount.toLocaleString()} image pixels. X-axis is intensity 0 to 255; Y-axis is pixel count.`;
			drawHistogram(byId("rgbHistogram"), series, description);
			[
				["redHistogram", series[0]],
				["greenHistogram", series[1]],
				["blueHistogram", series[2]],
			].forEach(([id, channel]) => {
				drawHistogram(byId(id), [channel], `${channel.label} intensity histogram from ${pixelCount.toLocaleString()} pixels. X-axis is intensity 0 to 255; Y-axis is pixel count.`);
			});
			return;
		}

		if (Array.isArray(histograms.grayscale)) {
			if (rgbSection) {
				rgbSection.hidden = true;
			}
			if (graySection) {
				graySection.hidden = false;
			}
			const values = validateHistogram(histograms.grayscale, "grayscale");
			const pixelCount = values.reduce((total, count) => total + count, 0);
			drawHistogram(byId("grayHistogram"), [{ label: "Grayscale", color: "#46585d", values }], `Grayscale intensity histogram from ${pixelCount.toLocaleString()} pixels. X-axis is intensity 0 to 255; Y-axis is pixel count.`);
			return;
		}
		throw new Error("The server returned no supported RGB or grayscale histogram data.");
	}

	function renderLsbPlane(plane) {
		if (!plane || typeof plane.png_base64 !== "string" || !/^[A-Za-z0-9+/]+={0,2}$/.test(plane.png_base64)) {
			throw new Error("The server did not return a valid LSB-plane image.");
		}
		const image = byId("lsbPlaneImage");
		image.src = `data:image/png;base64,${plane.png_base64}`;
		image.hidden = false;
		image.alt = `LSB plane of ${plane.width} by ${plane.height} pixels`;
		byId("lsbPlaneCaption").textContent = `${Number(plane.width).toLocaleString()} × ${Number(plane.height).toLocaleString()} px · Generated from the uploaded image's pixel LSBs.`;
	}

	function initializeMetrics() {
		const form = byId("metricsForm");
		if (!form) {
			return;
		}
		form.noValidate = true;
		const originalInput = byId("metricsOriginalImage");
		const processedInput = byId("metricsProcessedImage");
		const button = byId("metricsButton");
		const errorMessage = byId("metricsErrorMessage");
		const successMessage = byId("metricsSuccessMessage");
		const results = byId("metricsResult");
		[originalInput, processedInput].forEach((input) => input?.addEventListener("change", () => {
			if (results) {
				results.hidden = true;
			}
			window.StegaVision.clearNotice(errorMessage);
			window.StegaVision.clearNotice(successMessage);
		}));

		form.addEventListener("submit", async (event) => {
			event.preventDefault();
			if (form.dataset.pending === "true") {
				return;
			}
			form.dataset.pending = "true";
			window.StegaVision.clearNotice(errorMessage);
			window.StegaVision.clearNotice(successMessage);
			if (results) {
				results.hidden = true;
			}
			try {
				const original = window.StegaVision.validateImageFile(originalInput?.files?.[0]);
				const processed = window.StegaVision.validateImageFile(processedInput?.files?.[0]);
				if (original.size + processed.size > window.StegaVision.MAX_FILE_BYTES) {
					throw new Error("The two images together exceed the server's 16 MB request limit. Choose smaller files.");
				}
				if (!window.StegaVision.showLoading(button, "Comparing images...")) {
					return;
				}
				const payload = await window.StegaVision.uploadForm(form.dataset.apiEndpoint, new FormData(form));
				["mse", "psnr", "ssim"].forEach((name) => {
					if (payload[name] === undefined || payload[name] === null) {
						throw new Error(`The server did not return ${name.toUpperCase()}.`);
					}
				});
				window.StegaVision.displayMetrics("metrics", payload);
				window.StegaVision.showSuccess(successMessage, "Metrics calculated from the selected images.");
				window.StegaVision.focusResult(results);
			} catch (error) {
				window.StegaVision.showError(errorMessage, error.message || "Image metrics could not be calculated.");
			} finally {
				delete form.dataset.pending;
				window.StegaVision.hideLoading(button);
			}
		});
	}

	function initialize() {
		const form = byId("analysisForm");
		if (form) {
			form.noValidate = true;
			const input = byId("analysisImage");
			const button = byId("analysisButton");
			const errorMessage = byId("analysisErrorMessage");
			const successMessage = byId("analysisSuccessMessage");
			const results = byId("analysisResults");
			input?.addEventListener("change", () => {
				if (results) {
					results.hidden = true;
				}
				window.StegaVision.clearNotice(successMessage);
			});
			form.addEventListener("submit", async (event) => {
				event.preventDefault();
				if (form.dataset.pending === "true") {
					return;
				}
				form.dataset.pending = "true";
				window.StegaVision.clearNotice(errorMessage);
				window.StegaVision.clearNotice(successMessage);
				if (results) {
					results.hidden = true;
				}
				try {
					window.StegaVision.validateImageFile(input?.files?.[0]);
					if (!window.StegaVision.showLoading(button, "Analyzing image...")) {
						return;
					}
					const payload = await window.StegaVision.uploadForm(form.dataset.apiEndpoint, new FormData(form));
					renderImageInfo(payload.image_info, input.files[0]);
					results.hidden = false;
					renderHistograms(payload.histograms);
					renderLsbPlane(payload.lsb_plane);
					window.StegaVision.showSuccess(successMessage, "Image analysis completed from the uploaded image.");
					window.StegaVision.focusResult(results);
				} catch (error) {
					if (results) {
						results.hidden = true;
					}
					window.StegaVision.showError(errorMessage, error.message || "Image analysis failed.");
				} finally {
					delete form.dataset.pending;
					window.StegaVision.hideLoading(button);
				}
			});
		}
		initializeMetrics();
	}

	document.addEventListener("DOMContentLoaded", initialize, { once: true });
})();
