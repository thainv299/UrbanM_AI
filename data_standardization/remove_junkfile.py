import os
import cv2

DATASET_DIR = "Dataset/COCO_Balanced"

def clean_garbage_files(split):
    img_dir = os.path.join(DATASET_DIR, "images", split)
    lbl_dir = os.path.join(DATASET_DIR, "labels", split)
    
    if not os.path.exists(img_dir):
        return

    images = [f for f in os.listdir(img_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
    print(f"\n=== ĐANG DỌN RÁC TẬP {split.upper()} ===")
    
    deleted_count = 0
    for img_name in images:
        img_path = os.path.join(img_dir, img_name)
        lbl_path = os.path.join(lbl_dir, os.path.splitext(img_name)[0] + '.txt')
        
        is_corrupt = False
        
        if os.path.getsize(img_path) == 0:
            is_corrupt = True
        else:
            img_test = cv2.imread(img_path)
            if img_test is None:
                is_corrupt = True
                
        if is_corrupt:
            os.remove(img_path)
            if os.path.exists(lbl_path):
                os.remove(lbl_path)
            deleted_count += 1
            print(f"[-] Đã xóa file hỏng: {img_name}")
            
    print(f"-> Hoàn tất! Đã dọn sạch {deleted_count} file rác trong tập {split}.")

clean_garbage_files("train")
clean_garbage_files("val")