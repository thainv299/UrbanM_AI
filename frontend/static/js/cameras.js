document.addEventListener("DOMContentLoaded", () => {
    const tableBody = document.getElementById("cameras-table-body");
    const form = document.getElementById("camera-form");
    const feedback = document.getElementById("cameras-feedback");
    const refreshButton = document.getElementById("cameras-refresh");
    const resetButton = document.getElementById("camera-form-reset");
    const formTitle = document.getElementById("camera-form-title");

    if (!tableBody || !form) {
        return;
    }

    const fields = {
        id: document.getElementById("camera_id"),
        name: document.getElementById("camera_name"),
        streamSource: document.getElementById("stream_source"),
        description: document.getElementById("description"),
        modelPath: document.getElementById("model_path"),
        enableSimulation: document.getElementById("enable_simulation"),
        simulationVideoFile: document.getElementById("simulation_video_file"),
        simulationVideoStatus: document.getElementById("simulation_video_status"),
        roiPoints: document.getElementById("roi_points"),
        noParkingPoints: document.getElementById("no_parking_points"),
        roiFilePicker: document.getElementById("roi_file_picker"),
        roiStatus: document.getElementById("roi_points_status"),
        noParkingFilePicker: document.getElementById("no_parking_file_picker"),
        noParkingStatus: document.getElementById("no_parking_points_status"),
        enableCongestion: document.getElementById("enable_congestion"),
        enableIllegalParking: document.getElementById("enable_illegal_parking"),
        enableLicensePlate: document.getElementById("enable_license_plate"),
        isActive: document.getElementById("camera_is_active"),
    };

    const state = {
        cameras: [],
    };

    let currentEditingCameraId = null;
    let firstFrameDataUrl = null;

    function setForm(camera = null) {
        currentEditingCameraId = camera !== null ? camera.id : null;
        fields.id.value = camera !== null ? camera.id : "";
        fields.name.value = camera?.name || "";
        fields.streamSource.value = camera?.stream_source || "";
        fields.description.value = camera?.description || "";
        
        if (camera?.model_path) {
            fields.modelPath.value = camera.model_path;
        } else {
            // Default select first or standard
            if (fields.modelPath.options.length > 0) fields.modelPath.selectedIndex = 0;
        }

        fields.simulationVideoFile.value = "";
        fields.simulationVideoStatus.textContent = camera?.stream_source ? `Nguồn hiện tại: ${camera.stream_source}` : "Chưa chọn video giả lập.";
        fields.simulationVideoStatus.style.color = "var(--text-muted)";
        
        firstFrameDataUrl = null;

        fields.roiPoints.value = camera?.roi_points ? JSON.stringify(camera.roi_points) : "";
        fields.roiFilePicker.value = "";
        fields.roiStatus.textContent = camera?.roi_points ? "Đã có dữ liệu từ trước." : "Chưa có dữ liệu.";
        
        fields.noParkingPoints.value = camera?.no_parking_points ? JSON.stringify(camera.no_parking_points) : "";
        fields.noParkingFilePicker.value = "";
        fields.noParkingStatus.textContent = camera?.no_parking_points ? "Đã có dữ liệu từ trước." : "Chưa có vùng cấm đỗ.";

        fields.enableCongestion.checked = camera ? Boolean(camera.enable_congestion) : true;
        fields.enableIllegalParking.checked = camera ? Boolean(camera.enable_illegal_parking) : true;
        fields.enableLicensePlate.checked = camera ? Boolean(camera.enable_license_plate) : true;
        fields.isActive.checked = camera ? Boolean(camera.is_active) : true;

        fields.enableSimulation.checked = camera ? Boolean(camera.enable_simulation) : false;
        updateSimulationLayout();

        formTitle.textContent = camera ? `Cập nhật camera #${camera.id}` : "Thêm camera mới";
    }

    function updateSimulationLayout() {
        const simulationField = document.querySelector(".simulation-field");
        if (!simulationField) return;
        simulationField.style.display = fields.enableSimulation.checked ? "block" : "none";
        if (!fields.enableSimulation.checked) {
            fields.simulationVideoStatus.textContent = "Chế độ giả lập tắt.";
        }
    }

    // Fix Simulation Video Selection Display
    if (fields.simulationVideoFile) {
        fields.simulationVideoFile.addEventListener("change", (e) => {
            const file = e.target.files[0];
            if (file) {
                fields.simulationVideoStatus.textContent = `Sẵn sàng tải lên: ${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)`;
                fields.simulationVideoStatus.style.color = "var(--color-primary, teal)";
                firstFrameDataUrl = null; // Clear old preview
            }
        });
    }

    // ── ROI FRAME EXTRACTION (Using robust method from test_video) ──
    async function getSnapshotFromCamera(cameraId) {
        try {
            const response = await fetch(`/api/cameras/${cameraId}/snapshot?ts=${Date.now()}`);
            if (!response.ok) throw new Error("Không thể lấy snapshot từ camera.");
            const blob = await response.blob();
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result);
                reader.readAsDataURL(blob);
            });
        } catch (error) {
            console.error(error);
            return null;
        }
    }

    async function extractFrameLocally(file) {
        return new Promise((resolve, reject) => {
            const videoURL = URL.createObjectURL(file);
            const video = document.createElement("video");
            video.muted = true;
            video.playsInline = true;
            video.preload = "metadata";
            video.src = videoURL;

            let timeoutId = setTimeout(() => {
                cleanup();
                reject(new Error("Timeout khi trích xuất frame"));
            }, 8000);

            const cleanup = () => {
                clearTimeout(timeoutId);
                video.pause();
                video.src = "";
                URL.revokeObjectURL(videoURL);
            };

            video.addEventListener("loadeddata", () => {
                video.currentTime = 0.5;
            });

            video.addEventListener("seeked", () => {
                const canvas = document.createElement("canvas");
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                const ctx = canvas.getContext("2d");
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataUrl = canvas.toDataURL("image/jpeg", 0.9);
                cleanup();
                resolve(dataUrl);
            });

            video.load();
        });
    }

    document.querySelectorAll(".roi-draw-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.preventDefault();
            const targetId = btn.dataset.target;
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = "Đang lấy frame...";

            try {
                // Determine source for frame
                if (fields.enableSimulation.checked && fields.simulationVideoFile.files.length > 0) {
                    const file = fields.simulationVideoFile.files[0];
                    if (!firstFrameDataUrl) {
                        firstFrameDataUrl = await extractFrameLocally(file);
                    }
                } else if (currentEditingCameraId) {
                    // Try to get live snapshot
                    firstFrameDataUrl = await getSnapshotFromCamera(currentEditingCameraId);
                }

                if (!firstFrameDataUrl) {
                    throw new Error("Không thể trích xuất ảnh nền. Hãy chọn file video hoặc lưu camera để lấy ảnh từ luồng trực tiếp.");
                }

                if (window.roiDrawingTool) {
                    window.roiDrawingTool.openModal(targetId, firstFrameDataUrl);
                }
            } catch (err) {
                alert("Lỗi: " + err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        });
    });

    function handleFileSelect(fileInput, hiddenInput, statusSpan) {
        fileInput.addEventListener("change", (event) => {
            const file = event.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    let parsed = JSON.parse(e.target.result);
                    if (parsed && parsed.points) parsed = parsed.points;
                    if (!Array.isArray(parsed)) throw new Error("JSON không hợp lệ");
                    hiddenInput.value = JSON.stringify(parsed);
                    statusSpan.textContent = "Đã tải file thành công.";
                } catch (error) {
                    alert("Lỗi file JSON");
                }
            };
            reader.readAsText(file);
        });
    }

    if (fields.roiFilePicker) handleFileSelect(fields.roiFilePicker, fields.roiPoints, fields.roiStatus);
    if (fields.noParkingFilePicker) handleFileSelect(fields.noParkingFilePicker, fields.noParkingPoints, fields.noParkingStatus);

    if (fields.enableSimulation) {
        fields.enableSimulation.addEventListener("change", () => {
            updateSimulationLayout();
            firstFrameDataUrl = null;
        });
    }

    async function loadCameras() {
        try {
            const data = await window.portalApi.get("/api/cameras");
            state.cameras = data.cameras || [];
            renderTable();
        } catch (error) {
            window.portalApi.showNotice(feedback, error.message, "error");
        }
    }

    function renderTable() {
        if (!state.cameras.length) {
            tableBody.innerHTML = `<tr><td colspan="5"><div class="empty-state">Chưa có camera nào.</div></td></tr>`;
            return;
        }

        tableBody.innerHTML = state.cameras.map((camera) => `
            <tr>
                <td><strong>${camera.name}</strong></td>
                <td><code class="small">${camera.stream_source || "Chưa có nguồn"}</code></td>
                <td>
                    <div class="pill-row">
                        <span class="pill ${camera.enable_congestion ? "teal" : "gray"}">Tắc nghẽn</span>
                        <span class="pill ${camera.enable_illegal_parking ? "orange" : "gray"}">Đỗ sai</span>
                        <span class="pill ${camera.enable_license_plate ? "teal" : "gray"}">Biển số</span>
                    </div>
                </td>
                <td><span class="badge ${camera.is_active ? "success" : "muted"}">${camera.is_active ? "Hoạt động" : "Tắt"}</span></td>
                <td>
                    <div class="button-row">
                        <button class="button secondary tiny" data-action="edit" data-id="${camera.id}">Sửa</button>
                        <button class="button danger tiny" data-action="delete" data-id="${camera.id}">Xóa</button>
                    </div>
                </td>
            </tr>
        `).join("");
    }

    async function saveCamera(event) {
        event.preventDefault();
        const payload = {
            name: fields.name.value.trim(),
            stream_source: fields.streamSource.value.trim(),
            description: fields.description.value.trim(),
            model_path: fields.modelPath.value,
            roi_points: fields.roiPoints.value.trim(),
            no_parking_points: fields.noParkingPoints.value.trim(),
            enable_congestion: fields.enableCongestion.checked,
            enable_simulation: fields.enableSimulation.checked,
            enable_illegal_parking: fields.enableIllegalParking.checked,
            enable_license_plate: fields.enableLicensePlate.checked,
            is_active: fields.isActive.checked,
        };
        const isEditing = fields.id.value !== "";
        const editingId = isEditing ? Number(fields.id.value) : null;

        try {
            // Upload simulation video if selected
            if (fields.enableSimulation.checked && fields.simulationVideoFile.files.length > 0) {
                const file = fields.simulationVideoFile.files[0];
                const fd = new FormData();
                fd.append('video_file', file);
                
                fields.simulationVideoStatus.textContent = "Đang tải video lên...";
                const uploadResult = await window.portalApi.submitFormChunked('/api/cameras/upload-source', fd, (percent) => {
                    fields.simulationVideoStatus.textContent = `Đang tải lên: ${percent}%`;
                });
                
                if (uploadResult && uploadResult.ok && uploadResult.path) {
                    payload.stream_source = uploadResult.path;
                    fields.simulationVideoStatus.textContent = "Tải lên hoàn tất.";
                } else {
                    throw new Error("Lỗi tải video giả lập.");
                }
            }

            if (isEditing) {
                await window.portalApi.put(`/api/cameras/${editingId}`, payload);
                window.portalApi.showNotice(feedback, "Đã cập nhật camera.", "success");
            } else {
                await window.portalApi.post("/api/cameras", payload);
                window.portalApi.showNotice(feedback, "Đã thêm camera mới.", "success");
            }
            setForm();
            await loadCameras();
        } catch (error) {
            window.portalApi.showNotice(feedback, error.message, "error");
        }
    }

    tableBody.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) return;
        const cameraId = Number(button.dataset.id);
        const camera = state.cameras.find((item) => item.id === cameraId);
        if (!camera) return;

        if (button.dataset.action === "edit") {
            setForm(camera);
            return;
        }

        if (button.dataset.action === "delete") {
            if (!confirm(`Xóa camera ${camera.name}?`)) return;
            try {
                await window.portalApi.delete(`/api/cameras/${cameraId}`);
                setForm();
                await loadCameras();
            } catch (error) {
                window.portalApi.showNotice(feedback, error.message, "error");
            }
        }
    });

    resetButton.addEventListener("click", () => setForm());
    form.addEventListener("submit", saveCamera);

    setForm();
    loadCameras();
});
