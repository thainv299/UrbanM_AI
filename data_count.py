import os
from collections import defaultdict

def check_yolo_labels(label_dir):
    if not os.path.exists(label_dir):
        print(f"Thư mục không tồn tại: {label_dir}")
        return

    # Từ điển tên class theo đúng ID 
    class_map = {0: "Person", 1: "Bicycle", 2: "Car", 3: "Motorcycle", 4 :"Plate", 5: "Bus", 6: "Truck"}
    
    images_per_class = defaultdict(int) # Đếm số ảnh chứa class
    boxes_per_class = defaultdict(int)  # Đếm tổng số hộp (box) của class

    files = [f for f in os.listdir(label_dir) if f.endswith('.txt')]
    print(f"\n--- Đang quét {len(files)} file trong: {os.path.basename(os.path.dirname(label_dir))}/{os.path.basename(label_dir)} ---")

    for f in files:
        with open(os.path.join(label_dir, f), 'r') as file:
            lines = file.readlines()
            
        # Dùng set để biết class nào có mặt trong bức ảnh này (chống đếm trùng nếu 1 ảnh có 2 chiếc ô tô)
        classes_in_image = set()
        for line in lines:
            parts = line.split()
            if not parts: continue
            
            c_id = int(parts[0])
            classes_in_image.add(c_id)
            boxes_per_class[c_id] += 1
            
        for c_id in classes_in_image:
            images_per_class[c_id] += 1

    for c_id in sorted(images_per_class.keys()):
        name = class_map.get(c_id, f"ID {c_id} (Biển số/Khác)")
        print(f"-> {name}: Xuất hiện trong {images_per_class[c_id]} ảnh (Tổng: {boxes_per_class[c_id]} đối tượng)")

check_yolo_labels("Dataset/archive/labels/train")
check_yolo_labels("Dataset/archive/labels/val")