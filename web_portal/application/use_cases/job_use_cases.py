import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from application.interfaces.detection_interface import DetectionInterface
from domain.entities.job import Job
from infrastructure.file_system.local_storage import LocalStorage


class JobUseCases:
    def __init__(self, detection_service: DetectionInterface, file_storage: LocalStorage):
        self.detection_service = detection_service
        self.file_storage = file_storage
        
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.job_lock = threading.Lock()
        self.jobs: Dict[str, Job] = {}

    def set_job(self, job_id: str, **updates: Any) -> Job:
        with self.job_lock:
            if job_id not in self.jobs:
                self.jobs[job_id] = Job(id=job_id)
            job = self.jobs[job_id]
            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self.job_lock:
            return self.jobs.get(job_id)

    def get_queue_position(self, job_id: str) -> Optional[int]:
        with self.job_lock:
            active_jobs = [
                j for j in self.jobs.values()
                if j.status in {"queued", "running"}
            ]
            active_jobs.sort(key=lambda item: item.submitted_at or 0.0)

        for index, item in enumerate(active_jobs, start=1):
            if item.id == job_id and item.status == "queued":
                return index
        return None

    def run_detection_job(
        self,
        job_id: str,
        input_path: str,
        output_filename: str,
        detection_settings: Dict[str, Any],
    ) -> None:
        output_path = self.file_storage.get_output_path(output_filename)

        def handle_progress(progress: Dict[str, Any]) -> None:
            progress_payload = dict(progress)
            preview_jpeg = progress_payload.pop("preview_jpeg", None)
            if preview_jpeg:
                self.file_storage.save_preview_image(job_id, preview_jpeg)

            phase = progress.get("phase")
            percent = progress.get("progress_percent")
            processed_frames = progress.get("processed_frames")
            total_frames = progress.get("source_total_frames")

            if phase == "loading_model":
                message = "Đang tải model YOLO..."
            elif phase == "finalizing_output":
                message = "Đang hoàn tất video kết quả..."
            elif processed_frames is not None:
                total_text = total_frames if total_frames else "?"
                if percent is None:
                    message = f"Đang xử lý {processed_frames}/{total_text} frame..."
                else:
                    message = f"Đang xử lý {processed_frames}/{total_text} frame ({percent:.1f}%)"
            else:
                message = "Đang xử lý video..."

            self.set_job(
                job_id,
                status="running",
                message=message,
                error=None,
                started_at=time.time(),
                progress=progress_payload,
            )

        self.set_job(
            job_id,
            status="running",
            message="Đang khởi tạo job detect...",
            error=None,
            started_at=time.time(),
            progress={
                "phase": "starting",
                "processed_frames": 0,
                "source_total_frames": None,
                "progress_percent": 0.0,
                "elapsed_seconds": 0.0,
                "latest_status": "Đang khởi tạo job detect...",
            },
        )

        try:
            summary = self.detection_service.process_video(
                input_path=input_path,
                output_path=str(output_path),
                settings=detection_settings,
                progress_callback=handle_progress,
            )
            self.set_job(
                job_id,
                status="completed",
                message="Đã hoàn thành xử lý video.",
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
            self.file_storage.delete_output_file(output_filename)
            self.set_job(
                job_id,
                status="failed",
                message="Xử lý video thất bại.",
                error=str(exc),
                summary=None,
                output_filename=None,
                finished_at=time.time(),
            )

    def submit_job(self, job_id: str, input_path: str, output_filename: str, settings: Dict[str, Any]) -> Job:
        submitted_at = time.time()
        job = self.set_job(
            job_id,
            status="queued",
            message="Đã nhận yêu cầu. Job sẽ được xử lý theo hàng đợi.",
            error=None,
            output_filename=None,
            summary=None,
            source_video=input_path,
            submitted_at=submitted_at,
            progress={
                "phase": "queued",
                "processed_frames": 0,
                "source_total_frames": None,
                "progress_percent": 0.0,
                "elapsed_seconds": 0.0,
                "latest_status": "Đang chờ đến lượt xử lý...",
            },
        )

        self.executor.submit(
            self.run_detection_job,
            job_id,
            input_path,
            output_filename,
            settings,
        )
        return job
