import sqlite3

from werkzeug.security import generate_password_hash

from frontend.core.config import DATABASE_PATH


def connect() -> sqlite3.Connection:
    """Tạo kết nối mới tới CSDL SQLite"""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Khởi tạo cấu trúc bảng nếu chưa có"""
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS nguoi_dung (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ten_dang_nhap TEXT NOT NULL UNIQUE,
                ho_ten TEXT NOT NULL,
                mat_khau_hash TEXT NOT NULL,
                vai_tro TEXT NOT NULL DEFAULT 'operator',
                trang_thai_hoat_dong INTEGER NOT NULL DEFAULT 1,
                ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ngay_cap_nhat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS camera (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ten_camera TEXT NOT NULL UNIQUE,
                nguon_phat TEXT,
                mo_ta TEXT,
                toa_do_vung_chon TEXT,
                toa_do_cam_do TEXT,
                bat_phat_hien_un_tac INTEGER NOT NULL DEFAULT 1,
                bat_phat_hien_do_sai INTEGER NOT NULL DEFAULT 1,
                bat_phat_hien_bien_so INTEGER NOT NULL DEFAULT 1,
                trang_thai_hoat_dong INTEGER NOT NULL DEFAULT 1,
                ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ngay_cap_nhat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS thong_ke_giao_thong (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_camera INTEGER NOT NULL,
                so_luong_xe INTEGER NOT NULL DEFAULT 0,
                ngay_ghi_nhan TEXT NOT NULL,
                ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_camera) REFERENCES camera(id),
                UNIQUE(id_camera, ngay_ghi_nhan)
            );

            CREATE TABLE IF NOT EXISTS vi_pham_do_xe (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_camera INTEGER NOT NULL,
                bien_so TEXT,
                thoi_gian_vi_pham TEXT NOT NULL,
                thoi_gian_do_giay INTEGER NOT NULL DEFAULT 0,
                duong_dan_anh TEXT,
                da_giai_quyet INTEGER NOT NULL DEFAULT 0,
                ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_camera) REFERENCES camera(id)
            );

            CREATE TABLE IF NOT EXISTS nhat_ky_un_tac (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_camera INTEGER NOT NULL,
                muc_do_un_tac INTEGER NOT NULL DEFAULT 1,
                thoi_gian_bat_dau TEXT NOT NULL,
                thoi_gian_ket_thuc TEXT,
                thoi_gian_keo_dai_giay INTEGER DEFAULT 0,
                ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_camera) REFERENCES camera(id)
            );

            CREATE TABLE IF NOT EXISTS bien_so_phat_hien (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bien_so TEXT NOT NULL,
                ngay_phat_hien TEXT NOT NULL,
                so_lan_phat_hien INTEGER NOT NULL DEFAULT 1,
                do_chinh_xac_tb REAL DEFAULT 0.0,
                duong_dan_anh TEXT,
                ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ngay_cap_nhat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(bien_so, ngay_phat_hien)
            );

            CREATE TABLE IF NOT EXISTS lich_su_phuong_tien (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_camera INTEGER DEFAULT 0,
                bien_so_xe TEXT,
                loai_xe TEXT,
                thoi_gian_di_qua TEXT NOT NULL,
                ngay_tao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cau_hinh_he_thong (
                khoa TEXT PRIMARY KEY,
                gia_tri TEXT
            );
            """
        )

        camera_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(camera)").fetchall()
        }
        if "bat_phat_hien_bien_so" not in camera_columns:
            connection.execute(
                "ALTER TABLE camera ADD COLUMN bat_phat_hien_bien_so INTEGER NOT NULL DEFAULT 1"
            )

        # Cấu hình mặc định
        default_settings = {
            "confidence": "0.32",
            "frame_skip": "1",
            "iou_threshold": "0.45",
            "congestion_threshold": "70",
            "parking_violation_time": "30",
            "log_retention": "30_days",
            "evidence_format": "jpg"
        }
        for k, v in default_settings.items():
            connection.execute(
                "INSERT OR IGNORE INTO cau_hinh_he_thong (khoa, gia_tri) VALUES (?, ?)",
                (k, v)
            )

        connection.execute(
            """
            INSERT OR IGNORE INTO nguoi_dung (ten_dang_nhap, ho_ten, mat_khau_hash, vai_tro, trang_thai_hoat_dong)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "admin",
                "Quản trị hệ thống",
                generate_password_hash("Admin@123"),
                "admin",
                1,
            ),
        )
        connection.commit()


def get_total_vehicle_count() -> int:
    """Lấy tổng số xe đi qua"""
    with connect() as connection:
        row = connection.execute(
            "SELECT SUM(so_luong_xe) as total FROM thong_ke_giao_thong"
        ).fetchone()
    return int(row["total"]) if row["total"] else 0


def get_illegal_parking_violations() -> list:
    """Lấy danh sách xe đỗ sai (chưa giải quyết)"""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT pv.id, pv.id_camera as camera_id, pv.bien_so as license_plate, pv.thoi_gian_vi_pham as violation_time,
                   pv.thoi_gian_do_giay as duration_seconds, pv.duong_dan_anh as frame_path, pv.da_giai_quyet as is_resolved,
                   pv.ngay_tao as created_at, c.ten_camera as camera_name
            FROM vi_pham_do_xe pv
            LEFT JOIN camera c ON pv.id_camera = c.id
            ORDER BY pv.da_giai_quyet ASC, pv.thoi_gian_vi_pham DESC
            LIMIT 50
            """
        ).fetchall()
    return [dict(row) for row in rows]

