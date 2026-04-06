import os
from ultralytics import YOLO
import cv2
DATASET_DIR = "Dataset/COCO_Balanced"
PLATE_MODEL_PATH = "models/plate_detect_model.pt"
PLATE_CLASS_ID = 4

model = YOLO(PLATE_MODEL_PATH)

for split in ["train", "val"]:
    img_dir = os.path.join(DATASET_DIR, "images", split)
    lbl_dir = os.path.join(DATASET_DIR, "labels", split)
    
    if not os.path.exists(img_dir): 
        continue
        
    images = [f for f in os.listdir(img_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
    print(f"\n--- Đang quét biển số tập {split.upper()} ({len(images)} ảnh) ---")
    
    for img_name in images:
        img_path = os.path.join(img_dir, img_name)
        lbl_path = os.path.join(lbl_dir, os.path.splitext(img_name)[0] + '.txt')
        
        # Bỏ qua nếu file rỗng (0 bytes)
        if os.path.getsize(img_path) == 0:
            print(f"Bỏ qua ảnh rỗng: {img_name}")
            continue
            
        # Bỏ qua nếu OpenCV không đọc được (file hỏng)
        img_test = cv2.imread(img_path)
        if img_test is None:
            print(f"Bỏ qua ảnh hỏng: {img_name}")
            continue
            
        # Chạy dự đoán bình thường với file ảnh chuẩn
        results = model.predict(source=img_path, conf=0.5, verbose=False)
        
        new_lines = []
        for box in results[0].boxes:
            x, y, w, h = box.xywhn[0].tolist()
            new_lines.append(f"{PLATE_CLASS_ID} {x:.6f} {y:.6f} {w:.6f} {h:.6f}\n")
        
        if new_lines:
            with open(lbl_path, 'a') as f:
                f.writelines(new_lines)

print("\nHoàn tất !")