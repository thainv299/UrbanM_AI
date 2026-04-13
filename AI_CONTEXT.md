# AI Agent Context — Hệ Thống Giám Sát Giao Thông Thông Minh (ITS)

> **Mục đích file**: Cung cấp ngữ cảnh nhanh cho AI coding agent, giúp hiểu toàn bộ kiến trúc, thuật toán, và dữ liệu trong dự án mà KHÔNG cần đọc từng file source code. Cập nhật lần cuối: 2026-04-10.

---

## 1. TỔNG QUAN DỰ ÁN

- **Tên**: UrbanM_AI — Hệ thống Giám sát Giao thông Đô thị Thông minh
- **Ngôn ngữ**: Python 3.x
- **Nền tảng**: FastAPI (web backend) + Tkinter (desktop GUI) + OpenCV (xử lý video)
- **CSDL**: SQLite (file `frontend/runtime/portal.db`)
- **Mô hình AI**: YOLOv26m (Ultralytics) + PaddleOCR
- **Tracker**: ByteTrack (`bytetrack.yaml`)
- **Cảnh báo**: Telegram Bot API (pyTeleBot + requests)
- **Entry points**:
  - `run_system.py` — Chạy đồng thời FastAPI (port 5000) + Tkinter GUI trên 2 thread
  - `main_api.py` — Chỉ chạy FastAPI server
  - `main.py` — Chỉ chạy desktop Tkinter app

---

## 2. CẤU TRÚC THƯ MỤC

```
e:\DATN_PROJECT\
├── main.py                    # Desktop app (Tkinter + OpenCV + YOLO + OCR)
├── main_api.py                # FastAPI entry point (legacy, dùng routers/)
├── run_system.py              # Launcher: chạy cả FastAPI + Tkinter
├── model_trainning.py         # Script huấn luyện YOLO
├── exportRT.py                # Script export model sang TensorRT (.engine)
├── .env                       # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
├── requirements.txt           # Dependencies
│
├── core/                      # Cấu hình hệ thống (dùng cho main_api.py)
│   ├── config.py              # Paths, ThreadPoolExecutor, Jinja2 templates
│   ├── security.py            # JWT authentication (get_user_by_id)
│   ├── exceptions.py          # HTTP exception handlers
│   └── utils.py               # Utility functions
│
├── modules/                   # Các module xử lý nghiệp vụ (dùng cho main.py)
│   ├── ocr/
│   │   ├── ocr_processor.py   # Pipeline OCR: perspective → CLAHE → PaddleOCR → regex
│   │   └── ocr_manager.py     # Quản lý OCR queue, voting, spatial memory
│   ├── parking/
│   │   ├── parking_logic.py   # State machine: MOVING→WAITING→VIOLATION→RECORDING_DONE
│   │   └── parking_manager.py # Quản lý vùng cấm đỗ, bằng chứng, Telegram alert
│   ├── traffic/
│   │   └── traffic_monitor.py # Đếm xe/người, tính occupancy & speed, 4 cấp tắc nghẽn
│   └── utils/
│       ├── alpr_logger.py           # Ghi log biển số → CSV + ảnh bằng chứng
│       ├── telegram_bot.py          # Gửi ảnh/video qua Telegram (requests)
│       ├── interactive_telegram_bot.py  # Bot tương tác có nút ACK (pyTeleBot)
│       ├── traffic_alert_manager.py # Debounce + snooze + escalation logic
│       └── common_utils.py          # ensure_dir, now_ts, load/save JSON
│
├── frontend/                  # Web application (Clean Architecture)
│   ├── app.py                 # FastAPI entry point (Clean Architecture)
│   ├── core/
│   │   ├── config.py          # Settings, DATABASE_PATH
│   │   ├── utils.py
│   │   └── errors.py
│   ├── database/
│   │   ├── sqlite_db.py       # DB init + CRUD functions
│   │   ├── sqlite_user_repo.py
│   │   └── sqlite_camera_repo.py
│   ├── domain/                # Clean Architecture: Business logic
│   │   ├── entities/
│   │   │   ├── user.py
│   │   │   ├── camera.py
│   │   │   └── job.py
│   │   └── repositories/
│   │       ├── user_repository.py
│   │       └── camera_repository.py
│   ├── application/           # Use cases
│   │   ├── use_cases/
│   │   │   ├── user_use_cases.py
│   │   │   ├── camera_use_cases.py
│   │   │   ├── dashboard_use_cases.py
│   │   │   └── job_use_cases.py
│   │   └── interfaces/
│   │       └── detection_interface.py
│   ├── infrastructure/        # External services
│   │   ├── file_system/
│   │   │   └── local_storage.py
│   │   └── ml/
│   │       ├── detection_bridge.py  # Headless detection pipeline
│   │       └── ocr_license_plate.py # License plate OCR service
│   ├── presentation/          # HTTP layer (Clean Architecture)
│   │   ├── container.py       # Dependency injection
│   │   ├── middlewares/
│   │   │   └── auth.py
│   │   └── web/
│   │       ├── auth_views.py
│   │       ├── dashboard_views.py
│   │       ├── camera_views.py
│   │       ├── user_views.py
│   │       ├── test_video_views.py
│   │       └── vehicle_views.py    # NEW: License plate logs
│   ├── services/
│   │   └── detection_bridge.py  # (old location, also exists in infrastructure/)
│   ├── templates/             # Jinja2 HTML templates
│   │   ├── base.html, dashboard.html, login.html
│   │   ├── cameras.html, users.html, test_video.html
│   │   └── error.html
│   ├── static/                # CSS, JS
│   ├── portal.db              # SQLite database (NEW: moved from runtime/)
│   └── runtime/               # uploaded videos, output videos
│       ├── inputs/
│       ├── outputs/
│       └── previews/
│
├── routers/                   # FastAPI route handlers (legacy, for main_api.py)
│   ├── web_views.py           # HTML page routes (old structure)
│   ├── api_users.py           # REST API: CRUD users
│   ├── api_cameras.py         # REST API: CRUD cameras
│   ├── api_jobs.py            # REST API: video detection jobs + MJPEG streaming
│   └── api_license_plates.py  # NEW: REST API for license plates
│
├── services/
│   ├── job_manager.py         # Background job runner (process_video → DB update)
│   └── camera_service.py      # Camera management service
│
├── layouts/                   # Saved ROI & no-parking polygons (JSON)
├── logs/                      # Runtime logs
│   ├── ALPR_log.csv           # License plate detection log
│   ├── plates/                # Evidence images (full frame + bounding box)
│   └── violations/            # Parking violation evidence (img + video + metadata JSON)
└── models/                    # YOLO model files (.pt, .engine)
```

