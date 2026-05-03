from __future__ import annotations

import os
import sys
import time
import threading
import queue
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

# Thiết lập PROJECT_ROOT để import các module từ thư mục gốc
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import các manager và database
from modules.parking.parking_manager import ParkingManager
from modules.traffic.traffic_monitor import TrafficMonitor
from modules.ocr.ocr_manager import OCRManager
from modules.utils.alpr_logger import ALPRLogger
from modules.utils.traffic_alert_manager import TrafficAlertManager
from modules.utils.interactive_telegram_bot import start_bot_thread
from modules.utils.async_io_worker import AsyncIOWorker
from database.sqlite_db import (
    log_passed_vehicle,
    log_congestion,
    update_congestion_end_time,
    log_parking_violation,
    log_vehicle_count,
    log_detected_license_plate
)
from paddleocr import PaddleOCR
from collections import deque

# Nhãn nhận diện
TRAFFIC_LABELS = {"person", "bicycle", "car", "motorcycle", "bus", "truck"}
VEHICLE_LABELS = {"car", "motorcycle", "bus", "truck"}
PARKING_LABELS = {"car", "bus", "truck"}
LICENSE_PLATE_LABELS = {"license_plate", "licenseplate", "number_plate", "licence_plate"}
DETECTABLE_LABELS = TRAFFIC_LABELS | LICENSE_PLATE_LABELS

# Màu sắc cho các loại phương tiện
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
    """Chuẩn hóa label về dạng snake_case."""
    return str(label).strip().lower().replace("-", "_").replace(" ", "_")


def _display_label(label_key: str) -> str:
    """Chuyển key label sang dạng hiển thị."""
    return label_key.replace("_", " ")


def _normalize_points(points: Optional[List[List[Any]]], width: int, height: int, metadata: Dict[str, Any] = None) -> Optional[List[List[int]]]:
    """
    Quy đổi tọa độ từ Frontend về tọa độ Pixel của Video gốc.
    Hỗ trợ cả 3 chế độ: Pixels tuyệt đối, Tỉ lệ % (Legacy) và Tọa độ tham chiếu (Reference).
    """
    if not points:
        return None
        
    metadata = metadata or {}
    units = metadata.get("units")
    ref_w = metadata.get("ref_width")
    ref_h = metadata.get("ref_height")

    normalized_res = []
    
    # Chế độ 1: Tọa độ tham chiếu (Reference Resolution) - Chính xác nhất
    if units == "reference" and ref_w and ref_h:
        scale_x = width / float(ref_w)
        scale_y = height / float(ref_h)
        for pt in points:
            try:
                actual_x = int(round(float(pt[0]) * scale_x))
                actual_y = int(round(float(pt[1]) * scale_y))
                normalized_res.append([actual_x, actual_y])
            except: continue
        return normalized_res

    # Chế độ 2 & 3: Tự động nhận diện Pixel hoặc % (Legacy support)
    is_percentage = True
    for pt in points:
        if not pt or len(pt) < 2: continue
        val_x, val_y = pt[0], pt[1]
        if val_x > 1.0 or val_y > 1.0:
            is_percentage = False
            break
            
    for pt in points:
        try:
            x, y = float(pt[0]), float(pt[1])
            if is_percentage:
                actual_x = int(round(x * width))
                actual_y = int(round(y * height))
            else:
                actual_x = int(round(x))
                actual_y = int(round(y))
            normalized_res.append([actual_x, actual_y])
        except (ValueError, TypeError):
            continue
            
    if len(normalized_res) < 3:
        return None
    return normalized_res


def _to_polygon(points: Optional[List[List[int]]]) -> Optional[np.ndarray]:
    """Chuyển danh sách điểm sang mảng numpy cho OpenCV."""
    if not points:
        return None
    return np.array(points, dtype=np.int32)


def _full_frame_polygon(width: int, height: int) -> List[List[int]]:
    """Tạo polygon phủ toàn bộ frame."""
    return [
        [0, 0],
        [max(0, width - 1), 0],
        [max(0, width - 1), max(0, height - 1)],
        [0, max(0, height - 1)],
    ]


def _encode_preview_frame(frame: np.ndarray, max_width: int = 960) -> Optional[bytes]:
    """Mã hóa frame sang JPEG để preview MJPEG."""
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


