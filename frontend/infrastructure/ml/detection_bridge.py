from __future__ import annotations

import os
import sys
import time
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.parking.parking_manager import ParkingManager
from modules.traffic.traffic_monitor import TrafficMonitor
from modules.ocr.ocr_manager import OCRManager
from modules.utils.alpr_logger import ALPRLogger
from modules.utils.traffic_alert_manager import TrafficAlertManager
from modules.utils.interactive_telegram_bot import start_bot_thread
from database.sqlite_db import (
    log_passed_vehicle,
    log_congestion,
    log_parking_violation,
    log_vehicle_count,
    log_detected_license_plate
)
from paddleocr import PaddleOCR
from collections import deque

TRAFFIC_LABELS = {"person", "bicycle", "car", "motorcycle", "bus", "truck"}
VEHICLE_LABELS = {"car", "motorcycle", "bus", "truck"}
PARKING_LABELS = {"car", "bus", "truck"}
LICENSE_PLATE_LABELS = {"license_plate", "licenseplate", "number_plate", "licence_plate"}
DETECTABLE_LABELS = TRAFFIC_LABELS | LICENSE_PLATE_LABELS
BOX_COLORS = {
    "person": (0, 255, 0),
    "bicycle": (255, 127, 0),
    "car": (255, 255, 0),
    "motorcycle": (0, 255, 255),
    "bus": (0, 165, 255),
    "truck": (255, 0, 255),
    "license_plate": (255, 105, 180),
}


def _canonical_label(label: Any) -> str:
    return str(label).strip().lower().replace("-", "_").replace(" ", "_")


def _display_label(label_key: str) -> str:
    translations = {
        "person": "người", 
        "car": "ô tô",
        "motorcycle": "xe máy",
        "bus": "xe buýt",
        "truck": "xe tải",
    }
    if label_key in LICENSE_PLATE_LABELS:
        return "biển số"
    return translations.get(label_key, label_key.replace("_", " "))


def _normalize_points(points: Optional[List[List[int]]]) -> Optional[List[List[int]]]:
    if not points:
        return None

    normalized: List[List[int]] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue
        normalized.append([int(point[0]), int(point[1])])

    if len(normalized) < 3:
        return None
    return normalized


def _to_polygon(points: Optional[List[List[int]]]) -> Optional[np.ndarray]:
    normalized = _normalize_points(points)
    if normalized is None:
        return None
    return np.array(normalized, dtype=np.int32)


def _full_frame_polygon(width: int, height: int) -> List[List[int]]:
    return [
        [0, 0],
        [max(0, width - 1), 0],
        [max(0, width - 1), max(0, height - 1)],
        [0, max(0, height - 1)],
    ]


def _encode_preview_frame(frame: np.ndarray, max_width: int = 960) -> Optional[bytes]:
    if frame is None or frame.size == 0:
        return None

    preview = frame
    height, width = preview.shape[:2]
    if width > max_width:
        scale = max_width / float(width)
        preview = cv2.resize(preview, (max_width, max(1, int(height * scale))), interpolation=cv2.INTER_AREA)

    success, encoded = cv2.imencode(
        '.jpg',
        preview,
        [int(cv2.IMWRITE_JPEG_QUALITY), 82],
    )
    if not success:
        return None
    return encoded.tobytes()


def _load_model(model_path: Path) -> YOLO:
    model_str = str(model_path)
    if model_str.lower().endswith(".engine"):
        return YOLO(model_str, task="detect")

    model = YOLO(model_str)
    preferred_device = os.environ.get("WEB_DETECT_DEVICE", "").strip()
    if preferred_device:
        try:
            model.to(preferred_device)
        except Exception:
            pass
    return model