---

## 3. YOLO MODEL — 7 LỚP ĐỐI TƯỢNG

```python
# main.py:21-24
class_names = {
    0: "Person",    1: "Bicycle",   2: "Car",
    3: "Motorcycle", 4: "License Plate", 5: "Bus", 6: "Truck"
}
```

- **Dataset huấn luyện**: `E:/DATN_code/Dataset/COCO_Balanced/dataset.yaml`
- **Model file**: `models/yolo26m.pt` (có thể export sang `.engine` cho TensorRT)
- **Confidence threshold**: `0.32`
- **Tracker**: `model.track(frame, persist=True, tracker="bytetrack.yaml")`
- **Frame skipping**: Xử lý YOLO mỗi 2 frame (`frame_count % 2`), frame còn lại dùng kết quả cũ
- **Target classes** (dùng khi detect): `["person", "car", "motorcycle", "license_plate", "bus", "truck"]` — **KHÔNG** filter bicycle

---

## 4. MODULE OCR — Pipeline Nhận Diện Biển Số

### 4.1 Kiến trúc
```
ocr_manager.py (Controller)          ocr_processor.py (Processing)
─────────────────────────            ─────────────────────────────
Queue(maxsize=3)                     get_plate_perspective()  ← Nắn góc
Worker thread (daemon)               preprocess_plate()       ← CLAHE
Voting (Counter + threshold=3)       run_ocr()               ← PaddleOCR
Spatial Memory (100px, 300 frames)   correct_plate_format()   ← Sửa lỗi VN
Grace Period (5 lost frames)         is_valid_vn_plate()      ← Regex filter
```

