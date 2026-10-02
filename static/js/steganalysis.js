"use strict";

(() => {
	const byId = (id) => document.getElementById(id);

	function renderDistribution(distribution) {
		const total = Number(distribution?.total_analyzed_bits);
		const zeros = Number(distribution?.lsb_0_count);
		const ones = Number(distribution?.lsb_1_count);
		const zeroPercent = Number(distribution?.lsb_0_percentage);
		const onePercent = Number(distribution?.lsb_1_percentage);
		if (![total, zeros, ones, zeroPercent, onePercent].every(Number.isFinite) || total <= 0 || zeros + ones !== total) {
			throw new Error("The server returned an invalid LSB distribution.");
		}
		const percent = (value) => `${value.toFixed(2)}%`;
		window.StegaVision.setOutput("totalAnalyzedBits", total.toLocaleString());
		window.StegaVision.setOutput("lsbZeroCount", zeros.toLocaleString());
		window.StegaVision.setOutput("lsbOneCount", ones.toLocaleString());
		window.StegaVision.setOutput("lsbZeroPercentage", percent(zeroPercent));
		window.StegaVision.setOutput("lsbOnePercentage", percent(onePercent));

		const zeroBar = byId("lsbZeroBar");
		const oneBar = byId("lsbOneBar");
		zeroBar.style.width = `${Math.max(0, Math.min(100, zeroPercent))}%`;
		oneBar.style.width = `${Math.max(0, Math.min(100, onePercent))}%`;
		zeroBar.title = `LSB 0: ${zeros.toLocaleString()} (${percent(zeroPercent)})`;
		oneBar.title = `LSB 1: ${ones.toLocaleString()} (${percent(onePercent)})`;
		byId("lsbDistributionChart").setAttribute(
			"aria-label",
			`LSB values across ${total.toLocaleString()} analyzed bits: zero ${zeros.toLocaleString()} (${percent(zeroPercent)}), one ${ones.toLocaleString()} (${percent(onePercent)}).`,
		);
	}

	function renderPixelStatistics(statistics) {
		if (!statistics || typeof statistics !== "object" || Array.isArray(statistics)) {
			throw new Error("The server did not return pixel statistics.");
		}
		const rows = Object.entries(statistics);
		if (!rows.length) {
			throw new Error("The server returned no channel statistics.");
		}
		const body = byId("pixelStatistics");
		body.replaceChildren();
		rows.forEach(([channel, values]) => {
			if (!values || ![values.mean, values.standard_deviation, values.minimum, values.maximum].every((value) => Number.isFinite(Number(value)))) {
				throw new Error(`The server returned invalid statistics for ${channel}.`);
			}
			const row = document.createElement("tr");
			const channelCell = document.createElement("th");
			channelCell.scope = "row";
			channelCell.textContent = channel[0].toUpperCase() + channel.slice(1);
			row.append(channelCell);
			[
				Number(values.mean).toFixed(3),
				Number(values.standard_deviation).toFixed(3),
				String(values.minimum),
				String(values.maximum),
			].forEach((value) => {
				const cell = document.createElement("td");
				cell.textContent = value;
				row.append(cell);
			});
			body.append(row);
		});
	}

	function renderList(list, values, emptyMessage) {
		if (!Array.isArray(values) || values.some((value) => typeof value !== "string")) {
			throw new Error("The server returned malformed educational notes.");
		}
		list.replaceChildren();
		if (values.length === 0) {
			const item = document.createElement("li");
			item.textContent = emptyMessage;
			list.append(item);
			return;
		}
		values.forEach((value) => {
			const item = document.createElement("li");
			item.textContent = value;
			list.append(item);
		});
	}

	function initialize() {
		const form = byId("steganalysisForm");
		if (!form) {
			return;
		}
		form.noValidate = true;
		const input = byId("steganalysisImage");
		const button = byId("steganalysisButton");
		const errorMessage = byId("steganalysisErrorMessage");
		const successMessage = byId("steganalysisSuccessMessage");	
		const results = byId("steganalysisResults");
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
				renderDistribution(payload.lsb_distribution);
				renderPixelStatistics(payload.pixel_statistics);
				renderList(byId("basicObservations"), payload.observations, "No observations were returned.");
				renderList(byId("analysisLimitations"), payload.warnings, "No additional limitations were returned.");
				window.StegaVision.showSuccess(successMessage, "Statistical analysis completed.");
				window.StegaVision.focusResult(results);
			} catch (error) {
				window.StegaVision.showError(errorMessage, error.message || "Steganalysis failed.");
			} finally {
				delete form.dataset.pending;
				window.StegaVision.hideLoading(button);
			}
		});
	}

	document.addEventListener("DOMContentLoaded", initialize, { once: true });
})();