def _get_drawing_params(width: int) -> Tuple[float, int, int]:
    """
    Tính toán các tham số vẽ (fontScale, thickness, offset) dựa trên chiều rộng frame.
    Lấy chuẩn là 1280px (HD).
    """
    base_width = 1280
    ratio = width / base_width
    
    font_scale = max(0.45, 0.55 * ratio)
    thickness = max(1, int(round(2 * ratio)))
    # Khoảng cách từ text đến box
    offset = max(10, int(round(15 * ratio)))
    
    return font_scale, thickness, offset


def _load_model(model_path: Path) -> YOLO:
    """Tải model YOLO, hỗ trợ TensorRT .engine."""
    model_str = str(model_path)
    if model_str.lower().endswith(".engine"):
        return YOLO(model_str, task="detect")

    model = YOLO(model_str)
    print(f"[AI Model] Model labels: {model.names}")
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
    Xử lý phân tích video. Hỗ trợ luồng stream hoặc file.
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

    # Các ngưỡng cấu hình
    confidence_threshold = float(settings.get("confidence_threshold", 0.25))
    enable_congestion = bool(settings.get("enable_congestion", True))
    enable_illegal_parking = bool(settings.get("enable_illegal_parking", True))
    enable_license_plate = bool(settings.get("enable_license_plate", True))
    stop_seconds = float(settings.get("stop_seconds", 30.0))
    move_threshold_px = float(settings.get("parking_move_threshold_px", 10.0))
    process_stride = max(1, int(settings.get("process_every_n_frames", 2)))

    capture = cv2.VideoCapture(str(input_video_path))
    if not capture.isOpened():
        raise RuntimeError("Không thể mở video để phân tích.")

    # Frame đầu tiên để lấy resolution THẬT
    success, first_frame = capture.read()
    if not success:
        capture.release()
        raise RuntimeError("Không thể đọc frame từ video.")
    
    frame_height, frame_width = first_frame.shape[:2]
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    ideal_frame_time = 1.0 / fps if fps > 0 else 0.033

    # Reset capture
    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

    # Tính toán tham số vẽ động dựa trên resolution thật của video
    f_scale, f_thick, f_offset = _get_drawing_params(frame_width)

    # Vùng ROI
    raw_roi = settings.get("roi_points")
    roi_points = _normalize_points(
        raw_roi, frame_width, frame_height, settings.get("roi_meta")
    ) or _full_frame_polygon(frame_width, frame_height)
    
    roi_polygon = _to_polygon(roi_points)
    
    no_parking_points = _normalize_points(
        settings.get("no_parking_points"), frame_width, frame_height, settings.get("no_park_meta")
    )
    
    if roi_polygon is None:
        raise ValueError("Vùng ROI không hợp lệ.")

    # Tính diện tích ROI 1 lần duy nhất (dùng để lọc box nhiễu trong vòng lặp)
    roi_contour_area = cv2.contourArea(roi_polygon)

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
    
    # ── AsyncIOWorker: Xử lý I/O nền (Telegram, ghi file, ghi DB) ──
    io_worker = AsyncIOWorker(num_threads=2, max_queue_size=200)
    io_worker.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    io_worker.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    io_worker.start()

    # Khởi tạo các Manager (inject io_worker)
    camera_id = int(settings.get("camera_id", 0))
    alpr_logger = ALPRLogger(db_callback=log_detected_license_plate, id_camera=camera_id)
    alpr_logger.io_worker = io_worker
    
    traffic_alert_manager = TrafficAlertManager()
    traffic_alert_manager.io_worker = io_worker
    
    parking_manager = ParkingManager(None, None) 
    parking_manager.no_park_polygon = _to_polygon(no_parking_points)
    parking_manager.stop_seconds = stop_seconds
    parking_manager.move_thr_px = move_threshold_px
    parking_manager.camera_id = camera_id  # Thêm để truyền ID Camera
    parking_manager.violation_callback = log_parking_violation  # Ủy quyền cho Manager lưu DB sau 10s
    parking_manager.io_worker = io_worker
    parking_manager.setup_detection(fps)
    
    # Telegram Bot
    parking_manager.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    parking_manager.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    try:
        start_bot_thread(traffic_alert_manager)
    except Exception as e:
        print(f"[Telegram] Không khởi động được polling thread: {e}")
    
    # Flags quản lý job
    logged_vehicle_ids: set = set()
    logged_violation_track_ids: set = set()
    last_db_traffic_level = 0
    last_congestion_record_id = None
    unique_passed_count = 0
    violation_events = []
    clear_start_time = 0  # Để theo dõi thời gian level = 0 liên tục
    true_clear_seconds = 5.0  # Chỉ coi là hết tắc khi level = 0 liên tục 5 giây

    frame_index = 0
    last_results = None
    started_at = time.time()
    latest_status = ""
    fps_prev_time = started_at
    fps_frame_count = 0
    current_fps = 0.0

    # Khởi tạo luồng nền nén ảnh JPEG (Giúp tăng FPS)
    preview_queue = queue.Queue(maxsize=1)
    preview_state = {"last_jpeg": None, "stop": False}

    def preview_encoder_worker():
        while not preview_state["stop"]:
            try:
                frame_to_encode = preview_queue.get(timeout=0.2)
                preview_state["last_jpeg"] = _encode_preview_frame(frame_to_encode)
            except queue.Empty:
                continue

    threading.Thread(target=preview_encoder_worker, daemon=True).start()

    # OCR Manager setup
    import logging
    logging.getLogger("ppocr").setLevel(logging.ERROR)
    ocr_reader = PaddleOCR(lang='en')
    ocr_manager = OCRManager(ocr_reader, alpr_logger=alpr_logger)
    if enable_license_plate:
        ocr_manager.start_worker()

    try:
        while capture.isOpened():
            # Xử lý Tạm dừng
            if pause_event and pause_event.is_set():
                if progress_callback is not None:
                    p_frame = frame.copy() if 'frame' in locals() else np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
                    # Vẽ hộp chữ nhật TẠM DỪNG to hơn trên 4K
                    rect_w, rect_h = int(300 * (frame_width/1280)), int(100 * (frame_height/720))
                    cv2.rectangle(p_frame, (frame_width//2 - rect_w//2, frame_height//2 - rect_h//2), 
                                 (frame_width//2 + rect_w//2, frame_height//2 + rect_h//2), (0, 0, 0), -1)
                    cv2.putText(p_frame, "TẠM DỪNG", (frame_width//2 - int(100 * (frame_width/1280)), frame_height//2 + int(15 * (frame_height/720))), 
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2 * (frame_width/1280), (0, 255, 255), f_thick + 1)
                    progress_callback({
                        "phase": "running_detection",
                        "processed_frames": frame_index,
                        "source_total_frames": total_frames,
                        "progress_percent": None,
                        "elapsed_seconds": round(time.time() - started_at, 1),
                        "latest_status": "Đang tạm dừng...",
                        "preview_jpeg": _encode_preview_frame(p_frame),
                    })
                time.sleep(0.5)
                continue

            frame_start_time = time.time()
            success, frame = capture.read()
            if not success:
                # Nếu là file video (total_frames > 0) thì quay lại từ đầu để lặp liên tục
                if total_frames > 0:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    success, frame = capture.read()
                    if not success: break
                else:
                    break

            clean_frame = frame.copy()
            if enable_illegal_parking:
                parking_manager.update_buffer(clean_frame.copy())

            frame_index += 1
            current_time = time.time()

            # Tracking
            if process_stride > 1 and (frame_index - 1) % process_stride != 0 and last_results is not None:
                results = last_results
            else:
                results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
                last_results = results

            if traffic_monitor is not None:
                traffic_monitor.reset_counters()

            current_plate_ids = set()
            valid_vehicles = []
            
            # Tiền xử lý list xe cho OCR
            for result in results:
                for box in result.boxes:
                    lbl = _canonical_label(model.names[int(box.cls[0])])
                    # Chỉ nạp ô tô, xe tải, xe bus vào danh sách chạy OCR (bỏ qua xe máy)
                    if lbl in PARKING_LABELS:
                        vx1, vy1, vx2, vy2 = map(int, box.xyxy[0])
                        v_track_id = int(box.id[0]) if box.id is not None else -1
                        valid_vehicles.append((vx1, vy1, vx2, vy2, v_track_id))

            # Vòng lặp chính xử lý detection
            for result in results:
                if frame_index % 100 == 0:
                    print(f"[AI] Frame {frame_index} found {len(result.boxes)} objects")
                for box in result.boxes:
                    label = _canonical_label(model.names[int(box.cls[0])])
                    if label not in DETECTABLE_LABELS: continue
                    if label in LICENSE_PLATE_LABELS and not enable_license_plate: continue

                    confidence = float(box.conf[0])
                    if confidence < confidence_threshold: continue

                    track_id = int(box.id[0]) if box.id is not None else -1
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2

                    in_roi = cv2.pointPolygonTest(roi_polygon, (center_x, center_y), False) >= 0
                    
                    if not in_roi:
                        continue

                    # Lọc nhiễu: Bỏ qua Bounding Box lớn bất thường (> 30% diện tích ROI)
                    # Chỉ áp dụng cho person, motorcycle, bicycle, car (bus/truck bản thân đã to)
                    SMALL_OBJECT_LABELS = {"person", "motorcycle", "bicycle", "car"}
                    box_area = (x2 - x1) * (y2 - y1)
                    if label in SMALL_OBJECT_LABELS and roi_contour_area > 0 and box_area > roi_contour_area * 0.3:
                        continue

                    # Xác định màu sắc nhãn
                    if label in BOX_COLORS:
                        box_color = BOX_COLORS[label]
                    else:
                        import hashlib
                        h = hashlib.md5(label.encode()).digest()
                        box_color = (h[0], h[1], h[2])
                        
                    label_text = _display_label(label)
                    display_label = label_text if track_id == -1 else f"ID:{track_id} {label_text}"

                    # 1. OCR Biển số
                    if label in LICENSE_PLATE_LABELS:
                        if enable_license_plate and track_id != -1:
                            processed_id = ocr_manager.process_plate(
                                frame, clean_frame, track_id, x1, y1, x2, y2, center_x, center_y, 
                                valid_vehicles, current_time, frame_index,
                                drawing_params=(f_scale, f_thick, f_offset)
                            )
                            if processed_id:
                                current_plate_ids.add(processed_id)
                        continue

                    # 2. Đếm phương tiện và người
                    if label == "person":
                        if traffic_monitor is not None: 
                            # Pass bbox của người để tính vào occupancy
                            traffic_monitor.log_person(bbox=(x1, y1, x2, y2))
                    elif label in VEHICLE_LABELS and traffic_monitor is not None:
                        traffic_monitor.log_vehicle(track_id, center_x, center_y, current_time, (x1, y1, x2, y2))

                    # 3. Quản lý Đỗ Xe Trái Phép
                    if label in VEHICLE_LABELS and enable_illegal_parking:
                        license_plate = None
                        if enable_license_plate:
                            for p_box in result.boxes:
                                p_lbl = _canonical_label(model.names[int(p_box.cls[0])])
                                if p_lbl in LICENSE_PLATE_LABELS:
                                    p_tid = int(p_box.id[0]) if p_box.id is not None else -1
                                    px1, py1, px2, py2 = map(int, p_box.xyxy[0])
                                    pcx, pcy = (px1 + px2) // 2, (py1 + py2) // 2
                                    if x1 <= pcx <= x2 and y1 <= pcy <= y2:
                                        if p_tid in ocr_manager.plate_confirmed:
                                            license_plate = ocr_manager.plate_confirmed[p_tid]
                                        break
                        
                        display_label_p, box_color_p = parking_manager.process_vehicle(
                            frame, clean_frame, track_id, label, center_x, center_y, frame_index, bbox=(x1, y1, x2, y2), license_plate=license_plate,
                            drawing_params=(f_scale, f_thick, f_offset)
                        )
                        
                        if display_label_p:
                            display_label = display_label_p
                            # Cập nhật biển số mới nhất vào recording qua method chính thức
                            if license_plate:
                                parking_manager.update_plate(track_id, license_plate)
                            
                            # Log vi phạm vào DB ngay khi trạng thái chuyển sang VIOLATION
                            if "VIOLATION" in display_label_p and track_id not in logged_violation_track_ids:
                                logged_violation_track_ids.add(track_id)

                        if box_color_p is not None: box_color = box_color_p

                    # 4. Lưu phương tiện đi qua
                    if track_id != -1 and track_id not in logged_vehicle_ids:
                        io_worker.enqueue_db_write(log_passed_vehicle, args=(camera_id, f"ID_{track_id}", label))
                        logged_vehicle_ids.add(track_id)
                        unique_passed_count += 1

                    # Vẽ frame
                    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, f_thick)
                    cv2.putText(frame, display_label, (x1, max(f_offset, y1-5)), cv2.FONT_HERSHEY_SIMPLEX, f_scale, box_color, f_thick)

            # Cập nhật Traffic Monitor
            if traffic_monitor is not None:
                avg_spd, st_txt, st_clr, lvl = traffic_monitor.calculate_speed_and_status(current_time, frame.shape)
                traffic_monitor.draw_status(frame, avg_spd, st_txt, st_clr, f_scale, f_thick)
                latest_status = st_txt
                
                # Cập nhật trạng thái traffic với debounce logic
                traffic_alert_manager.update_traffic_state(lvl, clean_frame)
                
                # ===== LOGIC GHI DATABASE VỚI DEBOUNCE & TRUE_CLEAR =====
                # Sử dụng confirmed_level từ traffic_alert_manager (đã debounce 1s)
                confirmed_lvl = traffic_alert_manager.confirmed_level
                
                # Tra cứu thời gian level = 0 liên tục để implement true_clear
                if confirmed_lvl == 0:
                    if clear_start_time == 0:
                        # Lần đầu nó = 0 → ghi lại thời điểm bắt đầu
                        clear_start_time = current_time
                    elif current_time - clear_start_time >= true_clear_seconds:
                        # Đã = 0 liên tục ≥5 giây → xác nhận HẾT TẮC dứt điểm
                        if last_db_traffic_level > 0 and last_congestion_record_id:
                            # Update end_time cho record tắc trong database
                            io_worker.enqueue_db_write(update_congestion_end_time, args=(last_congestion_record_id,))
                            last_congestion_record_id = None
                        last_db_traffic_level = 0
                else:
                    # Level > 0 → reset bộ đếm clear
                    clear_start_time = 0
                
                # Ghi DB chỉ khi:
                # 1. confirmed_level thay đổi (từ debounce)
                # 2. Hoặc level > 0 (escalation hoặc level mới)
                if confirmed_lvl != last_db_traffic_level:
                    if last_db_traffic_level > 0 and confirmed_lvl == 0 and last_congestion_record_id:
                        # Từ tắc → không tắc → update end_time
                        io_worker.enqueue_db_write(update_congestion_end_time, args=(last_congestion_record_id,))
                        last_congestion_record_id = None
                    elif confirmed_lvl > 0:
                        # Bắt đầu tắc hoặc escalation → ghi log mới (vẫn đồng bộ vì cần record_id)
                        last_congestion_record_id = log_congestion(camera_id, confirmed_lvl)
                    last_db_traffic_level = confirmed_lvl

            # Tính và vẽ FPS
            fps_frame_count += 1
            fps_now = time.time()
            if fps_now - fps_prev_time >= 1.0:
                current_fps = fps_frame_count / (fps_now - fps_prev_time)
                fps_prev_time = fps_now
                fps_frame_count = 0
            cv2.putText(frame, f"FPS: {int(current_fps)}", (30, frame_height - 20), cv2.FONT_HERSHEY_SIMPLEX, f_scale, (0, 255, 255), f_thick)
            
            # Nén ảnh JPEG bằng luồng phụ (không đợi)
            if progress_callback is not None:
                if preview_queue.empty():
                    # Đưa frame vào queue để luồng phụ nén (dùng copy để an toàn)
                    preview_queue.put(frame.copy())
                
                progress_callback({
                    "phase": "running_detection",
                    "processed_frames": frame_index,
                    "source_total_frames": total_frames,
                    "progress_percent": None,
                    "elapsed_seconds": round(time.time() - started_at, 1),
                    "latest_status": latest_status,
                    "preview_jpeg": preview_state["last_jpeg"],
                })

            # Control FPS
            elapsed = time.time() - frame_start_time
            if elapsed < ideal_frame_time:
                time.sleep(ideal_frame_time - elapsed)

    finally:
        preview_state["stop"] = True
        capture.release()
        if enable_license_plate: ocr_manager.stop_worker()
        if last_congestion_record_id: update_congestion_end_time(last_congestion_record_id)
        log_vehicle_count(camera_id, unique_passed_count)
        # Chờ io_worker xử lý hết các task còn lại trước khi kết thúc job
        io_worker.shutdown(wait=True, timeout=60.0)
        if should_cleanup_temp and input_video_path.exists():
            try: os.unlink(input_video_path)
            except: pass

    return {
        "processed_frames": frame_index,
        "processing_seconds": round(time.time() - started_at, 2),
        "parking_violation_count": len(logged_violation_track_ids),
        "unique_passed_count": unique_passed_count,
        "latest_status": latest_status,
    }

from application.interfaces.detection_interface import DetectionInterface

class YoloDetectionService(DetectionInterface):
    def process_video(self, input_stream=None, input_path=None, input_ext=None, settings=None, progress_callback=None, pause_event=None):
        return process_video(input_stream, input_path, input_ext, settings, progress_callback, pause_event)
