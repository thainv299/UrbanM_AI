import cv2
import numpy as np
import os
import json
import tkinter as tk
from tkinter import filedialog
from collections import deque
import threading
import datetime
import time
import math
from .parking_logic import ViolationLogic, MOVING, WAITING, VIOLATION, RECORDING_DONE
from modules.utils.telegram_bot import send_telegram_image, send_telegram_video
from modules.utils.common_utils import ensure_dir, now_ts

class ParkingManager:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.no_park_polygon = None
        
        # --- CẤU HÌNH ĐỖ XE TRÁI PHÉP ---
        self.stop_seconds = 30
        self.move_thr_px = 10.0
        self.cooldown_seconds = 30.0
        self.telegram_enabled = True
        self.save_violation_frames = True
        self.telegram_bot_token = ""
        self.telegram_chat_id = ""

        self.logic = None
        self.frame_buffer = None
        self.fps = 30.0
        self.active_recordings = {}
        self.waiting_vehicles = {}

    def init_ui(self):
        self.frame_no_park = tk.LabelFrame(self.root, text="3. Quản lý Vùng Cấm Đỗ", font=("Arial", 11, "bold"))
        self.frame_no_park.pack(fill="x", padx=10, pady=5)

        self.btn_load_no_park = tk.Button(self.frame_no_park, text="Load Vùng Cấm", command=self.load_no_park, width=14, state=tk.NORMAL, font=("Arial", 10))
        self.btn_load_no_park.grid(row=0, column=0, padx=5, pady=5)

        self.btn_clear_no_park = tk.Button(self.frame_no_park, text="Hủy Vùng Cấm", command=self.clear_no_park, width=12, state=tk.NORMAL, font=("Arial", 10))
        self.btn_clear_no_park.grid(row=0, column=1, padx=5, pady=5)

        self.btn_draw_no_park = tk.Button(self.frame_no_park, text="Vẽ Vùng Cấm", command=self.open_draw_no_park, width=14, state=tk.DISABLED, font=("Arial", 10))
        self.btn_draw_no_park.grid(row=0, column=2, padx=5, pady=5)

        self.lbl_no_park_status = tk.Label(self.frame_no_park, text="Vùng cấm: Chưa có", fg="red", font=("Arial", 10, "italic"))
        self.lbl_no_park_status.grid(row=1, column=0, columnspan=3, pady=2)

    def load_no_park(self):
        path = filedialog.askopenfilename(title="Chọn File Vùng Cấm", filetypes=[("JSON Files", "*.json")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.no_park_polygon = np.array(json.load(f).get("points"))
                self.lbl_no_park_status.config(text=f"Vùng cấm: Đã load {os.path.basename(path)}", fg="green")

    def clear_no_park(self):
        self.no_park_polygon = None
        self.lbl_no_park_status.config(text="Vùng cấm: Chưa có", fg="red")

    def open_draw_no_park(self):
        if not self.app.video_path: return
        cap = cv2.VideoCapture(self.app.video_path)
        ret, first_frame = cap.read()
        cap.release()
        polygon = self.app.draw_polygon(first_frame, self.no_park_polygon, "Draw No Parking Zone", (0, 0, 255))
        if polygon is not None:
            self.no_park_polygon = polygon
            self.lbl_no_park_status.config(text="Vùng cấm: Đã vẽ tạm", fg="orange")
            
            # Thêm prompt lưu file
            from tkinter import messagebox
            if messagebox.askyesno("Lưu Vùng Cấm", "Bạn có muốn lưu vùng cấm đỗ này không?"):
                video_name = os.path.splitext(os.path.basename(self.app.video_path))[0]
                save_dir = "layouts"
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, f"{video_name}_parking_layout.json")
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump({"points": self.no_park_polygon.tolist()}, f)
                self.lbl_no_park_status.config(text=f"Vùng cấm: Đã lưu {os.path.basename(save_path)}", fg="green")

    def enable_draw_btn(self):
        self.btn_draw_no_park.config(state=tk.NORMAL)

    def setup_detection(self, fps):
        self.fps = fps
        ensure_dir("logs/violations")
        self.logic = ViolationLogic(self.stop_seconds, self.move_thr_px, self.cooldown_seconds, fps=fps)
        self.frame_buffer = deque(maxlen=int(5 * fps))
        self.active_recordings = {}
        self.waiting_vehicles = {}
        self.ghost_tracks = {}
        self.last_seen = {}

    def update_buffer(self, frame_copy):
        if self.frame_buffer is not None:
            self.frame_buffer.append(frame_copy)
            
            to_delete = []
            for track_id, record_data in self.active_recordings.items():
                record_data['frames'].append(frame_copy.copy())
                record_data['frames_needed'] -= 1
                if record_data['frames_needed'] <= 0:
                    threading.Thread(target=self._save_evidence_and_notify_thread, args=(track_id, record_data), daemon=True).start()
                    self.logic.set_recording_done(track_id)
                    to_delete.append(track_id)
                    
            for tid in to_delete:
                del self.active_recordings[tid]

    def _send_warning_thread(self, img_t0, caption):
        img_path = os.path.join("logs", "violations", f"temp_warning_{now_ts()}.jpg")
        cv2.imwrite(img_path, img_t0)
        send_telegram_image(img_path, caption, self.telegram_bot_token, self.telegram_chat_id)
        try: os.remove(img_path)
        except: pass

    def _save_evidence_and_notify_thread(self, track_id, data):
        evt_id = f"EVT_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{track_id}"
        plate_folder = data.get('plate', f"ID_{track_id}")
        save_dir = os.path.join("logs", "violations", plate_folder, evt_id)
        os.makedirs(save_dir, exist_ok=True)
        
        img_t0_path = os.path.join(save_dir, "img_T0.jpg")
        img_t1_path = os.path.join(save_dir, "img_T1.jpg")
        combined_path = os.path.join(save_dir, "combined_alert.jpg")
        video_path = os.path.join(save_dir, "video_record.mp4")
        json_path = os.path.join(save_dir, "evidence.json")
        
        cv2.imwrite(img_t0_path, data['img_t0'])
        cv2.imwrite(img_t1_path, data['img_t1'])
        
        # Ghép ảnh thông báo nguyên khối (T0 + T1)
        h1, w1 = data['img_t0'].shape[:2]
        h2, w2 = data['img_t1'].shape[:2]
        target_w = max(w1, w2)
        img1 = cv2.resize(data['img_t0'], (target_w, int(h1 * target_w / w1)))
        img2 = cv2.resize(data['img_t1'], (target_w, int(h2 * target_w / w2)))
        cv2.putText(img1, "T0: Bat dau do", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(img2, "T1: Vi pham", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        combined = np.vstack((img1, img2))
        cv2.putText(combined, f"PLATE: {plate_folder}", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        cv2.imwrite(combined_path, combined)
        
        # Lưu video bằng chứng
        if data['frames']:
            fh, fw = data['frames'][0].shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(video_path, fourcc, self.fps, (fw, fh))
            for f in data['frames']:
                out.write(f)
            out.release()
            
        # Lưu file Metadata JSON
        meta = {
            "track_id": track_id,
            "plate": plate_folder,
            "label": data.get('label', ''),
            "start_time": data.get('start_time', datetime.datetime.now()).strftime('%Y-%m-%d %H:%M:%S'),
            "violation_time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(json_path, 'w', encoding='utf-8') as jf:
            json.dump(meta, jf, indent=4)
            
        if self.telegram_enabled:
            caption_img = f"🚨 VI PHẠM CHỐT: Xe {plate_folder} đỗ sai quy định."
            send_telegram_image(combined_path, caption_img, self.telegram_bot_token, self.telegram_chat_id)
            caption_vid = f"Bằng chứng Video 15s cho xe {plate_folder}"
            send_telegram_video(video_path, caption_vid, self.telegram_bot_token, self.telegram_chat_id)

    def process_vehicle(self, frame, clean_frame, track_id, label, cx, cy, frame_count, bbox=None):
        """Kiểm tra và cập nhật trạng thái đỗ xe, trả về display_label và box_color mới (nếu có)"""
        if self.logic is None:
            return None, None
            
        # Bỏ qua xe máy, xe đạp và người đi bộ (không xét lỗi đỗ trái phép)
        if label in ["motorcycle", "bicycle", "person"]:
            return None, None

        current_time = time.time()

        # 1. Dọn dẹp Ghost Tracks hết hạn (> 10s)
        expired_ghosts = [gid for gid, ginfo in self.ghost_tracks.items() if current_time - ginfo['lost_time'] > 10.0]
        for gid in expired_ghosts:
            del self.ghost_tracks[gid]

        # 2. Phát hiện xe bị mất dấu (> 1s) và đẩy vào Ghost Tracks
        lost_ids = [lid for lid, linfo in self.last_seen.items() if current_time - linfo['last_time'] > 1.0]
        for lid in lost_ids:
            self.ghost_tracks[lid] = {
                'cx': self.last_seen[lid]['cx'],
                'cy': self.last_seen[lid]['cy'],
                'lost_time': current_time
            }
            if lid in self.logic.states:
                self.ghost_tracks[lid]['logic_state'] = self.logic.states.pop(lid)
            if lid in self.waiting_vehicles:
                self.ghost_tracks[lid]['waiting_data'] = self.waiting_vehicles.pop(lid)
            del self.last_seen[lid]

        # 3. Thuật toán Spatial Re-ID (Sáp nhập Track vỡ nếu xuất hiện ID mới tại cùng vị trí)
        if track_id not in self.last_seen:
            best_match = None
            min_dist = float('inf')
            max_dist_px = max(60.0, self.move_thr_px * 2) # Khoảng cách tối đa cho phép nối ghép
            
            for gid, ginfo in self.ghost_tracks.items():
                dist = math.hypot(cx - ginfo['cx'], cy - ginfo['cy'])
                if dist < max_dist_px and dist < min_dist:
                    min_dist = dist
                    best_match = gid
            
            if best_match is not None:
                # Nối ghép thành công! Khôi phục trí nhớ cho xe
                ginfo = self.ghost_tracks.pop(best_match)
                if 'logic_state' in ginfo:
                    self.logic.states[track_id] = ginfo['logic_state']
                if 'waiting_data' in ginfo:
                    self.waiting_vehicles[track_id] = ginfo['waiting_data']

        # Cập nhật vị trí và dấu thời gian hiện tại
        self.last_seen[track_id] = {'cx': cx, 'cy': cy, 'last_time': current_time}

        in_no_park = False
        if self.no_park_polygon is not None:
            in_no_park = cv2.pointPolygonTest(self.no_park_polygon, (cx, cy), False) >= 0

        if in_no_park:
            state, just_changed = self.logic.update(track_id, (cx, cy), frame_count)
            
            if state == WAITING:
                box_color = (0, 165, 255) # Orange
                state_str = "WAITING"
                if just_changed:
                    img_t0 = clean_frame.copy()
                    if bbox is not None:
                        x1, y1, x2, y2 = bbox
                        cv2.rectangle(img_t0, (x1, y1), (x2, y2), box_color, 3)
                        cv2.putText(img_t0, f"{label.upper()} {track_id} - BAT DAU DO", (x1, max(0, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, box_color, 2)
                        
                    self.waiting_vehicles[track_id] = {'img_t0': img_t0, 'start_time': datetime.datetime.now()}
                    if self.telegram_enabled:
                        caption = f"⚠️ CẢNH BÁO: Xe ID {track_id} bắt đầu đỗ tại vùng cấm. Đang đếm giờ..."
                        threading.Thread(target=self._send_warning_thread, args=(img_t0, caption), daemon=True).start()
                        
            elif state == VIOLATION:
                box_color = (0, 0, 255) # Red
                state_str = "VIOLATION"
                if just_changed:
                    waiting_data = self.waiting_vehicles.get(track_id, {})
                    img_t0 = waiting_data.get('img_t0', clean_frame.copy())
                    start_time = waiting_data.get('start_time', datetime.datetime.now())
                    
                    img_t1 = clean_frame.copy()
                    if bbox is not None:
                        x1, y1, x2, y2 = bbox
                        cv2.rectangle(img_t1, (x1, y1), (x2, y2), box_color, 4)
                        cv2.putText(img_t1, f"{label.upper()} {track_id} - VI PHAM!", (x1, max(0, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, box_color, 3)
                        
                    self.active_recordings[track_id] = {
                        'frames': list(self.frame_buffer),
                        'frames_needed': int(10 * self.fps),
                        'img_t0': img_t0,
                        'img_t1': img_t1,
                        'plate': f"ID_{track_id}",
                        'start_time': start_time,
                        'label': label
                    }
                    
                    h, w = frame.shape[:2]
                    cv2.rectangle(frame, (0, 0), (w, 80), (0, 0, 0), -1)
                    cv2.putText(frame, "VI PHAM: DO XE SAI QUY DINH!", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3)
                    
            elif state == RECORDING_DONE:
                box_color = (0, 0, 255)
                state_str = "RECORDED"
            else:
                box_color = None
                state_str = "MOVING"
                
            display_label = f"ID:{track_id} {label} {state_str}"
            return display_label, box_color
        return None, None

    def draw_polygon_overlay(self, frame):
        """Vẽ vùng cấm đỗ màu đỏ lên frame"""
        if self.no_park_polygon is not None:
            overlay = frame.copy()
            cv2.fillPoly(overlay, [self.no_park_polygon], (0, 0, 180))
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
            cv2.polylines(frame, [self.no_park_polygon], True, (0, 0, 255), 2)
