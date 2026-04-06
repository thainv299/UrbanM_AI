import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

# Thêm đường dẫn dự án vào PYTHONPATH nếu chưa có
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import Clean Architecture Components
from core.config import SECRET_KEY, MAX_CONTENT_LENGTH, APP_DIR
from infrastructure.database.sqlite_db import init_db
from presentation.container import container, templates
from presentation.web.auth_views import auth_router
from presentation.web.camera_views import camera_router
from presentation.web.dashboard_views import dashboard_router
from presentation.web.test_video_views import test_video_router
from presentation.web.user_views import user_router


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

    # 4. Static Files
    app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

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
    app.include_router(test_video_router)

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=False)
