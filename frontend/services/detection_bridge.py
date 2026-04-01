from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.parking.parking_logic import WAITING, VIOLATION, ViolationLogic
from modules.traffic.traffic_monitor import TrafficMonitor

TRAFFIC_LABELS = {"person", "car", "motorcycle", "bus", "truck"}
VEHICLE_LABELS = {"car", "motorcycle", "bus", "truck"}
PARKING_LABELS = {"car", "bus", "truck"}
LICENSE_PLATE_LABELS = {"license_plate", "licenseplate", "number_plate", "licence_plate"}
DETECTABLE_LABELS = TRAFFIC_LABELS | LICENSE_PLATE_LABELS
BOX_COLORS = {
    "person": (0, 255, 0),
    "car": (255, 255, 0),
    "motorcycle": (0, 255, 255),
    "bus": (0, 165, 255),
    "truck": (255, 0, 255),
    "license_plate": (255, 105, 180),
}


def _canonical_label(label: Any) -> str:
    return str(label).strip().lower().replace("-", "_").replace(" ", "_")


def _display_label(label_key: str) -> str:
    if label_key in LICENSE_PLATE_LABELS:
        return "bien so"
    return label_key.replace("_", " ")


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


class ParkingOverlayMonitor:
    def __init__(
        self,
        no_parking_points: Optional[List[List[int]]],
        fps: float,
        stop_seconds: float = 30.0,
        move_threshold_px: float = 10.0,
    ) -> None:
        self.no_parking_polygon = _to_polygon(no_parking_points)
        self.logic = ViolationLogic(
            stop_seconds=stop_seconds,
            move_thr_px=move_threshold_px,
            cooldown_seconds=30.0,
            fps=fps,
        )
        self.confirmed_violation_ids: set[int] = set()

    def process_vehicle(
        self,
        track_id: int,
        label: str,
        center_x: int,
        center_y: int,
        frame_index: int,
    ) -> Tuple[Optional[str], Optional[Tuple[int, int, int]], Optional[Dict[str, Any]]]:
        if self.no_parking_polygon is None:
            return None, None, None
        if track_id == -1 or label not in PARKING_LABELS:
            return None, None, None
        if cv2.pointPolygonTest(self.no_parking_polygon, (center_x, center_y), False) < 0:
            return None, None, None

        state, just_changed = self.logic.update(track_id, (center_x, center_y), frame_index)

        if state == WAITING:
            return (
                f"ID:{track_id} {label} WAITING",
                (0, 165, 255),
                None,
            )

        if state == VIOLATION:
            event = None
            if just_changed and track_id not in self.confirmed_violation_ids:
                self.confirmed_violation_ids.add(track_id)
                event = {
                    "track_id": track_id,
                    "label": label,
                    "frame_index": frame_index,
                }
            return (
                f"ID:{track_id} {label} VIOLATION",
                (0, 0, 255),
                event,
            )

        return (
            f"ID:{track_id} {label} MONITOR",
            (255, 255, 255),
            None,
        )

    def draw_zone(self, frame: np.ndarray) -> None:
        if self.no_parking_polygon is None:
            return
        overlay = frame.copy()
        cv2.fillPoly(overlay, [self.no_parking_polygon], (0, 0, 180))
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
        cv2.polylines(frame, [self.no_parking_polygon], True, (0, 0, 255), 2)


