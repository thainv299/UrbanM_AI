(function () {
    function buildHeaders(options) {
        const headers = new Headers(options.headers || {});
        if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
            headers.set("Content-Type", "application/json");
        }
        return headers;
    }

    async function request(url, options = {}) {
        const response = await fetch(url, {
            credentials: "same-origin",
            ...options,
            headers: buildHeaders(options),
        });

        const isJson = response.headers.get("content-type")?.includes("application/json");
        const payload = isJson ? await response.json() : null;

        if (!response.ok) {
            throw new Error(payload?.error || `Yêu cầu thất bại (${response.status})`);
        }

        return payload;
    }

    function showNotice(target, message, tone = "info") {
        if (!target) {
            return;
        }
        target.innerHTML = message
            ? `<div class="notice ${tone}">${message}</div>`
            : "";
    }

    function pillText(enabled, yesText = "Bật", noText = "Tắt") {
        return enabled ? yesText : noText;
    }

    function showToast(message, type = 'info', title = '', duration = 4500) {
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        const container = document.getElementById('notificationContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast-notification ${type}`;
        
        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || '●'}</div>
            <div class="toast-content">
                ${title ? `<div class="toast-title">${title}</div>` : ''}
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" type="button">✕</button>
        `;

        container.appendChild(toast);

        const closeBtn = toast.querySelector('.toast-close');
        const removeToast = () => {
            toast.classList.add('hide');
            setTimeout(() => toast.remove(), 300);
        };

        closeBtn.addEventListener('click', removeToast);
        
        if (duration > 0) {
            setTimeout(removeToast, duration);
        }

        return toast;
    }

    function readJsonFileToInput(fileInput, targetElementId) {
        const file = fileInput.files[0];
        if (!file) return;
        const target = document.getElementById(targetElementId) || document.querySelector(`textarea[name="${targetElementId}"]`);
        if (!target) return;
        
        const reader = new FileReader();
        reader.onload = function(e) {
            try {
                let content = JSON.parse(e.target.result);
                // Thích ứng với chuẩn JSON format Tkinter: {"points": [[x,y],...]}
                if (content && content.points) {
                    target.value = JSON.stringify(content.points);
                } else {
                    target.value = JSON.stringify(content);
                }
                showToast('Đã tải cấu hình vùng thành công', 'success');
            } catch (err) {
                console.error(err);
                showToast('Tệp JSON không hợp lệ!', 'error', 'Lỗi');
            }
            // Reset chuỗi để có thể nạp lại file đó
            fileInput.value = '';
        };
        reader.readAsText(file);
    }

    window.portalApi = {
        get: (url) => request(url, { method: "GET" }),
        post: (url, body) => request(url, { method: "POST", body: JSON.stringify(body) }),
        put: (url, body) => request(url, { method: "PUT", body: JSON.stringify(body) }),
        delete: (url) => request(url, { method: "DELETE" }),
        submitForm: (url, formData) => request(url, { method: "POST", body: formData }),
        showNotice,
        pillText,
        showToast,
        readJsonFileToInput,
    };
})();
