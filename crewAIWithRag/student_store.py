import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("STUDENT_INFO_DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.getenv("STUDENT_DB_PATH", os.path.join(DATA_DIR, "students.db"))


STUDENT_FIELDS = [
    "name",
    "class_name",
    "student_id",
    "phone",
    "dorm_location",
    "dorm_room",
    "advisor_name",
    "gender",
    "political_status",
    "tripartite_status",
    "destination_type",
    "employer_name",
    "job_title",
    "job_city",
    "is_further_study",
    "destination_note",
]


FIELD_LABELS = {
    "name": "姓名",
    "class_name": "班级",
    "student_id": "学号",
    "phone": "联系电话",
    "dorm_location": "寝室位置",
    "dorm_room": "寝室号",
    "advisor_name": "导师姓名",
    "gender": "性别",
    "political_status": "政治面貌",
    "tripartite_status": "是否签署三方",
    "destination_type": "去向类型",
    "employer_name": "单位名称",
    "job_title": "岗位",
    "job_city": "城市",
    "is_further_study": "是否升学",
    "destination_note": "去向备注",
}


SELECT_OPTIONS = {
    "gender": ["未知", "男", "女"],
    "political_status": ["未知", "中共党员", "中共预备党员", "共青团员", "群众", "民主党派", "其他"],
    "tripartite_status": ["未知", "是", "否", "不涉及"],
    "is_further_study": ["未知", "是", "否"],
    "destination_type": ["未知", "国企", "私企", "事业单位", "公务员", "升学", "科研院所", "高校", "参军", "自主创业", "自由职业", "待就业", "其他"],
}


VALUE_NORMALIZERS = {
    "gender": {
        "男": "男",
        "女": "女",
        "ХЎ": "男",
        "Фа": "女",
        "male": "男",
        "female": "女",
        "m": "男",
        "f": "女",
    }
}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def normalize_field_value(field: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    mapped = VALUE_NORMALIZERS.get(field, {}).get(text)
    return mapped if mapped is not None else text


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                class_name TEXT DEFAULT '',
                student_id TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                dorm_location TEXT DEFAULT '',
                dorm_room TEXT DEFAULT '',
                advisor_name TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        for field in STUDENT_FIELDS:
            if field not in ("name", "class_name", "student_id", "phone", "dorm_location", "dorm_room", "advisor_name"):
                ensure_column(conn, "students", field, "TEXT DEFAULT ''")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rewards_punishments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                record_type TEXT NOT NULL CHECK(record_type IN ('奖励', '惩罚')),
                title TEXT NOT NULL,
                record_date TEXT NOT NULL,
                description TEXT DEFAULT '',
                source TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                activity_date TEXT NOT NULL,
                task_name TEXT NOT NULL,
                task_quantity REAL DEFAULT 1,
                duration_hours REAL DEFAULT 1,
                score REAL DEFAULT 0,
                score_rule TEXT DEFAULT '任务量 * 时长',
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dynamic_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_key TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                field_type TEXT NOT NULL DEFAULT 'text',
                options_json TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS student_extra_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                value TEXT DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE(student_id, field_key),
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS import_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                imported_count INTEGER DEFAULT 0,
                updated_count INTEGER DEFAULT 0,
                conflict_count INTEGER DEFAULT 0,
                new_student_count INTEGER DEFAULT 0,
                skipped_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS import_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                student_pk INTEGER,
                student_number TEXT DEFAULT '',
                student_name TEXT DEFAULT '',
                field_key TEXT NOT NULL,
                field_label TEXT NOT NULL,
                old_value TEXT DEFAULT '',
                new_value TEXT DEFAULT '',
                change_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY(batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_students_name ON students(name)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_sid_unique ON students(student_id) WHERE student_id <> ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_student ON rewards_punishments(student_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_student ON daily_activities(student_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_import_changes_batch ON import_changes(batch_id)")
        for bad_value, fixed_value in {"ХЎ": "男", "Фа": "女"}.items():
            conn.execute("UPDATE students SET gender = ? WHERE gender = ?", (fixed_value, bad_value))


def get_dynamic_fields() -> List[Dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM dynamic_fields ORDER BY id").fetchall()
    result = []
    for row in rows:
        item = row_to_dict(row)
        item["options"] = json.loads(item.get("options_json") or "[]")
        result.append(item)
    return result


def upsert_dynamic_field(field_key: str, label: str, field_type: str = "text", options: Optional[List[str]] = None) -> Dict[str, Any]:
    init_db()
    stamp = now_text()
    options_json = json.dumps(options or [], ensure_ascii=False)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO dynamic_fields(field_key, label, field_type, options_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(field_key) DO UPDATE SET
                label = excluded.label,
                field_type = excluded.field_type,
                options_json = excluded.options_json
            """,
            (field_key, label, field_type, options_json, stamp),
        )
    return {"field_key": field_key, "label": label, "field_type": field_type, "options": options or []}


def upsert_dynamic_field_with_conn(conn: sqlite3.Connection, field_key: str, label: str, field_type: str = "text", options: Optional[List[str]] = None) -> None:
    options_json = json.dumps(options or [], ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO dynamic_fields(field_key, label, field_type, options_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(field_key) DO UPDATE SET
            label = excluded.label,
            field_type = excluded.field_type,
            options_json = excluded.options_json
        """,
        (field_key, label, field_type, options_json, now_text()),
    )


def set_extra_value(student_pk: int, field_key: str, value: str) -> None:
    init_db()
    stamp = now_text()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO student_extra_values(student_id, field_key, value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(student_id, field_key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (student_pk, field_key, value, stamp),
        )


def get_extra_values(student_pk: int) -> Dict[str, str]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT field_key, value FROM student_extra_values WHERE student_id = ?",
            (student_pk,),
        ).fetchall()
    return {row["field_key"]: row["value"] for row in rows}


def list_students(query: str = "", filters: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    init_db()
    filters = filters or {}
    params: List[Any] = []
    clauses = []
    if query:
        like = f"%{query}%"
        clauses.append(
            """
            (name LIKE ? OR class_name LIKE ? OR student_id LIKE ?
             OR phone LIKE ? OR dorm_location LIKE ? OR dorm_room LIKE ?
             OR advisor_name LIKE ? OR gender LIKE ? OR political_status LIKE ?
             OR tripartite_status LIKE ? OR destination_type LIKE ? OR employer_name LIKE ?)
            """
        )
        params.extend([like] * 12)

    for field in ["class_name", "advisor_name", "dorm_location", "gender", "political_status", "tripartite_status", "destination_type"]:
        value = (filters.get(field) or "").strip()
        if value:
            clauses.append(f"{field} = ?")
            params.append(value)

    if filters.get("missing_phone") == "true":
        clauses.append("phone = ''")
    if filters.get("has_records") == "true":
        clauses.append("id IN (SELECT DISTINCT student_id FROM rewards_punishments)")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM students {where} ORDER BY class_name, name, id DESC",
            params,
        ).fetchall()
        students = [row_to_dict(row) for row in rows]
        ids = [student["id"] for student in students]
        if not ids:
            return students
        placeholders = ", ".join(["?"] * len(ids))
        record_rows = conn.execute(
            f"SELECT student_id, COUNT(*) AS count FROM rewards_punishments WHERE student_id IN ({placeholders}) GROUP BY student_id",
            ids,
        ).fetchall()
        activity_rows = conn.execute(
            f"""
            SELECT student_id, COUNT(*) AS count, COALESCE(SUM(score), 0) AS score
            FROM daily_activities
            WHERE student_id IN ({placeholders})
            GROUP BY student_id
            """,
            ids,
        ).fetchall()
        extra_rows = conn.execute(
            f"SELECT student_id, field_key, value FROM student_extra_values WHERE student_id IN ({placeholders})",
            ids,
        ).fetchall()

    record_counts = {row["student_id"]: row["count"] for row in record_rows}
    activity_counts = {row["student_id"]: row["count"] for row in activity_rows}
    activity_scores = {row["student_id"]: round(float(row["score"] or 0), 2) for row in activity_rows}
    extras: Dict[int, Dict[str, str]] = {}
    for row in extra_rows:
        extras.setdefault(row["student_id"], {})[row["field_key"]] = row["value"]

    for student in students:
        student["records"] = []
        student["record_count"] = record_counts.get(student["id"], 0)
        student["activities"] = []
        student["activity_count"] = activity_counts.get(student["id"], 0)
        student["activity_score"] = activity_scores.get(student["id"], 0)
        student["extra_values"] = extras.get(student["id"], {})
    return students


def batch_search_students(terms: List[str]) -> Dict[str, Any]:
    init_db()
    cleaned_terms: List[str] = []
    seen_terms = set()
    for term in terms:
        value = str(term or "").strip()
        if value and value not in seen_terms:
            cleaned_terms.append(value)
            seen_terms.add(value)

    results: List[Dict[str, Any]] = []
    missing: List[str] = []
    seen_student_ids = set()

    with get_connection() as conn:
        for term in cleaned_terms:
            exact_rows = conn.execute(
                """
                SELECT * FROM students
                WHERE student_id = ? OR name = ? OR phone = ?
                ORDER BY
                    CASE
                        WHEN student_id = ? THEN 0
                        WHEN name = ? THEN 1
                        WHEN phone = ? THEN 2
                        ELSE 3
                    END,
                    class_name,
                    name,
                    id DESC
                """,
                (term, term, term, term, term, term),
            ).fetchall()

            exact_ids = [row["id"] for row in exact_rows]
            if exact_ids:
                enriched = {student["id"]: student for student in list_students(term)}
                matches = [enriched.get(student_id) for student_id in exact_ids if enriched.get(student_id)]
            else:
                matches = []
            if not matches:
                matches = list_students(term)

            if not matches:
                missing.append(term)
                continue

            for student in matches:
                student["matched_term"] = term
                if student["id"] not in seen_student_ids:
                    results.append(student)
                    seen_student_ids.add(student["id"])

    return {"terms": cleaned_terms, "students": results, "missing": missing}


def get_student(student_pk: int) -> Optional[Dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM students WHERE id = ?", (student_pk,)).fetchone()
    if not row:
        return None
    student = row_to_dict(row)
    student["records"] = list_records(student_pk)
    student["activities"] = list_activities(student_pk)
    student["activity_score"] = get_activity_score(student_pk)
    student["extra_values"] = get_extra_values(student_pk)
    return student


def find_student_id_by_number(student_number: str) -> Optional[int]:
    init_db()
    value = str(student_number or "").strip()
    if not value:
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM students WHERE student_id = ? ORDER BY id DESC LIMIT 1",
            (value,),
        ).fetchone()
    return int(row["id"]) if row else None


def save_student(data: Dict[str, Any], student_pk: Optional[int] = None) -> Dict[str, Any]:
    init_db()
    existing = get_student(student_pk) if student_pk else None
    values = {}
    for field in STUDENT_FIELDS:
        default_value = existing.get(field, "") if existing else ""
        values[field] = normalize_field_value(field, data.get(field, default_value))
    if not values["name"]:
        raise ValueError("学生姓名不能为空")

    duplicate_id = find_student_id_by_number(values["student_id"])
    if values["student_id"] and duplicate_id and duplicate_id != student_pk:
        raise ValueError("学号已存在，不能保存为重复学号")

    stamp = now_text()
    with get_connection() as conn:
        if student_pk:
            assignments = ", ".join(f"{field} = ?" for field in STUDENT_FIELDS)
            conn.execute(
                f"UPDATE students SET {assignments}, updated_at = ? WHERE id = ?",
                [values[field] for field in STUDENT_FIELDS] + [stamp, student_pk],
            )
            target_id = student_pk
        else:
            columns = ", ".join(STUDENT_FIELDS + ["created_at", "updated_at"])
            placeholders = ", ".join(["?"] * (len(STUDENT_FIELDS) + 2))
            cursor = conn.execute(
                f"INSERT INTO students ({columns}) VALUES ({placeholders})",
                [values[field] for field in STUDENT_FIELDS] + [stamp, stamp],
            )
            target_id = int(cursor.lastrowid)

    extra_values = data.get("extra_values") or {}
    for key, value in extra_values.items():
        set_extra_value(target_id, key, str(value or "").strip())

    student = get_student(target_id)
    if not student:
        raise ValueError("保存学生信息失败")
    return student


def delete_student(student_pk: int) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM students WHERE id = ?", (student_pk,))


def batch_delete_students(student_ids: List[int]) -> int:
    init_db()
    ids = [int(item) for item in student_ids if str(item).strip()]
    if not ids:
        return 0
    placeholders = ", ".join(["?"] * len(ids))
    with get_connection() as conn:
        cursor = conn.execute(f"DELETE FROM students WHERE id IN ({placeholders})", ids)
        return int(cursor.rowcount)


def reset_all() -> None:
    init_db()
    with get_connection() as conn:
        for table in [
            "import_changes",
            "import_batches",
            "student_extra_values",
            "dynamic_fields",
            "daily_activities",
            "rewards_punishments",
            "students",
        ]:
            conn.execute(f"DELETE FROM {table}")


def list_records(student_pk: int) -> List[Dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM rewards_punishments
            WHERE student_id = ?
            ORDER BY record_date DESC, id DESC
            """,
            (student_pk,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def add_record(student_pk: int, data: Dict[str, Any]) -> Dict[str, Any]:
    init_db()
    if not get_student(student_pk):
        raise ValueError("学生不存在")
    record_type = str(data.get("record_type", "") or "").strip()
    title = str(data.get("title", "") or "").strip()
    record_date = str(data.get("record_date", "") or "").strip()
    description = str(data.get("description", "") or "").strip()
    source = str(data.get("source", "") or "").strip()
    if record_type not in ("奖励", "惩罚"):
        raise ValueError("奖惩类型必须是 奖励 或 惩罚")
    if not title:
        raise ValueError("奖惩标题不能为空")
    if not record_date:
        raise ValueError("奖惩日期不能为空")
    stamp = now_text()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO rewards_punishments (
                student_id, record_type, title, record_date,
                description, source, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (student_pk, record_type, title, record_date, description, source, stamp, stamp),
        )
        row = conn.execute(
            "SELECT * FROM rewards_punishments WHERE id = ?",
            (int(cursor.lastrowid),),
        ).fetchone()
    return row_to_dict(row)


def delete_record(record_pk: int) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM rewards_punishments WHERE id = ?", (record_pk,))


def list_activities(student_pk: int) -> List[Dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM daily_activities
            WHERE student_id = ?
            ORDER BY activity_date DESC, id DESC
            """,
            (student_pk,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_activity_score(student_pk: int) -> float:
    init_db()
    with get_connection() as conn:
        value = conn.execute(
            "SELECT COALESCE(SUM(score), 0) FROM daily_activities WHERE student_id = ?",
            (student_pk,),
        ).fetchone()[0]
    return round(float(value or 0), 2)


def add_activity(student_pk: int, data: Dict[str, Any]) -> Dict[str, Any]:
    init_db()
    if not get_student(student_pk):
        raise ValueError("学生不存在")
    activity_date = str(data.get("activity_date", "") or "").strip()
    task_name = str(data.get("task_name", "") or "").strip()
    task_quantity = float(data.get("task_quantity") or 0)
    duration_hours = float(data.get("duration_hours") or 0)
    score = float(data.get("score") or 0)
    score_rule = str(data.get("score_rule", "") or "任务量 * 时长").strip()
    note = str(data.get("note", "") or "").strip()
    if not activity_date:
        raise ValueError("活动时间不能为空")
    if not task_name:
        raise ValueError("任务名称不能为空")
    stamp = now_text()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO daily_activities (
                student_id, activity_date, task_name, task_quantity,
                duration_hours, score, score_rule, note, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (student_pk, activity_date, task_name, task_quantity, duration_hours, score, score_rule, note, stamp, stamp),
        )
        row = conn.execute(
            "SELECT * FROM daily_activities WHERE id = ?",
            (int(cursor.lastrowid),),
        ).fetchone()
    return row_to_dict(row)


def delete_activity(activity_pk: int) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM daily_activities WHERE id = ?", (activity_pk,))


def create_import_batch(filename: str) -> int:
    init_db()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO import_batches(filename, created_at) VALUES (?, ?)",
            (filename, now_text()),
        )
        return int(cursor.lastrowid)


def update_import_batch(batch_id: int, **counts: int) -> None:
    if not counts:
        return
    allowed = {"imported_count", "updated_count", "conflict_count", "new_student_count", "skipped_count"}
    pairs = [(key, value) for key, value in counts.items() if key in allowed]
    if not pairs:
        return
    with get_connection() as conn:
        conn.execute(
            f"UPDATE import_batches SET {', '.join(key + ' = ?' for key, _ in pairs)} WHERE id = ?",
            [value for _, value in pairs] + [batch_id],
        )


def add_import_change(
    batch_id: int,
    student_pk: Optional[int],
    student_number: str,
    student_name: str,
    field_key: str,
    field_label: str,
    old_value: str,
    new_value: str,
    change_type: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO import_changes (
                batch_id, student_pk, student_number, student_name,
                field_key, field_label, old_value, new_value, change_type, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                student_pk,
                student_number,
                student_name,
                field_key,
                field_label,
                old_value,
                new_value,
                change_type,
                now_text(),
            ),
        )


def list_import_changes(batch_id: int, status: str = "pending", limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM import_changes
            WHERE batch_id = ? AND status = ?
            ORDER BY id
            LIMIT ? OFFSET ?
            """,
            (batch_id, status, limit, offset),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def count_import_changes(batch_id: int, status: str = "pending") -> int:
    init_db()
    with get_connection() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM import_changes WHERE batch_id = ? AND status = ?",
                (batch_id, status),
            ).fetchone()[0]
        )


def list_import_change_ids(batch_id: int, status: str = "pending", limit: int = 100) -> List[int]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id FROM import_changes
            WHERE batch_id = ? AND status = ?
            ORDER BY id
            LIMIT ?
            """,
            (batch_id, status, limit),
        ).fetchall()
    return [int(row["id"]) for row in rows]


def list_import_batches(limit: int = 20) -> List[Dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM import_batches ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    result = [row_to_dict(row) for row in rows]
    for item in result:
        item["pending_count"] = count_import_changes(item["id"])
    return result


def apply_import_change(change_id: int, action: str, manual_value: Optional[str] = None) -> Dict[str, Any]:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM import_changes WHERE id = ?", (change_id,)).fetchone()
        if not row:
            raise ValueError("变更不存在")
        change = row_to_dict(row)
        if change["status"] != "pending":
            return change

        if action == "ignore":
            conn.execute("UPDATE import_changes SET status = 'ignored' WHERE id = ?", (change_id,))
            change["status"] = "ignored"
            return change

        value = manual_value if manual_value is not None else change["new_value"]
        value = normalize_field_value(change["field_key"], value)
        if change["change_type"] == "new_field":
            upsert_dynamic_field_with_conn(conn, change["field_key"], change["field_label"])
        if change["student_pk"]:
            if change["field_key"] in STUDENT_FIELDS:
                conn.execute(
                    f"UPDATE students SET {change['field_key']} = ?, updated_at = ? WHERE id = ?",
                    (value, now_text(), change["student_pk"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO student_extra_values(student_id, field_key, value, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(student_id, field_key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (change["student_pk"], change["field_key"], value, now_text()),
                )
        conn.execute("UPDATE import_changes SET status = 'applied' WHERE id = ?", (change_id,))
        change["status"] = "applied"
        return change


def get_stats() -> Dict[str, Any]:
    init_db()
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        missing_phone = conn.execute("SELECT COUNT(*) FROM students WHERE phone = ''").fetchone()[0]
        missing_dorm = conn.execute("SELECT COUNT(*) FROM students WHERE dorm_location = '' OR dorm_room = ''").fetchone()[0]
        missing_advisor = conn.execute("SELECT COUNT(*) FROM students WHERE advisor_name = ''").fetchone()[0]
        pending_changes = conn.execute("SELECT COUNT(*) FROM import_changes WHERE status = 'pending'").fetchone()[0]
        duplicate_names = conn.execute(
            "SELECT COUNT(*) FROM (SELECT name FROM students WHERE name <> '' GROUP BY name HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        reward_count = conn.execute("SELECT COUNT(*) FROM rewards_punishments WHERE record_type = '奖励'").fetchone()[0]
        punishment_count = conn.execute("SELECT COUNT(*) FROM rewards_punishments WHERE record_type = '惩罚'").fetchone()[0]
        activity_count = conn.execute("SELECT COUNT(*) FROM daily_activities").fetchone()[0]
        activity_score = conn.execute("SELECT COALESCE(SUM(score), 0) FROM daily_activities").fetchone()[0]

        def group(field: str, empty_label: str = "未填写") -> List[Dict[str, Any]]:
            rows = conn.execute(
                f"SELECT CASE WHEN {field} = '' THEN ? ELSE {field} END AS label, COUNT(*) AS count FROM students GROUP BY label ORDER BY count DESC, label",
                (empty_label,),
            ).fetchall()
            return [row_to_dict(row) for row in rows]

    return {
        "total": total,
        "missing_phone": missing_phone,
        "missing_dorm": missing_dorm,
        "missing_advisor": missing_advisor,
        "pending_changes": pending_changes,
        "duplicate_names": duplicate_names,
        "reward_count": reward_count,
        "punishment_count": punishment_count,
        "activity_count": activity_count,
        "activity_score": round(float(activity_score or 0), 2),
        "gender": group("gender", "未知/未填"),
        "class_name": group("class_name"),
        "advisor_name": group("advisor_name"),
        "dorm_location": group("dorm_location"),
        "political_status": group("political_status"),
        "tripartite_status": group("tripartite_status"),
        "destination_type": group("destination_type"),
    }


def batch_update_students(student_ids: List[int], updates: Dict[str, str]) -> int:
    init_db()
    safe_updates = {key: str(value or "").strip() for key, value in updates.items() if key in STUDENT_FIELDS and key != "student_id"}
    if not student_ids or not safe_updates:
        return 0
    assignments = ", ".join(f"{key} = ?" for key in safe_updates)
    placeholders = ", ".join(["?"] * len(student_ids))
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE students SET {assignments}, updated_at = ? WHERE id IN ({placeholders})",
            list(safe_updates.values()) + [now_text()] + student_ids,
        )
        return int(cursor.rowcount)