def process_video(
    input_path: str,
    output_path: str,
    settings: Dict[str, Any],
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    input_video_path = Path(input_path)
    output_video_path = Path(output_path)
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_video_path.exists():
        raise FileNotFoundError(f"Khong tim thay video dau vao: {input_video_path}")

    model_path = Path(str(settings["model_path"]))
    if not model_path.exists():
        raise FileNotFoundError(f"Khong tim thay model YOLO: {model_path}")

    confidence_threshold = float(settings.get("confidence_threshold", 0.32))
    enable_congestion = bool(settings.get("enable_congestion", True))
    enable_illegal_parking = bool(settings.get("enable_illegal_parking", True))
    enable_license_plate = bool(settings.get("enable_license_plate", True))
    stop_seconds = float(settings.get("stop_seconds", 30.0))
    move_threshold_px = float(settings.get("parking_move_threshold_px", 10.0))
    process_stride = max(1, int(settings.get("process_every_n_frames", 2)))

    capture = cv2.VideoCapture(str(input_video_path))
    if not capture.isOpened():
        raise RuntimeError("Khong the mo video de chay kiem tra.")

    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    roi_points = _normalize_points(settings.get("roi_points")) or _full_frame_polygon(
        frame_width, frame_height
    )
    no_parking_points = _normalize_points(settings.get("no_parking_points"))
    roi_polygon = _to_polygon(roi_points)

    if roi_polygon is None:
        raise ValueError("ROI khong hop le.")

    writer = cv2.VideoWriter(
        str(output_video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (frame_width, frame_height),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError("Khong the tao file video ket qua.")

    if progress_callback is not None:
        progress_callback(
            {
                "phase": "loading_model",
                "processed_frames": 0,
                "source_total_frames": total_frames,
                "progress_percent": 0.0,
                "elapsed_seconds": 0.0,
                "latest_status": "Dang tai model YOLO...",
            }
        )

    model = _load_model(model_path)
    traffic_monitor = TrafficMonitor(roi_polygon=roi_polygon) if enable_congestion else None
    parking_monitor = (
        ParkingOverlayMonitor(
            no_parking_points=no_parking_points,
            fps=fps,
            stop_seconds=stop_seconds,
            move_threshold_px=move_threshold_px,
        )
        if enable_illegal_parking
        else None
    )

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
    latest_status = "Dang bat dau phan tich"
    violation_events: List[Dict[str, Any]] = []

    try:
        while True:
            success, frame = capture.read()
            if not success:
                break

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

                    if parking_monitor is not None and label in VEHICLE_LABELS:
                        override_label, override_color, event = parking_monitor.process_vehicle(
                            track_id=track_id,
                            label=label,
                            center_x=center_x,
                            center_y=center_y,
                            frame_index=frame_index,
                        )
                        if override_label:
                            display_label = override_label
                        if override_color is not None:
                            box_color = override_color
                        if event is not None:
                            violation_events.append(event)

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

            cv2.polylines(frame, [roi_polygon], True, (255, 0, 0), 2)
            if parking_monitor is not None:
                parking_monitor.draw_zone(frame)

            if traffic_monitor is not None:
                average_speed, status_text, status_color, traffic_level = (
                    traffic_monitor.calculate_speed_and_status(current_time, frame.shape)
                )
                traffic_monitor.draw_status(frame, average_speed, status_text, status_color)
                latest_status = status_text
                max_vehicle_count = max(max_vehicle_count, traffic_monitor.vehicle_count)
                max_people_count = max(max_people_count, traffic_monitor.people_count)
                max_occupancy = max(max_occupancy, traffic_monitor.last_occupancy)
                highest_traffic_level = max(highest_traffic_level, traffic_level)
                if traffic_level > 0:
                    congestion_frames += 1
            else:
                latest_status = "Tat phat hien tac nghen"
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
                plate_status = f"Bien so: {current_license_plate_count}"
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

            feature_text = (
                f"Tac nghen: {'ON' if enable_congestion else 'OFF'} | "
                f"Do xe sai quy dinh: {'ON' if enable_illegal_parking else 'OFF'} | "
                f"Bien so: {'ON' if enable_license_plate else 'OFF'}"
            )
            cv2.putText(
                frame,
                feature_text,
                (30, frame_height - 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )
            cv2.putText(
                frame,
                f"Frame: {frame_index}",
                (30, frame_height - 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )

            writer.write(frame)

            if progress_callback is not None:
                now = time.time()
                if frame_index == 1 or now - last_progress_emit >= 1.0:
                    progress_callback(
                        {
                            "phase": "running_detection",
                            "processed_frames": frame_index,
                            "source_total_frames": total_frames,
                            "progress_percent": round((frame_index / total_frames) * 100, 2)
                            if total_frames
                            else None,
                            "elapsed_seconds": round(now - started_at, 1),
                            "latest_status": latest_status,
                            "preview_jpeg": _encode_preview_frame(frame),
                        }
                    )
                    last_progress_emit = now
    finally:
        capture.release()
        writer.release()

    processing_seconds = max(0.001, time.time() - started_at)
    parking_violation_ids = (
        sorted(parking_monitor.confirmed_violation_ids) if parking_monitor is not None else []
    )

    if progress_callback is not None:
        progress_callback(
            {
                "phase": "finalizing_output",
                "processed_frames": frame_index,
                "source_total_frames": total_frames,
                "progress_percent": 100.0,
                "elapsed_seconds": round(processing_seconds, 1),
                "latest_status": "Dang hoan tat video ket qua...",
            }
        )

    return {
        "input_path": str(input_video_path),
        "output_path": str(output_video_path),
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
        "feature_flags": {
            "enable_congestion": enable_congestion,
            "enable_illegal_parking": enable_illegal_parking,
            "enable_license_plate": enable_license_plate,
        },
        "violation_events": violation_events[:20],
    }
