# Web Portal riêng cho CrowDetection

Thư mục `web_portal/` là một lớp web mới hoàn toàn, không sửa các file hiện có của project.

## Chức năng
- Đăng nhập và đăng xuất bằng session Flask.
- Quản lý tài khoản người dùng với SQLite.
- Quản lý camera: lưu nguồn camera, mô tả, ROI, vùng cấm đỗ, bật hoặc tắt phát hiện tắc nghẽn và đỗ xe sai quy định.
- Hiển thị preview camera bằng snapshot.
- Test chức năng bằng video: upload file hoặc nhập đường dẫn local, backend xử lý và trả về video kết quả.

## Cấu trúc
- `web_portal/app.py`: backend Flask và route giao diện/API.
- `web_portal/database.py`: lớp SQLite cho user và camera.
- `web_portal/services/detection_bridge.py`: adapter riêng gọi YOLO + logic detect từ project hiện tại.
- `web_portal/templates/`: giao diện HTML.
- `web_portal/static/`: CSS và JavaScript frontend.

## Chạy thử
```bash
python web_portal/app.py
```

Mặc định mở ở:
```text
http://127.0.0.1:5000
```

## Tài khoản mặc định
- Username: `admin`
- Password: `Admin@123`

Nên đổi mật khẩu ngay sau khi đăng nhập lần đầu.

## Ghi chú
- Model mặc định đang trỏ tới `models/best.pt` của project.
- Nếu môi trường có GPU và muốn ép model dùng thiết bị cụ thể, có thể đặt biến môi trường `WEB_DETECT_DEVICE`, ví dụ `cuda`.
- Kết quả video test sẽ được lưu ở `web_portal/runtime/outputs/`.
- Dữ liệu tài khoản và camera được lưu ở `web_portal/runtime/portal.db`.
