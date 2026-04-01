document.addEventListener("DOMContentLoaded", () => {
    const tableBody = document.getElementById("users-table-body");
    const form = document.getElementById("user-form");
    const feedback = document.getElementById("users-feedback");
    const resetButton = document.getElementById("user-form-reset");
    const refreshButton = document.getElementById("users-refresh");
    const formTitle = document.getElementById("user-form-title");

    if (!tableBody || !form) {
        return;
    }

    const state = {
        users: [],
        editingId: null,
    };

    function setForm(user = null) {
        state.editingId = user?.id || null;
        form.user_id.value = user?.id || "";
        form.username.value = user?.username || "";
        form.full_name.value = user?.full_name || "";
        form.password.value = "";
        form.role.value = user?.role || "operator";
        form.is_active.checked = user ? Boolean(user.is_active) : true;
        formTitle.textContent = user ? `Cập nhật người dùng #${user.id}` : "Tạo người dùng mới";
    }

    function renderUsers() {
        if (!state.users.length) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5">
                        <div class="empty-state">
                            <div>
                                <h3>Chưa có người dùng nào</h3>
                                <p class="muted">Tạo tài khoản đầu tiên để bắt đầu.</p>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tableBody.innerHTML = state.users.map((user) => `
            <tr>
                <td><strong>${user.username}</strong></td>
                <td>${user.full_name}</td>
                <td><span class="pill ${user.role === "admin" ? "teal" : "gray"}">${user.role}</span></td>
                <td><span class="badge ${user.is_active ? "success" : "muted"}">${user.is_active ? "Đang bật" : "Đang khóa"}</span></td>
                <td>
                    <div class="button-row">
                        <button class="button secondary tiny" data-action="edit" data-id="${user.id}">Sửa</button>
                        <button class="button danger tiny" data-action="delete" data-id="${user.id}">Xóa</button>
                    </div>
                </td>
            </tr>
        `).join("");
    }

    async function loadUsers() {
        try {
            const data = await window.portalApi.get("/api/users");
            state.users = data.users || [];
            renderUsers();
        } catch (error) {
            window.portalApi.showNotice(feedback, error.message, "error");
        }
    }

    tableBody.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) {
            return;
        }

        const userId = Number(button.dataset.id);
        const user = state.users.find((item) => item.id === userId);
        if (!user) {
            return;
        }

        if (button.dataset.action === "edit") {
            setForm(user);
            window.portalApi.showNotice(feedback, `Đang chỉnh sửa tài khoản ${user.username}.`, "info");
            return;
        }

        if (button.dataset.action === "delete") {
            if (!window.confirm(`Xóa tài khoản ${user.username}?`)) {
                return;
            }
            try {
                await window.portalApi.delete(`/api/users/${userId}`);
                window.portalApi.showNotice(feedback, "Đã xóa người dùng.", "success");
                if (state.editingId === userId) {
                    setForm();
                }
                await loadUsers();
            } catch (error) {
                window.portalApi.showNotice(feedback, error.message, "error");
            }
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const payload = {
            username: form.username.value.trim(),
            full_name: form.full_name.value.trim(),
            password: form.password.value,
            role: form.role.value,
            is_active: form.is_active.checked,
        };

        const editing = Boolean(state.editingId);
        const url = editing ? `/api/users/${state.editingId}` : "/api/users";

        try {
            if (editing) {
                await window.portalApi.put(url, payload);
                window.portalApi.showNotice(feedback, "Đã cập nhật người dùng.", "success");
            } else {
                await window.portalApi.post(url, payload);
                window.portalApi.showNotice(feedback, "Đã tạo người dùng mới.", "success");
            }
            setForm();
            await loadUsers();
        } catch (error) {
            window.portalApi.showNotice(feedback, error.message, "error");
        }
    });

    resetButton.addEventListener("click", () => {
        setForm();
        window.portalApi.showNotice(feedback, "", "info");
    });

    refreshButton.addEventListener("click", loadUsers);

    setForm();
    loadUsers();
});
