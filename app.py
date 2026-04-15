import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

# ---------------------------------------------------------------------------
# Path setup
# app.py nằm ở d:\UrbanM_AI\UrbanM_AI\ (project root)
# Các module nội bộ (core, database, presentation) nằm bên trong frontend/
# → Thêm frontend/ vào đầu sys.path để import không cần prefix "frontend."
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent          # d:\UrbanM_AI\UrbanM_AI\
FRONTEND_DIR = PROJECT_ROOT / "frontend"                # d:\UrbanM_AI\UrbanM_AI\frontend\

if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Import Clean Architecture Components
from frontend.core.config import SECRET_KEY
from frontend.database.sqlite_db import init_db
from frontend.presentation.container import container, templates
from frontend.presentation.web.auth_views import auth_router
from frontend.presentation.web.camera_views import camera_router
from frontend.presentation.web.dashboard_views import dashboard_router
from frontend.presentation.web.test_video_views import test_video_router
from frontend.presentation.web.user_views import user_router
from frontend.presentation.web.vehicle_views import vehicle_router
from frontend.presentation.web.violation_views import violation_router
from frontend.presentation.web.congestion_views import congestion_router


def create_app() -> FastAPI:
    # 1. Khởi tạo DB
    init_db()

    # 2. Tạo FastAPI app
    app = FastAPI(
        title="CityVision AI Portal",
        docs_url=None,  # Tắt auto docs nếu muốn bảo mật
        redoc_url=None
    )
    
    # 3. Middlewares
    # Before Request logic (Auth)
    @app.middleware("http")
    async def load_logged_in_user_middleware(request: Request, call_next):
        user_id = request.session.get("user_id")
        request.state.current_user = None
        
        if user_id:
            user = container.user_use_cases.user_repo.get_by_id(int(user_id))
            if user and user.is_active:
                request.state.current_user = user
            else:
                request.session.clear()
        
        response = await call_next(request)
        return response

    # Session Middleware (Outer layer)
    app.add_middleware(SessionMiddleware, secret_key=str(SECRET_KEY))

    # Inject Template context (Global)
    # FastAPI doesn't have a direct context processor, 
    # but we can enhance the TemplateResponse call or the templates object itself.
    # Here we add a global function to the templates environment.
    templates.env.globals["current_user_obj"] = lambda request: getattr(request.state, "current_user", None)
    # Re-map url_for to be more compatible with legacy templates if needed, 
    # but we already updated templates to use blueprint notation.

    # 4. Static Files — trỏ đến frontend/static/
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
    
    # Mount thư mục logs để phục vụ ảnh biển số và vi phạm
    LOGS_DIR = PROJECT_ROOT / "logs"
    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/logs", StaticFiles(directory=str(LOGS_DIR)), name="logs")

    # 5. Error Handlers
    @app.exception_handler(403)
    async def forbidden_exception_handler(request: Request, exc):
        return container.render_template(
            request,
            "error.html",
            {
                "page": "error",
                "status_code": 403,
                "title": "Không có quyền truy cập",
                "message": "Tài khoản hiện tại không được phép mở trang này.",
            }
        )

    @app.exception_handler(404)
    async def not_found_exception_handler(request: Request, exc):
        return container.render_template(
            request,
            "error.html",
            {
                "page": "error",
                "status_code": 404,
                "title": "Không tìm thấy nội dung",
                "message": "Đường dẫn bạn mở không tồn tại trong web portal.",
            }
        )


    # 6. Routers (Blueprints)
    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(user_router)
    app.include_router(camera_router)
    app.include_router(vehicle_router)
    app.include_router(violation_router)
    app.include_router(congestion_router)
    app.include_router(test_video_router)

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        reload=os.environ.get("RELOAD", "false").lower() == "true",
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )
