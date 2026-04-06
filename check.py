import cv2
import os
import tkinter as tk
from tkinter import filedialog, messagebox

class_names = {
    0: "Nguoi", 
    1: "Xe_dap", 
    2: "O_to", 
    3: "Xe_may", 
    4: "Bien_so",
    5: "Xe_bus",   
    6: "Xe_tai"    
}

colors = {
    0: (0, 255, 0),     # Nguoi: Xanh lá
    1: (255, 0, 0),     # Xe_dap: Xanh dương
    2: (255, 255, 0),   # O_to: Xanh lơ (Cyan)
    3: (0, 255, 255),   # Xe_may: Vàng
    4: (0, 0, 255),     # Bien_so: Đỏ
    5: (0, 165, 255),   # Xe_bus: Cam
    6: (255, 0, 255)    # Xe_tai: Tím (Magenta)
}

class LabelCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Kiểm tra nhãn YOLO")
        self.root.geometry("600x250")
        
        self.img_paths = []
        self.txt_path = None

        # Title
        tk.Label(root, text="Kiểm tra Auto-label (Ảnh & Txt)", font=("Arial", 14, "bold")).pack(pady=10)

        # Frame chứa input
        frame = tk.Frame(root)
        frame.pack(fill="x", padx=20, pady=10)

        # Trọng số cho các cột để giãn cho đẹp
        frame.columnconfigure(1, weight=1)

        # Chọn ảnh
        tk.Label(frame, text="Đường dẫn ảnh:", font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=5)
        self.lbl_img = tk.Label(frame, text="Chưa chọn ảnh", fg="gray", font=("Arial", 10), wraplength=350, justify="left")
        self.lbl_img.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        tk.Button(frame, text="Chọn Ảnh", command=self.select_images, width=12).grid(row=0, column=2, padx=5, pady=5)

        # Chọn txt
        tk.Label(frame, text="Đường dẫn txt:", font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=5)
        self.lbl_txt = tk.Label(frame, text="Chưa chọn txt (Chỉ dùng nếu 1 ảnh)", fg="gray", font=("Arial", 10), wraplength=350, justify="left")
        self.lbl_txt.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        tk.Button(frame, text="Chọn Txt", command=self.select_txt, width=12).grid(row=1, column=2, padx=5, pady=5)

        # Nút thực thi
        self.btn_check = tk.Button(root, text="Kiểm Tra Nhãn", command=self.check_label, 
                                   bg="#4CAF50", fg="black", font=("Arial", 12, "bold"), width=20, height=2)
        self.btn_check.pack(pady=10)

        # Hướng dẫn
        tk.Label(root, text="[Q]: Ảnh tiếp theo | [ESC]: Thoát", font=("Arial", 10, "italic"), fg="red").pack(pady=5)

    def select_images(self):
        filepaths = filedialog.askopenfilenames(
            title="Chọn hình ảnh",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp"), ("All files", "*.*")]
        )
        if filepaths:
            self.img_paths = list(filepaths)
            if len(self.img_paths) == 1:
                self.lbl_img.config(text=os.path.basename(self.img_paths[0]), fg="blue")
                
                # Cố đoán file txt nếu chỉ chọn 1 ảnh
                txt_guess = os.path.splitext(self.img_paths[0])[0] + ".txt"
                if "images" in txt_guess:
                    txt_guess_2 = txt_guess.replace("images", "labels", 1)
                    if os.path.exists(txt_guess_2):
                        txt_guess = txt_guess_2
                if os.path.exists(txt_guess):
                    self.txt_path = txt_guess
                    self.lbl_txt.config(text=os.path.basename(self.txt_path), fg="blue")
            else:
                self.lbl_img.config(text=f"Đã chọn {len(self.img_paths)} ảnh", fg="blue")
                self.lbl_txt.config(text="Auto-detect txt cho từng ảnh...", fg="gray")
                self.txt_path = None # Reset txt path vì sẽ dùng auto detect

    def select_txt(self):
        # Chỉ có tác dụng nếu chọn 1 ảnh và muốn chọn lại txt thủ công
        if len(self.img_paths) > 1:
            messagebox.showinfo("Thông báo", "Đang ở chế độ nhiều ảnh, phần mềm sẽ tự suy luận file txt tương ứng theo tên ảnh!")
            return
            
        filepath = filedialog.askopenfilename(
            title="Chọn file txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            self.txt_path = filepath
            self.lbl_txt.config(text=os.path.basename(filepath), fg="blue")

    def check_label(self):
        if not self.img_paths:
            messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 hình ảnh!")
            return

        for i, img_path in enumerate(self.img_paths):
            if not os.path.exists(img_path):
                print(f"Ảnh không tồn tại: {img_path}")
                continue
                
            # Suy luận file txt
            current_txt_path = self.txt_path if len(self.img_paths) == 1 and self.txt_path else None
            
            if not current_txt_path:
                txt_guess = os.path.splitext(img_path)[0] + ".txt"
                if "images" in txt_guess:
                    txt_guess_2 = txt_guess.replace("images", "labels", 1)
                    if os.path.exists(txt_guess_2):
                        txt_guess = txt_guess_2
                
                if os.path.exists(txt_guess):
                    current_txt_path = txt_guess

            if not current_txt_path or not os.path.exists(current_txt_path):
                print(f"Không tìm thấy file nhãn cho ảnh: {img_path}")
                # Optional: có thể vẽ text lên ảnh báo thiếu nhãn, nhưng mặc định nên bỏ qua
                img = cv2.imread(img_path)
                cv2.putText(img, "MISSING TXT FILE", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
            else:
                img = cv2.imread(img_path)
                if img is None: continue
                    
                h, w, _ = img.shape

                try:
                    with open(current_txt_path, "r") as f:
                        lines = f.readlines()

                    for line in lines:
                        data = line.strip().split()
                        if len(data) == 0: continue
                        
                        try:
                            class_id = int(data[0])
                            x_c, y_c, box_w, box_h = map(float, data[1:5])
                        except ValueError:
                            continue
                        
                        x1 = int((x_c - box_w / 2) * w)
                        y1 = int((y_c - box_h / 2) * h)
                        x2 = int((x_c + box_w / 2) * w)
                        y2 = int((y_c + box_h / 2) * h)
                        
                        color = colors.get(class_id, (128, 128, 128))
                        
                        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(img, class_names.get(class_id, f"ID_{class_id}"), (x1, y1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                except Exception as e:
                    print(f"Lỗi khi đọc file {current_txt_path}: {str(e)}")

            # Hiển thị ảnh
            window_title = f"Kiem tra Auto-label ({i+1}/{len(self.img_paths)})"
            cv2.imshow(window_title, img)
            
            # Đợi phím
            while True:
                key = cv2.waitKey(100) & 0xFF
                if key == 27: # ESC
                    cv2.destroyAllWindows()
                    return # Exit function completely
                elif key == ord('q') or key == ord('Q'):
                    cv2.destroyWindow(window_title)
                    break # Go to next image

                # Xử lý khi người dùng bấm nút X tắt cửa sổ
                try:
                    if cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) < 1:
                        cv2.destroyAllWindows()
                        return # Thoát hoàn toàn giống hệt ESC
                except cv2.error:
                    cv2.destroyAllWindows()
                    return
                    
        cv2.destroyAllWindows()
        messagebox.showinfo("Hoàn thành", "Đã duyệt qua toàn bộ hình ảnh đã chọn!")

if __name__ == "__main__":
    root = tk.Tk()
    app = LabelCheckerApp(root)
    root.mainloop()