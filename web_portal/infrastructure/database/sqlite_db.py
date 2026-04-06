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
