import os
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor

# ---------------------------------------------------------------------------
# Đường dẫn dự án
# backend/core/config.py → parent.parent = backend/ → parent = PROJECT_ROOT
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # d:\UrbanM_AI\
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Thư mục thực thi
INPUTS_DIR = PROJECT_ROOT / "runtime" / "inputs"
OUTPUTS_DIR = PROJECT_ROOT / "runtime" / "outputs"
PREVIEWS_DIR = PROJECT_ROOT / "runtime" / "previews"

# Cấu hình file / ML
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".mpeg", ".mpg"}
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "best.pt"

# Cấu hình người dùng
VALID_ROLES = {"admin", "operator"}

# Security
SECRET_KEY = os.environ.get("CROWD_PORTAL_SECRET", "crow-detection-web-secret")
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB

# SQL
DATABASE_PATH = PROJECT_ROOT / "portal.db"

from fastapi.templating import Jinja2Templates

INPUTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))

# Khởi tạo executor và dictionary quản lý threads toàn cục
executor = ThreadPoolExecutor(max_workers=1)
job_lock = threading.Lock()
jobs = {}
