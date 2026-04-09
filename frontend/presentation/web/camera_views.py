import cv2
from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from typing import Any, Dict, Optional
import io

from core.errors import AppError, NotFoundError
from presentation.container import container, templates
from presentation.middlewares.auth import login_required

camera_router = APIRouter()


@camera_router.get("/cameras", name="cameras.cameras_page")
async def cameras_page(request: Request, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    return container.render_template(request, "cameras.html", {"page": "cameras"})


@camera_router.get("/api/cameras")
async def api_list_cameras(user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    cameras = container.camera_use_cases.list_cameras()
    return {"ok": True, "cameras": [c.to_dict() for c in cameras]}


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
