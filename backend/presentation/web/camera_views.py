import cv2
import uuid
from pathlib import Path
from fastapi import APIRouter, Request, Depends, status, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from typing import Any, Dict, Optional
import io

from core.config import ALLOWED_VIDEO_EXTENSIONS, INPUTS_DIR, PROJECT_ROOT, DEFAULT_MODEL_PATH
from core.errors import AppError, NotFoundError
from presentation.container import container, templates
from presentation.middlewares.auth import login_required

camera_router = APIRouter()


@camera_router.get("/cameras", name="cameras.cameras_page")
async def cameras_page(request: Request, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    
    # Scan models
    models_dir = PROJECT_ROOT / "models"
    available_models = []
    if models_dir.exists():
        for f in models_dir.iterdir():
            if f.is_file() and f.suffix.lower() in [".pt", ".engine"]:
                available_models.append(f.name)
    available_models.sort()

    return container.render_template(
        request, 
        "cameras.html", 
        {
            "page": "cameras", 
            "available_models": available_models,
            "default_model_path": str(DEFAULT_MODEL_PATH)
        }
    )


@camera_router.get("/api/cameras")
async def api_list_cameras(user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    cameras = container.camera_use_cases.list_cameras()
    return {"ok": True, "cameras": [c.to_dict() for c in cameras]}


@camera_router.get("/api/cameras/{camera_id}")
async def api_get_camera(camera_id: int, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    try:
        camera = container.camera_use_cases.get_camera(camera_id)
        return {"ok": True, "camera": camera.to_dict()}
    except NotFoundError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Camera không tồn tại."})


@camera_router.post("/api/cameras/upload-source")
async def api_upload_camera_source(
    video_file: Optional[UploadFile] = File(None),
    upload_id: Optional[str] = Form(None),
    original_filename: Optional[str] = Form(None),
    user=Depends(login_required)
):
    if isinstance(user, RedirectResponse):
        return user

    import os
    import tempfile
    
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    
    if upload_id:
        # Handle chunked upload completion
        temp_dir = Path(tempfile.gettempdir()) / "video_uploads"
        temp_file = temp_dir / f"{upload_id}.part"
        if not temp_file.exists():
            return JSONResponse(status_code=400, content={"ok": False, "error": "Không tìm thấy dữ liệu upload."})
        
        filename = original_filename or "video.mp4"
        suffix = Path(filename).suffix.lower()
        target_path = INPUTS_DIR / f"{uuid.uuid4().hex}{suffix}"
        
        # Move file from temp to inputs
        import shutil
        shutil.move(str(temp_file), str(target_path))
        
    elif video_file and video_file.filename:
        # Handle direct upload
        suffix = Path(video_file.filename).suffix.lower()
        if suffix not in ALLOWED_VIDEO_EXTENSIONS:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Định dạng video không được hỗ trợ."})
            
        target_path = INPUTS_DIR / f"{uuid.uuid4().hex}{suffix}"
        try:
            content = await video_file.read()
            with target_path.open("wb") as handle:
                handle.write(content)
        except Exception:
            return JSONResponse(status_code=500, content={"ok": False, "error": "Không thể lưu file video."})
    else:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Không có file nào được gửi."})

    return {"ok": True, "path": str(target_path.resolve())}


@camera_router.post("/api/cameras")
async def api_create_camera(payload: Dict[str, Any], user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    try:
        created = container.camera_use_cases.create_camera(payload)
        return JSONResponse(status_code=status.HTTP_201_CREATED, content={"ok": True, "camera": created.to_dict()})
    except AppError as exc:
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.message})
    except Exception as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})


@camera_router.put("/api/cameras/{camera_id}")
async def api_update_camera(camera_id: int, payload: Dict[str, Any], user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    try:
        updated = container.camera_use_cases.update_camera(camera_id, payload)
        return {"ok": True, "camera": updated.to_dict()}
    except AppError as exc:
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.message})
    except Exception as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})


@camera_router.delete("/api/cameras/{camera_id}")
async def api_delete_camera(camera_id: int, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    try:
        container.camera_use_cases.delete_camera(camera_id)
        return {"ok": True}
    except AppError as exc:
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.message})
    except Exception as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})


@camera_router.get("/api/cameras/{camera_id}/snapshot")
async def api_camera_snapshot(camera_id: int, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
        
    try:
        camera = container.camera_use_cases.get_camera(camera_id)
    except NotFoundError:
        from core.utils import build_placeholder_frame
        return StreamingResponse(io.BytesIO(build_placeholder_frame("Không tìm thấy camera.")), media_type="image/jpeg")

    from core.utils import build_placeholder_frame, encode_jpeg, normalize_capture_source, prepare_snapshot_frame
    
    capture_source = normalize_capture_source(camera.stream_source)
    if capture_source is None:
        return StreamingResponse(
            io.BytesIO(build_placeholder_frame("Chưa cấu hình nguồn camera.", camera.name)),
            media_type="image/jpeg",
        )

    capture = cv2.VideoCapture(capture_source)
    try:
        success, frame = capture.read()
    finally:
        capture.release()

    if not success or frame is None:
        detail = camera.stream_source or "Nguồn camera trống."
        return StreamingResponse(
            io.BytesIO(build_placeholder_frame("Không đọc được hình ảnh camera.", detail)),
            media_type="image/jpeg",
        )

    prepared = prepare_snapshot_frame(frame, camera.to_dict())
    return StreamingResponse(io.BytesIO(encode_jpeg(prepared)), media_type="image/jpeg")