### 4.2 PaddleOCR Config
```python
PaddleOCR(use_angle_cls=False, det=True, lang='en', show_log=False)
```

### 4.3 Tham số quan trọng
| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `OCR_INTERVAL` | 4 | Chỉ gửi ảnh OCR mỗi 4 frame |
| `VOTE_THRESHOLD` | 3 | Cần ≥3 kết quả trùng nhau để confirm |
| `MAX_LOST_FRAMES` | 5 | Giữ hiển thị biển số khi tracker mất dấu |
| `pad` | 2px | Padding khi crop biển số từ frame |
| Biển vuông (w/h < 1.8) | 240×180 | Xe máy 2 dòng |
| Biển dài (w/h ≥ 1.8) | 480×120 | Ô tô 1 dòng |

### 4.4 Regex biển số VN
```python
pattern = r"^[1-9][0-9][A-Z][0-9]{4,5}$"
```

### 4.5 Correct Plate Format — Bảng sửa lỗi OCR
```python
char_to_num = {'O':'0', 'Q':'0', 'I':'1', 'Z':'2', 'S':'5', 'G':'6', 'B':'8', 'A':'4'}
num_to_char = {'0':'D', '8':'B', '4':'A', '5':'S', '2':'Z'}
# Rule: 2 ký tự đầu = số (mã tỉnh), ký tự 3 = chữ (sê-ri), còn lại = số
```

### 4.6 Lọc biển số hợp lệ
Chỉ xử lý OCR cho biển số mà **tâm (cx, cy) nằm bên trong bounding box** của xe lớn (car/bus/truck). Loại bỏ biển số có kích thước quá nhỏ (w ≤ 20 hoặc h ≤ 10).

### 4.7 Output
- File log: `logs/ALPR_log.csv` (columns: Time, Frame, Plate, Full_Frame_Image_Path)
- Ảnh bằng chứng: `logs/plates/{YYYY}/{MM}/{DD}/{biển_số}_{HH-MM-SS}.jpg`
- Session tracking: `disappear_threshold=1800` frames — nếu biển số đã ghi log mà vẫn xuất hiện liên tục thì không ghi lại.

---

## 5. MODULE TRAFFIC MONITOR — Giám Sát Mật Độ

### 5.1 Cơ chế hoạt động
- Đếm `vehicle_count` và `people_count` **hiện diện** trong ROI mỗi frame (KHÔNG đếm ra/vào)
- Tính **Occupancy%** bằng kỹ thuật Mask Overlap (ROI mask ∩ vehicles mask → pixel ratio)
- Tính **Average Speed** (px/s) dựa trên track_history (lưu 2s gần nhất)
- Lọc nhiễu: bỏ box có diện tích > 30% ROI

### 5.2 Ngưỡng 4 cấp tắc nghẽn
```python
CONG_COUNT_THR = 10           # Số xe tối thiểu → Level 1
CONG_PEOPLE_THR = 30          # Số người tối thiểu → Level 1
CONG_AREA_PERCENT_THR = 40.0  # % diện tích tối thiểu → Level 2
CONG_SPEED_THR = 10.0         # Vận tốc tối đa (px/s) → Level 3
MAX_VEHICLE_AREA_RATIO = 0.3  # Bỏ box nhiễu > 30% ROI
```

| Level | Điều kiện | Trạng thái |
|-------|-----------|------------|
| 0 | Dưới ngưỡng count VÀ occupancy < 40% | Thông thoáng |
| 1 | Count ≥ 10 xe HOẶC ≥ 30 người, occupancy < 40% | Đông đúc |
| 2 | Occupancy ≥ 40% VÀ speed > 10 px/s | Rất đông |
| 3 | Occupancy ≥ 40% VÀ speed ≤ 10 px/s | TẮC NGHẼN |

---

## 6. MODULE PARKING — Phát Hiện Đỗ Xe Trái Phép

### 6.1 State Machine (parking_logic.py)
```
MOVING (0) ──speed < thr──→ WAITING (1) ──frames ≥ stop_frames──→ VIOLATION (2) ──record done──→ RECORDING_DONE (3)
     ↑                           │
     └──grace > 10 frames────────┘
```

