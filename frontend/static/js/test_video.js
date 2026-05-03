// Initialize immediately since script loads at end of page (after DOM is ready)
function initTestVideoForm() {
    const feedback = document.getElementById("test-job-feedback");
    const statusPanel = document.getElementById("job-status-panel");
    const viewerPanel = document.getElementById("viewer-panel");
    const activeCameraName = document.getElementById("active-camera-name");
    const streamOutput = document.getElementById("stream-output");
    const streamOutputNote = document.getElementById("stream-output-note");
    const resultSummary = document.getElementById("result-summary");
    const stopButton = document.getElementById("stop-test-job");
    const previewGrid = document.getElementById("camera-preview-grid");
    const refreshGridBtn = document.getElementById("cameras-refresh-grid");

    let currentJobId = null;
    let pollingHandle = null;
    let allCameras = [];
    let refreshTimer = null;

    // ── JOB MANAGEMENT ──────────────────────────────────────
    function stopPolling() {
        if (pollingHandle) {
            clearInterval(pollingHandle);
            pollingHandle = null;
        }
    }

    function clearStream() {
        if (streamOutput) {
            streamOutput.removeAttribute("src");
            delete streamOutput.dataset.jobId;
        }
    }

    function startStream(jobId, streamUrl) {
        if (!streamOutput || !streamUrl) return;
        streamOutput.dataset.jobId = jobId;
        streamOutput.src = streamUrl;
    }

    function renderStatus(job) {
        const statusMap = {
            "uploading": "Đang Tải Lên",
            "queued": "Đang Xếp Hàng",
            "running": "Đang Giám Sát",
            "completed": "Hoàn Thành",
            "failed": "Thất Bại",
            "aborted": "Đã Hủy"
        };
        const statusText = statusMap[job.status] || job.status || "Không rõ";
        const badgeClass = job.status === "running" ? "teal" : (job.status === "completed" ? "teal" : "gray");

        statusPanel.innerHTML = `
            <article class="status-card" style="padding: 16px; background: var(--surface); border-radius: 12px; border: 1px solid var(--border);">
                <span class="pill ${badgeClass}" style="margin-bottom: 8px;">${statusText}</span>
                <h4 style="margin: 0; font-size: 1rem;">${job.message || "Đang xử lý..."}</h4>
                ${job.error ? `<p class="muted small" style="color: var(--danger); margin-top: 4px;">${job.error}</p>` : ""}
            </article>
        `;
    }

    function renderSummary(summary) {
        resultSummary.innerHTML = `
            <div style="display: grid; grid-template-columns: 1fr; gap: 8px;">
                <article class="summary-card" style="display: flex; justify-content: space-between; padding: 12px; background: var(--bg-main); border-radius: 8px;">
                    <span class="small">Lượt xe qua</span>
                    <strong>${summary.unique_passed_count ?? "-"}</strong>
                </article>
                <article class="summary-card" style="display: flex; justify-content: space-between; padding: 12px; background: var(--bg-main); border-radius: 8px;">
                    <span class="small">Vi phạm đỗ xe</span>
                    <strong>${summary.parking_violation_count ?? "-"}</strong>
                </article>
                <article class="summary-card" style="display: flex; justify-content: space-between; padding: 12px; background: var(--bg-main); border-radius: 8px;">
                    <span class="small">Frames xử lý</span>
                    <strong>${summary.processed_frames ?? "-"}</strong>
                </article>
            </div>
        `;
    }

    async function pollJob(jobId) {
        try {
            const data = await window.portalApi.get(`/api/test-jobs/${jobId}`);
            const job = data.job;
            
            if (job.stream_url && streamOutput.dataset.jobId !== job.id) {
                startStream(job.id, job.stream_url);
            }

            renderStatus(job);

            if (job.status !== "queued" && job.status !== "running") {
                stopPolling();
                if (job.status === "completed") {
                    renderSummary(job.summary || {});
                    streamOutputNote.textContent = "Giám sát hoàn tất.";
                } else {
                    streamOutputNote.textContent = job.error || "Giám sát bị dừng.";
                }
            }
        } catch (error) {
            stopPolling();
        }
    }

    async function startMonitoring(camera) {
        window.portalApi.showNotice(feedback, `Đang khởi tạo giám sát cho: ${camera.name}...`, "info");
        stopPolling();
        clearStream();

        viewerPanel.hidden = false;
        viewerPanel.scrollIntoView({ behavior: "smooth" });
        activeCameraName.textContent = `Camera: ${camera.name}`;
        streamOutputNote.textContent = "Đang kết nối tới luồng camera...";
        resultSummary.innerHTML = "";
        
        // Prepare payload (match the expected Form-style data or JSON depending on backend)
        const payload = {
            camera_id: camera.id,
            roi_points: camera.roi_points ? JSON.stringify(camera.roi_points) : "",
            no_parking_points: camera.no_parking_points ? JSON.stringify(camera.no_parking_points) : "",
            enable_congestion: camera.enable_congestion ? "on" : "off",
            enable_illegal_parking: camera.enable_illegal_parking ? "on" : "off",
            enable_license_plate: camera.enable_license_plate ? "on" : "off",
            model_path: camera.model_path || ""
        };

        try {
            // submitForm uses FormData, so we convert payload
            const fd = new FormData();
            for (const key in payload) fd.append(key, payload[key]);

            const data = await window.portalApi.submitForm("/api/test-jobs", fd);
            const job = data.job;
            currentJobId = job.id;
            
            pollingHandle = setInterval(() => pollJob(job.id), 3000);
            pollJob(job.id);
        } catch (error) {
            window.portalApi.showNotice(feedback, error.message, "error");
        }
    }

    if (stopButton) {
        stopButton.addEventListener("click", async () => {
            if (!currentJobId) return;
            stopButton.disabled = true;
            try {
                await window.portalApi.post(`/api/test-jobs/${currentJobId}/stop`);
                stopPolling();
                streamOutputNote.textContent = "Đã dừng giám sát.";
            } catch (error) {
                console.error("Lỗi dừng job:", error);
            } finally {
                stopButton.disabled = false;
            }
        });
    }

    // ── CAMERA DASHBOARD GRID ──────────────────────────────
    function renderPreviewGrid() {
        if (!previewGrid) return;
        if (!allCameras.length) {
            previewGrid.innerHTML = `<div class="empty-state">Chưa có camera nào để hiển thị.</div>`;
            return;
        }

        previewGrid.innerHTML = allCameras.map((camera) => {
            const congestionPill = `<span class="pill ${camera.enable_congestion ? "teal" : "gray"}">Tắc nghẽn</span>`;
            const parkingPill = `<span class="pill ${camera.enable_illegal_parking ? "orange" : "gray"}">Đỗ sai</span>`;
            const licensePill = `<span class="pill ${camera.enable_license_plate ? "teal" : "gray"}">Biển số</span>`;

            return `
                <article class="camera-preview-card" data-id="${camera.id}">
                    <div class="preview-container">
                        <img src="/api/cameras/${camera.id}/snapshot?ts=${Date.now()}" alt="${camera.name}" class="camera-preview-image" data-camera-id="${camera.id}">
                        <div class="status-overlay">
                            <span class="badge ${camera.is_active ? "success" : "muted"}">${camera.is_active ? "SẴN SÀNG" : "OFFLINE"}</span>
                        </div>
                        <div class="play-hint">▶</div>
                    </div>
                    <div class="camera-body">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <h3>${camera.name}</h3>
                        </div>
                        <p class="muted tiny" style="margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            ${camera.stream_source || "Chưa cấu hình nguồn"}
                        </p>
                        <div class="pill-row">${congestionPill}${parkingPill}${licensePill}</div>
                        
                        <div class="preview-actions">
                            <button class="button secondary xs" data-action="toggle" data-feature="enable_congestion" data-id="${camera.id}">Tắc nghẽn</button>
                            <button class="button secondary xs" data-action="toggle" data-feature="enable_illegal_parking" data-id="${camera.id}">Đỗ sai</button>
                            <button class="button secondary xs" data-action="toggle" data-feature="enable_license_plate" data-id="${camera.id}">Biển số</button>
                            <button class="button secondary xs" data-action="toggle" data-feature="is_active" data-id="${camera.id}">Bật/Tắt</button>
                        </div>
                    </div>
                </article>
            `;
        }).join("");
    }

    async function loadAllCameras() {
        try {
            const data = await window.portalApi.get("/api/cameras");
            allCameras = data.cameras || [];
            renderPreviewGrid();
        } catch (error) {
            console.error("Lỗi tải camera grid:", error);
        }
    }

    async function updateCameraFeature(cameraId, feature, value) {
        const camera = allCameras.find(c => c.id === cameraId);
        if (!camera) return;
        const payload = { ...camera, [feature]: value };
        try {
            await window.portalApi.put(`/api/cameras/${cameraId}`, payload);
            await loadAllCameras();
        } catch (error) {
            window.portalApi.showNotice(feedback, "Lỗi cập nhật camera: " + error.message, "error");
        }
    }

    if (previewGrid) {
        previewGrid.addEventListener("click", async (e) => {
            const toggleBtn = e.target.closest("button[data-action='toggle']");
            if (toggleBtn) {
                e.stopPropagation();
                const id = parseInt(toggleBtn.dataset.id);
                const feature = toggleBtn.dataset.feature;
                const camera = allCameras.find(c => c.id === id);
                if (camera) {
                    await updateCameraFeature(id, feature, !camera[feature]);
                }
                return;
            }

            const card = e.target.closest(".camera-preview-card");
            if (card) {
                const id = parseInt(card.dataset.id);
                const camera = allCameras.find(c => c.id === id);
                if (camera) {
                    startMonitoring(camera);
                }
            }
        });
    }

    if (refreshGridBtn) {
        refreshGridBtn.addEventListener("click", loadAllCameras);
    }

    function refreshSnapshots() {
        if (!previewGrid) return;
        previewGrid.querySelectorAll("img[data-camera-id]").forEach(img => {
            img.src = `/api/cameras/${img.dataset.cameraId}/snapshot?ts=${Date.now()}`;
        });
    }

    // Fullscreen logic
    const fsContainer = document.getElementById("stream-fullscreen-container");
    const fsEnterBtn = document.getElementById("fullscreen-btn");
    const fsExitBtn = document.getElementById("fullscreen-exit-btn");

    if (fsEnterBtn) {
        fsEnterBtn.addEventListener("click", () => {
            if (fsContainer.requestFullscreen) fsContainer.requestFullscreen();
            else if (fsContainer.webkitRequestFullscreen) fsContainer.webkitRequestFullscreen();
        });
    }
    if (fsExitBtn) {
        fsExitBtn.addEventListener("click", () => {
            if (document.exitFullscreen) document.exitFullscreen();
        });
    }

    // Khởi động
    loadAllCameras();
    refreshTimer = setInterval(refreshSnapshots, 10000); // 10s refresh for snapshots
}

document.addEventListener('DOMContentLoaded', initTestVideoForm);
