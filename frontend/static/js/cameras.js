document.addEventListener("DOMContentLoaded", () => {
    const tableBody = document.getElementById("cameras-table-body");
    const previewGrid = document.getElementById("camera-preview-grid");
    const form = document.getElementById("camera-form");
    const feedback = document.getElementById("cameras-feedback");
    const refreshButton = document.getElementById("cameras-refresh");
    const resetButton = document.getElementById("camera-form-reset");
    const formTitle = document.getElementById("camera-form-title");

    if (!tableBody || !previewGrid || !form) {
        return;
    }

    const fields = {
        id: document.getElementById("camera_id"),
        name: document.getElementById("camera_name"),
        streamSource: document.getElementById("stream_source"),
        description: document.getElementById("description"),
        roiPoints: document.getElementById("roi_points"),
        noParkingPoints: document.getElementById("no_parking_points"),
        enableCongestion: document.getElementById("enable_congestion"),
        enableIllegalParking: document.getElementById("enable_illegal_parking"),
        enableLicensePlate: document.getElementById("enable_license_plate"),
        isActive: document.getElementById("camera_is_active"),
    };

    const state = {
        cameras: [],
        refreshTimer: null,
    };

    function setForm(camera = null) {
        fields.id.value = camera?.id || "";
        fields.name.value = camera?.name || "";
        fields.streamSource.value = camera?.stream_source || "";
        fields.description.value = camera?.description || "";
        fields.roiPoints.value = camera?.roi_points ? JSON.stringify(camera.roi_points, null, 2) : "";
        fields.noParkingPoints.value = camera?.no_parking_points ? JSON.stringify(camera.no_parking_points, null, 2) : "";
        fields.enableCongestion.checked = camera ? Boolean(camera.enable_congestion) : true;
        fields.enableIllegalParking.checked = camera ? Boolean(camera.enable_illegal_parking) : true;
        fields.enableLicensePlate.checked = camera ? Boolean(camera.enable_license_plate) : true;
        fields.isActive.checked = camera ? Boolean(camera.is_active) : true;
        formTitle.textContent = camera ? `Cap nhat camera #${camera.id}` : "Them camera moi";
    }

    function formatDetection(camera) {
        return `
            <div class="pill-row">
                <span class="pill ${camera.enable_congestion ? "teal" : "gray"}">Tac nghen ${window.portalApi.pillText(camera.enable_congestion, "ON", "OFF")}</span>
                <span class="pill ${camera.enable_illegal_parking ? "orange" : "gray"}">Do sai ${window.portalApi.pillText(camera.enable_illegal_parking, "ON", "OFF")}</span>
                <span class="pill ${camera.enable_license_plate ? "teal" : "gray"}">Bien so ${window.portalApi.pillText(camera.enable_license_plate, "ON", "OFF")}</span>
            </div>
        `;
    }

    function renderTable() {
        if (!state.cameras.length) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5">
                        <div class="empty-state">
                            <div>
                                <h3>Chua co camera nao</h3>
                                <p class="muted">Them camera de hien thi preview va cau hinh detect.</p>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tableBody.innerHTML = state.cameras.map((camera) => `
            <tr>
                <td><strong>${camera.name}</strong></td>
                <td>${camera.stream_source || "Chua co nguon"}</td>
                <td>${formatDetection(camera)}</td>
                <td><span class="badge ${camera.is_active ? "success" : "muted"}">${camera.is_active ? "Dang bat" : "Dang tat"}</span></td>
                <td>
                    <div class="button-row">
                        <button class="button secondary tiny" data-action="edit" data-id="${camera.id}">Sua</button>
                        <button class="button danger tiny" data-action="delete" data-id="${camera.id}">Xoa</button>
                    </div>
                </td>
            </tr>
        `).join("");
    }

    function renderPreviewGrid() {
        if (!state.cameras.length) {
            previewGrid.innerHTML = `
                <div class="empty-state panel full-span">
                    <div>
                        <h3>Chua co camera de hien thi</h3>
                        <p class="muted">Sau khi them camera, anh preview se duoc lam moi tu dong.</p>
                    </div>
                </div>
            `;
            return;
        }

        previewGrid.innerHTML = state.cameras.map((camera) => `
            <article class="camera-preview-card">
                <img
                    src="/api/cameras/${camera.id}/snapshot?ts=${Date.now()}"
                    alt="Preview ${camera.name}"
                    class="camera-preview-image"
                    data-camera-id="${camera.id}"
                >
                <div class="camera-body">
                    <div class="camera-mini-head">
                        <strong>${camera.name}</strong>
                        <span class="badge ${camera.is_active ? "success" : "muted"}">${camera.is_active ? "Dang bat" : "Tat"}</span>
                    </div>
                    <p class="muted small">${camera.stream_source || "Chua cau hinh nguon camera"}</p>
                    ${formatDetection(camera)}
                    <div class="preview-actions">
                        <button class="button secondary tiny" data-action="toggle-congestion" data-id="${camera.id}">Bat hoac tat tac nghen</button>
                        <button class="button secondary tiny" data-action="toggle-parking" data-id="${camera.id}">Bat hoac tat do sai</button>
                        <button class="button secondary tiny" data-action="toggle-license-plate" data-id="${camera.id}">Bat hoac tat bien so</button>
                        <button class="button secondary tiny" data-action="toggle-active" data-id="${camera.id}">Bat hoac tat camera</button>
                    </div>
                </div>
            </article>
        `).join("");
    }

    async function loadCameras() {
        try {
            const data = await window.portalApi.get("/api/cameras");
            state.cameras = data.cameras || [];
            renderTable();
            renderPreviewGrid();
        } catch (error) {
            window.portalApi.showNotice(feedback, error.message, "error");
        }
    }

    function buildPayloadFromForm() {
        return {
            name: fields.name.value.trim(),
            stream_source: fields.streamSource.value.trim(),
            description: fields.description.value.trim(),
            roi_points: fields.roiPoints.value.trim(),
            no_parking_points: fields.noParkingPoints.value.trim(),
            enable_congestion: fields.enableCongestion.checked,
            enable_illegal_parking: fields.enableIllegalParking.checked,
            enable_license_plate: fields.enableLicensePlate.checked,
            is_active: fields.isActive.checked,
        };
    }

    async function saveCamera(event) {
        event.preventDefault();
        const payload = buildPayloadFromForm();
        const editingId = Number(fields.id.value || 0);

        try {
            if (editingId) {
                await window.portalApi.put(`/api/cameras/${editingId}`, payload);
                window.portalApi.showNotice(feedback, "Da cap nhat camera.", "success");
            } else {
                await window.portalApi.post("/api/cameras", payload);
                window.portalApi.showNotice(feedback, "Da them camera moi.", "success");
            }
            setForm();
            await loadCameras();
        } catch (error) {
            window.portalApi.showNotice(feedback, error.message, "error");
        }
    }

    async function updateCameraFlags(cameraId, updates) {
        const camera = state.cameras.find((item) => item.id === cameraId);
        if (!camera) {
            return;
        }
        const payload = {
            name: camera.name,
            stream_source: camera.stream_source,
            description: camera.description,
            roi_points: camera.roi_points,
            no_parking_points: camera.no_parking_points,
            enable_congestion: camera.enable_congestion,
            enable_illegal_parking: camera.enable_illegal_parking,
            enable_license_plate: camera.enable_license_plate,
            is_active: camera.is_active,
            ...updates,
        };
        try {
            await window.portalApi.put(`/api/cameras/${cameraId}`, payload);
            await loadCameras();
        } catch (error) {
            window.portalApi.showNotice(feedback, error.message, "error");
        }
    }

    tableBody.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) {
            return;
        }

        const cameraId = Number(button.dataset.id);
        const camera = state.cameras.find((item) => item.id === cameraId);
        if (!camera) {
            return;
        }

        if (button.dataset.action === "edit") {
            setForm(camera);
            window.portalApi.showNotice(feedback, `Dang chinh sua camera ${camera.name}.`, "info");
            return;
        }

        if (button.dataset.action === "delete") {
            if (!window.confirm(`Xoa camera ${camera.name}?`)) {
                return;
            }
            try {
                await window.portalApi.delete(`/api/cameras/${cameraId}`);
                if (Number(fields.id.value || 0) === cameraId) {
                    setForm();
                }
                window.portalApi.showNotice(feedback, "Da xoa camera.", "success");
                await loadCameras();
            } catch (error) {
                window.portalApi.showNotice(feedback, error.message, "error");
            }
        }
    });

    previewGrid.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) {
            return;
        }

        const cameraId = Number(button.dataset.id);
        const camera = state.cameras.find((item) => item.id === cameraId);
        if (!camera) {
            return;
        }

        if (button.dataset.action === "toggle-congestion") {
            await updateCameraFlags(cameraId, { enable_congestion: !camera.enable_congestion });
        }
        if (button.dataset.action === "toggle-parking") {
            await updateCameraFlags(cameraId, { enable_illegal_parking: !camera.enable_illegal_parking });
        }
        if (button.dataset.action === "toggle-license-plate") {
            await updateCameraFlags(cameraId, { enable_license_plate: !camera.enable_license_plate });
        }
        if (button.dataset.action === "toggle-active") {
            await updateCameraFlags(cameraId, { is_active: !camera.is_active });
        }
    });

    resetButton.addEventListener("click", () => {
        setForm();
        window.portalApi.showNotice(feedback, "", "info");
    });

    refreshButton.addEventListener("click", loadCameras);
    form.addEventListener("submit", saveCamera);

    function refreshSnapshots() {
        previewGrid.querySelectorAll("img[data-camera-id]").forEach((image) => {
            const cameraId = image.dataset.cameraId;
            image.src = `/api/cameras/${cameraId}/snapshot?ts=${Date.now()}`;
        });
    }

    state.refreshTimer = window.setInterval(refreshSnapshots, 5000);
    setForm();
    loadCameras();
});
