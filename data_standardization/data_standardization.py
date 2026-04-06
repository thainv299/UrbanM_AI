import os
import glob

LABEL_DIR = "Dataset/archive/labels/val"
OUTPUT_DIR = "Dataset/archive/labels/val_hbb_cleaned"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Lấy tất cả file txt
txt_paths = glob.glob(os.path.join(LABEL_DIR, "*.txt"))

print(f"Bắt đầu chuyển đổi {len(txt_paths)} file nhãn sang chuẩn HBB (4 tọa độ)...")

for txt_path in txt_paths:
    base_name = os.path.basename(txt_path)
    out_path = os.path.join(OUTPUT_DIR, base_name)
    
    new_lines = []
    
    with open(txt_path, "r") as f:
        lines = f.readlines()
        
    for line in lines:
        data = line.strip().split()
        if len(data) == 0: continue
        
        # Nếu dòng có 9 phần tử (1 class_id + 8 tọa độ của OBB/Polygon)
        if len(data) == 9:
            class_id = int(data[0])
            coords = list(map(float, data[1:]))
            
            # Tách X và Y
            x_coords = coords[0::2] # Lấy các phần tử ở vị trí chẵn: x1, x2, x3, x4
            y_coords = coords[1::2] # Lấy các phần tử ở vị trí lẻ: y1, y2, y3, y4
            
            # Tìm tọa độ bao ngoài cùng (Bounding Box thẳng)
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # Tính toán x_center, y_center, width, height
            w = max_x - min_x
            h = max_y - min_y
            x_center = min_x + w / 2
            y_center = min_y + h / 2
            
            # Đổi Class ID: Nếu đang là 1 (biển số trong dataset cũ), đổi thành 4
            if class_id == 1:
                final_class_id = 4
            else:
                final_class_id = 4 # Giữ nguyên nếu có class khác
                
            # Lưu lại theo chuẩn YOLO
            new_lines.append(f"{final_class_id} {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}")
            
        # Nếu dòng vô tình đã ở chuẩn YOLO 4 tọa độ (len == 5)
        elif len(data) == 5:
            class_id = int(data[0])
            if class_id == 1:
                class_id = 4
            new_lines.append(f"{class_id} " + " ".join(data[1:]))

    # Ghi ra file mới
    with open(out_path, "w") as f:
        for line in new_lines:
            f.write(line + "\n")

print("Hoàn tất!")