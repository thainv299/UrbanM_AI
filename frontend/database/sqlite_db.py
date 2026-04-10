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
            WHERE pv.da_giai_quyet = 0
            ORDER BY pv.thoi_gian_vi_pham DESC
            LIMIT 10
            """
        ).fetchall()
    return [dict(row) for row in rows]


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
    return int(row["total"]) if row["total"] else 0


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