def resolve_parking_violation(violation_id: int) -> bool:
    """Đánh dấu vi phạm đỗ xe đã được giải quyết"""
    with connect() as connection:
        cursor = connection.execute(
            "UPDATE vi_pham_do_xe SET da_giai_quyet = 1 WHERE id = ?",
            (violation_id,)
        )
        connection.commit()
        return cursor.rowcount > 0


def get_congestion_count() -> int:
    """Lấy số lần tắc nghẽn trong hôm nay"""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) as total FROM nhat_ky_un_tac
            WHERE DATE(thoi_gian_bat_dau) = ?
            """,
            (today,)
        ).fetchone()
    return row["total"] if row and row["total"] else 0

def get_congestion_history() -> list:
    """Lấy lịch sử ùn tắc"""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT n.id, n.id_camera as camera_id, n.muc_do_un_tac as congestion_level,
                   n.thoi_gian_bat_dau as start_time, n.thoi_gian_ket_thuc as end_time,
                   n.thoi_gian_keo_dai_giay as duration_seconds, c.ten_camera as camera_name
            FROM nhat_ky_un_tac n
            LEFT JOIN camera c ON n.id_camera = c.id
            ORDER BY n.thoi_gian_bat_dau DESC
            LIMIT 50
            """
        ).fetchall()
    return [dict(row) for row in rows]


def log_vehicle_count(camera_id: int, count: int, recorded_date: str = None) -> None:
    """Ghi lại số xe đi qua"""
    from datetime import datetime
    if recorded_date is None:
        recorded_date = datetime.now().strftime("%Y-%m-%d")
    
    with connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO thong_ke_giao_thong (id_camera, so_luong_xe, ngay_ghi_nhan)
            VALUES (?, ?, ?)
            """,
            (camera_id, count, recorded_date)
        )
        connection.commit()


def log_parking_violation(camera_id: int, license_plate: str = None, violation_time: str = None, duration: int = 0, frame_path: str = None) -> None:
    """Ghi lại vi phạm đỗ xe"""
    from datetime import datetime
    if violation_time is None:
        violation_time = datetime.now().isoformat()
    
    # Đảm bảo đường dẫn lưu vào DB là tương đối và đúng thư mục logs/violations/
    if frame_path and "runtime/violations/" in frame_path:
        frame_path = frame_path.replace("runtime/violations/", "logs/violations/")
    
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO vi_pham_do_xe (id_camera, bien_so, thoi_gian_vi_pham, thoi_gian_do_giay, duong_dan_anh)
            VALUES (?, ?, ?, ?, ?)
            """,
            (camera_id, license_plate, violation_time, duration, frame_path)
        )
        connection.commit()


