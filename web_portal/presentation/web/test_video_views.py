import io
import uuid
import json
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, status, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse, FileResponse
from pathlib import Path

from core.config import ALLOWED_VIDEO_EXTENSIONS, DEFAULT_MODEL_PATH
from core.errors import AppError, NotFoundError, ValidationError
from core.utils import build_placeholder_frame, resolve_path
from presentation.container import container, templates
from presentation.middlewares.auth import login_required

test_video_router = APIRouter()


def _parse_polygon(value: Any) -> Optional[list]:
    if value in (None, "", []):
        return None
    if isinstance(value, str):
        try:
            data = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValidationError("Polygon JSON không hợp lệ.") from exc
    else:
        data = value
    if not isinstance(data, list):
        raise ValidationError("Polygon phải là một mảng điểm.")
    normalized = []
    for point in data:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValidationError("Mỗi điểm polygon phải có đúng 2 tọa độ.")
        normalized.append([int(point[0]), int(point[1])])
    if normalized and len(normalized) < 3:
        raise ValidationError("Polygon cần tối thiểu 3 điểm.")
    return normalized or None


def _build_test_settings(form_data: Dict[str, Any], camera: Any) -> Dict[str, Any]:
    model_path_text = str(form_data.get("model_path", "")).strip() or str(DEFAULT_MODEL_PATH)
    model_path = resolve_path(model_path_text)
    if not model_path.exists():
        raise ValidationError(f"Không tìm thấy model: {model_path}")

    roi_value = form_data.get("roi_points")
    parking_value = form_data.get("no_parking_points")

    roi_points = _parse_polygon(roi_value) if roi_value not in (None, "") else None
    no_parking_points = _parse_polygon(parking_value) if parking_value not in (None, "") else None

    if camera is not None:
        if roi_points is None:
            roi_points = camera.roi_points
        if no_parking_points is None:
            no_parking_points = camera.no_parking_points

    enable_congestion = True
    if "enable_congestion" in form_data:
        val = form_data.get("enable_congestion")
        enable_congestion = str(val).lower() in {"1", "true", "yes", "on"}
    elif camera:
        enable_congestion = camera.enable_congestion

    enable_illegal_parking = True
    if "enable_illegal_parking" in form_data:
        val = form_data.get("enable_illegal_parking")
        enable_illegal_parking = str(val).lower() in {"1", "true", "yes", "on"}
    elif camera:
        enable_illegal_parking = camera.enable_illegal_parking

    enable_license_plate = True
    if "enable_license_plate" in form_data:
        val = form_data.get("enable_license_plate")
        enable_license_plate = str(val).lower() in {"1", "true", "yes", "on"}
    elif camera:
        enable_license_plate = camera.enable_license_plate

    def _parse_float(val, d):
        try:
            return float(val) if val not in (None, "") else d
        except: return d
    def _parse_int(val, d):
        try:
            return int(val) if val not in (None, "") else d
        except: return d

    return {
        "model_path": str(model_path),
        "confidence_threshold": _parse_float(form_data.get("confidence_threshold"), 0.32),
        "enable_congestion": enable_congestion,
        "enable_illegal_parking": enable_illegal_parking,
        "enable_license_plate": enable_license_plate,
        "stop_seconds": _parse_float(form_data.get("stop_seconds"), 30.0),
        "parking_move_threshold_px": _parse_float(form_data.get("parking_move_threshold_px"), 10.0),
        "process_every_n_frames": _parse_int(form_data.get("process_every_n_frames"), 2),
        "roi_points": roi_points,
        "no_parking_points": no_parking_points,
    }


