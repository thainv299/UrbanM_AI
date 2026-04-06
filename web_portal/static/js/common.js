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

    window.portalApi = {
        get: (url) => request(url, { method: "GET" }),
        post: (url, body) => request(url, { method: "POST", body: JSON.stringify(body) }),
        put: (url, body) => request(url, { method: "PUT", body: JSON.stringify(body) }),
        delete: (url) => request(url, { method: "DELETE" }),
        submitForm: (url, formData) => request(url, { method: "POST", body: formData }),
        showNotice,
        pillText,
    };
})();
