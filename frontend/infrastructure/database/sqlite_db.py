import sqlite3

from werkzeug.security import generate_password_hash

from core.config import DATABASE_PATH


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
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'operator',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                stream_source TEXT,
                description TEXT,
                roi_points TEXT,
                no_parking_points TEXT,
                enable_congestion INTEGER NOT NULL DEFAULT 1,
                enable_illegal_parking INTEGER NOT NULL DEFAULT 1,
                enable_license_plate INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS traffic_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id INTEGER NOT NULL,
                vehicle_count INTEGER NOT NULL DEFAULT 0,
                recorded_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (camera_id) REFERENCES cameras(id),
                UNIQUE(camera_id, recorded_date)
            );

            CREATE TABLE IF NOT EXISTS parking_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id INTEGER NOT NULL,
                license_plate TEXT,
                violation_time TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL DEFAULT 0,
                frame_path TEXT,
                is_resolved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (camera_id) REFERENCES cameras(id)
            );

            CREATE TABLE IF NOT EXISTS congestion_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id INTEGER NOT NULL,
                congestion_level INTEGER NOT NULL DEFAULT 1,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (camera_id) REFERENCES cameras(id)
            );

            CREATE TABLE IF NOT EXISTS detected_license_plates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_plate TEXT NOT NULL,
                detected_date TEXT NOT NULL,
                detection_count INTEGER NOT NULL DEFAULT 1,
                avg_confidence REAL DEFAULT 0.0,
                image_paths TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(license_plate, detected_date)
            );
            """
        )

        camera_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(cameras)").fetchall()
        }
        if "enable_license_plate" not in camera_columns:
            connection.execute(
                "ALTER TABLE cameras ADD COLUMN enable_license_plate INTEGER NOT NULL DEFAULT 1"
            )

        connection.execute(
            """
            INSERT OR IGNORE INTO users (username, full_name, password_hash, role, is_active)
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
            "SELECT SUM(vehicle_count) as total FROM traffic_stats"
        ).fetchone()
    return int(row["total"]) if row["total"] else 0


def get_illegal_parking_violations() -> list:
    """Lấy danh sách xe đỗ sai (chưa giải quyết)"""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT pv.*, c.name as camera_name
            FROM parking_violations pv
            LEFT JOIN cameras c ON pv.camera_id = c.id
            WHERE pv.is_resolved = 0
            ORDER BY pv.violation_time DESC
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
            SELECT COUNT(*) as total FROM congestion_logs
            WHERE DATE(start_time) = ?
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
            INSERT OR REPLACE INTO traffic_stats (camera_id, vehicle_count, recorded_date)
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
            INSERT INTO parking_violations (camera_id, license_plate, violation_time, duration_seconds, frame_path)
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
            INSERT INTO congestion_logs (camera_id, congestion_level, start_time)
            VALUES (?, ?, ?)
            """,
            (camera_id, level, start_time)
        )
        connection.commit()


def log_detected_license_plate(license_plate: str, detection_count: int = 1, avg_confidence: float = 0.0, image_paths: str = None) -> None:
    """Lưu biển số được phát hiện"""
    from datetime import datetime
    detected_date = datetime.now().strftime("%Y-%m-%d")
    
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO detected_license_plates (license_plate, detected_date, detection_count, avg_confidence, image_paths)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(license_plate, detected_date) DO UPDATE SET
                detection_count = detection_count + ?,
                avg_confidence = ?,
                image_paths = CASE 
                    WHEN image_paths IS NULL THEN ?
                    ELSE image_paths || ',' || ?
                END,
                updated_at = CURRENT_TIMESTAMP
            """,
            (license_plate, detected_date, detection_count, avg_confidence, image_paths, detection_count, avg_confidence, image_paths, image_paths)
        )
        connection.commit()


def get_detected_license_plates(limit: int = 100) -> list:
    """Lấy danh sách biển số được phát hiện"""
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT license_plate, detected_date, detection_count, avg_confidence, image_paths
            FROM detected_license_plates
            ORDER BY updated_at DESC
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
            SELECT license_plate, detected_date, detection_count, avg_confidence, image_paths
            FROM detected_license_plates
            WHERE detected_date = ?
            ORDER BY license_plate ASC
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
