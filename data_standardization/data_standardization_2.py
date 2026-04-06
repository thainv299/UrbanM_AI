import os
import glob

LABEL_DIR = "Dataset/archive/labels/train" 

txt_paths = glob.glob(os.path.join(LABEL_DIR, "*.txt"))
print(f"Bắt đầu sửa lỗi và lọc trùng lặp cho {len(txt_paths)} file nhãn...")

sua_loi_count = 0
xoa_trung_count = 0

for txt_path in txt_paths:
    with open(txt_path, "r") as f:
        lines = f.readlines()
        
    boxes = []
    
    # Sửa sai tên class
    for line in lines:
        data = line.strip().split()
        if not data: continue
        
        cls = int(data[0])
        x, y, w, h = map(float, data[1:5])
        
        # Đổi Người (0) nằm ngang thành Biển số (4)
        if cls == 0 and w > h:
            cls = 4
            sua_loi_count += 1
            
        boxes.append([cls, x, y, w, h])
        
    # Lọc trùng lặp (Loại bỏ các khung đè lên nhau)
    final_boxes = []
    for box in boxes:
        is_duplicate = False
        for f_box in final_boxes:
            # Nếu 2 khung có CÙNG CLASS (ví dụ đều là 4) 
            # VÀ tọa độ tâm (x, y) quá sát nhau (sai số < 0.02, tức là lệch chưa tới 2% bức ảnh)
            if box[0] == f_box[0] and abs(box[1] - f_box[1]) < 0.02 and abs(box[2] - f_box[2]) < 0.02:
                is_duplicate = True
                xoa_trung_count += 1
                break # Phát hiện trùng thì vứt box này đi
                
        if not is_duplicate:
            final_boxes.append(box)
            
    # Ghi lại file 
    with open(txt_path, "w") as f:
        for box in final_boxes:
            f.write(f"{box[0]} {box[1]:.6f} {box[2]:.6f} {box[3]:.6f} {box[4]:.6f}\n")

print("-" * 30)
print(f"Hoàn tất!")
print(f"- Đã thu hồi được {sua_loi_count} biển số từ lỗi nhận nhầm của AI.")
print(f"- Đã xóa {xoa_trung_count} khung bị đè lên nhau để tối ưu dataset.")