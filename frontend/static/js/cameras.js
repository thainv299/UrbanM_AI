document.addEventListener("DOMContentLoaded", () => {
    // Các phần tử DOM chính
    const tableBody = document.getElementById("cameras-table-body");
    const form = document.getElementById("camera-form");
    const feedback = document.getElementById("cameras-feedback");
    const refreshButton = document.getElementById("cameras-refresh");
    const resetButton = document.getElementById("camera-form-reset");
    const formTitle = document.getElementById("camera-form-title");

    if (!tableBody || !form) {
        return;
    }

    // Đối tượng chứa các trường nhập liệu
    const fields = {
        id: document.getElementById("camera_id"),
        name: document.getElementById("camera_name"),
        streamSource: document.getElementById("stream_source"),
        description: document.getElementById("description"),
        modelPath: document.getElementById("model_path"),
        enableSimulation: document.getElementById("enable_simulation"),
        browseServerBtn: document.getElementById("browse-server-btn"),
        serverBrowserModal: document.getElementById("server-browser-modal"),
        serverFileList: document.getElementById("server-file-list"),
        closeServerBrowser: document.getElementById("close-server-browser"),
        cancelServerBrowser: document.getElementById("cancel-server-browser"),
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

    // Cập nhật thông báo trạng thái số điểm tọa độ
    function updatePointsStatus(targetId) {
        const textarea = document.getElementById(targetId);
        const statusDiv = document.getElementById(targetId + "_status");
        if (!textarea || !statusDiv) return;

        try {
            const val = textarea.value.trim();
            if (!val || val === "[]" || val === "") {
                statusDiv.innerHTML = `<span style="color: var(--text-subtle);">Chưa thiết lập</span>`;
                return;
            }
            const data = JSON.parse(val);
            const pts = Array.isArray(data) ? data : (data.points || []);
            if (Array.isArray(pts)) {
                statusDiv.innerHTML = `<span style="color: var(--brand-main); font-weight: 600;">Đã thiết lập (${pts.length} điểm)</span>`;
            } else {
                statusDiv.innerHTML = `<span style="color: var(--text-danger);">Định dạng lỗi</span>`;
            }
        } catch (e) {
            statusDiv.innerHTML = `<span style="color: var(--text-danger);">JSON không hợp lệ</span>`;
        }
    }

    // Ghi đè setter .value để bắt được các cập nhật từ công cụ vẽ ROI
    const originalValueSetter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
    Object.defineProperty(HTMLTextAreaElement.prototype, 'value', {
        set: function (val) {
            originalValueSetter.call(this, val);
            if (this.id === 'roi_points' || this.id === 'no_parking_points') {
                updatePointsStatus(this.id);
            }
        }
    });

    // Thiết lập dữ liệu cho form (thêm mới hoặc chỉnh sửa)
    function setForm(camera = null) {
        currentEditingCameraId = camera !== null ? camera.id : null;
        fields.id.value = camera !== null ? camera.id : "";
        fields.name.value = camera?.name || "";
        fields.streamSource.value = camera?.stream_source || "";
        fields.description.value = camera?.description || "";

        if (camera?.model_path) {
            fields.modelPath.value = camera.model_path;
        } else {
            // Mặc định chọn option đầu tiên
            if (fields.modelPath.options.length > 0) fields.modelPath.selectedIndex = 0;
        }

        fields.enableSimulation.checked = camera ? Boolean(camera.enable_simulation) : false;

        firstFrameDataUrl = null;

        if (camera?.roi_points) {
            const roiData = { points: camera.roi_points, ...(camera.roi_meta || {}) };
            fields.roiPoints.value = JSON.stringify(roiData);
        } else {
            fields.roiPoints.value = "";
        }
        fields.roiFilePicker.value = "";

        if (camera?.no_parking_points) {
            const npData = { points: camera.no_parking_points, ...(camera.no_park_meta || {}) };
            fields.noParkingPoints.value = JSON.stringify(npData);
        } else {
            fields.noParkingPoints.value = "";
        }
        fields.noParkingFilePicker.value = "";

        fields.enableCongestion.checked = camera ? Boolean(camera.enable_congestion) : true;
        fields.enableIllegalParking.checked = camera ? Boolean(camera.enable_illegal_parking) : true;
        fields.enableLicensePlate.checked = camera ? Boolean(camera.enable_license_plate) : true;
        fields.isActive.checked = camera ? Boolean(camera.is_active) : true;

        formTitle.textContent = camera ? `Cập nhật camera #${camera.id}` : "Thêm camera mới";

        // Cập nhật trạng thái tọa độ
        updatePointsStatus("roi_points");
        updatePointsStatus("no_parking_points");
    }

    function updateSimulationLayout() {
        // Placeholder cho cập nhật giao diện giả lập nếu cần
    }

    // ── TRÍCH XUẤT ẢNH TỪ CAMERA ──
    async function getSnapshotFromCamera(cameraId, raw = false) {
        try {
            const response = await fetch(`/api/cameras/${cameraId}/snapshot?raw=${raw}&ts=${Date.now()}`);
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

    // Trích xuất frame từ file video cục bộ
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

    // Xử lý sự kiện nhấn nút vẽ ROI/Vùng
    document.querySelectorAll(".roi-draw-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.preventDefault();
            const targetId = btn.dataset.target;
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = "Đang lấy frame...";

            try {
                let frameUrl = null;
                const sourceValue = fields.streamSource.value.trim();

                // 1. Nếu đang sửa camera đã lưu -> Lấy snapshot từ server
                if (currentEditingCameraId !== null) {
                    console.log("ROI: Lấy snapshot cho camera hiện tại", currentEditingCameraId);
                    frameUrl = await getSnapshotFromCamera(currentEditingCameraId, true);
                }

                // 2. Nếu là camera mới hoặc snapshot server lỗi -> Thử lấy từ nguồn đang nhập
                if (!frameUrl && sourceValue) {
                    console.log("ROI: Thử lấy frame từ nguồn nhập vào", sourceValue);

                    // Nếu là webcam (số hiệu)
                    if (/^\d+$/.test(sourceValue)) {
                        throw new Error("Không thể trích xuất ảnh nền từ Webcam local qua trình duyệt. Hãy lưu camera và bật 'Kích hoạt' để hệ thống lấy ảnh từ luồng trực tiếp.");
                    }

                    // Nếu là file server (không phải luồng trực tiếp)
                    if (!sourceValue.startsWith("rtsp://") && !sourceValue.startsWith("http")) {
                        try {
                            const resp = await fetch(`/api/server-videos/preview?path=${encodeURIComponent(sourceValue)}`);
                            if (resp.ok) {
                                const blob = await resp.blob();
                                frameUrl = await new Promise(r => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => r(reader.result);
                                    reader.readAsDataURL(blob);
                                });
                            } else {
                                const errData = await resp.json();
                                console.warn("Lỗi API preview server:", errData);
                            }
                        } catch (pErr) {
                            console.warn("Lỗi khi fetch preview server", pErr);
                        }
                    } else if (sourceValue.startsWith("rtsp://")) {
                        throw new Error("Luồng RTSP cần được lưu và kích hoạt camera trước khi có thể trích xuất ảnh nền.");
                    }
                }

                if (!frameUrl) {
                    throw new Error("Không thể trích xuất ảnh nền. Nguyên nhân có thể do:\n1. Nguồn video không hợp lệ hoặc không truy cập được.\n2. Camera chưa được lưu hoặc chưa kích hoạt.\n3. Định dạng video không được hỗ trợ trích xuất nhanh.");
                }

                if (window.roiDrawingTool) {
                    window.roiDrawingTool.openModal(targetId, frameUrl);
                }
            } catch (err) {
                alert("Lỗi: " + err.message);
            } finally {
                btn.disabled = false;
                btn.textContent = originalText;
            }
        });
    });

    // Xử lý chọn file JSON từ máy tính
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
            firstFrameDataUrl = null;
        });
    }

    // ── LOGIC DUYỆT VIDEO TRÊN SERVER ──────────────────────────
    if (fields.browseServerBtn) {
        fields.browseServerBtn.addEventListener("click", openServerBrowser);
    }
    if (fields.closeServerBrowser) fields.closeServerBrowser.addEventListener("click", closeServerBrowser);
    if (fields.cancelServerBrowser) fields.cancelServerBrowser.addEventListener("click", closeServerBrowser);

    const previewFields = {
        img: document.getElementById("server-file-preview-img"),
        placeholder: document.getElementById("server-file-preview-placeholder"),
        loader: document.getElementById("server-file-preview-loader"),
        info: document.getElementById("server-file-info"),
        name: document.getElementById("server-file-info-name"),
        size: document.getElementById("server-file-info-size"),
    };

    async function openServerBrowser() {
        fields.serverBrowserModal.style.display = "flex";
        fields.serverFileList.innerHTML = '<p class="muted center">Đang tải danh sách file...</p>';
        resetPreview();

        try {
            const data = await window.portalApi.get("/api/server-videos");
            if (data.ok && data.groups && Object.keys(data.groups).length > 0) {
                let html = "";

                // Duyệt qua từng nhóm thư mục
                for (const [groupName, videos] of Object.entries(data.groups)) {
                    html += `
                        <div class="video-group" style="margin-bottom: 12px;">
                            <div class="group-header" style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; color: var(--brand-main); margin-bottom: 6px; padding-left: 4px; display: flex; align-items: center; gap: 6px;">
                                ${groupName}
                            </div>
                            <div style="display: grid; gap: 8px;">
                                ${videos.map(v => `
                                    <div class="file-item server-video-item" 
                                         data-filename="${v.filename}" 
                                         data-path="${v.path}"
                                         data-size="${(v.size / (1024 * 1024)).toFixed(1)} MB" 
                                         style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border: 1px solid var(--border); border-radius: 10px; background: var(--bg-panel); cursor: pointer; transition: all 0.2s; gap: 12px;">
                                        <div style="display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0;">
                                            <div style="flex: 1; min-width: 0;">
                                                <div style="font-weight: 600; font-size: 0.9rem; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 500px;" title="${v.filename}">${v.filename}</div>
                                                <div class="muted small">${(v.size / (1024 * 1024)).toFixed(1)} MB • Video File</div>
                                            </div>
                                        </div>
                                        <button type="button" class="button primary sm select-file-btn" data-path="${v.path}" style="flex-shrink: 0; padding: 6px 16px; border-radius: 6px;">Chọn</button>
                                    </div>
                                `).join("")}
                            </div>
                        </div>
                    `;
                }

                fields.serverFileList.innerHTML = html;

                const items = fields.serverFileList.querySelectorAll(".server-video-item");
                items.forEach(item => {
                    item.addEventListener("mouseenter", () => loadPreview(item.dataset.path, item.dataset.filename, item.dataset.size));
                    item.addEventListener("click", (e) => {
                        if (e.target.classList.contains("select-file-btn")) return;
                        loadPreview(item.dataset.path, item.dataset.filename, item.dataset.size);
                    });
                });

                fields.serverFileList.querySelectorAll(".select-file-btn").forEach(btn => {
                    btn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        fields.streamSource.value = btn.dataset.path;
                        fields.enableSimulation.checked = true;
                        closeServerBrowser();
                    });
                });

                // Tự động load preview file đầu tiên
                if (items.length > 0) {
                    const first = items[0];
                    loadPreview(first.dataset.path, first.dataset.filename, first.dataset.size);
                }
            } else {
                fields.serverFileList.innerHTML = `
                    <div class="center" style="padding: 40px 20px;">
                        <p class="muted">Không tìm thấy file video nào trong thư mục <code>data/</code>.</p>
                        <p class="small muted">Hãy đảm bảo file có đuôi .mp4, .avi, .mkv...</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error("Lỗi trình duyệt server:", error);
            fields.serverFileList.innerHTML = `
                <div class="center error" style="padding: 40px 20px;">
                    <p>Lỗi khi kết nối đến máy chủ:</p>
                    <code style="display: block; margin-top: 10px; color: var(--text-error);">${error.message}</code>
                </div>
            `;
        }
    }

    let previewAbortController = null;
    async function loadPreview(path, filename, size) {
        if (previewAbortController) previewAbortController.abort();
        previewAbortController = new AbortController();

        previewFields.loader.style.display = "flex";
        previewFields.placeholder.style.display = "none";
        previewFields.info.style.display = "block";
        previewFields.name.textContent = filename;
        previewFields.size.textContent = size;

        try {
            const url = `/api/server-videos/preview?path=${encodeURIComponent(path)}`;
            const response = await fetch(url, { signal: previewAbortController.signal });
            if (!response.ok) throw new Error("Preview failed");

            const blob = await response.blob();
            const objectURL = URL.createObjectURL(blob);

            previewFields.img.src = objectURL;
            previewFields.img.style.display = "block";
            previewFields.loader.style.display = "none";
        } catch (err) {
            if (err.name === "AbortError") return;
            console.error("Lỗi tải preview:", err);
            previewFields.loader.style.display = "none";
            previewFields.placeholder.style.display = "flex";
            previewFields.img.style.display = "none";
        }
    }

    function resetPreview() {
        if (previewAbortController) previewAbortController.abort();
        previewFields.img.src = "";
        previewFields.img.style.display = "none";
        previewFields.placeholder.style.display = "flex";
        previewFields.loader.style.display = "none";
        previewFields.info.style.display = "none";
    }

    function closeServerBrowser() {
        fields.serverBrowserModal.style.display = "none";
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
            tableBody.innerHTML = `<tr><td colspan="6"><div class="empty-state">Chưa có camera nào.</div></td></tr>`;
            return;
        }

        tableBody.innerHTML = state.cameras.map((camera, index) => {
            let displaySource = camera.stream_source || "Chưa có nguồn";
            if (camera.enable_simulation && camera.stream_source) {
                const filename = camera.stream_source.split(/[\\\/]/).pop();
                displaySource = `${filename}`;
            }

            return `
                <tr>
                    <td style="text-align: center;">${index + 1}</td>
                    <td>
                        <div style="font-weight: 700; color: var(--text-main); margin-bottom: 4px;">${camera.name}</div>
                        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                            ${camera.enable_congestion ? '<span data-tooltip="Phát hiện Tắc nghẽn" style="width:10px; height:10px; border-radius:50%; background:var(--brand-main); display:inline-block;"></span>' : ''}
                            ${camera.enable_illegal_parking ? '<span data-tooltip="Phát hiện Đỗ sai" style="width:10px; height:10px; border-radius:50%; background:orange; display:inline-block;"></span>' : ''}
                            ${camera.enable_license_plate ? '<span data-tooltip="Nhận diện Biển số" style="width:10px; height:10px; border-radius:50%; background:teal; display:inline-block;"></span>' : ''}
                        </div>
                    </td>
                    <td>
                        <div class="small muted" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px;" title="${camera.stream_source}">
                            ${displaySource}
                        </div>
                    </td>
                    <td>
                        <span class="badge ${camera.is_active ? "success" : "muted"}" style="font-size: 0.7rem; padding: 2px 8px;">
                            ${camera.is_active ? "Hoạt động" : "Đang tắt"}
                        </span>
                    </td>
                    <td>
                        <div style="display: flex; gap: 6px; justify-content: center;">
                            <button class="button secondary xs" data-action="edit" data-id="${camera.id}" style="padding: 4px 8px;">Sửa</button>
                            <button class="button danger xs" data-action="delete" data-id="${camera.id}" style="padding: 4px 8px;">Xóa</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
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

    refreshButton.addEventListener("click", () => loadCameras());
    resetButton.addEventListener("click", () => setForm());
    form.addEventListener("submit", saveCamera);

    setForm();
    loadCameras();
});
