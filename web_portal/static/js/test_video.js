document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("test-video-form");
    const feedback = document.getElementById("test-job-feedback");
    const statusPanel = document.getElementById("job-status-panel");
    const viewerPanel = document.getElementById("viewer-panel");
    const inputVideo = document.getElementById("input-video");
    const inputVideoNote = document.getElementById("input-video-note");
    const livePreview = document.getElementById("live-preview");
    const previewNote = document.getElementById("preview-note");
    const resultVideo = document.getElementById("result-video");
    const resultVideoNote = document.getElementById("result-video-note");
    const resultSummary = document.getElementById("result-summary");
    const submitButton = document.getElementById("submit-test-job");
    const uploadInput = form?.querySelector('input[name="video_file"]');
    const localPathInput = form?.querySelector('input[name="local_path"]');
    const featureCheckboxes = form ? Array.from(form.querySelectorAll('input[type="checkbox"][name^="enable_"]')) : [];

    if (!form || !uploadInput || !localPathInput) {
        return;
    }

    let pollingHandle = null;
    let currentInputObjectUrl = null;

    function stopPolling() {
        if (pollingHandle) {
            clearInterval(pollingHandle);
            pollingHandle = null;
        }
    }

    function revokeInputPreviewUrl() {
        if (!currentInputObjectUrl) {
            return;
        }
        URL.revokeObjectURL(currentInputObjectUrl);
        currentInputObjectUrl = null;
    }

    function clearVideo(video) {
        if (!video) {
            return;
        }
        video.pause();
        video.removeAttribute("src");
        delete video.dataset.src;
        video.load();
    }

    function setVideoSource(video, url) {
        if (!video || !url) {
            return;
        }
        if (video.dataset.src === url) {
            return;
        }
        video.dataset.src = url;
        video.src = url;
        video.load();
    }

    function pickTone(status) {
        if (status === "failed") {
            return "error";
        }
        if (status === "completed") {
            return "success";
        }
        if (status === "queued") {
            return "warning";
        }
        if (status === "running") {
            return "info";
        }
        return "gray";
    }

    function renderStatus(job, tone = "gray") {
        const badgeClass = tone === "error"
            ? "red"
            : tone === "success"
                ? "teal"
                : tone === "warning"
                    ? "orange"
                    : tone === "info"
                        ? "teal"
                        : "gray";

        const progress = job.progress || {};
        const hasProgress = Number.isFinite(progress.processed_frames) || Number.isFinite(progress.progress_percent);
        const percentText = Number.isFinite(progress.progress_percent)
            ? `${progress.progress_percent.toFixed(1)}%`
            : "Đang đợi...";
        const frameText = Number.isFinite(progress.processed_frames)
            ? `${progress.processed_frames}/${progress.source_total_frames || "?"} frame`
            : null;
        const queueText = job.status === "queued" && job.queue_position
            ? `Vị trí trong hàng đợi: ${job.queue_position}`
            : null;
        const latestText = progress.latest_status || null;

        statusPanel.innerHTML = `
            <article class="status-card panel">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                    <span class="pill ${badgeClass}">${job.status?.toUpperCase() || "KHÔNG RÕ"}</span>
                    <span class="muted small">Job ID: ${job.id?.substring(0, 8) || "-"}</span>
                </div>
                <h4 style="font-size: 1.2rem; margin-bottom: 8px;">${job.message || "Đang đợi trạng thái"}</h4>
                
                ${queueText ? `<div class="notice info" style="font-size: 0.9rem;">${queueText}</div>` : ""}
                
                <div class="progress-info" style="margin-top: 16px;">
                    ${hasProgress ? `
                        <p class="muted small" style="margin-bottom: 8px;">Tiến độ xử lý: <strong>${percentText}</strong></p>
                        <div class="progress-bar-bg" style="height: 8px; background: var(--bg-accent); border-radius: 10px; overflow: hidden;">
                            <div class="progress-bar-fill" style="height: 100%; background: var(--primary); width: ${progress.progress_percent || 0}%"></div>
                        </div>
                        <p class="muted tiny" style="margin-top: 8px;">${frameText ? `Đã xử lý: ${frameText}` : ""}</p>
                    ` : ""}
                </div>

                ${latestText ? `<p class="muted small" style="margin-top: 12px; font-style: italic;">🔍 ${latestText}</p>` : ""}
                ${job.error ? `<div class="notice error" style="margin-top: 12px;">${job.error}</div>` : ""}
            </article>
        `;
    }

    function renderSummary(summary) {
        const plates = summary.recognized_plates || [];
        const platesHtml = plates.length > 0
            ? plates.map(p => `<span class="pill teal" style="margin: 3px; font-size: 0.85rem; letter-spacing: 0.5px;">${p}</span>`).join("")
            : `<span class="muted small">Không nhận diện được biển số nào</span>`;

        resultSummary.innerHTML = `
            <article class="summary-card">
                <span>Frames đã xử lý</span>
                <strong>${summary.processed_frames ?? "-"}</strong>
            </article>
            <article class="summary-card">
                <span>Thời lượng video</span>
                <strong>${summary.duration_seconds ?? "-"}s</strong>
            </article>
            <article class="summary-card">
                <span>FPS trung bình</span>
                <strong>${summary.average_processing_fps ?? "-"}</strong>
            </article>
            <article class="summary-card">
                <span>Mật độ cao nhất</span>
                <strong>${summary.max_occupancy_percent ?? "-"}%</strong>
            </article>
            <article class="summary-card">
                <span>Giao thông cao nhất</span>
                <strong>${summary.highest_traffic_level ?? "-"}</strong>
            </article>
            <article class="summary-card">
                <span>Vi phạm đỗ xe</span>
                <strong>${summary.parking_violation_count ?? "-"}</strong>
            </article>
            <article class="summary-card">
                <span>Xe lớn nhất</span>
                <strong>${summary.max_vehicle_count ?? "-"}</strong>
            </article>
            <article class="summary-card">
                <span>Biển số phát hiện</span>
                <strong>${summary.max_license_plate_count ?? "-"}</strong>
            </article>
            <article class="summary-card">
                <span>Biển số đã đọc (OCR)</span>
                <strong>${summary.total_plates_recognized ?? "0"}</strong>
            </article>
            <article class="summary-card summary-card-wide">
                <span>Trạng thái cuối</span>
                <strong>${summary.latest_status || "N/A"}</strong>
            </article>
            <article class="summary-card summary-card-wide" style="text-align: left;">
                <span style="display: block; margin-bottom: 8px;">🔢 Danh sách Biển số nhận diện</span>
                <div style="display: flex; flex-wrap: wrap; gap: 4px;">${platesHtml}</div>
            </article>
        `;
    }

    function renderPendingSummary(message) {
        resultSummary.innerHTML = `
            <article class="summary-card summary-card-wide">
                <span>Tong quan</span>
                <strong>${message}</strong>
            </article>
        `;
    }

    function resetOutputView(message) {
        viewerPanel.hidden = false;
        clearVideo(resultVideo);
        livePreview.removeAttribute("src");
        delete livePreview.dataset.jobId;
        previewNote.textContent = "Preview cu da duoc xoa. Preview moi se hien khi backend bat dau xu ly video moi.";
        resultVideoNote.textContent = "Video ket qua cu da duoc thay the. Ket qua moi se xuat hien sau khi job tiep theo hoan tat.";
        renderPendingSummary(message);
    }

    function showSelectedUpload(file) {
        if (!file) {
            return;
        }
        viewerPanel.hidden = false;
        revokeInputPreviewUrl();
        currentInputObjectUrl = URL.createObjectURL(file);
        setVideoSource(inputVideo, currentInputObjectUrl);
        inputVideoNote.textContent = `Dang xem truoc video moi: ${file.name}. Khi ban chay job, video nay se thay the video cu.`;
    }

    function showPendingLocalSource(pathText) {
        viewerPanel.hidden = false;
        revokeInputPreviewUrl();
        clearVideo(inputVideo);
        inputVideoNote.textContent = `Da nhap video moi: ${pathText}. Trinh duyet khong mo truc tiep duong dan local, nhung sau khi gui job web se thay the bang video nay.`;
    }

    function refreshPreview(job) {
        if (!job.preview_image_url) {
            return;
        }
        livePreview.dataset.jobId = job.id || "";
        livePreview.src = `${job.preview_image_url}?t=${Date.now()}`;

        const progress = job.progress || {};
        if (job.status === "queued") {
            previewNote.textContent = job.queue_position
                ? `Job dang nam trong hang doi, vi tri ${job.queue_position}. Preview se xuat hien khi backend bat dau phan tich.`
                : "Job dang cho den luot xu ly. Preview se xuat hien khi backend bat dau phan tich.";
            return;
        }
        if (job.status === "running") {
            const processedFrames = Number.isFinite(progress.processed_frames) ? progress.processed_frames : "?";
            const totalFrames = Number.isFinite(progress.source_total_frames) ? progress.source_total_frames : "?";
            const percentText = Number.isFinite(progress.progress_percent)
                ? `${progress.progress_percent.toFixed(1)}%`
                : "Dang cap nhat";
            previewNote.textContent = `Preview dang cap nhat tu frame ${processedFrames}/${totalFrames}. Tien do hien tai: ${percentText}.`;
            return;
        }
        if (job.status === "completed") {
            previewNote.textContent = "Preview dang hien frame phan tich cuoi cung. Video ket qua da san sang de xem lai.";
            return;
        }
        if (job.status === "failed") {
            previewNote.textContent = job.error || "Job that bai, khong the tiep tuc tao preview phan tich.";
        }
    }

    function prepareViewer(job) {
        viewerPanel.hidden = false;

        if (job.input_video_url) {
            revokeInputPreviewUrl();
            setVideoSource(inputVideo, job.input_video_url);
            inputVideoNote.textContent = "Video nguon cua job hien tai da thay the video cu tren giao dien.";
        } else {
            clearVideo(inputVideo);
            inputVideoNote.textContent = "Khong tim thay video nguon cho job nay.";
        }

        refreshPreview(job);

        if (job.status !== "completed") {
            clearVideo(resultVideo);
            resultVideoNote.textContent = "Video ket qua se xuat hien sau khi backend xu ly xong.";
        }
    }

    async function pollJob(jobId) {
        try {
            const data = await window.portalApi.get(`/api/test-jobs/${jobId}`);
            const job = data.job;
            prepareViewer(job);
            renderStatus(job, pickTone(job.status));

            if (job.status === "queued" || job.status === "running") {
                return;
            }
            if (job.status === "failed") {
                submitButton.disabled = false;
                resultVideoNote.textContent = job.error || "Xu ly video that bai.";
                stopPolling();
                return;
            }
            if (job.status === "completed") {
                if (job.result_url) {
                    setVideoSource(resultVideo, job.result_url);
                }
                resultVideoNote.textContent = "Video ket qua da san sang. Ban co the phat truc tiep tren web.";
                renderSummary(job.summary || {});
                submitButton.disabled = false;
                stopPolling();
            }
        } catch (error) {
            window.portalApi.showNotice(feedback, error.message, "error");
            submitButton.disabled = false;
            stopPolling();
        }
    }

    uploadInput.addEventListener("change", () => {
        const file = uploadInput.files && uploadInput.files[0] ? uploadInput.files[0] : null;
        stopPolling();
        submitButton.disabled = false;
        if (file) {
            localPathInput.value = "";
            resetOutputView("Da chon video moi. Video ket qua va preview cu da duoc thay the, san sang cho job moi.");
            showSelectedUpload(file);
        } else if (!localPathInput.value.trim()) {
            revokeInputPreviewUrl();
            clearVideo(inputVideo);
            inputVideoNote.textContent = "Hay chon video de bat dau job moi.";
        }
    });

    localPathInput.addEventListener("input", () => {
        const pathText = localPathInput.value.trim();
        stopPolling();
        submitButton.disabled = false;
        if (pathText) {
            uploadInput.value = "";
            resetOutputView("Da nhap duong dan video moi. Video ket qua va preview cu da duoc thay the, san sang cho job moi.");
            showPendingLocalSource(pathText);
        } else if (!(uploadInput.files && uploadInput.files[0])) {
            clearVideo(inputVideo);
            inputVideoNote.textContent = "Hay nhap duong dan local hoac upload video de bat dau job moi.";
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        window.portalApi.showNotice(feedback, "", "info");
        stopPolling();

        const formData = new FormData(form);
        featureCheckboxes.forEach((checkbox) => {
            formData.set(checkbox.name, checkbox.checked ? "true" : "false");
        });
        const hasFile = Boolean(formData.get("video_file") && formData.get("video_file").name);
        const hasLocalPath = Boolean((formData.get("local_path") || "").trim());
        if (!hasFile && !hasLocalPath) {
            window.portalApi.showNotice(feedback, "Hay chon file upload hoac nhap duong dan local.", "error");
            return;
        }

        resetOutputView("Job dang duoc tao cho video moi. Web se thay the toan bo preview va ket qua cu bang job moi nay.");
        if (!hasFile) {
            clearVideo(inputVideo);
            inputVideoNote.textContent = "Dang gui video local moi len backend. Video nguon se hien lai ngay khi job duoc tao.";
        }

        submitButton.disabled = true;
        renderStatus({ status: "queued", message: "Dang gui yeu cau len backend..." }, "warning");

        try {
            const data = await window.portalApi.submitForm("/api/test-jobs", formData);
            const job = data.job;
            prepareViewer(job);
            renderStatus(job, pickTone(job.status));
            renderPendingSummary("Backend dang xu ly video moi. Preview phan tich se duoc lam moi dinh ky ngay tai trang nay.");

            pollingHandle = setInterval(() => pollJob(job.id), 2000);
            pollJob(job.id);
        } catch (error) {
            submitButton.disabled = false;
            window.portalApi.showNotice(feedback, error.message, "error");
            renderStatus({ status: "failed", message: "Khong tao duoc job kiem tra.", error: error.message }, "error");
        }
    });

    window.addEventListener("beforeunload", () => {
        stopPolling();
        revokeInputPreviewUrl();
    });
});