@test_video_router.get("/test-video", name="test_video.test_video_page")
async def test_video_page(request: Request, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    cameras = container.camera_use_cases.list_cameras()
    return container.render_template(
        request,
        "test_video.html",
        {
            "page": "test-video",
            "cameras": [c.to_dict() for c in cameras],
            "default_model_path": str(DEFAULT_MODEL_PATH),
        }
    )



@test_video_router.post("/api/test-jobs")
async def api_create_test_job(
    request: Request,
    user=Depends(login_required),
    camera_id: Optional[str] = Form(None),
    local_path: Optional[str] = Form(None),
    video_file: Optional[UploadFile] = File(None),
    model_path: Optional[str] = Form(None),
    confidence_threshold: Optional[str] = Form(None),
    enable_congestion: Optional[str] = Form(None),
    enable_illegal_parking: Optional[str] = Form(None),
    enable_license_plate: Optional[str] = Form(None),
    stop_seconds: Optional[str] = Form(None),
    parking_move_threshold_px: Optional[str] = Form(None),
    process_every_n_frames: Optional[str] = Form(None),
    roi_points: Optional[str] = Form(None),
    no_parking_points: Optional[str] = Form(None),
):
    if isinstance(user, RedirectResponse):
        return user
        
    job_id = uuid.uuid4().hex
    camera = None
    camera_id_strip = (camera_id or "").strip()
    if camera_id_strip:
        try:
            camera = container.camera_use_cases.get_camera(int(camera_id_strip))
        except NotFoundError:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Camera được chọn không tồn tại."})

    input_path = None
    if video_file and video_file.filename:
        if not container.file_storage.is_allowed_video(video_file.filename):
            return JSONResponse(status_code=400, content={"ok": False, "error": "Định dạng video không được hỗ trợ."})
        # Save file
        input_path = container.file_storage.save_upload_fastapi(video_file, job_id)
    elif local_path and local_path.strip():
        input_path = container.file_storage.resolve_local_video(local_path.strip())
        if not input_path:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Đường dẫn video local không hợp lệ."})
    else:
        return JSONResponse(status_code=400, content={"ok": False, "error": "Hãy chọn file upload hoặc nhập đường dẫn local."})

    form_dict = {
        "model_path": model_path,
        "confidence_threshold": confidence_threshold,
        "enable_congestion": enable_congestion,
        "enable_illegal_parking": enable_illegal_parking,
        "enable_license_plate": enable_license_plate,
        "stop_seconds": stop_seconds,
        "parking_move_threshold_px": parking_move_threshold_px,
        "process_every_n_frames": process_every_n_frames,
        "roi_points": roi_points,
        "no_parking_points": no_parking_points,
    }

    try:
        test_settings = _build_test_settings(form_dict, camera)
    except ValidationError as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": exc.message})

    output_filename = f"{job_id}_result.mp4"
    job = container.job_use_cases.submit_job(
        job_id=job_id,
        input_path=str(input_path),
        output_filename=output_filename,
        settings=test_settings
    )

    payload = job.to_dict()
    payload["input_video_url"] = str(request.url_for("test_video.serve_test_job_source", job_id=job.id))
    payload["preview_image_url"] = str(request.url_for("test_video.serve_test_job_preview", job_id=job.id))
    payload["queue_position"] = container.job_use_cases.get_queue_position(job.id)

    return JSONResponse(status_code=202, content={"ok": True, "job": payload})


@test_video_router.get("/api/test-jobs/{job_id}")
async def api_get_test_job(request: Request, job_id: str, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    job = container.job_use_cases.get_job(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Không tìm thấy job kiểm tra."})
        
    payload = job.to_dict()
    payload["result_url"] = str(request.url_for("test_video.serve_result_video", filename=job.output_filename)) if job.output_filename else None
    payload["input_video_url"] = str(request.url_for("test_video.serve_test_job_source", job_id=job.id)) if job.source_video else None
    payload["preview_image_url"] = str(request.url_for("test_video.serve_test_job_preview", job_id=job.id))
    payload["queue_position"] = container.job_use_cases.get_queue_position(job.id)

    return {"ok": True, "job": payload}


@test_video_router.get("/results/{filename}", name="test_video.serve_result_video")
async def serve_result_video(filename: str, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    output_dir = container.file_storage.get_output_path("").parent
    file_path = output_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(file_path)


@test_video_router.get("/job-sources/{job_id}", name="test_video.serve_test_job_source")
async def serve_test_job_source(job_id: str, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    job = container.job_use_cases.get_job(job_id)
    if not job or not job.source_video:
        raise HTTPException(status_code=404)
    source_path = Path(str(job.source_video))
    if not source_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(source_path)


@test_video_router.get("/job-previews/{job_id}.jpg", name="test_video.serve_test_job_preview")
async def serve_test_job_preview(job_id: str, user=Depends(login_required)):
    if isinstance(user, RedirectResponse):
        return user
    job = container.job_use_cases.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404)

    preview_path = container.file_storage.get_preview_path(job_id)
    if preview_path.exists():
        return FileResponse(
            preview_path, 
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
        )

    if job.status == "running":
        title = "Đang phân tích video"
    elif job.status == "completed":
        title = "Đã hoàn tất xử lý"
    elif job.status == "failed":
        title = "Không tạo được preview"
    else:
        title = "Đang chờ đến lượt xử lý"

    detail = str(job.message)
    return StreamingResponse(
        io.BytesIO(build_placeholder_frame(title, detail)), 
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
    )
