import cv2
import numpy as np
import re
import math
from collections import Counter
from ultralytics import YOLO
from paddleocr import PaddleOCR

VIDEO_PATH = r"E:\DATN_code\videos\Parking\parking_video3.mp4"
MODEL_PATH = r"E:\DATN_code\models\best.pt"

OCR_INTERVAL    = 4       
VOTE_THRESHOLD  = 3       
CONF_THRESHOLD  = 0.32    
MAX_LOST_FRAMES = 5       


def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def preprocess_plate(img_bgr):
    h, w = img_bgr.shape[:2]
    img_scaled = cv2.resize(img_bgr, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    
    img_gray = cv2.cvtColor(img_scaled, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(4, 4))
    img_enhanced = clahe.apply(img_gray)
    
    img_enhanced_bgr = cv2.cvtColor(img_enhanced, cv2.COLOR_GRAY2BGR)
    return img_enhanced_bgr


def correct_plate_format(text):
    """Sửa lỗi OCR: Ép đúng vị trí nào là số, vị trí nào là chữ."""
    if len(text) < 6: # Tối thiểu 2 số + 1 chữ + 3 số (thường là 7, nhưng chặn trước ở 6)
        return text

    dict_char_to_num = {'O': '0', 'Q': '0', 'I': '1', 'Z': '2', 'S': '5', 'G': '6', 'B': '8', 'A': '4'}
    dict_num_to_char = {'0': 'D', '8': 'B', '4': 'A', '5': 'S', '2': 'Z'}

    text_list = list(text)

    # 1. Hai ký tự đầu tiên PHẢI là số (Mã tỉnh)
    for i in range(0, min(2, len(text_list))):
        if text_list[i].isalpha() and text_list[i] in dict_char_to_num:
            text_list[i] = dict_char_to_num[text_list[i]]

    # 2. Ký tự thứ 3 PHẢI là chữ (Sê-ri)
    if len(text_list) > 2 and text_list[2].isdigit() and text_list[2] in dict_num_to_char:
        text_list[2] = dict_num_to_char[text_list[2]]

    # 3. Kể từ ký tự thứ 4 trở đi PHẢI là số
    for i in range(3, len(text_list)):
        if text_list[i].isalpha() and text_list[i] in dict_char_to_num:
            text_list[i] = dict_char_to_num[text_list[i]]

    return "".join(text_list)


def is_valid_vn_plate(text):
    """
    Kiểm tra biển số có khớp chuẩn:
    - Bắt đầu: 1 số từ 1-9, theo sau là 1 số 0-9.
    - Ký tự 3: 1 chữ cái A-Z.
    - Đuôi: 4 hoặc 5 số.
    """
    pattern = r"^[1-9][0-9][A-Z][0-9]{4,5}$"
    return bool(re.match(pattern, text))


def run_ocr(ocr_reader, img_bgr):
    img_processed = preprocess_plate(img_bgr)
    read_text = ""
    
    res = ocr_reader.ocr(img_processed, cls=False)
    
    if res and res[0]:
        lines = sorted(res[0], key=lambda x: x[0][0][1])
        for line in lines:
            read_text += line[1][0].upper()

    clean_text = re.sub(r'[^A-Z0-9]', '', read_text)
    final_text = correct_plate_format(clean_text)
    
    return clean_text, final_text, img_processed


def main():
    model = YOLO(MODEL_PATH).to("cuda")

    ocr_reader = PaddleOCR(
        use_angle_cls=False,
        det=True, 
        lang='en',
        use_gpu=True,
        show_log=False
    )

    cap = cv2.VideoCapture(VIDEO_PATH)
    frame_count = 0

    plate_history   = {}   
    plate_confirmed = {}   
    plate_raw_cache = {}   
    active_tracks   = {}   
    spatial_memory  = {}   

    last_comparison_window = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1

        results = model.track(frame, persist=True, verbose=False, imgsz=640)
        current_detected_ids = set()

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                label  = model.names[cls_id]
                conf   = float(box.conf[0])

                if label != "license_plate" or conf <= CONF_THRESHOLD:
                    continue

                track_id = int(box.id[0]) if box.id is not None else -1
                if track_id == -1:
                    continue

                current_detected_ids.add(track_id)

                x1, y1, x2, y2 = map(int, box.xyxy[0])
                w, h = x2 - x1, y2 - y1
                if w <= 20 or h <= 10:
                    continue
                
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                # Kế thừa SPATIAL MEMORY
                if track_id not in plate_confirmed:
                    for old_id, (old_cx, old_cy, old_text, old_frame) in list(spatial_memory.items()):
                        if frame_count - old_frame < 150 and math.hypot(cx - old_cx, cy - old_cy) < 50:
                            plate_confirmed[track_id] = old_text
                            plate_raw_cache[track_id] = "INHERITED"
                            break

                active_tracks[track_id] = {'bbox': (x1, y1, x2, y2), 'missed_frames': 0}

                pad = 2
                x1_p = max(0, x1 - pad)
                y1_p = max(0, y1 - pad)
                x2_p = min(frame.shape[1], x2 + pad)
                y2_p = min(frame.shape[0], y2 + pad)

                img_before = frame[y1_p:y2_p, x1_p:x2_p].copy()
                
                ratio = w / h
                if ratio < 1.8:
                    dst_w, dst_h = 240, 180   
                else:
                    dst_w, dst_h = 480, 120   

                gray = cv2.cvtColor(img_before, cv2.COLOR_BGR2GRAY)
                blur = cv2.GaussianBlur(gray, (5, 5), 0)
                edged = cv2.Canny(blur, 50, 200)
                dilated = cv2.dilate(edged, np.ones((3, 3), np.uint8), iterations=1)
                contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

                rect_pts = None
                for c in contours:
                    perimeter = cv2.arcLength(c, True)
                    approx = cv2.approxPolyDP(c, 0.03 * perimeter, True)
                    if len(approx) == 4:
                        rect_pts = approx.reshape(4, 2)
                        break

                if rect_pts is not None:
                    ordered_pts = order_points(rect_pts)
                    dst_pts = np.array([[0, 0], [dst_w - 1, 0], [dst_w - 1, dst_h - 1], [0, dst_h - 1]], dtype="float32")
                    M = cv2.getPerspectiveTransform(ordered_pts, dst_pts)
                    img_plate_color = cv2.warpPerspective(img_before, M, (dst_w, dst_h))
                    status_text = f"Nan goc ({dst_w}x{dst_h})"
                else:
                    img_plate_color = cv2.resize(img_before, (dst_w, dst_h), interpolation=cv2.INTER_CUBIC)
                    status_text = f"Phong to ({dst_w}x{dst_h})"

                # --- OCR và LỌC FORMAT ---
                if track_id in plate_confirmed:
                    clean_text = plate_raw_cache.get(track_id, "")
                    final_text = plate_confirmed[track_id]
                    display_text = f"[OK] {final_text}"
                    img_processed = preprocess_plate(img_plate_color)
                    spatial_memory[track_id] = (cx, cy, final_text, frame_count)

                elif frame_count % OCR_INTERVAL == 0:
                    clean_text, final_text, img_processed = run_ocr(ocr_reader, img_plate_color)
                    plate_raw_cache[track_id] = clean_text

                    # BỘ LỌC FORMAT HOẠT ĐỘNG Ở ĐÂY
                    if is_valid_vn_plate(final_text):
                        if track_id not in plate_history:
                            plate_history[track_id] = []
                        plate_history[track_id].append(final_text)

                        counter = Counter(plate_history[track_id])
                        best, count = counter.most_common(1)[0]

                        if count >= VOTE_THRESHOLD:
                            plate_confirmed[track_id] = best
                            display_text = f"[OK] {best}"
                            spatial_memory[track_id] = (cx, cy, best, frame_count)
                        else:
                            display_text = f"[?] {best} ({count}/{VOTE_THRESHOLD})"
                    else:
                        # Bị loại do sai định dạng (thiếu số, thừa chữ, v.v...)
                        display_text = f"[SKIP] {final_text}" if final_text else "..."
                else:
                    clean_text = plate_raw_cache.get(track_id, "")
                    # Ưu tiên lấy lịch sử đúng format, nếu chưa có thì in tạm
                    final_text = (plate_history.get(track_id) or [plate_raw_cache.get(track_id, "...")])[-1]
                    display_text = final_text
                    img_processed = preprocess_plate(img_plate_color)

                # Vẽ Box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                if "[OK]" in display_text:
                    color = (0, 255, 0)
                elif "[SKIP]" in display_text:
                    color = (0, 0, 255) # Đỏ cảnh báo sai format
                else:
                    color = (0, 255, 255) # Vàng chờ confirm
                cv2.putText(frame, display_text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

                # Cửa sổ so sánh
                DISPLAY_W, DISPLAY_H = dst_w, dst_h
                img_before_resized = cv2.resize(img_before, (DISPLAY_W, DISPLAY_H))
                img_after_bgr = cv2.resize(img_processed, (DISPLAY_W, DISPLAY_H))

                cv2.putText(img_before_resized, "BEFORE", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                cv2.putText(img_after_bgr, status_text, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.putText(img_after_bgr, f"RAW : {clean_text}", (5, DISPLAY_H - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                cv2.putText(img_after_bgr, f"FIX : {display_text}", (5, DISPLAY_H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                last_comparison_window = np.vstack((img_before_resized, img_after_bgr))

        # Logic Bù Frame
        for tid in list(active_tracks.keys()):
            if tid not in current_detected_ids:
                active_tracks[tid]['missed_frames'] += 1
                if active_tracks[tid]['missed_frames'] > MAX_LOST_FRAMES:
                    del active_tracks[tid]
                else:
                    old_x1, old_y1, old_x2, old_y2 = active_tracks[tid]['bbox']
                    if tid in plate_confirmed:
                        display_text = f"[OK] {plate_confirmed[tid]}"
                        color = (0, 255, 0) 
                    else:
                        display_text = (plate_history.get(tid) or ["..."])[-1]
                        color = (0, 165, 255) 

                    cv2.rectangle(frame, (old_x1, old_y1), (old_x2, old_y2), color, 2)
                    cv2.putText(frame, display_text, (old_x1, old_y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        if last_comparison_window is not None:
            cv2.imshow("Before vs After Processing", last_comparison_window)
        cv2.imshow("Main Video", frame)

        key = cv2.waitKey(1)
        if key == 27:      
            break
        elif key == 32:    
            cv2.waitKey(0)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()