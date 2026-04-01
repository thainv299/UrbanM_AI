import os
import csv
import cv2
from datetime import datetime

class ALPRLogger:
    def __init__(self, disappear_threshold=1800):
        self.logs_dir = "logs"
        self.plates_dir = os.path.join(self.logs_dir, "plates")
        self.csv_path = os.path.join(self.logs_dir, "ALPR_log.csv")
        self.disappear_threshold = disappear_threshold
        self.plate_sessions = {}
        
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_name = f"{timestamp}_{plate_text}_evidence.jpg"
        img_path = os.path.join(self.plates_dir, img_name)
        
        # Make a copy of full_frame to draw on
        evidence_frame = full_frame.copy()
        
        # Draw bounding box on the evidence copy
        x1, y1, x2, y2 = plate_coords
        cv2.rectangle(evidence_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
        
        # Save image
        cv2.imwrite(img_path, evidence_frame)
        
        # Append object to csv log
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), current_frame, plate_text, img_path])
