import uuid
import time
from pathlib import Path
from fastapi import APIRouter, Request, Depends, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse, Response
from werkzeug.utils import secure_filename

from core.config import executor, INPUTS_DIR, OUTPUTS_DIR, ALLOWED_VIDEO_EXTENSIONS
from core.utils import json_error, resolve_path, build_test_settings
from core.security import require_login
from frontend.database import get_camera
from services.job_manager import (
    set_job,
    get_job,
    public_job,
    preview_path_for_job,
    run_detection_job
)
from services.camera_service import build_placeholder_frame

router = APIRouter()

@router.get("/results/{filename}")
def serve_result_video(filename: str, user=Depends(require_login)):
    file_path = OUTPUTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(file_path)

@router.get("/job-sources/{job_id}")
def serve_test_job_source(job_id: str, user=Depends(require_login)):
    job = get_job(job_id)
    if not job or not job.get("source_video"):
        raise HTTPException(status_code=404)
    source_path = Path(job["source_video"])
    if not source_path.exists() or source_path.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=404)
    return FileResponse(source_path)

@router.get("/job-previews/{job_id}.jpg")
def serve_test_job_preview(job_id: str, user=Depends(require_login)):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404)

    preview_path = preview_path_for_job(job_id)
    if preview_path.exists():
        return FileResponse(preview_path, media_type="image/jpeg", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})

    status_str = str(job.get("status", "queued"))
    if status_str == "running":
        title = "Dang phan tich video"
    elif status_str == "completed":
        title = "Da hoan tat xu ly"
    elif status_str == "failed":
        title = "Khong tao duoc preview"
    else:
        title = "Dang cho den luot xu ly"

    detail = str(job.get("message", ""))
    return Response(content=build_placeholder_frame(title, detail), media_type="image/jpeg", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@router.post("/api/test-jobs")
async def api_create_test_job(request: Request, user=Depends(require_login)):
    form = await request.form()
    job_id = uuid.uuid4().hex
    camera = None
    camera_id_text = str(form.get("camera_id", "")).strip()
    if camera_id_text:
        camera = get_camera(int(camera_id_text))
        if camera is None:
            return json_error("Camera duoc chon khong ton tai.", 404)

    upload_file = form.get("video_file")
    local_path_text = str(form.get("local_path", "")).strip()

    if isinstance(upload_file, UploadFile) and upload_file.filename:
        extension = Path(upload_file.filename).suffix.lower()
        if extension not in ALLOWED_VIDEO_EXTENSIONS:
            return json_error("Dinh dang video khong duoc ho tro.", 400)
        safe_name = secure_filename(upload_file.filename)
        input_path = INPUTS_DIR / f"{job_id}_{safe_name}"
        with open(input_path, "wb") as buffer:
            while True:
                chunk = await upload_file.read(8192)
                if not chunk:
                    break
                buffer.write(chunk)
    elif local_path_text:
        input_path = resolve_path(local_path_text)
        if not input_path.exists():
            return json_error("Duong dan video local khong ton tai.", 400)
        if input_path.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
            return json_error("Dinh dang video khong duoc ho tro.", 400)
    else:
        return json_error("Hay chon file upload hoac nhap duong dan local.", 400)

    try:
        form_data = {k: v for k, v in form.multi_items()}
        test_settings = build_test_settings(form_data, camera)
    except ValueError as exc:
        return json_error(str(exc), 400)

    output_filename = f"{job_id}_result.mp4"
    submitted_at = time.time()
    set_job(
        job_id,
        status="queued",
        message="Da nhan yeu cau. Job se duoc xu ly theo hang doi.",
        error=None,
        output_filename=None,
        summary=None,
        source_video=str(input_path),
        submitted_at=submitted_at,
        progress={
            "phase": "queued",
            "processed_frames": 0,
            "source_total_frames": None,
            "progress_percent": 0.0,
            "elapsed_seconds": 0.0,
            "latest_status": "Dang cho den luot xu ly...",
        },
    )
    
    executor.submit(
        run_detection_job,
        job_id,
        str(input_path),
        output_filename,
        test_settings,
    )

    return JSONResponse({"ok": True, "job": public_job(get_job(job_id) or {"id": job_id})}, status_code=202)

@router.get("/api/test-jobs/{job_id}")
def api_get_test_job(job_id: str, user=Depends(require_login)):
    job = get_job(job_id)
    if job is None:
        return json_error("Không tìm thấy job kiểm tra.", 404)
    return {"ok": True, "job": public_job(job)}
