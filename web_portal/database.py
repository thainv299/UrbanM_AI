from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "runtime" / "portal.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _load_points(raw_value: Optional[str]) -> Optional[List[List[int]]]:
    if not raw_value:
        return None
    try:
        points = json.loads(raw_value)
    except json.JSONDecodeError:
        return None

    if not isinstance(points, list):
        return None

    normalized: List[List[int]] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue
        normalized.append([int(point[0]), int(point[1])])

    return normalized or None


def _dump_points(points: Optional[List[List[int]]]) -> Optional[str]:
    if not points:
        return None
    return json.dumps(points, ensure_ascii=False)


def _serialize_user(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "full_name": row["full_name"],
        "role": row["role"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_camera(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "stream_source": row["stream_source"] or "",
        "description": row["description"] or "",
        "roi_points": _load_points(row["roi_points"]),
        "no_parking_points": _load_points(row["no_parking_points"]),
        "enable_congestion": bool(row["enable_congestion"]),
        "enable_illegal_parking": bool(row["enable_illegal_parking"]),
        "enable_license_plate": bool(row["enable_license_plate"]),
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def init_db() -> None:
    with _connect() as connection:
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
                "Qu?n tr? h? th?ng",
                generate_password_hash("Admin@123"),
                "admin",
                1,
            ),
        )
        connection.commit()


def get_user_record_by_id(user_id: int) -> Optional[sqlite3.Row]:
    with _connect() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def get_user_record_by_username(username: str) -> Optional[sqlite3.Row]:
    with _connect() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    row = get_user_record_by_id(user_id)
    if row is None:
        return None
    return _serialize_user(row)


def list_users() -> List[Dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM users ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [_serialize_user(row) for row in rows]


def count_admin_users() -> int:
    with _connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS total FROM users WHERE role = 'admin'"
        ).fetchone()
    return int(row["total"])


def create_user(payload: Dict[str, Any]) -> Dict[str, Any]:
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (username, full_name, password_hash, role, is_active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload["username"],
                payload["full_name"],
                payload["password_hash"],
                payload["role"],
                int(payload["is_active"]),
            ),
        )
        connection.commit()
        user_id = int(cursor.lastrowid)
    created = get_user_by_id(user_id)
    if created is None:
        raise RuntimeError("Không thể tạo tài khoản người dùng.")
    return created


def update_user(user_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    assignments = []
    values: List[Any] = []

    if "username" in payload:
        assignments.append("username = ?")
        values.append(payload["username"])
    if "full_name" in payload:
        assignments.append("full_name = ?")
        values.append(payload["full_name"])
    if "password_hash" in payload:
        assignments.append("password_hash = ?")
        values.append(payload["password_hash"])
    if "role" in payload:
        assignments.append("role = ?")
        values.append(payload["role"])
    if "is_active" in payload:
        assignments.append("is_active = ?")
        values.append(int(payload["is_active"]))

    if not assignments:
        return get_user_by_id(user_id)

    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(user_id)

    with _connect() as connection:
        cursor = connection.execute(
            f"UPDATE users SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        connection.commit()
        if cursor.rowcount == 0:
            return None

    return get_user_by_id(user_id)


def delete_user(user_id: int) -> bool:
    with _connect() as connection:
        cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        connection.commit()
        return cursor.rowcount > 0


def get_camera(camera_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM cameras WHERE id = ?",
            (camera_id,),
        ).fetchone()
    if row is None:
        return None
    return _serialize_camera(row)


def list_cameras() -> List[Dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM cameras ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return [_serialize_camera(row) for row in rows]


def create_camera(payload: Dict[str, Any]) -> Dict[str, Any]:
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO cameras (
                name, stream_source, description, roi_points, no_parking_points,
                enable_congestion, enable_illegal_parking, enable_license_plate, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["name"],
                payload.get("stream_source", ""),
                payload.get("description", ""),
                _dump_points(payload.get("roi_points")),
                _dump_points(payload.get("no_parking_points")),
                int(payload.get("enable_congestion", True)),
                int(payload.get("enable_illegal_parking", True)),
                int(payload.get("enable_license_plate", True)),
                int(payload.get("is_active", True)),
            ),
        )
        connection.commit()
        camera_id = int(cursor.lastrowid)
    created = get_camera(camera_id)
    if created is None:
        raise RuntimeError("Không thể tạo camera mới.")
    return created


def update_camera(camera_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    assignments = []
    values: List[Any] = []

    if "name" in payload:
        assignments.append("name = ?")
        values.append(payload["name"])
    if "stream_source" in payload:
        assignments.append("stream_source = ?")
        values.append(payload.get("stream_source", ""))
    if "description" in payload:
        assignments.append("description = ?")
        values.append(payload.get("description", ""))
    if "roi_points" in payload:
        assignments.append("roi_points = ?")
        values.append(_dump_points(payload.get("roi_points")))
    if "no_parking_points" in payload:
        assignments.append("no_parking_points = ?")
        values.append(_dump_points(payload.get("no_parking_points")))
    if "enable_congestion" in payload:
        assignments.append("enable_congestion = ?")
        values.append(int(payload["enable_congestion"]))
    if "enable_illegal_parking" in payload:
        assignments.append("enable_illegal_parking = ?")
        values.append(int(payload["enable_illegal_parking"]))
    if "enable_license_plate" in payload:
        assignments.append("enable_license_plate = ?")
        values.append(int(payload["enable_license_plate"]))
    if "is_active" in payload:
        assignments.append("is_active = ?")
        values.append(int(payload["is_active"]))

    if not assignments:
        return get_camera(camera_id)

    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(camera_id)

    with _connect() as connection:
        cursor = connection.execute(
            f"UPDATE cameras SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
        connection.commit()
        if cursor.rowcount == 0:
            return None

    return get_camera(camera_id)


def delete_camera(camera_id: int) -> bool:
    with _connect() as connection:
        cursor = connection.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
        connection.commit()
        return cursor.rowcount > 0


def get_dashboard_stats() -> Dict[str, Any]:
    with _connect() as connection:
        user_count = int(
            connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        )
        camera_count = int(
            connection.execute("SELECT COUNT(*) AS total FROM cameras").fetchone()["total"]
        )
        active_cameras = int(
            connection.execute(
                "SELECT COUNT(*) AS total FROM cameras WHERE is_active = 1"
            ).fetchone()["total"]
        )
        congestion_enabled = int(
            connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM cameras
                WHERE is_active = 1 AND enable_congestion = 1
                """
            ).fetchone()["total"]
        )
        illegal_parking_enabled = int(
            connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM cameras
                WHERE is_active = 1 AND enable_illegal_parking = 1
                """
            ).fetchone()["total"]
        )
        license_plate_enabled = int(
            connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM cameras
                WHERE is_active = 1 AND enable_license_plate = 1
                """
            ).fetchone()["total"]
        )
        recent_camera_rows = connection.execute(
            "SELECT * FROM cameras ORDER BY updated_at DESC, id DESC LIMIT 6"
        ).fetchall()

    return {
        "user_count": user_count,
        "camera_count": camera_count,
        "active_cameras": active_cameras,
        "congestion_enabled": congestion_enabled,
        "illegal_parking_enabled": illegal_parking_enabled,
        "license_plate_enabled": license_plate_enabled,
        "recent_cameras": [_serialize_camera(row) for row in recent_camera_rows],
    }
