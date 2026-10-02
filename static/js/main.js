"use strict";

(() => {
	const MAX_FILE_BYTES = 16 * 1024 * 1024 - 64 * 1024;
	const ALLOWED_EXTENSIONS = new Set(["png", "jpg", "jpeg", "bmp", "webp"]);
	const ALLOWED_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/bmp", "image/webp"]);
	const previewUrls = new WeakMap();
	const activePreviewUrls = new Set();

	function byId(id) {
		return document.getElementById(id);
	}

	function resolveElement(target) {
		if (typeof target === "string") {
			return byId(target);
		}
		return target instanceof Element ? target : null;
	}

	function setNotice(target, message, variant) {
		const element = resolveElement(target);
		if (!element) {
			return;
		}
		element.textContent = message == null ? "" : String(message);
		element.classList.remove("form-message--error", "form-message--success", "warning-message", "info-message");
		if (message) {
			const className = {
				error: "form-message--error",
				success: "form-message--success",
				warning: "warning-message",
				info: "info-message",
			}[variant];
			if (className) {
				element.classList.add(className);
			}
		}
	}

	function showSuccess(target, message) {
		setNotice(target, message, "success");
	}

	function showError(target, message) {
		setNotice(target, message, "error");
	}

	function showWarning(target, message) {
		setNotice(target, message, "warning");
	}

	function showInfo(target, message) {
		setNotice(target, message, "info");
	}

	function clearNotice(target) {
		setNotice(target, "", "info");
	}

	function formatBytes(bytes) {
		if (!Number.isFinite(bytes) || bytes < 0) {
			return "";
		}
		if (bytes < 1024) {
			return `${bytes} B`;
		}
		const units = ["KB", "MB", "GB"];
		let value = bytes / 1024;
		let unitIndex = 0;
		while (value >= 1024 && unitIndex < units.length - 1) {
			value /= 1024;
			unitIndex += 1;
		}
		return `${value.toFixed(value >= 10 ? 1 : 2)} ${units[unitIndex]}`;
	}

	function validateImageFile(file) {
		if (!file) {
			throw new Error("Choose an image file to continue.");
		}
		if (file.size <= 0) {
			throw new Error("The selected file is empty.");
		}
		if (file.size > MAX_FILE_BYTES) {
			throw new Error("Image must be smaller than 16 MB to fit the server upload limit.");
		}
		const extension = file.name.split(".").pop()?.toLowerCase() || "";
		if (!ALLOWED_EXTENSIONS.has(extension)) {
			throw new Error("Unsupported image format. Choose PNG, JPG, JPEG, BMP, or WEBP.");
		}
		const mimeType = (file.type || "").toLowerCase();
		if (mimeType.startsWith("image/") && !ALLOWED_MIME_TYPES.has(mimeType)) {
			throw new Error("Unsupported image type. Choose PNG, JPG, JPEG, BMP, or WEBP.");
		}
		return file;
	}

	function releasePreview(input, preview) {
		const objectUrl = previewUrls.get(input);
		if (objectUrl) {
			URL.revokeObjectURL(objectUrl);
			activePreviewUrls.delete(objectUrl);
			previewUrls.delete(input);
		}
		if (preview) {
			preview.removeAttribute("src");
			preview.hidden = true;
		}
	}

	function updateFileInput(input, file) {
		const field = input.closest(".form-field");
		const zone = input.closest("[data-dropzone]");
		const filename = zone?.querySelector(".selected-filename");
		const preview = field?.querySelector(".image-preview");
		const error = field?.querySelector(".form-message");
		clearNotice(error);
		input.removeAttribute("aria-invalid");
		zone?.classList.remove("is-invalid", "has-error");
		releasePreview(input, preview);

		if (!file) {
			if (filename) {
				filename.textContent = "No file selected";
			}
			zone?.classList.remove("is-selected", "has-file");
			return;
		}

		try {
			validateImageFile(file);
		} catch (validationError) {
			if (filename) {
				filename.textContent = "No file selected";
			}
			if (zone) {
				zone.classList.remove("is-selected", "has-file");
				zone.classList.add("is-invalid");
			}
			input.setAttribute("aria-invalid", "true");
			showError(error, validationError.message);
			input.value = "";
			return;
		}

		zone?.classList.add("is-selected");
		zone?.classList.add("has-file");
		if (filename) {
			filename.textContent = `${file.name} · ${formatBytes(file.size)}`;
		}
		if (!preview) {
			return;
		}

		const objectUrl = URL.createObjectURL(file);
		previewUrls.set(input, objectUrl);
		activePreviewUrls.add(objectUrl);
		preview.alt = `Preview of ${file.name}`;
		preview.onload = () => {
			if (input.files?.[0] !== file || previewUrls.get(input) !== objectUrl) {
				return;
			}
			preview.hidden = false;
			if (filename) {
				filename.textContent = `${file.name} · ${preview.naturalWidth} × ${preview.naturalHeight}px · ${formatBytes(file.size)}`;
			}
		};
		preview.onerror = () => {
			if (previewUrls.get(input) === objectUrl) {
				showError(error, "The selected file could not be displayed as an image.");
				preview.hidden = true;
			}
		};
		preview.src = objectUrl;
	}

	function installDropZone(input) {
		const zone = input.closest("[data-dropzone]");
		if (!zone || zone.dataset.dropzoneReady === "true") {
			return;
		}
		zone.dataset.dropzoneReady = "true";
		zone.tabIndex = 0;
		zone.setAttribute("role", "group");
		const label = input.getAttribute("aria-labelledby");
		const labelText = label ? byId(label)?.textContent : "Image upload";
		zone.setAttribute("aria-label", `${labelText || "Image"} upload area. Press Enter or Space to browse files.`);

		input.addEventListener("change", () => updateFileInput(input, input.files?.[0] || null));
		zone.addEventListener("keydown", (event) => {
			if (event.target === zone && (event.key === "Enter" || event.key === " ")) {
				event.preventDefault();
				input.click();
			}
		});
		zone.addEventListener("click", (event) => {
			if (event.target === zone || (!event.target.closest("label, input, button, a") && event.target !== input)) {
				input.click();
			}
		});

		let dragDepth = 0;
		zone.addEventListener("dragenter", (event) => {
			event.preventDefault();
			dragDepth += 1;
			zone.classList.add("is-drag-over");
		});
		zone.addEventListener("dragover", (event) => {
			event.preventDefault();
			if (event.dataTransfer) {
				event.dataTransfer.dropEffect = "copy";
			}
			zone.classList.add("is-drag-over");
		});
		zone.addEventListener("dragleave", (event) => {
			event.preventDefault();
			dragDepth = Math.max(0, dragDepth - 1);
			if (dragDepth === 0) {
				zone.classList.remove("is-drag-over");
			}
		});
		zone.addEventListener("drop", (event) => {
			event.preventDefault();
			dragDepth = 0;
			zone.classList.remove("is-drag-over");
			const file = event.dataTransfer?.files?.[0];
			if (!file) {
				return;
			}
			try {
				validateImageFile(file);
				const transfer = new DataTransfer();
				transfer.items.add(file);
				input.files = transfer.files;
				input.dispatchEvent(new Event("change", { bubbles: true }));
			} catch (error) {
				const field = input.closest(".form-field");
				const message = field?.querySelector(".form-message");
				const filename = zone.querySelector(".selected-filename");
				releasePreview(input, field?.querySelector(".image-preview"));
				input.value = "";
				input.setAttribute("aria-invalid", "true");
				if (filename) {
					filename.textContent = "No file selected";
				}
				zone.classList.remove("is-selected", "has-file");
				zone.classList.add("is-invalid");
				showError(message, error.message || "This browser could not accept the dropped file. Use Browse image instead.");
			}
		});
	}

	function initializeUploaders() {
		document.querySelectorAll('input[type="file"]').forEach(installDropZone);
	}

	async function uploadForm(endpoint, formData) {
		if (!endpoint) {
			throw new Error("This operation is not connected to a Flask API endpoint.");
		}
		let response;
		try {
			response = await fetch(endpoint, {
				method: "POST",
				headers: { Accept: "application/json" },
				body: formData,
			});
		} catch (error) {
			if (error instanceof TypeError) {
				throw new Error("Could not reach the server. Check that the StegaVision app is running and try again.");
			}
			throw error;
		}

		let payload;
		try {
			payload = await response.json();
		} catch {
			throw new Error(response.ok
				? "The server returned an unreadable response. Please try again."
				: `The server request failed with HTTP ${response.status}. Please try again.`);
		}
		if (!response.ok || payload?.success === false) {
			throw new Error(payload?.error || `The server request failed with HTTP ${response.status}.`);
		}
		if (!payload || typeof payload !== "object") {
			throw new Error("The server returned an invalid response.");
		}
		return payload;
	}

	function showLoading(button, message) {
		const element = resolveElement(button);
		if (!element || element.disabled) {
			return false;
		}
		element.disabled = true;
		element.classList.add("is-loading");
		const indicator = element.querySelector(".loading-indicator") || element.parentElement?.querySelector(".loading-indicator");
		if (indicator) {
			indicator.textContent = message;
			indicator.hidden = false;
			if (!element.contains(indicator)) {
				indicator.parentElement?.classList.add("is-loading");
			}
		}
		return true;
	}

	function hideLoading(button) {
		const element = resolveElement(button);
		if (!element) {
			return;
		}
		element.disabled = false;
		element.classList.remove("is-loading");
		const indicator = element.querySelector(".loading-indicator") || element.parentElement?.querySelector(".loading-indicator");
		if (indicator) {
			indicator.hidden = true;
			if (!element.contains(indicator)) {
				indicator.parentElement?.classList.remove("is-loading");
			}
		}
	}

	function setOutput(id, value) {
		const output = byId(id);
		if (output) {
			output.textContent = value == null ? "" : String(value);
		}
	}

	function utf8Size(text) {
		return new TextEncoder().encode(text).length;
	}

	function formatMetric(value, places = 6) {
		if (value === "Infinity" || value === Infinity) {
			return "Infinity";
		}
		const number = Number(value);
		return Number.isFinite(number) ? number.toFixed(places) : "Unavailable";
	}

	function displayMetrics(prefix, metrics) {
		if (!metrics || typeof metrics !== "object") {
			return;
		}
		setOutput(`${prefix}Mse`, formatMetric(metrics.mse));
		setOutput(`${prefix}Psnr`, `${formatMetric(metrics.psnr, 3)} dB`);
		setOutput(`${prefix}Ssim`, formatMetric(metrics.ssim, 6));
	}

	function sameOriginUrl(value) {
		const url = new URL(value, window.location.href);
		if (url.origin !== window.location.origin) {
			throw new Error("The server returned an unsafe cross-site URL.");
		}
		return url.href;
	}

	async function downloadActualFile(url, filename) {
		const response = await fetch(url, { headers: { Accept: "image/png" } });
		if (!response.ok) {
			let message = `Download failed with HTTP ${response.status}.`;
			try {
				const payload = await response.json();
				message = payload.error || message;
			} catch {
				// Keep the status-based message when the download response is not JSON.
			}
			throw new Error(message);
		}
		const blob = await response.blob();
		if (!blob.size) {
			throw new Error("The server returned an empty download.");
		}
		const objectUrl = URL.createObjectURL(blob);
		const link = document.createElement("a");
		link.href = objectUrl;
		link.download = filename || "stegavision-output.png";
		link.hidden = true;
		document.body.append(link);
		link.click();
		link.remove();
		window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
	}

	function bindDownloadLink(anchor, errorTarget) {
		if (!anchor || anchor.dataset.downloadReady === "true") {
			return;
		}
		anchor.dataset.downloadReady = "true";
		anchor.addEventListener("click", async (event) => {
			if (anchor.getAttribute("aria-disabled") === "true" || !anchor.href) {
				event.preventDefault();
				return;
			}
			event.preventDefault();
			if (anchor.dataset.pending === "true") {
				return;
			}
			anchor.dataset.pending = "true";
			anchor.setAttribute("aria-busy", "true");
			try {
				await downloadActualFile(sameOriginUrl(anchor.href), anchor.download);
				clearNotice(errorTarget);
			} catch (error) {
				showError(errorTarget, error.message || "The image download failed.");
			} finally {
				delete anchor.dataset.pending;
				anchor.removeAttribute("aria-busy");
			}
		});
	}

	async function copyToClipboard(text) {
		if (typeof text !== "string") {
			throw new Error("There is no message to copy.");
		}
		if (navigator.clipboard?.writeText && window.isSecureContext) {
			await navigator.clipboard.writeText(text);
			return;
		}
		const textarea = document.createElement("textarea");
		textarea.value = text;
		textarea.setAttribute("readonly", "");
		textarea.style.position = "fixed";
		textarea.style.opacity = "0";
		document.body.append(textarea);
		textarea.select();
		const copied = document.execCommand("copy");
		textarea.remove();
		if (!copied) {
			throw new Error("Clipboard access was denied. Select and copy the message manually.");
		}
	}

	function focusResult(element) {
		if (!element) {
			return;
		}
		element.hidden = false;
		const heading = element.querySelector("h3");
		if (heading) {
			heading.tabIndex = -1;
			heading.focus({ preventScroll: true });
		}
		element.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" });
	}

	function initializeStego({ prefix }) {
		const encodeForm = byId(`${prefix}EncodeForm`);
		const decodeForm = byId(`${prefix}DecodeForm`);
		if (!encodeForm || !decodeForm || encodeForm.dataset.jsReady === "true") {
			return;
		}
		encodeForm.dataset.jsReady = "true";
		const encodeImage = byId(`${prefix}EncodeImage`);
		const decodeImage = byId(`${prefix}DecodeImage`);
		const messageInput = byId(`${prefix}Message`);
		const charCount = byId(`${prefix}CharCount`);
		const capacityButton = byId(`${prefix}CalculateCapacityButton`);
		const capacityStatus = byId(`${prefix}CapacityStatus`);
		const encodeButton = byId(`${prefix}EncodeButton`);
		const decodeButton = byId(`${prefix}DecodeButton`);
		const encodeError = byId(`${prefix}EncodeErrorMessage`);
		const decodeError = byId(`${prefix}DecodeErrorMessage`);
		const encodeSuccess = byId(`${prefix}EncodeSuccessMessage`);
		const decodeSuccess = byId(`${prefix}DecodeSuccessMessage`);
		const encodeResult = byId(`${prefix}EncodeResult`);
		const decodeResult = byId(`${prefix}DecodeResult`);
		const downloadButton = byId(`${prefix}DownloadButton`);
		const stegoPreview = byId(`${prefix}StegoPreview`);
		const decodedMessage = byId(`${prefix}DecodedMessage`);
		const copyButton = byId(`${prefix}CopyButton`);
		const copyStatus = byId(`${prefix}CopyStatus`);
		let capacityRecord = null;
		let capacityPromise = null;
		let capacityFile = null;

		encodeForm.noValidate = true;
		decodeForm.noValidate = true;
		bindDownloadLink(downloadButton, encodeError);

		function selectedMessage() {
			return messageInput?.value ?? "";
		}

		function byteLabel(value) {
			return `${value.toLocaleString()} ${value === 1 ? "byte" : "bytes"}`;
		}

		function updateMessageSize() {
			const text = selectedMessage();
			const bytes = utf8Size(text);
			if (charCount) {
				const characters = Array.from(text).length;
				charCount.textContent = `${characters} ${characters === 1 ? "character" : "characters"}`;
			}
			setOutput(`${prefix}MessageSize`, byteLabel(bytes));
			if (capacityRecord) {
				renderCapacity(capacityRecord, bytes);
			}
		}

		function renderCapacity(payload, messageBytes = utf8Size(selectedMessage())) {
			const capacity = payload.capacity || payload;
			const maxBytes = Number(capacity.max_message_bytes);
			if (!Number.isFinite(maxBytes) || maxBytes < 0) {
				throw new Error("The capacity response did not include a valid payload size.");
			}
			if (prefix === "lsb") {
				setOutput("lsbImageDimensions", `${payload.width} × ${payload.height} px`);
			} else {
				setOutput("dctBlockCount", `${capacity.block_count} blocks`);
			}
			setOutput(`${prefix}AvailableCapacity`, byteLabel(maxBytes));
			setOutput(`${prefix}MessageSize`, byteLabel(messageBytes));
			const remaining = maxBytes - messageBytes;
			setOutput(`${prefix}RemainingCapacity`, remaining >= 0
				? byteLabel(remaining)
				: `${byteLabel(Math.abs(remaining))} over capacity`);
			if (remaining >= 0) {
				showSuccess(capacityStatus, `Message fits. ${byteLabel(remaining)} remain after the message.`);
			} else {
				showError(capacityStatus, `Message is ${byteLabel(Math.abs(remaining))} larger than this image's available capacity.`);
			}
		}

		async function calculateCapacity() {
			const file = encodeImage?.files?.[0];
			if (!file) {
				throw new Error("Choose a cover image before calculating capacity.");
			}
			if (capacityRecord && capacityFile === file) {
				renderCapacity(capacityRecord);
				return capacityRecord;
			}
			if (capacityPromise) {
				return capacityPromise;
			}
			const endpoint = encodeForm.dataset.capacityEndpoint;
			const data = new FormData();
			data.append("image", file, file.name);
			capacityPromise = uploadForm(endpoint, data).then((payload) => {
				if (encodeImage.files?.[0] !== file) {
					throw new Error("The selected image changed during the capacity check. Calculate capacity again.");
				}
				capacityFile = file;
				capacityRecord = payload;
				renderCapacity(payload);
				return payload;
			}).finally(() => {
				capacityPromise = null;
			});
			return capacityPromise;
		}

		capacityButton?.addEventListener("click", async () => {
			if (!showLoading(capacityButton, "Calculating capacity...")) {
				return;
			}
			clearNotice(capacityStatus);
			try {
				await calculateCapacity();
			} catch (error) {
				showError(capacityStatus, error.message || "Capacity could not be calculated.");
			} finally {
				hideLoading(capacityButton);
			}
		});

		encodeImage?.addEventListener("change", () => {
			capacityRecord = null;
			capacityFile = null;
			["ImageDimensions", "AvailableCapacity", "RemainingCapacity"].forEach((name) => setOutput(`${prefix}${name}`, ""));
			clearNotice(capacityStatus);
			if (encodeResult) {
				encodeResult.hidden = true;
			}
			updateMessageSize();
		});

		messageInput?.addEventListener("input", updateMessageSize);
		updateMessageSize();

		encodeForm.addEventListener("submit", async (event) => {
			event.preventDefault();
			if (encodeForm.dataset.pending === "true") {
				return;
			}
			encodeForm.dataset.pending = "true";
			clearNotice(encodeError);
			clearNotice(encodeSuccess);
			if (encodeResult) {
				encodeResult.hidden = true;
			}
			const file = encodeImage?.files?.[0];
			const message = selectedMessage();
			try {
				validateImageFile(file);
				if (message.length === 0) {
					throw new Error("Enter a message before encoding.");
				}
				const payload = capacityRecord && capacityFile === file ? capacityRecord : await calculateCapacity();
				const maximum = Number(payload.capacity?.max_message_bytes);
				const messageBytes = utf8Size(message);
				if (messageBytes > maximum) {
					throw new Error(`The message is ${byteLabel(messageBytes - maximum)} over this image's ${byteLabel(maximum)} capacity.`);
				}
				if (!showLoading(encodeButton, "Encoding image...")) {
					return;
				}
				const formData = new FormData(encodeForm);
				const result = await uploadForm(encodeForm.dataset.apiEndpoint, formData);
				if (!result.output_filename || !result.download_url) {
					throw new Error("The server did not return a generated image download URL.");
				}
				setOutput(`${prefix}GeneratedFile`, result.output_filename);
				setOutput(`${prefix}CapacityUsed`, `${byteLabel(messageBytes)} / ${byteLabel(maximum)}`);
				displayMetrics(prefix, result.metrics);
				if (downloadButton) {
					downloadButton.href = sameOriginUrl(result.download_url);
					downloadButton.download = result.output_filename;
					downloadButton.setAttribute("aria-disabled", "false");
					downloadButton.hidden = false;
				}
				if (stegoPreview && result.preview_url) {
					stegoPreview.alt = `Generated ${prefix.toUpperCase()} stego image ${result.output_filename}`;
					stegoPreview.onerror = () => {
						stegoPreview.hidden = true;
						showWarning(encodeError, "The image was encoded, but its preview could not be loaded. The download remains available.");
					};
					stegoPreview.src = sameOriginUrl(result.preview_url);
					stegoPreview.hidden = false;
				}
				if (result.capacity) {
					capacityRecord = { ...result, width: payload.width, height: payload.height };
					capacityFile = file;
					renderCapacity(capacityRecord, messageBytes);
				}
				showSuccess(encodeSuccess, result.message || "Encoding completed successfully.");
				focusResult(encodeResult);
			} catch (error) {
				showError(encodeError, error.message || "The image could not be encoded.");
			} finally {
				delete encodeForm.dataset.pending;
				hideLoading(encodeButton);
			}
		});

		decodeImage?.addEventListener("change", () => {
			if (decodeResult) {
				decodeResult.hidden = true;
			}
			clearNotice(decodeSuccess);
		});

		decodeForm.addEventListener("submit", async (event) => {
			event.preventDefault();
			if (decodeForm.dataset.pending === "true") {
				return;
			}
			decodeForm.dataset.pending = "true";
			clearNotice(decodeError);
			clearNotice(decodeSuccess);
			if (decodeResult) {
				decodeResult.hidden = true;
			}
			try {
				validateImageFile(decodeImage?.files?.[0]);
				if (!showLoading(decodeButton, "Decoding image...")) {
					return;
				}
				const formData = new FormData(decodeForm);
				const result = await uploadForm(decodeForm.dataset.apiEndpoint, formData);
				if (typeof result.message !== "string" || result.message.length === 0) {
					throw new Error("The image did not contain a readable message.");
				}
				if (decodedMessage) {
					decodedMessage.textContent = result.message;
				}
				showSuccess(decodeSuccess, "Message decoded successfully.");
				focusResult(decodeResult);
			} catch (error) {
				showError(decodeError, error.message || "The image could not be decoded.");
			} finally {
				delete decodeForm.dataset.pending;
				hideLoading(decodeButton);
			}
		});

		copyButton?.addEventListener("click", async () => {
			clearNotice(copyStatus);
			try {
				const text = decodedMessage?.textContent ?? "";
				if (!text) {
					throw new Error("There is no decoded message to copy.");
				}
				await copyToClipboard(text);
				showSuccess(copyStatus, "Decoded message copied to the clipboard.");
			} catch (error) {
				showError(copyStatus, error.message || "The message could not be copied.");
			}
		});
	}

	function initialize() {
		initializeUploaders();
	}

	document.addEventListener("DOMContentLoaded", initialize, { once: true });
	window.addEventListener("pagehide", () => {
		activePreviewUrls.forEach((objectUrl) => URL.revokeObjectURL(objectUrl));
		activePreviewUrls.clear();
	});

	window.StegaVision = {
		MAX_FILE_BYTES,
		ALLOWED_EXTENSIONS,
		formatBytes,
		validateImageFile,
		uploadForm,
		showLoading,
		hideLoading,
		showSuccess,
		showError,
		showWarning,
		showInfo,
		clearNotice,
		setOutput,
		utf8Size,
		formatMetric,
		displayMetrics,
		sameOriginUrl,
		bindDownloadLink,
		copyToClipboard,
		focusResult,
		initializeStego,
	};
})();
