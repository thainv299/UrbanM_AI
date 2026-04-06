import os
import glob
from ultralytics import YOLO

model = YOLO("models/yolo26l.engine", task="detect") 

IMAGE_DIR = "Dataset/archive/images/train" 
LABEL_DIR = "Dataset/archive/labels/train"

TARGET_CLASSES = [0, 1, 2, 3, 5, 7] # person, bicycle, car, motorcycle, bus, truck

image_paths = []
for ext in ('*.jpg', '*.png', '*.jpeg'):
    image_paths.extend(glob.glob(os.path.join(IMAGE_DIR, ext)))

print(f"Bắt đầu ép xung auto-label cho {len(image_paths)} ảnh bằng TensorRT...")

for img_path in image_paths:
    results = model(img_path, device='0', imgsz=640, half=True, conf=0.4, verbose=False)
    
    base_name = os.path.splitext(os.path.basename(img_path))[0]
    label_path = os.path.join(LABEL_DIR, f"{base_name}.txt")
    
    new_labels_to_append = []
    
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
            
        for box in boxes:
            class_id = int(box.cls[0].item())
            
            if class_id in TARGET_CLASSES:
                x_c, y_c, w, h = box.xywhn[0].tolist()
                label_line = f"{class_id} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}"
                new_labels_to_append.append(label_line)
                
    if new_labels_to_append:
        with open(label_path, 'a') as f:
            if os.path.exists(label_path) and os.path.getsize(label_path) > 0:
                with open(label_path, 'r') as check_f:
                    if not check_f.read().endswith('\n'):
                        f.write('\n')
                        
            for label in new_labels_to_append:
                f.write(label + "\n")

print("Hoàn tất gán nhãn")