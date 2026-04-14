// Initialize immediately since script loads at end of page (after DOM is ready)
function initTestVideoForm() {
    const form = document.getElementById("test-video-form");
    const feedback = document.getElementById("test-job-feedback");
    const statusPanel = document.getElementById("job-status-panel");
    const viewerPanel = document.getElementById("viewer-panel");
    const streamOutput = document.getElementById("stream-output");
    const streamOutputNote = document.getElementById("stream-output-note");
    const resultSummary = document.getElementById("result-summary");
    const submitButton = document.getElementById("submit-test-job");
    const uploadInput = form?.querySelector('input[name="video_file"]');
    const featureCheckboxes = form ? Array.from(form.querySelectorAll('input[type="checkbox"][name^="enable_"]')) : [];

    const testRoiFilePicker = document.getElementById("test_roi_file_picker");
    const testRoiPoints = document.getElementById("test_roi_points");
    const testRoiStatus = document.getElementById("test_roi_points_status");

    const testNoParkingFilePicker = document.getElementById("test_no_parking_file_picker");
    const testNoParkingPoints = document.getElementById("test_no_parking_points");
    const testNoParkingStatus = document.getElementById("test_no_parking_points_status");

    const stopButton = document.getElementById("stop-test-job");
    let currentJobId = null;

    if (!form || !uploadInput) {
        console.error("Form hoặc input video không tìm thấy");
        return;
    }

    function handleFileSelect(fileInput, hiddenInput, statusSpan) {
        fileInput.addEventListener("change", (event) => {
            const file = event.target.files[0];
            if (!file) {
                hiddenInput.value = "";
                statusSpan.textContent = "Nếu để trống sẽ dùng cấu hình camera.";
                return;
            }
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    let parsed = JSON.parse(e.target.result);

                    // Support layout JSON format from main.py {"points": [...]}
                    if (parsed && typeof parsed === "object" && !Array.isArray(parsed) && Array.isArray(parsed.points)) {
                        parsed = parsed.points;
                    }

                    if (!Array.isArray(parsed) || parsed.length < 3) {
                        throw new Error("Dữ liệu JSON phải là mảng tọa độ chứa ít nhất 3 điểm.");
                    }
                    hiddenInput.value = JSON.stringify(parsed);
                    statusSpan.textContent = "Đã tải file thành công.";
                    statusSpan.style.color = "var(--color-primary, teal)";
                } catch (error) {
                    fileInput.value = "";
                    hiddenInput.value = "";
                    statusSpan.textContent = "Lỗi file không đúng chuẩn JSON Polygon.";
                    statusSpan.style.color = "var(--color-danger, red)";
                }
            };
            reader.readAsText(file);
        });
    }

    if (testRoiFilePicker && testRoiPoints && testRoiStatus) {
        handleFileSelect(testRoiFilePicker, testRoiPoints, testRoiStatus);
    }
    if (testNoParkingFilePicker && testNoParkingPoints && testNoParkingStatus) {
        handleFileSelect(testNoParkingFilePicker, testNoParkingPoints, testNoParkingStatus);
    }

    let pollingHandle = null;

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
        if (!streamOutput || !streamUrl) {
            return;
        }
        streamOutput.dataset.jobId = jobId;
        streamOutput.src = streamUrl;
        streamOutputNote.textContent = "Dang phat truc tiep stream phan tich thoi gian thuc...";
    }

    function pickTone(status) {
        if (status === "failed" || status === "aborted") {
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
        const queueText = job.status === "queued" && job.queue_position
            ? `Vi tri trong hang doi: ${job.queue_position}`
            : null;
        const latestText = progress.latest_status || null;

        statusPanel.innerHTML = `
            <article class="status-card">
                <span class="pill ${badgeClass}">${job.status || "Khong ro"}</span>
                <h4>${job.message || "Dang doi trang thai"}</h4>
                ${queueText ? `<p class="muted">${queueText}</p>` : ""}
                ${latestText ? `<p class="muted">Trang thai: ${latestText}</p>` : ""}
                ${job.error ? `<p class="muted">${job.error}</p>` : ""}
            </article>
        `;
    }

    function renderSummary(summary) {
        resultSummary.innerHTML = `
            <article class="summary-card">
                <span>Frames da xu ly</span>
                <strong>${summary.processed_frames ?? "-"}</strong>
            </article>
            <article class="summary-card">
                <span>Thoi luong video</span>
                <strong>${summary.duration_seconds ?? "-"}s</strong>
            </article>
            <article class="summary-card">
                <span>FPS xu ly trung binh</span>
                <strong>${summary.average_processing_fps ?? "-"}</strong>
            </article>
            <article class="summary-card">
                <span>Mat do cao nhat</span>
                <strong>${summary.max_occupancy_percent ?? "-"}%</strong>
            </article>
            <article class="summary-card">
                <span>Muc giao thong</span>
                <strong>${summary.highest_traffic_level ?? "-"}</strong>
            </article>
            <article class="summary-card">
                <span>Vi pham do xe</span>
                <strong>${summary.parking_violation_count ?? "-"}</strong>
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
        clearStream();
        streamOutputNote.textContent = "Video sẽ hiển thị khi backend bắt đầu xử lý.";
        renderPendingSummary(message);
    }

    function prepareViewer(job) {
        viewerPanel.hidden = false;

        // Start stream if available
        if (job.stream_url && streamOutput.dataset.jobId !== job.id) {
            startStream(job.id, job.stream_url);
        }

        if (job.status === "completed") {
            streamOutputNote.textContent = "Luong stream da hoan tat. Xem tom tat ben duoi.";
        } else if (job.status === "failed" || job.status === "aborted") {
            streamOutputNote.textContent = job.error || "Job da bi huy hoac that bai.";
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
            if (job.status === "failed" || job.status === "aborted") {
                submitButton.disabled = false;
                if (stopButton) stopButton.style.display = "none";
                streamOutputNote.textContent = job.error || "Xu ly video that bai hoac da bi dung.";
                stopPolling();
                return;
            }
            if (job.status === "completed") {
                renderSummary(job.summary || {});
                submitButton.disabled = false;
                if (stopButton) stopButton.style.display = "none";
                stopPolling();
            }
        } catch (error) {
            window.portalApi.showNotice(feedback, error.message, "error");
            submitButton.disabled = false;
            if (stopButton) stopButton.style.display = "none";
            stopPolling();
        }
    }

    uploadInput.addEventListener("change", () => {
        const file = uploadInput.files && uploadInput.files[0] ? uploadInput.files[0] : null;
        stopPolling();
        submitButton.disabled = false;
        if (file) {
            resetOutputView("Da chon video moi. San sang cho job moi.");
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        window.portalApi.showNotice(feedback, "", "info");
        stopPolling();
        clearStream();

        const formData = new FormData(form);
        featureCheckboxes.forEach((checkbox) => {
            formData.set(checkbox.name, checkbox.checked ? "true" : "false");
        });
        const hasFile = Boolean(formData.get("video_file") && formData.get("video_file").name);
        if (!hasFile) {
            window.portalApi.showNotice(feedback, "Hãy chọn file upload.", "error");
            return;
        }

        resetOutputView("Job đang được tạo. Stream sẽ được hiển thị ngay khi backend xử lý.");

        submitButton.disabled = true;
        renderStatus({ status: "queued", message: "Đang gửi yêu cầu về backend..." }, "warning");

        try {
            const data = await window.portalApi.submitForm("/api/test-jobs", formData);
            const job = data.job;
            currentJobId = job.id;
            if (stopButton) {
                stopButton.style.display = "block";
                stopButton.disabled = false;
            }
            prepareViewer(job);
            renderStatus(job, pickTone(job.status));
            renderPendingSummary("Backend dang xu ly video. Luong stream se cap nhat truc tiep.");

            pollingHandle = setInterval(() => pollJob(job.id), 3000);
            pollJob(job.id);
        } catch (error) {
            submitButton.disabled = false;
            if (stopButton) stopButton.style.display = "none";
            window.portalApi.showNotice(feedback, error.message, "error");
            renderStatus({ status: "failed", message: "Khong tao duoc job kiem tra.", error: error.message }, "error");
        }
    });

    if (stopButton) {
        stopButton.addEventListener("click", async () => {
            if (!currentJobId) return;
            stopButton.disabled = true;
            try {
                await window.portalApi.post(`/api/test-jobs/${currentJobId}/stop`);
                window.portalApi.showNotice(feedback, "Đã gửi yêu cầu dừng phân tích.", "info");
            } catch (error) {
                window.portalApi.showNotice(feedback, error.message, "error");
                stopButton.disabled = false;
            }
        });
    }

    window.addEventListener("beforeunload", () => {
        stopPolling();
    });

    // Show "Draw ROI" buttons only after video is selected
    const videoFileInput = form?.querySelector('input[name="video_file"]');
    let firstFrameDataUrl = null;

    if (videoFileInput) {
        videoFileInput.addEventListener("change", async (e) => {
            const file = videoFileInput.files && videoFileInput.files[0] ? videoFileInput.files[0] : null;
            const hasVideo = !!file;
            const buttons = document.querySelectorAll(".roi-draw-btn");
            buttons.forEach((btn) => {
                btn.style.display = hasVideo ? "inline-block" : "none";
            });

            if (hasVideo) {
                firstFrameDataUrl = null; // Reset
                const formData = new FormData();
                formData.append("video_file", file);

                try {
                    // Hiển thị trạng thái đang xử lý nếu cần
                    console.log("Đang trích xuất frame từ Backend...");
                    const data = await window.portalApi.submitForm("/api/test-video/extract-frame", formData);
                    if (data.ok && data.frame_data) {
                        firstFrameDataUrl = data.frame_data;
                        console.log(`Đã trích xuất frame (${data.width}x${data.height}) từ Backend.`);
                    } else {
                        throw new Error(data.error || "Không thể lấy frame từ Backend.");
                    }
                } catch (error) {
                    console.error("Lỗi lấy frame:", error);
                    alert("Lỗi khi trích xuất frame từ Video. Hãy thử lại hoặc chọn video khác.");
                }
            }
        });
    }

    // Setup ROI Draw buttons
    document.querySelectorAll(".roi-draw-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            if (!firstFrameDataUrl) {
                alert("Chưa thể trích xuất frame đầu tiên. Vui lòng chọn lại video.");
                return;
            }
            const targetId = btn.dataset.target;

            // Check if tool is initialized
            if (!window.roiDrawingTool || !window.roiDrawingTool.modal) {
                if (window.roiDrawingTool && typeof window.roiDrawingTool.init === 'function') {
                    window.roiDrawingTool.init();
                }
            }

            if (window.roiDrawingTool && typeof window.roiDrawingTool.openModal === 'function') {
                window.roiDrawingTool.openModal(targetId, firstFrameDataUrl);
            } else {
                console.error("roiDrawingTool is not properly initialized");
                alert("Công cụ vẽ ROI chưa sẵn sàng. Vui lòng thử lại sau giây lát.");
            }
        });
    });
}

// Khởi tạo form
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTestVideoForm);
} else {
    initTestVideoForm();
}