### 6.2 Tham số mặc định
| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `stop_seconds` | 30 | Thời gian đỗ tối đa (giây) trước khi vi phạm |
| `move_thr_px` | 10.0 | Ngưỡng pixel/frame để coi là đứng yên |
| `cooldown_seconds` | 30.0 | Thời gian chờ giữa 2 lần cảnh báo cùng xe |
| Grace count | 10 frames | Ân hạn trước khi chuyển từ WAITING → MOVING |
| History buffer | 10 positions | Số vị trí gần nhất để tính tốc độ trung bình |

### 6.3 Đối tượng áp dụng
- CHỈ xét: `car`, `bus`, `truck`
- KHÔNG xét: `motorcycle`, `bicycle`, `person`

### 6.4 Ghost Tracks & Spatial Re-ID
- Xe mất dấu > 1s → đẩy vào `ghost_tracks` (giữ logic state + waiting data)
- ID mới xuất hiện gần ghost (< 60px hoặc 2× move_thr) → nối ghép, khôi phục trạng thái
- Ghost hết hạn sau 10s

### 6.5 Bằng chứng vi phạm (output)
```
logs/violations/{plate_or_ID}/EVT_{timestamp}_{track_id}/
├── img_T0.jpg           # Ảnh lúc bắt đầu đỗ
├── img_T1.jpg           # Ảnh lúc xác nhận vi phạm
├── combined_alert.jpg   # Ghép T0+T1 kèm biển số
├── video_record.mp4     # Video 15s (5s buffer + 10s sau vi phạm)
└── evidence.json        # Metadata (track_id, plate, timestamps)
```

### 6.6 Cảnh báo Telegram
1. Khi WAITING bắt đầu: gửi ảnh T0 + caption "⚠️ CẢNH BÁO"
2. Khi VIOLATION xác nhận: gửi ảnh ghép + video bằng chứng "🚨 VI PHẠM CHỐT"

---

## 7. TRAFFIC ALERT MANAGER — Hệ Thống Cảnh Báo Tắc Nghẽn

### 7.1 Kiến trúc Debounce + Snooze
```
Raw Level → Debounce (1s) → Confirmed Level → Alert Logic → Telegram
                                                  ↓
                                        Escalation / Timer expired
                                                  ↓
                                        Trigger + Snooze timer
```

### 7.2 Thời gian snooze
| Level | Chưa ACK (giây) | Đã ACK (giây) |
|-------|-----------------|----------------|
| 1 | 300 (5 phút) | 900 (15 phút) |
| 2 | 60 (1 phút) | 600 (10 phút) |
| 3 | 30 (30 giây) | 300 (5 phút) |

### 7.3 Reset hoàn toàn
Đường vắng **liên tục 5 giây** (`TRUE_CLEAR_SECONDS`) → reset `last_alert_level` và `snooze_until`

### 7.4 ACK channels
- **Bàn phím**: Nhấn 'A' trên cửa sổ OpenCV
- **Telegram**: Nhấn nút "Xác nhận ✅" trên tin nhắn bot

---

## 8. DATABASE SCHEMA (SQLite)

### 8.1 Vị trí và initialization
- **Đường dẫn**: `frontend/portal.db` (cũ: `frontend/runtime/portal.db`)
- **Init**: `frontend/database/sqlite_db.py` → `init_db()` tạo bảng + default admin user
- **CRUD functions**: Tất cả nằm trong file này

### 8.2 Bảng dữ liệu (sử dụng tiếng Việt)

#### Bảng 1: Quản lý người dùng
```sql
CREATE TABLE IF NOT EXISTS nguoi_dung (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ten_dang_nhap TEXT NOT NULL UNIQUE,           -- username
    ho_ten TEXT NOT NULL,                         -- full_name
    mat_khau_hash TEXT NOT NULL,                  -- password_hash (werkzeug.security)
    vai_tro TEXT NOT NULL DEFAULT 'operator',     -- role: 'admin' or 'operator'
    trang_thai_hoat_dong INTEGER NOT NULL DEFAULT 1,  -- is_active (0/1)
    ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ngay_cap_nhat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Default admin: username="admin", password="Admin@123"
```