def process_video(
    input_stream: Any = None,
    input_path: str = None,
    input_ext: str = None,
    settings: Dict[str, Any] = None,
    progress_callback: Callable[[Dict[str, Any]], None] = None,
    pause_event: threading.Event = None,
) -> Dict[str, Any]:
    """
    Xử lý video. Hỗ trợ luồng stream trực tiếp hoặc đường dẫn file truyền thống.
    """
    import tempfile
    if input_stream is not None:
        with tempfile.NamedTemporaryFile(suffix=input_ext or ".mp4", delete=False) as tmp:
            tmp.write(input_stream.getvalue())
            temp_path = tmp.name
        input_video_path = Path(temp_path)
        should_cleanup_temp = True
    elif input_path is not None:
        input_video_path = Path(input_path)
        should_cleanup_temp = False
    else:
        raise ValueError("Yêu cầu cung cấp input_stream hoặc input_path")

    if not input_video_path.exists():
        raise FileNotFoundError(f"Không tìm thấy video đầu vào: {input_video_path}")

    model_path = Path(str(settings["model_path"]))
    if not model_path.exists():
        raise FileNotFoundError(f"Không tìm thấy mô hình YOLO tại: {model_path}")

    confidence_threshold = float(settings.get("confidence_threshold", 0.32))
    enable_congestion = bool(settings.get("enable_congestion", True))
    enable_illegal_parking = bool(settings.get("enable_illegal_parking", True))
    enable_license_plate = bool(settings.get("enable_license_plate", True))
    stop_seconds = float(settings.get("stop_seconds", 30.0))
    move_threshold_px = float(settings.get("parking_move_threshold_px", 10.0))
    process_stride = max(1, int(settings.get("process_every_n_frames", 2)))

    capture = cv2.VideoCapture(str(input_video_path))
    if not capture.isOpened():
        raise RuntimeError("Không thể mở video để phân tích.")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    ideal_frame_time = 1.0 / fps if fps > 0 else 0.033


    roi_points = _normalize_points(settings.get("roi_points")) or _full_frame_polygon(
        frame_width, frame_height
    )
    no_parking_points = _normalize_points(settings.get("no_parking_points"))
    roi_polygon = _to_polygon(roi_points)

    if roi_polygon is None:
        raise ValueError("Vùng ROI (Khu vực quan tâm) không hợp lệ.")

    if progress_callback is not None:
        progress_callback(
            {
                "phase": "loading_model",
                "processed_frames": 0,
                "source_total_frames": total_frames,
                "progress_percent": 0.0,
                "elapsed_seconds": 0.0,
                "latest_status": "Đang tải model YOLO...",
            }
        )

    model = _load_model(model_path)
    traffic_monitor = TrafficMonitor(roi_polygon=roi_polygon) if enable_congestion else None
    
    # Khởi tạo các Manager tiêu chuẩn của dự án (Giống main.py)
    camera_id = int(settings.get("camera_id", 0))  # Lục id camera từ settings
    alpr_logger = ALPRLogger(db_callback=log_detected_license_plate, id_camera=camera_id)
    traffic_alert_manager = TrafficAlertManager()
    parking_manager = ParkingManager(None, None) 
    
    # Cấu hình ParkingManager
    parking_manager.no_park_polygon = _to_polygon(no_parking_points)
    parking_manager.stop_seconds = stop_seconds
    parking_manager.move_thr_px = move_threshold_px
    parking_manager.setup_detection(fps)
    
    # Đồng bộ cấu hình Telegram từ môi trường giống main.py
    import os
    parking_manager.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    parking_manager.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    # Khởi động luồng Bot chờ lệnh (Nếu chưa chạy) để nhận nút bấm Xác nhận
    try:
        start_bot_thread(traffic_alert_manager)
    except Exception as e:
        print(f"[Telegram] Không khởi động được polling thread: {e}")
    
    logged_vehicle_ids: set = set()  # Các xe đã ghi nhận đi qua
    last_db_traffic_level = 0  # Mức độ ùn tắc cuối cùng đã lưu DB
    unique_passed_count = 0
    violation_events: List[Dict[str, Any]] = []  # Danh sách vi phạm (tương thích ngược với API response)

    frame_index = 0
    last_results = None
    started_at = time.time()
    last_progress_emit = 0.0
    max_vehicle_count = 0
    max_people_count = 0
    max_license_plate_count = 0
    max_occupancy = 0.0
    highest_traffic_level = 0
    congestion_frames = 0
    import logging
    logging.getLogger("ppocr").setLevel(logging.ERROR)
    ocr_reader = PaddleOCR(lang='en')
    ocr_manager = OCRManager(ocr_reader, alpr_logger=alpr_logger)
    if enable_license_plate:
        ocr_manager.start_worker()

    try:
        while capture.isOpened():
            # Kiểm tra trạng thái Tạm dừng (Pause)
            if pause_event and pause_event.is_set():
                if progress_callback is not None:
                    # Tạo bản sao frame để vẽ overlay "PAUSED" mà không làm hỏng frame gốc
                    pause_frame = frame.copy() if 'frame' in locals() else np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
                    cv2.rectangle(pause_frame, (frame_width//2 - 150, frame_height//2 - 50), 
                                 (frame_width//2 + 150, frame_height//2 + 50), (0, 0, 0), -1)
                    cv2.putText(pause_frame, "TẠM DỪNG", (frame_width//2 - 100, frame_height//2 + 15), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
                    
                    progress_callback(
                        {
                            "phase": "running_detection",
                            "processed_frames": frame_index,
                            "source_total_frames": total_frames,
                            "progress_percent": round((frame_index / total_frames) * 100, 2)
                            if total_frames
                            else None,
                            "elapsed_seconds": round(time.time() - started_at, 1),
                            "latest_status": "Đang tạm dừng quá trình phân tích...",
                            "preview_jpeg": _encode_preview_frame(pause_frame),
                        }
                    )
                time.sleep(0.5)
                continue

            frame_start_time = time.time()
            success, frame = capture.read()
            if not success:
                break

            clean_frame = frame.copy()
            if enable_illegal_parking:
                parking_manager.update_buffer(clean_frame.copy())

            frame_index += 1
            current_time = time.time()


            if process_stride > 1 and (frame_index - 1) % process_stride != 0 and last_results is not None:
                results = last_results
            else:
                results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
                last_results = results

            if traffic_monitor is not None:
                traffic_monitor.reset_counters()

            current_license_plate_count = 0
            current_plate_ids = set()
            valid_vehicles = []
            
            for result in results:
                for box in result.boxes:
                    lbl = _canonical_label(model.names[int(box.cls[0])])
                    if lbl in VEHICLE_LABELS:
                        vx1, vy1, vx2, vy2 = map(int, box.xyxy[0])
                        valid_vehicles.append((vx1, vy1, vx2, vy2))

            for result in results:
                for box in result.boxes:
                    label = _canonical_label(model.names[int(box.cls[0])])
                    if label not in DETECTABLE_LABELS:
                        continue
                    if label in LICENSE_PLATE_LABELS and not enable_license_plate:
                        continue

                    confidence = float(box.conf[0])
                    if confidence < confidence_threshold:
                        continue

                    track_id = int(box.id[0]) if box.id is not None else -1
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2

                    if cv2.pointPolygonTest(roi_polygon, (center_x, center_y), False) < 0:
                        continue

                    box_color = BOX_COLORS.get(label, (255, 255, 255))
                    label_text = _display_label(label)
                    display_label = label_text if track_id == -1 else f"ID:{track_id} {label_text}"

                    if label in LICENSE_PLATE_LABELS:
                        current_license_plate_count += 1
                        if enable_license_plate and track_id != -1:
                            processed_id = ocr_manager.process_plate(
                                frame, clean_frame, track_id, x1, y1, x2, y2, center_x, center_y, 
                                valid_vehicles, current_time, frame_index
                            )
                            if processed_id:
                                current_plate_ids.add(processed_id)
                        continue

                    if label == "person":
                        if traffic_monitor is not None:
                            traffic_monitor.log_person()
                    elif label in VEHICLE_LABELS and traffic_monitor is not None:
                        traffic_monitor.log_vehicle(
                            track_id=track_id,
                            cx=center_x,
                            cy=center_y,
                            current_time=current_time,
                            bbox=(x1, y1, x2, y2),
                        )

                    if label in VEHICLE_LABELS and enable_illegal_parking:
                        display_label_p, box_color_p = parking_manager.process_vehicle(
                            frame, clean_frame, track_id, label, center_x, center_y, frame_index, bbox=(x1, y1, x2, y2)
                        )
                        if display_label_p:
                            display_label = display_label_p
                            # Ghi nhận vi phạm đỗ xe vào Database nếu là trạng thái VIOLATION
                            if "VIOLATION" in display_label_p:
                                # Tránh ghi trùng lặp bằng cách kiểm tra record trong manager hoặc track state
                                state_info = parking_manager.logic.states.get(track_id)
                                if state_info and state_info.get("state") == 2: # VIOLATION state
                                     # Chúng ta chỉ lưu vào DB một lần khi vừa chuyển sang vi phạm ở vòng lặp trước đó
                                     # Hoặc đơn giản là kiểm tra nếu manager vừa tạo record mới
                                     if track_id in parking_manager.active_recordings:
                                         # Lưu vào DB
                                         log_parking_violation(
                                             camera_id=camera_id,
                                             license_plate=f"ID_{track_id}",
                                             duration=int(stop_seconds),
                                             frame_path=f"logs/violations/ID_{track_id}/" # Đường dẫn tương đối
                                         )

                        if box_color_p is not None:
                            box_color = box_color_p

                    # Ghi nhận phương tiện đi qua vào Database (Chỉ lưu 1 lần cho mỗi ID trong 1 Job)
                    if track_id != -1 and track_id not in logged_vehicle_ids:
                        log_passed_vehicle(
                            camera_id=camera_id,
                            bien_so_xe=f"ID_{track_id}",
                            loai_xe=label
                        )
                        logged_vehicle_ids.add(track_id)
                        unique_passed_count += 1

                    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                    cv2.circle(frame, (center_x, center_y), 3, (0, 0, 255), -1)
                    cv2.putText(
                        frame,
                        display_label,
                        (x1, max(20, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        box_color,
                        2,
                    )

            max_license_plate_count = max(max_license_plate_count, current_license_plate_count)

            if enable_license_plate:
                ocr_manager.draw_grace_period_boxes(frame, current_plate_ids)
                ocr_manager.cleanup_memory(current_time, frame_index)

            cv2.polylines(frame, [roi_polygon], True, (255, 0, 0), 2)
            if enable_illegal_parking:
                parking_manager.draw_polygon_overlay(frame)

            if traffic_monitor is not None:
                average_speed, status_text, status_color, traffic_level = (
                    traffic_monitor.calculate_speed_and_status(current_time, frame.shape)
                )
                traffic_monitor.draw_status(frame, average_speed, status_text, status_color)
                latest_status = status_text
                
                # Cảnh báo Telegram giống main.py
                traffic_alert_manager.update_traffic_state(traffic_level, clean_frame)
                
                # Ghi nhận nhật ký ùn tắc vào Database nếu mức độ thay đổi
                if traffic_level != last_db_traffic_level:
                    if traffic_level > 0:
                        log_congestion(camera_id=camera_id, level=traffic_level)
                    last_db_traffic_level = traffic_level
                
                max_vehicle_count = max(max_vehicle_count, traffic_monitor.vehicle_count)
                max_people_count = max(max_people_count, traffic_monitor.people_count)
                max_occupancy = max(max_occupancy, traffic_monitor.last_occupancy)
                highest_traffic_level = max(highest_traffic_level, traffic_level)
                if traffic_level > 0:
                    congestion_frames += 1
            else:
                latest_status = "Đã tắt tính năng tắc nghẽn"
                cv2.putText(
                    frame,
                    latest_status,
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (200, 200, 200),
                    2,
                )

            if enable_license_plate:
                plate_status = f"Số biển nhận diện: {current_license_plate_count}"
                cv2.putText(
                    frame,
                    plate_status,
                    (30, 78 if traffic_monitor is not None else 72),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    BOX_COLORS["license_plate"],
                    2,
                )
                latest_status = (
                    f"{latest_status} | {plate_status}"
                    if latest_status
                    else plate_status
                )

            # Xóa các thông báo feature_text và frame_index không cần thiết theo yêu cầu người dùng

            # Luôn gửi frame preview để stream MJPEG mượt mà, đồng bộ với xử lý
            if progress_callback is not None:
                progress_callback(
                    {
                        "phase": "running_detection",
                        "processed_frames": frame_index,
                        "source_total_frames": total_frames,
                        "progress_percent": round((frame_index / total_frames) * 100, 2)
                        if total_frames
                        else None,
                        "elapsed_seconds": round(time.time() - started_at, 1),
                        "latest_status": latest_status,
                        "preview_jpeg": _encode_preview_frame(frame),
                    }
                )

            # Đồng bộ hóa với tốc độ video thực tế (Real-time playback)
            elapsed = time.time() - frame_start_time
            if elapsed < ideal_frame_time:
                time.sleep(ideal_frame_time - elapsed)

    finally:
        capture.release()
        if enable_license_plate:
            ocr_manager.stop_worker()
            
        # Cuối Job, ghi nhận tổng lượng xe thống kê vào Database
        log_vehicle_count(camera_id=camera_id, count=unique_passed_count)
        if should_cleanup_temp and input_video_path.exists():
            import os
            try:
                os.unlink(input_video_path)
            except Exception:
                pass

    processing_seconds = max(0.001, time.time() - started_at)
    
    # Kết quả vi phạm từ Manager
    parking_violation_ids = (
        sorted(list(parking_manager.logic.states.keys())) if enable_illegal_parking else []
    )

    if progress_callback is not None:
        progress_callback(
            {
                "phase": "finalizing_output",
                "processed_frames": frame_index,
                "source_total_frames": total_frames,
                "progress_percent": 100.0,
                "elapsed_seconds": round(processing_seconds, 1),
                "latest_status": "Đang hoàn tất xử lý kết quả...",
            }
        )

    return {
        "input_path": str(input_video_path),
        "output_path": None,
        "processed_frames": frame_index,
        "source_total_frames": total_frames,
        "duration_seconds": round(frame_index / fps, 2) if fps else 0.0,
        "processing_seconds": round(processing_seconds, 2),
        "average_processing_fps": round(frame_index / processing_seconds, 2),
        "max_vehicle_count": max_vehicle_count,
        "max_people_count": max_people_count,
        "max_license_plate_count": max_license_plate_count,
        "max_occupancy_percent": round(max_occupancy, 2),
        "highest_traffic_level": highest_traffic_level,
        "congestion_alert_frames": congestion_frames,
        "parking_violation_count": len(parking_violation_ids),
        "parking_violation_ids": parking_violation_ids,
        "latest_status": latest_status,
        "roi_points": roi_points,
        "no_parking_points": no_parking_points,
        # Thông tin biển số OCR - Lấy từ alpr_logger sessions
        "detected_plates_count": len(alpr_logger.plate_sessions),
        "detected_plates": {
            plate: {
                "count": 1, # alpr_logger không lưu count gộp, tạm để 1
                "avg_confidence": 1.0, 
                "first_seen_frame": data["last_seen"],
                "last_seen_frame": data["last_seen"],
                "image_path": None, # Sẽ được lưu trực tiếp trong logs/plates/
            }
            for plate, data in alpr_logger.plate_sessions.items()
        },
        "feature_flags": {
            "enable_congestion": enable_congestion,
            "enable_illegal_parking": enable_illegal_parking,
            "enable_license_plate": enable_license_plate,
        },
        "violation_events": violation_events[:20],
    }

from application.interfaces.detection_interface import DetectionInterface

class YoloDetectionService(DetectionInterface):
    def process_video(
        self,
        input_stream: Any = None,
        input_path: str = None,
        input_ext: str = None,
        settings: Dict[str, Any] = None,
        progress_callback: Callable[[Dict[str, Any]], None] = None,
        pause_event: Any = None
    ) -> Dict[str, Any]:
        return process_video(
            input_stream=input_stream,
            input_path=input_path,
            input_ext=input_ext,
            settings=settings,
            progress_callback=progress_callback,
            pause_event=pause_event
        )

