// ROI Drawing Tool - Separate file to avoid syntax issues


window.roiDrawingTool = {
    modal: null,
    canvas: null,
    targetField: null,
    points: [],
    firstFrame: null,
    isDirty: false,
    keydownHandler: null,
    canvasClickHandler: null,
    canvasContextMenuHandler: null,

    init() {
        this.modal = document.getElementById("roi-drawing-modal");
        this.canvas = document.getElementById("roi-canvas");

        if (!this.modal || !this.canvas) {
            console.error("❌ Không tìm thấy Modal hoặc Canvas trong DOM!");
            return;
        }
    },

    openModal(targetFieldId, firstFrameData) {


        this.targetField = targetFieldId;
        this.points = [];
        this.firstFrame = firstFrameData;
        this.isDirty = false;

        // Set canvas size
        const img = new Image();
        img.onload = () => {
            const maxWidth = Math.min(800, window.innerWidth - 40);
            this.canvas.width = maxWidth;
            this.canvas.height = (maxWidth / img.width) * img.height;
            this.drawCanvas();
        };
        img.onerror = () => {
            console.error("❌ Lỗi tải ảnh!");
        };
        img.src = firstFrameData;

        this.modal.style.display = "flex";
        this.setupCanvasListeners();
    },

    closeModal() {
        this.modal.style.display = "none";
        this.points = [];
        this.firstFrame = null;
        this.removeCanvasListeners();
    },

    confirmPoints() {
        if (this.points.length < 3) {
            alert("Cần vẽ ít nhất 3 điểm!");
            return;
        }
        const el = document.getElementById(this.targetField);
        if (el) {
            el.value = JSON.stringify(this.points);
        }
        this.closeModal();
    },

    setupCanvasListeners() {

        this.canvasClickHandler = (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const x = Math.round((e.clientX - rect.left) * (this.canvas.width / rect.width));
            const y = Math.round((e.clientY - rect.top) * (this.canvas.height / rect.height));
            this.points.push([x, y]);
            this.drawCanvas();
        };

        this.canvasContextMenuHandler = (e) => {
            e.preventDefault();
            this.points = [];
            this.drawCanvas();
        };

        this.keydownHandler = (e) => {
            if (e.key === "Enter") {
                this.confirmPoints();
            } else if (e.key === "Escape") {
                this.closeModal();
            } else if (e.ctrlKey && e.key === "z") {
                e.preventDefault();
                if (this.points.length > 0) {
                    this.points.pop();
                    this.drawCanvas();
                }
            }
        };

        this.canvas.addEventListener("mousedown", this.canvasClickHandler);
        this.canvas.addEventListener("contextmenu", this.canvasContextMenuHandler);
        document.addEventListener("keydown", this.keydownHandler);
    },

    removeCanvasListeners() {
        if (this.canvasClickHandler) {
            this.canvas.removeEventListener("mousedown", this.canvasClickHandler);
            this.canvasClickHandler = null;
        }
        if (this.canvasContextMenuHandler) {
            this.canvas.removeEventListener("contextmenu", this.canvasContextMenuHandler);
            this.canvasContextMenuHandler = null;
        }
        if (this.keydownHandler) {
            document.removeEventListener("keydown", this.keydownHandler);
            this.keydownHandler = null;
        }
    },

    drawCanvas() {
        const ctx = this.canvas.getContext("2d");
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw background image
        if (this.firstFrame) {
            const img = new Image();
            img.onload = () => {
                ctx.drawImage(img, 0, 0, this.canvas.width, this.canvas.height);
                this.drawOverlay(ctx);
            };
            img.src = this.firstFrame;
        } else {
            this.drawOverlay(ctx);
        }
    },

    drawOverlay(ctx) {
        // Draw polygon
        if (this.points.length > 0) {
            ctx.fillStyle = "rgba(0, 255, 0, 0.2)";
            ctx.strokeStyle = "#00ff00";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(this.points[0][0], this.points[0][1]);
            for (let i = 1; i < this.points.length; i++) {
                ctx.lineTo(this.points[i][0], this.points[i][1]);
            }
            ctx.closePath();
            ctx.stroke();
            ctx.fill();

            // Draw points
            ctx.fillStyle = "#ff0000";
            for (let point of this.points) {
                ctx.beginPath();
                ctx.arc(point[0], point[1], 5, 0, 2 * Math.PI);
                ctx.fill();
            }

            // Draw point count
            ctx.fillStyle = "#fff";
            ctx.font = "14px Arial";
            ctx.fillText("Điểm: " + this.points.length, 10, 25);
        }
    }
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    window.roiDrawingTool.init();
}



