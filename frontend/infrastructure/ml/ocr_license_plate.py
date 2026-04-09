"""
Module xử lý OCR biển số xe trong real-time phân tích video
"""
import os
import re
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from paddleocr import PaddleOCR


# Cache OCR reader để tránh khởi tạo lại nhiều lần
_ocr_reader = None


def get_ocr_reader():
    """Lấy hoặc khởi tạo PaddleOCR reader (singleton)"""
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = PaddleOCR(
            use_angle_cls=False,
            det=True,
            lang='en',
            show_log=False
        )
    return _ocr_reader


def preprocess_plate_image(img_bgr):
    """Tiền xử lý ảnh biển số trước OCR"""
    if img_bgr is None or img_bgr.size == 0:
        return img_bgr
    
    h, w = img_bgr.shape[:2]
    # Scale up nếu ảnh quá nhỏ
    if w < 100 or h < 30:
        scale = max(1, 100 // w, 30 // h)
        img_bgr = cv2.resize(img_bgr, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    
    # Enhance contrast
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    img_enhanced = clahe.apply(img_gray)
    
    # Chuyển về BGR
    img_enhanced_bgr = cv2.cvtColor(img_enhanced, cv2.COLOR_GRAY2BGR)
    return img_enhanced_bgr


def correct_vietnam_plate_format(text: str) -> str:
    """
    Sửa lỗi OCR cho format biển số Việt Nam:
    Format: XX[A-Z]XXXXX (2 số + 1 chữ + 4-5 số)
    """
    if not text or len(text) < 6:
        return text.upper()
    
    text = text.upper().replace(" ", "").replace("-", "")
    
    # Mapping lỗi OCR phổ biến
    char_to_num = {
        'O': '0', 'Q': '0', 'Z': '2', 'S': '5', 'G': '6', 'B': '8', 'I': '1', 'L': '1'
    }
    num_to_char = {
        '0': 'O', '8': 'B', '4': 'A', '5': 'S', '2': 'Z', '1': 'I'
    }
    
    text_list = list(text)
    
    # Hai ký tự đầu: số
    for i in range(min(2, len(text_list))):
        if text_list[i].isalpha() and text_list[i] in char_to_num:
            text_list[i] = char_to_num[text_list[i]]
    
    # Ký tự thứ 3: chữ
    if len(text_list) > 2:
        if text_list[2].isdigit() and text_list[2] in num_to_char:
            text_list[2] = num_to_char[text_list[2]]
    
    # Phần còn lại: số
    for i in range(3, len(text_list)):
        if text_list[i].isalpha() and text_list[i] in char_to_num:
            text_list[i] = char_to_num[text_list[i]]
    
    return "".join(text_list)


def is_valid_plate(text: str) -> bool:
    """Kiểm tra biển số có hợp lệ Việt Nam không"""
    # Format: XX[A-Z]XXXX (7-8 ký tự)
    pattern = r"^[0-9]{2}[A-Z][0-9]{4,5}$"
    return bool(re.match(pattern, text.upper()))


def ocr_read_license_plate(img_bgr) -> Tuple[Optional[str], float]:
    """
    Đọc biển số từ ảnh crop biển số
    Returns: (license_plate_text, confidence)
    """
    if img_bgr is None or img_bgr.size == 0:
        return None, 0.0
    
    try:
        # Tiền xử lý
        img_processed = preprocess_plate_image(img_bgr)
        
        # Chạy OCR
        reader = get_ocr_reader()
        results = reader.ocr(img_processed, cls=False)
        
        if not results or not results[0]:
            return None, 0.0
        
        # Ghép text từ các boxes OCR
        texts = []
        confidences = []
        
        for line in results:
            for word_info in line:
                text = word_info[1]
                conf = float(word_info[2])
                texts.append(text)
                confidences.append(conf)
        
        if not texts:
            return None, 0.0
        
        # Ghép và sửa format
        raw_text = "".join(texts).strip()
        corrected_text = correct_vietnam_plate_format(raw_text)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Chỉ trả về nếu hợp lệ
        if is_valid_plate(corrected_text) and avg_confidence > 0.4:
            return corrected_text.upper(), avg_confidence
        
        return None, avg_confidence
        
    except Exception as e:
        print(f"[OCR] Lỗi đọc biển số: {e}")
        return None, 0.0


def save_plate_image(
    img_bgr,
    license_plate: str,
    output_dir: Optional[Path] = None
) -> Optional[Path]:
    """
    Lưu ảnh biển số vào folder: output_dir/plate_YYYY-MM-DD/
    Tên file: {LICENSE_PLATE}_{timestamp}.jpg
    """
    if img_bgr is None or not license_plate:
        return None
    
    if output_dir is None:
        output_dir = Path.cwd() / "runtime" / "license_plates"
    
    # Tạo thư mục theo ngày
    today = datetime.now().strftime("%Y-%m-%d")
    date_dir = output_dir / f"plate_{today}"
    date_dir.mkdir(parents=True, exist_ok=True)
    
    # Tên file: BIỂN_SỐ_TIMESTAMP.jpg
    timestamp = datetime.now().strftime("%H%M%S_%f")[:12]  # HH:MM:SS_microseconds
    filename = f"{license_plate}_{timestamp}.jpg"
    filepath = date_dir / filename
    
    try:
        cv2.imwrite(str(filepath), img_bgr)
        return filepath
    except Exception as e:
        print(f"[OCR] Lỗi lưu ảnh biển số: {e}")
        return None