#### Bảng 2: Quản lý camera
```sql
CREATE TABLE IF NOT EXISTS camera (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ten_camera TEXT NOT NULL UNIQUE,              -- camera_name
    nguon_phat TEXT,                              -- stream_source (rtsp://... or file path)
    mo_ta TEXT,                                   -- description
    toa_do_vung_chon TEXT,                        -- roi_points (JSON)
    toa_do_cam_do TEXT,                           -- no_parking_points (JSON)
    bat_phat_hien_un_tac INTEGER NOT NULL DEFAULT 1,        -- enable_congestion
    bat_phat_hien_do_sai INTEGER NOT NULL DEFAULT 1,        -- enable_illegal_parking
    bat_phat_hien_bien_so INTEGER NOT NULL DEFAULT 1,       -- enable_license_plate (NEW)
    trang_thai_hoat_dong INTEGER NOT NULL DEFAULT 1,        -- is_active
    ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ngay_cap_nhat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

#### Bảng 3: Thống kê giao thông
```sql
CREATE TABLE IF NOT EXISTS thong_ke_giao_thong (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_camera INTEGER NOT NULL,                   -- camera_id
    so_luong_xe INTEGER NOT NULL DEFAULT 0,       -- vehicle_count
    ngay_ghi_nhan TEXT NOT NULL,                  -- recorded_date (YYYY-MM-DD)
    ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_camera) REFERENCES camera(id),
    UNIQUE(id_camera, ngay_ghi_nhan)
);
```

#### Bảng 4: Vi phạm đỗ xe
```sql
CREATE TABLE IF NOT EXISTS vi_pham_do_xe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_camera INTEGER NOT NULL,                   -- camera_id
    bien_so TEXT,                                 -- license_plate
    thoi_gian_vi_pham TEXT NOT NULL,              -- violation_time (ISO format)
    thoi_gian_do_giay INTEGER NOT NULL DEFAULT 0, -- duration_seconds
    duong_dan_anh TEXT,                           -- frame_path (evidence image)
    da_giai_quyet INTEGER NOT NULL DEFAULT 0,     -- is_resolved (0/1)
    ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_camera) REFERENCES camera(id)
);
```

#### Bảng 5: Nhật ký tắc nghẽn
```sql
CREATE TABLE IF NOT EXISTS nhat_ky_un_tac (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_camera INTEGER NOT NULL,                   -- camera_id
    muc_do_un_tac INTEGER NOT NULL DEFAULT 1,     -- congestion_level (1-3)
    thoi_gian_bat_dau TEXT NOT NULL,              -- start_time (ISO format)
    thoi_gian_ket_thuc TEXT,                      -- end_time (ISO format, nullable)
    thoi_gian_keo_dai_giay INTEGER DEFAULT 0,     -- duration_seconds
    ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_camera) REFERENCES camera(id)
);
```

#### Bảng 6: Biển số phát hiện (NEW)
```sql
CREATE TABLE IF NOT EXISTS bien_so_phat_hien (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bien_so TEXT NOT NULL,                        -- license_plate
    ngay_phat_hien TEXT NOT NULL,                 -- detection_date (YYYY-MM-DD)
    so_lan_phat_hien INTEGER NOT NULL DEFAULT 1,  -- detection_count
    do_chinh_xac_tb REAL DEFAULT 0.0,             -- avg_confidence
    duong_dan_anh TEXT,                           -- image_paths (JSON list or comma-separated)
    ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ngay_cap_nhat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(bien_so, ngay_phat_hien)
);
```

#### Bảng 7: Lịch sử phương tiện (NEW)
```sql
CREATE TABLE IF NOT EXISTS lich_su_phuong_tien (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_camera INTEGER DEFAULT 0,                  -- camera_id
    bien_so_xe TEXT,                              -- license_plate
    loai_xe TEXT,                                 -- vehicle_type (car, motorcycle, etc.)
    thoi_gian_di_qua TEXT NOT NULL,               -- passed_time (ISO format)
    ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Lưu lại lịch sử các xe đã đi qua camera (cải thiện hơn vehicle_logs cũ)
```

### 8.3 CRUD Functions (sqlite_db.py)
- `get_total_vehicle_count()` → Tổng số xe
- `get_illegal_parking_violations()` → Danh sách vi phạm chưa giải quyết
- `get_congestion_count()` → Số sự kiện tắc nghẽn hôm nay
- `log_vehicle_count(camera_id, count, recorded_date)` → Ghi số xe
- `log_parking_violation(camera_id, license_plate, violation_time, duration, frame_path)` → Ghi vi phạm
- `log_congestion(camera_id, level, start_time)` → Ghi tắc nghẽn
- `log_passed_vehicle(camera_id, bien_so_xe, loai_xe, thoi_gian_di_qua)` → Ghi lịch sử phương tiện (NEW)
- `log_detected_license_plate(license_plate, detection_count, avg_confidence, image_paths)` → Ghi biển số (NEW)
- `list_detected_license_plates(limit, offset)` → Lấy danh sách biển số (NEW)
- `list_license_plates_by_date(detected_date)` → Lấy biển số theo ngày (NEW)

---

## 9. WEB APPLICATION (FastAPI)

### 9.1 2 Cách chạy FastAPI
- **Option A** (Clean Architecture): `frontend/app.py` → Khuyên dùng
- **Option B** (Legacy): `main_api.py` + `routers/` → Cũ nhưng còn dùng được

### 9.2 Clean Architecture (frontend/app.py)
```
Presentation Layer (web views) → Application Layer (use_cases) → Domain Layer (entities, repos) → Infrastructure (DB, ML)
```

**Routes (Clean Architecture - frontend/app.py)**:
- `auth_router` (auth_views.py)
  - `GET /login` → Trang đăng nhập
  - `POST /login` → Xử lý login
  - `GET /logout` → Logout

- `dashboard_router` (dashboard_views.py)
  - `GET /dashboard` → Trang tổng quan

- `camera_router` (camera_views.py)
  - `GET /cameras` → Quản lý camera
  - REST API cho CRUD camera

- `user_router` (user_views.py)
  - `GET /users` → Quản lý người dùng
  - REST API cho CRUD user

- `test_video_router` (test_video_views.py)
  - `GET /test-video` → Trang test video
  - REST API cho job management
  - `GET /api/test-jobs/{id}/stream` → MJPEG streaming

- `vehicle_router` (vehicle_views.py) **NEW**
  - `GET /vehicles` → Xem lịch sử phương tiện
  - REST API cho license plates

### 9.3 Legacy Routes (main_api.py + routers/)
```python
# main_api.py imports:
from routers import web_views, api_users, api_cameras, api_jobs, api_license_plates

app.include_router(web_views.router)
app.include_router(api_users.router)
app.include_router(api_cameras.router)
app.include_router(api_jobs.router)
app.include_router(api_license_plates.router)  # NEW
```

**Routes (Legacy)**:
| Route | Method | Mô tả |
|-------|--------|-------|
| `/api/license-plates` | GET | Lấy danh sách biển số (limit, offset) |
| `/api/license-plates/date/{detected_date}` | GET | Lấy biển số theo ngày (YYYY-MM-DD) |
| `/api/license-plates` | POST | Ghi lại một biển số phát hiện |
| `/results/{filename}` | GET | Download kết quả video (REMOVED: no output file) |
| `/api/test-jobs` | POST | Submit detection job (NEW: BytesIO stream input) |
| `/api/test-jobs/{id}` | GET | Lấy thông tin job (NEW: result_url=None) |
| `/api/test-jobs/{id}/stream` | GET | MJPEG streaming thực tế (real-time frame) |
| `/api/test-jobs/{id}/abort` | POST | Hủy job |

**REMOVED Endpoints**:
- ❌ `/job-sources/{job_id}` — Không cần (stream-only, no input file storage)

### 9.4 Detection Bridge (frontend/services/detection_bridge.py)
- Phiên bản **headless** (không GUI) của pipeline detection — **Đã tích hợp đầy đủ OCR**
- **Hỗ trợ stream input** từ BytesIO hoặc file path
  - `input_stream`: BytesIO object (video bytes từ upload, không lưu file)
  - `input_path`: Path string (backward compat, legacy)
  - `input_ext`: File extension (.mp4, .avi, etc.)
  - Video tạm decode từ BytesIO → temp file → xử lý → cleanup
- Bỏ cv2.VideoWriter → không ghi output video vào disk (stream-only)
- Dùng cho web: `process_video(input_stream=bytes_io, input_ext='.mp4', output_path=None, settings, progress_callback)`
- **Hỗ trợ đầy đủ**: congestion detection, illegal parking, **OCR nhận diện ký tự biển số** (PaddleOCR + OCRManager + ALPRLogger)
- OCR pipeline giống hệt `main.py`: perspective → CLAHE → PaddleOCR → voting → regex → ghi log CSV + ảnh bằng chứng
- Tham số `enable_ocr=True` để bật/tắt OCR (mặc định bật)
- Trả về summary dict: `max_vehicle_count`, `max_people_count`, `ocr_confirmed_plates` (list biển số), `ocr_confirmed_plate_count`, `parking_violation_ids`, `output_path=None`

### 9.5 Job Manager (services/job_manager.py)
- ThreadPoolExecutor(max_workers=1) — chạy 1 job tại 1 thời điểm
- **NEW**: Nhận video stream (BytesIO) thay vì file path
  - Signature: `run_detection_job(job_id, video_stream: BytesIO, file_ext, output_filename, settings)`
  - Backward compat: vẫn support `input_path: str` (dùng cho legacy)
- Sau khi job hoàn thành → xóa file tạm + **KHÔNG** lưu output file
- Summary trả về: processed frames, max counts, traffic_level, violations, BUT `output_path=None`
- Hỗ trợ abort job (đặt status="aborted")

---

## 10. CẤU HÌNH & ENVIRONMENT

```env
TELEGRAM_BOT_TOKEN=<bot_token>
TELEGRAM_CHAT_ID=<chat_id>
```

### Paths quan trọng
| Biến | Giá trị |
|------|---------|
| `PROJECT_ROOT` | `e:\DATN_PROJECT` |
| `APP_DIR` | `frontend/` |
| `DB_PATH` | `frontend/portal.db` **(cập nhật)** |
| `DEFAULT_MODEL_PATH` | `models/best.pt` |
| `INPUTS_DIR` | `frontend/runtime/inputs/` |
| `OUTPUTS_DIR` | `frontend/runtime/outputs/` |
| `PREVIEWS_DIR` | `frontend/runtime/previews/` |

---

## 11. LUỒNG DỮ LIỆU CHÍNH (DATA FLOW)

```
Camera/Video → YOLO26m.track(ByteTrack) → Bounding Boxes + Track IDs
                                              │
              ┌───────────────────────────────┼───────────────────────────┐
              ↓                               ↓                          ↓
    TrafficMonitor                    ParkingManager                 OCRManager
    - Đếm xe/người                    - State machine               - Crop biển số
    - Occupancy (mask)                - Ghost re-ID                 - Perspective transform
    - Speed (px/s)                    - Video evidence              - CLAHE + PaddleOCR
    - 4 cấp tắc nghẽn                - Telegram alert              - Voting (Counter)
              ↓                               ↓                     - Regex validate
    TrafficAlertManager               logs/violations/              - correct_plate_format
    - Debounce + Snooze                                                    ↓
    - Telegram alert                                               ALPRLogger
                                                                   - logs/ALPR_log.csv
                                                                   - logs/plates/*.jpg
```

---

## 12. LƯU Ý QUAN TRỌNG CHO AI AGENT

### Kiến trúc & Data Flow
1. **2 pipeline song song** (cùng logic OCR):
   - Desktop (main.py): Tkinter GUI + OCR text recognition
   - Web (frontend/app.py hoặc main_api.py): Headless detection, **ĐÃ CÓ đầy đủ OCR text recognition** (frontend/services/detection_bridge.py)

2. **Clean Architecture được áp dụng trong Frontend**:
   - Presentation Layer: web views (auth, dashboard, camera, user, test_video, vehicle views)
   - Application Layer: use_cases (login, search, create camera, etc.)
   - Domain Layer: entities (User, Camera, Job) + repositories (clean interfaces)
   - Infrastructure Layer: DB access (sqlite_db.py), ML services (detection_bridge.py, ocr_license_plate.py)

3. **Database**:
   - Vị trí: `frontend/portal.db` (KHÔNG phải runtime/ subdirectory)
   - Các bảng sử dụng tiếng Việt
   - Có 2 bảng mới: `bien_so_phat_hien`, `lich_su_phuong_tien`
   - KHÔNG có bảng `traffic_flows`: Traffic data chỉ real-time

### Algorithm & Detection Details
4. **Không có counting line**: Hệ thống đếm xe **hiện diện**, KHÔNG đếm ra/vào
5. **Bicycle có trong model** nhưng KHÔNG nằm trong `target_classes` filter → bị bỏ qua khi detect
6. **OCR chỉ xử lý biển số nằm trong xe lớn** (car/bus/truck), xe máy KHÔNG OCR
7. **Parking chỉ xét car/bus/truck**, KHÔNG xét motorcycle/bicycle/person
8. **Grace period & Ghost tracks**: Cơ chế duy trì track ByteTrack mất dấu tạm thời

### Configuration & Deployment
9. **Model**: Web dùng `models/best.pt`, Desktop người dùng tự chọn qua GUI
10. **Telegram credentials** nằm trong `.env` (KHÔNG commit lên git)
11. **Video streaming**: Web dùng MJPEG streaming qua `/api/test-jobs/{id}/stream`
12. **API License Plates** (NEW): `/api/license-plates` có 3 endpoints GET/POST
13. **Job Manager**: ThreadPoolExecutor(max_workers=1) — chỉ 1 job cùng lúc
14. **Session-based auth**: FastAPI sử dụng SessionMiddleware với secret key

### Cách chạy
15. **Desktop**: `python run_system.py` hoặc `python main.py` (Tkinter + detection modules)
16. **Web (Clean Architecture)**: `python -m uvicorn frontend.app:app --host 0.0.0.0 --port 5000` (khuyên dùng)
17. **Web (Legacy)**: `python main_api.py` (sử dụng routers/, cũ hơn)
18. **Stream-only Processing** (NEW): Upload → BytesIO → Temp file → Process → Stream MJPEG → Delete temp → No output file saved

---

## 13. STREAM-ONLY PROCESSING MODEL (NEW - 2026-04-10)

### Refactored Test Video Feature
**Workflow**:
```
1. User uploads video file
   ↓
2. POST /api/test-jobs → Read bytes (NO DISK SAVE)
   ↓ (BytesIO in memory)
3. Backend creates SHORT-LIVED temp file
   ↓
4. process_video(input_stream, output_path=None)
   ↓ (Frame-by-frame YOLO detection)
5. Each frame: JPEG encoded → job["latest_frame"]
   ↓
6. GET /api/test-jobs/{id}/stream (MJPEG)
   ↓ (Frontend <img> tag receives stream)
7. Processing complete → Cleanup temp file
   ↓
8. Return summary dict (output_path=None)
   ↓
(RESULT: No video files in runtime/ folder)
```

### Key Changes
| Component | Old | New |
|-----------|-----|-----|
| Input handling | Save to `INPUTS_DIR` | BytesIO stream (temp file) |
| Output video | Write to `OUTPUTS_DIR` | None (stream only) |
| /job-sources endpoint | Serve input video | REMOVED |
| /results endpoint | Download output MP4 | Returns 404 (no output) |
| Streaming | MJPEG from disk | MJPEG from memory |
| UI preview boxes | 2 (input + stream) | 1 (stream only) |
| Dependencies | OpenCV only | + PyAV (for stream), + tempfile |

### Benefits
✅ No input/output disk I/O
✅ Real-time frame streaming
✅ Minimal storage footprint
✅ Clean memory model (1 frame buffered)
✅ Faster job startup (no file I/O overhead)

### Implementation Files Modified
- `routers/api_jobs.py`: Skip file save, pass BytesIO
- `services/job_manager.py`: Accept stream, call process_video(input_stream, output_path=None)
- `frontend/services/detection_bridge.py`: Support BytesIO + temp file + cleanup
- `requirements.txt`: Add `av` (PyAV)
- `frontend/templates/test_video.html`: Update description
- `AI_CONTEXT.md`: Document changes
