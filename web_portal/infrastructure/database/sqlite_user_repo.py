import sqlite3
from typing import List, Optional

from domain.entities.user import User
from domain.repositories.user_repository import UserRepository
from infrastructure.database.sqlite_db import connect


class SqliteUserRepository(UserRepository):

    def _row_to_user(self, row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            full_name=row["full_name"],
            password_hash=row["password_hash"],
            role=row["role"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_by_id(self, user_id: int) -> Optional[User]:
        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return self._row_to_user(row) if row else None

    def get_by_username(self, username: str) -> Optional[User]:
        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return self._row_to_user(row) if row else None

    def list_all(self) -> List[User]:
        with connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._row_to_user(row) for row in rows]

    def count_admin(self) -> int:
        with connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM users WHERE role = 'admin'"
            ).fetchone()
        return int(row["total"])

    def create(self, user: User) -> User:
        with connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (username, full_name, password_hash, role, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user.username,
                    user.full_name,
                    user.password_hash,
                    user.role,
                    int(user.is_active),
                ),
            )
            connection.commit()
            user_id = int(cursor.lastrowid)
        
        created = self.get_by_id(user_id)
        if not created:
            raise RuntimeError("Lỗi lưu DB khi tạo User")
        return created

    def update(self, user: User) -> Optional[User]:
        assignments = []
        values = []

        if user.username is not None:
            assignments.append("username = ?")
            values.append(user.username)
        if user.full_name is not None:
            assignments.append("full_name = ?")
            values.append(user.full_name)
        if user.password_hash is not None:
            assignments.append("password_hash = ?")
            values.append(user.password_hash)
        if user.role is not None:
            assignments.append("role = ?")
            values.append(user.role)
        if user.is_active is not None:
            assignments.append("is_active = ?")
            values.append(int(user.is_active))

        if not assignments:
            return self.get_by_id(user.id)

        assignments.append("updated_at = CURRENT_TIMESTAMP")
        values.append(user.id)

        with connect() as connection:
            cursor = connection.execute(
                f"UPDATE users SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            connection.commit()
            if cursor.rowcount == 0:
                return None

        return self.get_by_id(user.id)

    def delete(self, user_id: int) -> bool:
        with connect() as connection:
            cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            connection.commit()
            return cursor.rowcount > 0
