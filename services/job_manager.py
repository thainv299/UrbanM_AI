import time
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional

from core.config import jobs, job_lock, PREVIEWS_DIR, OUTPUTS_DIR
from frontend.services.detection_bridge import process_video
from frontend.database import DB_PATH

def set_job(job_id: str, **updates: Any) -> Dict[str, Any]:
    with job_lock:
        job = jobs.setdefault(job_id, {"id": job_id})
        job.update(updates)
        return dict(job)

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with job_lock:
        job = jobs.get(job_id)
        return dict(job) if job is not None else None

def get_queue_position(job_id: str) -> Optional[int]:
    with job_lock:
        active_jobs = [
            item
            for item in jobs.values()
            if item.get("status") in {"queued", "running"}
        ]
        active_jobs.sort(key=lambda item: item.get("submitted_at", 0.0))
    for index, item in enumerate(active_jobs, start=1):
        if item.get("id") == job_id and item.get("status") == "queued":
            return index
    return None

def preview_path_for_job(job_id: str) -> Path:
    return PREVIEWS_DIR / f"{job_id}.jpg"

def public_job(job: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(job)
    # Loai bo latest_frame (bytes) de tranh loi UnicodeDecodeError khi FastAPI serialize JSON
    payload.pop("latest_frame", None)
    output_filename = payload.get("output_filename")
    payload["result_url"] = f"/results/{output_filename}" if output_filename else None
    payload["input_video_url"] = f"/job-sources/{payload['id']}" if payload.get("source_video") else None
    payload["stream_url"] = f"/api/test-jobs/{payload['id']}/stream"
    payload["queue_position"] = get_queue_position(payload.get("id", ""))
    return payload

def run_detection_job(
    job_id: str,
    input_path: str,
    output_filename: str,
    detection_settings: Dict[str, Any],
) -> None:
    output_path = OUTPUTS_DIR / output_filename

    def handle_progress(progress: Dict[str, Any]) -> None:
        # Kiem tra abort signal truoc khi tiep tuc xu ly
        with job_lock:
            current = jobs.get(job_id)
            if current and current.get("status") == "aborted":
                raise RuntimeError("Job da bi huy boi nguoi dung hoac server.")

        progress_payload = dict(progress)
        preview_jpeg = progress_payload.pop("preview_jpeg", None)
        if preview_jpeg:
            with job_lock:
                job = jobs.get(job_id)
                if job is not None:
                    job["latest_frame"] = preview_jpeg

        phase = progress.get("phase")
        processed_frames = progress.get("processed_frames")
        total_frames = progress.get("source_total_frames")

        if phase == "loading_model":
            message = "Dang tai model YOLO..."
        elif phase == "finalizing_output":
            message = "Dang hoan tat..."
        elif processed_frames is not None:
            total_text = total_frames if total_frames else "?"
            message = f"Dang xu ly {processed_frames}/{total_text} frame..."
        else:
            message = "Dang xu ly video..."

        set_job(
            job_id,
            status="running",
            message=message,
            error=None,
            started_at=time.time(),
            progress=progress_payload,
        )

    set_job(
        job_id,
        status="running",
        message="Dang khoi tao job detect...",
        error=None,
        started_at=time.time(),
        progress={
            "phase": "starting",
            "processed_frames": 0,
            "source_total_frames": None,
            "progress_percent": 0.0,
            "elapsed_seconds": 0.0,
            "latest_status": "Dang khoi tao job detect...",
        },
    )

    try:
        summary = process_video(
            input_path=input_path,
            output_path=str(output_path),
            settings=detection_settings,
            progress_callback=handle_progress,
        )
        if summary:
            try:
                total_v = summary.get("max_vehicle_count", 0)
                total_vi = summary.get("parking_violation_count", 0)
                violation_ids = summary.get("parking_violation_ids", [])

                with sqlite3.connect(DB_PATH) as conn:
                    conn.text_factory = str
                    for i in range(total_v):
                        conn.execute(
                            "INSERT INTO vehicle_logs (license_plate, created_at) VALUES (?, datetime('now', 'localtime'))",
                            (f"XE-{job_id[:4]}-{i+1}",)
                        )
                    for v_id in violation_ids:
                        conn.execute(
                            "INSERT INTO violations (license_plate, type, created_at) VALUES (?, ?, datetime('now', 'localtime'))",
                            (f"VP-{v_id}", "Do xe sai quy dinh")
                        )
                    conn.commit()
            except Exception as e:
                print(f"Lỗi cập nhật Dashboard: {e}")
        
        set_job(
            job_id,
            status="completed",
            message="Da hoan thanh xu ly video.",
            error=None,
            summary=summary,
            output_filename=output_filename,
            finished_at=time.time(),
            progress={
                "phase": "completed",
                "processed_frames": summary.get("processed_frames"),
                "source_total_frames": summary.get("source_total_frames"),
                "progress_percent": 100.0,
                "elapsed_seconds": summary.get("processing_seconds"),
                "latest_status": summary.get("latest_status"),
            },
        )
    except Exception as exc:
        try:
            if output_path.exists():
                output_path.unlink()
        except OSError:
            pass
        set_job(
            job_id,
            status="failed",
            message="Xu ly video that bai.",
            error=str(exc),
            summary=None,
            output_filename=None,
            finished_at=time.time(),
        )
