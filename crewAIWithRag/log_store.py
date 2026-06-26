import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("STUDENT_INFO_DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.getenv("STUDENT_LOG_DB_PATH", os.path.join(DATA_DIR, "operation_logs.db"))


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                target TEXT NOT NULL,
                detail TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_created_at ON operation_logs(created_at)")
    cleanup_old_logs()


def cleanup_old_logs(days: int = 7) -> None:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute("DELETE FROM operation_logs WHERE created_at < ?", (cutoff,))


def add_log(action: str, target: str, detail: str = "") -> Dict[str, Any]:
    init_db()
    stamp = now_text()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO operation_logs(action, target, detail, created_at) VALUES (?, ?, ?, ?)",
            (action, target, detail, stamp),
        )
        log_id = int(cursor.lastrowid)
    return {"id": log_id, "action": action, "target": target, "detail": detail, "created_at": stamp}


def list_logs(limit: int = 200) -> List[Dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM operation_logs ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit or 200), 500)),),
        ).fetchall()
    return [dict(row) for row in rows]
