import numpy as np
import cv2

# --- NGƯỠNG CẢNH BÁO GIAO THÔNG (CONGESTION THRESHOLDS) ---
CONG_COUNT_THR = 10              # Cấp 1: Số xe tối thiểu để được coi là "Đông đúc L1"
CONG_PEOPLE_THR = 30             # Cấp 1: Số người tối thiểu để được coi là "Đông đúc L1"
CONG_AREA_PERCENT_THR = 40.0     # Cấp 2: % Diện tích vùng giám sát tối thiểu bị lấp đầy để coi là "Rất đông L2"
CONG_SPEED_THR = 10.0            # Cấp 3: Vận tốc di chuyển tối đa (px/s) để bị coi là "Tắc nghẽn L3"
MAX_VEHICLE_AREA_RATIO = 0.3     # Bỏ qua những hộp Box nhiễu có diện tích lớn hơn 30% vùng giám sát (Tránh lỗi YOLO)

class TrafficMonitor:
    def __init__(self, roi_polygon=None):
        self.roi_polygon = roi_polygon
        self.roi_area = cv2.contourArea(np.array(self.roi_polygon)) if self.roi_polygon is not None else 0.0
        self.track_history = {}
        self.vehicle_count = 0
        self.people_count = 0
        self.current_ids_in_roi = []
        
        # Biến mới để lưu danh sách Bounding Box thay vì cộng dồn diện tích
        self.current_bboxes = [] 
        self.last_occupancy = 0.0
        
    def reset_counters(self):
        self.vehicle_count = 0
        self.people_count = 0
        self.current_ids_in_roi = []
        self.current_bboxes = [] # Reset list

    def log_person(self):
        self.people_count += 1

    def log_vehicle(self, track_id, cx, cy, current_time, bbox=None):
        """bbox truyền vào dưới dạng tuple (x1, y1, x2, y2)"""
        self.vehicle_count += 1
        if bbox is not None:
            # Lọc nhiễu: Bỏ qua bounding box lớn dị thường (lỗi YOLO) > 30% diện tích ROI
            if self.roi_area > 0:
                area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                if area <= (self.roi_area * MAX_VEHICLE_AREA_RATIO):
                    self.current_bboxes.append(bbox)
            else:
                self.current_bboxes.append(bbox)
            
        if track_id != -1:
            self.current_ids_in_roi.append(track_id)
            if track_id not in self.track_history:
                self.track_history[track_id] = []
            self.track_history[track_id].append((cx, cy, current_time))
            self.track_history[track_id] = [p for p in self.track_history[track_id] if current_time - p[2] <= 2.0]

    def calculate_speed_and_status(self, current_time, frame_shape):
        """Cần truyền thêm frame.shape (Kích thước video) để tạo Mask"""
        # 1. TÍNH VẬN TỐC
        total_speed = 0.0
        valid_speed_count = 0
        for tid in list(self.track_history.keys()):
            if tid not in self.current_ids_in_roi:
                if len(self.track_history[tid]) > 0 and (current_time - self.track_history[tid][-1][2]) > 1.0:
                    del self.track_history[tid]
                continue
            points = self.track_history[tid]
            if len(points) >= 2:
                dt = points[-1][2] - points[0][2]
                if dt > 0.2: 
                    speed = np.sqrt((points[-1][0]-points[0][0])**2 + (points[-1][1]-points[0][1])**2) / dt 
                    total_speed += speed
                    valid_speed_count += 1

        avg_speed = total_speed / valid_speed_count if valid_speed_count > 0 else 0.0

        # 2. TÍNH % DIỆN TÍCH BẰNG MASKING (Chống Overlap & Tràn viền)
        occupancy_percent = 0.0
        if self.roi_polygon is not None and len(self.current_bboxes) > 0 and len(frame_shape) >= 2:
            h, w = frame_shape[:2]
            
            # Tạo nền đen
            roi_mask = np.zeros((h, w), dtype=np.uint8)
            vehicles_mask = np.zeros((h, w), dtype=np.uint8)
            
            # Vẽ ROI màu trắng (255)
            cv2.fillPoly(roi_mask, [np.array(self.roi_polygon, dtype=np.int32)], 255)
            
            # Vẽ các Bounding Box màu trắng (255)
            for (x1, y1, x2, y2) in self.current_bboxes:
                x1, y1, x2, y2 = int(max(0, x1)), int(max(0, y1)), int(min(w, x2)), int(min(h, y2))
                cv2.rectangle(vehicles_mask, (x1, y1), (x2, y2), 255, -1)
                
            # Giao 2 vùng lại (Chỉ lấy phần xe nằm TRONG ROI)
            overlap_mask = cv2.bitwise_and(vehicles_mask, roi_mask)
            
            # Đếm số pixel màu trắng
            roi_pixel_area = cv2.countNonZero(roi_mask)
            occupied_pixel_area = cv2.countNonZero(overlap_mask)
            
            if roi_pixel_area > 0:
                occupancy_percent = (occupied_pixel_area / roi_pixel_area) * 100.0

        self.last_occupancy = occupancy_percent # Lưu lại để vẽ lên màn hình

        # 3. ĐÁNH GIÁ MỨC ĐỘ
        is_high_count = (self.vehicle_count >= CONG_COUNT_THR) or (self.people_count >= CONG_PEOPLE_THR)

        if not is_high_count and occupancy_percent < CONG_AREA_PERCENT_THR:
            traffic_level = 0
            status_text, status_color = "Trang thai: Thong thoang (MUC 0)", (0, 255, 0)
        elif is_high_count and occupancy_percent < CONG_AREA_PERCENT_THR:
            traffic_level = 1
            if self.vehicle_count >= CONG_COUNT_THR:
                status_text, status_color = f"Trang thai: Dong duc (MUC 1) - {self.vehicle_count} xe", (0, 165, 255)
            else:
                status_text, status_color = f"Trang thai: Dong duc (MUC 1) - {self.people_count} nguoi", (0, 165, 255)
        elif occupancy_percent >= CONG_AREA_PERCENT_THR and avg_speed > CONG_SPEED_THR:
            traffic_level = 2
            status_text, status_color = f"Trang thai: Rat dong (MUC 2) - {occupancy_percent:.1f}% dien tich", (0, 100, 255)
        elif occupancy_percent >= CONG_AREA_PERCENT_THR and avg_speed <= CONG_SPEED_THR:
            traffic_level = 3
            status_text, status_color = f"Trang thai: TAC NGHEN (MUC 3) - {avg_speed:.1f} px/s", (0, 0, 255)
        else:
            traffic_level = 0
            status_text, status_color = "Trang thai: Thong thoang (MUC 0)", (0, 255, 0)
            
        return avg_speed, status_text, status_color, traffic_level

    def draw_status(self, frame, avg_speed, status_text, status_color):
        cv2.putText(frame, f"Vehicles: {self.vehicle_count} | People: {self.people_count}", (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(frame, f"Occupancy: {self.last_occupancy:.1f}%", (30, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(frame, f"Avg Speed: {int(avg_speed)} px/s", (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(frame, status_text, (30, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.9, status_color, 2)