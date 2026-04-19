import os
import csv
import cv2
from datetime import datetime

class ALPRLogger:
    def __init__(self, disappear_threshold=1800, db_callback=None, id_camera=0):
        self.logs_dir = "logs"
        self.plates_dir = os.path.join(self.logs_dir, "plates")
        self.csv_path = os.path.join(self.logs_dir, "ALPR_log.csv")
        self.disappear_threshold = disappear_threshold
        self.plate_sessions = {}
        self.db_callback = db_callback
        self.id_camera = id_camera
        
        # AsyncIOWorker (inject từ bên ngoài, nếu None sẽ fallback gọi đồng bộ)
        self.io_worker = None
        
        os.makedirs(self.plates_dir, exist_ok=True)
        
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Time", "Frame", "Plate", "Full_Frame_Image_Path"])

    def process_plate(self, plate_text, current_frame, plate_img, full_frame, plate_coords):
        is_new_session = False
        
        if plate_text not in self.plate_sessions:
            is_new_session = True
        else:
            frames_missing = current_frame - self.plate_sessions[plate_text]["last_seen"]
            if frames_missing > self.disappear_threshold:
                is_new_session = True
                
        # Luôn luôn cập nhật thời điểm xuất hiện cuối cùng của xe này
        self.plate_sessions[plate_text] = {"last_seen": current_frame}
        
        if is_new_session:
            self._save_log(plate_text, current_frame, full_frame, plate_coords)
            
    def _save_log(self, plate_text, current_frame, full_frame, plate_coords):
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        
        # Create date-based folder structure: logs/plates/YYYY/MM/DD/
        date_dir = os.path.join(self.plates_dir, year, month, day)
        os.makedirs(date_dir, exist_ok=True)
        
        img_name = f"{plate_text}_{timestamp}.jpg"
        img_path = os.path.join(date_dir, img_name)
        
        # Make a copy of full_frame to draw on
        evidence_frame = full_frame.copy()
        
        # Drawing parameters based on resolution
        h, w = full_frame.shape[:2]
        f_thick = max(1, int(round(2 * (w / 1280))))
        
        # Draw bounding box on the evidence copy
        x1, y1, x2, y2 = plate_coords
        cv2.rectangle(evidence_frame, (x1, y1), (x2, y2), (0, 0, 255), f_thick)
        
        # Web path (forward slashes)
        web_path = img_path.replace(os.sep, "/")
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        csv_row = [time_str, current_frame, plate_text, web_path]
        
        if self.io_worker is not None:
            # ── Async mode: đẩy vào queue, return ngay ──
            self.io_worker.enqueue_save_image(img_path, evidence_frame)
            self.io_worker.enqueue_csv_append(self.csv_path, csv_row)
            if self.db_callback:
                self.io_worker.enqueue_db_write(
                    self.db_callback,
                    kwargs={
                        "license_plate": plate_text,
                        "detection_count": 1,
                        "avg_confidence": 0.0,
                        "image_paths": web_path,
                        "camera_id": self.id_camera,
                    }
                )
        else:
            # ── Fallback: gọi đồng bộ (legacy, cho desktop GUI) ──
            cv2.imwrite(img_path, evidence_frame)

            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(csv_row)
                
            if self.db_callback:
                try:
                    self.db_callback(
                        license_plate=plate_text,
                        detection_count=1,
                        avg_confidence=0.0,
                        image_paths=web_path,
                        camera_id=self.id_camera
                    )
                except Exception as e:
                    print(f"[ALPR Database] Lỗi khi ghi vào database: {e}")