def log_congestion(camera_id: int, level: int = 1, start_time: str = None) -> None:
    """Ghi lại sự kiện tắc nghẽn"""
    from datetime import datetime
    if start_time is None:
        start_time = datetime.now().isoformat()
    
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO nhat_ky_un_tac (id_camera, muc_do_un_tac, thoi_gian_bat_dau)
            VALUES (?, ?, ?)
            """,
            (camera_id, level, start_time)
        )
        connection.commit()


def log_passed_vehicle(camera_id: int, bien_so_xe: str, loai_xe: str, thoi_gian_di_qua: str = None) -> None:
    """Ghi lại lịch sử phương tiện đi qua"""
    from datetime import datetime
    if thoi_gian_di_qua is None:
        thoi_gian_di_qua = datetime.now().isoformat()
    
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO lich_su_phuong_tien (id_camera, bien_so_xe, loai_xe, thoi_gian_di_qua)
            VALUES (?, ?, ?, ?)
            """,
            (camera_id, bien_so_xe, loai_xe, thoi_gian_di_qua)
        )
        connection.commit()


def log_detected_license_plate(license_plate: str, detection_count: int = 1, avg_confidence: float = 0.0, image_paths: str = None) -> None:
    """Lưu biển số được phát hiện"""
    from datetime import datetime
    detected_date = datetime.now().strftime("%Y-%m-%d")
    
    # Đảm bảo đường dẫn lưu vào DB là tương đối và đúng thư mục logs/plates/
    if image_paths:
        image_paths = image_paths.replace("runtime/license_plates/", "logs/plates/")
    
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO bien_so_phat_hien (bien_so, ngay_phat_hien, so_lan_phat_hien, do_chinh_xac_tb, duong_dan_anh)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(bien_so, ngay_phat_hien) DO UPDATE SET
                so_lan_phat_hien = so_lan_phat_hien + ?,
                do_chinh_xac_tb = ?,
                duong_dan_anh = CASE 
                    WHEN duong_dan_anh IS NULL THEN ?
                    ELSE duong_dan_anh || ',' || ?
                END,
                ngay_cap_nhat = CURRENT_TIMESTAMP
            """,
            (license_plate, detected_date, detection_count, avg_confidence, image_paths, detection_count, avg_confidence, image_paths, image_paths)
        )
        connection.commit()


def get_detected_license_plates(limit: int = 100) -> list:
    """Lấy danh sách biển số được phát hiện"""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT bien_so as license_plate, ngay_phat_hien as detected_date, so_lan_phat_hien as detection_count, 
                   do_chinh_xac_tb as avg_confidence, duong_dan_anh as image_paths
            FROM bien_so_phat_hien
            ORDER BY ngay_cap_nhat DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_license_plate_by_date(detected_date: str) -> list:
    """Lấy biển số được phát hiện trong ngày cụ thể"""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT bien_so as license_plate, ngay_phat_hien as detected_date, so_lan_phat_hien as detection_count, 
                   do_chinh_xac_tb as avg_confidence, duong_dan_anh as image_paths
            FROM bien_so_phat_hien
            WHERE ngay_phat_hien = ?
            ORDER BY bien_so ASC
            """,
            (detected_date,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_dashboard_stats_data() -> dict:
    """Lấy tất cả dữ liệu thống kê cho dashboard"""
    return {
        "total_vehicles": get_total_vehicle_count(),
        "illegal_parking_violations": get_illegal_parking_violations(),
        "congestion_count": get_congestion_count(),
    }


def get_system_settings() -> dict:
    """Lấy tất cả cấu hình hệ thống"""
    with connect() as connection:
        rows = connection.execute("SELECT khoa, gia_tri FROM cau_hinh_he_thong").fetchall()
        # Chuyển đổi sang dict với kiểu dữ liệu phù hợp
        raw = {row["khoa"]: row["gia_tri"] for row in rows}
        
        # Parse giá trị số
        processed = {}
        for k, v in raw.items():
            if k in ["confidence", "iou_threshold"]:
                processed[k] = float(v)
            elif k in ["frame_skip", "congestion_threshold", "parking_violation_time"]:
                processed[k] = int(v)
            else:
                processed[k] = v
        return processed

def update_system_settings(settings: dict) -> None:
    """Cập nhật các cấu hình hệ thống"""
    with connect() as connection:
        for k, v in settings.items():
            connection.execute(
                "UPDATE cau_hinh_he_thong SET gia_tri = ? WHERE khoa = ?",
                (str(v), k)
            )
        connection.commit()


def global_search(query: str) -> dict:
    """Tìm kiếm camera và biển số xe"""
    results = {
        "cameras": [],
        "plates": []
    }
    if not query:
        return results
        
    q = f"%{query}%"
    with connect() as connection:
        # 1. Tìm camera
        cam_rows = connection.execute(
            "SELECT id, ten_camera, mo_ta, trang_thai_hoat_dong FROM camera WHERE ten_camera LIKE ? OR mo_ta LIKE ? LIMIT 5",
            (q, q)
        ).fetchall()
        results["cameras"] = [dict(row) for row in cam_rows]
        
        # 2. Tìm biển số
        plate_rows = connection.execute(
            """
            SELECT bien_so as license_plate, ngay_phat_hien as detected_date, duong_dan_anh as image_paths 
            FROM bien_so_phat_hien 
            WHERE bien_so LIKE ? 
            ORDER BY ngay_cap_nhat DESC LIMIT 5
            """,
            (q,)
        ).fetchall()
        results["plates"] = [dict(row) for row in plate_rows]
        
    return results


def fix_image_paths() -> int:
    """Cập nhật đường dẫn ảnh cũ và chuẩn hóa dấu gạch chéo"""
    import os
    count = 0
    with connect() as connection:
        # 1. Chuẩn hóa dấu gạch ngược \ thành gạch xuôi /
        connection.execute("UPDATE vi_pham_do_xe SET duong_dan_anh = REPLACE(duong_dan_anh, '\\', '/')")
        connection.execute("UPDATE bien_so_phat_hien SET duong_dan_anh = REPLACE(duong_dan_anh, '\\', '/')")
        
        # 2. Đổi runtime thành logs nếu còn sót
        connection.execute("UPDATE vi_pham_do_xe SET duong_dan_anh = REPLACE(duong_dan_anh, 'runtime/violations/', 'logs/violations/')")
        connection.execute("UPDATE bien_so_phat_hien SET duong_dan_anh = REPLACE(duong_dan_anh, 'runtime/license_plates/', 'logs/plates/')")
        
        # 3. Xử lý trường hợp vi phạm chỉ lưu thư mục (ID_xxx/)
        # Chúng ta cần tìm file ảnh thực sự bên trong
        rows = connection.execute("SELECT id, duong_dan_anh FROM vi_pham_do_xe WHERE duong_dan_anh LIKE '%/'").fetchall()
        for row in rows:
            vid, path = row["id"], row["duong_dan_anh"]
            if not path: continue
            
            full_path = os.path.join(os.getcwd(), path.replace('/', os.sep))
            if os.path.isdir(full_path):
                # Tìm file .jpg bên trong (ưu tiên combined_alert.jpg)
                found_img = None
                for root, dirs, files in os.walk(full_path):
                    for f in files:
                        if f.endswith('.jpg'):
                            found_img = os.path.join(root, f).replace(os.getcwd(), '').replace(os.sep, '/').lstrip('/')
                            if 'combined_alert' in f:
                                break
                    if found_img: break
                
                if found_img:
                    connection.execute("UPDATE vi_pham_do_xe SET duong_dan_anh = ? WHERE id = ?", (found_img, vid))
                    count += 1
        
        connection.commit()
    return count
