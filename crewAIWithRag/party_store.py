import json
import os
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from import_service import read_rows


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("STUDENT_INFO_DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.getenv("PARTY_INFO_DB_PATH", os.path.join(DATA_DIR, "party_info.db"))

IDENTITY_TYPES = {
    "activist": "积极分子",
    "probationary": "预备党员",
    "member": "党员",
}

COMMON_FIELDS = ["name", "class_name", "student_id", "gender", "phone", "branch_name", "note"]

CATEGORY_FIELDS = {
    "activist": ["applicant_date", "activist_date", "training_status", "recommender"],
    "probationary": ["activist_date", "pre_member_date", "probation_start_date", "probation_end_date", "introducer"],
    "member": ["member_date", "regularization_date", "party_position", "dues_status"],
}

ALL_FIELDS = [
    "identity_type",
    "name",
    "class_name",
    "student_id",
    "gender",
    "phone",
    "branch_name",
    "applicant_date",
    "activist_date",
    "training_status",
    "recommender",
    "pre_member_date",
    "probation_start_date",
    "probation_end_date",
    "introducer",
    "member_date",
    "regularization_date",
    "party_position",
    "dues_status",
    "note",
]

FIELD_LABELS = {
    "name": "姓名",
    "class_name": "班级",
    "student_id": "学号",
    "gender": "性别",
    "phone": "联系电话",
    "branch_name": "党支部",
    "applicant_date": "递交入党申请书时间",
    "activist_date": "确定积极分子时间",
    "training_status": "培养考察情况",
    "recommender": "培养联系人",
    "pre_member_date": "接收预备党员时间",
    "probation_start_date": "预备期开始时间",
    "probation_end_date": "预备期结束时间",
    "introducer": "入党介绍人",
    "member_date": "成为党员时间",
    "regularization_date": "转正时间",
    "party_position": "党内职务",
    "dues_status": "党费缴纳情况",
    "note": "备注",
}

FIELD_ALIASES = {
    "name": ["姓名", "学生姓名", "名字", "name"],
    "class_name": ["班级", "所在班级", "行政班", "class_name"],
    "student_id": ["学号", "学生学号", "student_id", "id"],
    "gender": ["性别", "gender"],
    "phone": ["联系电话", "电话", "手机号", "联系方式", "phone"],
    "branch_name": ["党支部", "所在党支部", "支部", "党组织", "branch_name"],
    "applicant_date": ["递交入党申请书时间", "申请入党时间", "入党申请时间", "申请书时间"],
    "activist_date": ["确定积极分子时间", "积极分子时间", "列为积极分子时间"],
    "training_status": ["培养考察情况", "培养情况", "考察情况", "培训情况"],
    "recommender": ["培养联系人", "联系人", "推荐人"],
    "pre_member_date": ["接收预备党员时间", "党支部党员大会接收预备党员时间", "成为预备党员时间"],
    "probation_start_date": ["预备期开始时间", "预备期起始时间"],
    "probation_end_date": ["预备期结束时间", "预备期截止时间"],
    "introducer": ["入党介绍人", "介绍人"],
    "member_date": ["成为党员时间", "入党时间", "党员时间"],
    "regularization_date": ["转正时间", "按期转正时间"],
    "party_position": ["党内职务", "职务"],
    "dues_status": ["党费缴纳情况", "党费情况"],
    "note": ["备注", "说明", "note"],
}


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    item = dict(row)
    item["extra_values"] = json.loads(item.get("extra_values_json") or "{}")
    item.pop("extra_values_json", None)
    item["identity_label"] = IDENTITY_TYPES.get(item.get("identity_type"), item.get("identity_type", ""))
    return item


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS party_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                class_name TEXT DEFAULT '',
                student_id TEXT DEFAULT '',
                gender TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                branch_name TEXT DEFAULT '',
                applicant_date TEXT DEFAULT '',
                activist_date TEXT DEFAULT '',
                training_status TEXT DEFAULT '',
                recommender TEXT DEFAULT '',
                pre_member_date TEXT DEFAULT '',
                probation_start_date TEXT DEFAULT '',
                probation_end_date TEXT DEFAULT '',
                introducer TEXT DEFAULT '',
                member_date TEXT DEFAULT '',
                regularization_date TEXT DEFAULT '',
                party_position TEXT DEFAULT '',
                dues_status TEXT DEFAULT '',
                note TEXT DEFAULT '',
                extra_values_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS party_dynamic_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identity_type TEXT NOT NULL,
                field_key TEXT NOT NULL,
                label TEXT NOT NULL,
                field_type TEXT DEFAULT 'text',
                options_json TEXT DEFAULT '[]',
                created_at TEXT NOT NULL,
                UNIQUE(identity_type, field_key)
            )
            """
        )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_party_student_unique ON party_records(student_id) WHERE student_id <> ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_party_identity ON party_records(identity_type)")


def normalize_header(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "").replace("_", "")


def make_dynamic_key(label: str) -> str:
    cleaned = re.sub(r"\W+", "_", label.strip().lower(), flags=re.UNICODE).strip("_")
    return f"extra_{cleaned or 'field'}"


def get_fields(identity_type: str) -> List[Dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM party_dynamic_fields WHERE identity_type = ? ORDER BY id",
            (identity_type,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["options"] = json.loads(item.get("options_json") or "[]")
        result.append(item)
    return result


def upsert_field(identity_type: str, label: str, field_type: str = "text", options: Optional[List[str]] = None) -> Dict[str, Any]:
    init_db()
    if identity_type not in IDENTITY_TYPES:
        raise ValueError("党团身份类型不正确")
    label = str(label or "").strip()
    if not label:
        raise ValueError("字段名不能为空")
    field_key = make_dynamic_key(label)
    options = options or []
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO party_dynamic_fields(identity_type, field_key, label, field_type, options_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(identity_type, field_key) DO UPDATE SET
                label = excluded.label,
                field_type = excluded.field_type,
                options_json = excluded.options_json
            """,
            (identity_type, field_key, label, field_type, json.dumps(options, ensure_ascii=False), now_text()),
        )
    return {"identity_type": identity_type, "field_key": field_key, "label": label, "field_type": field_type, "options": options}


def get_record(record_id: int) -> Optional[Dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM party_records WHERE id = ?", (record_id,)).fetchone()
    return row_to_dict(row) if row else None


def find_by_student_id(student_id: str) -> Optional[int]:
    init_db()
    if not student_id:
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM party_records WHERE student_id = ?", (student_id,)).fetchone()
    return int(row["id"]) if row else None


def list_records(identity_type: str = "", query: str = "") -> List[Dict[str, Any]]:
    init_db()
    clauses = []
    params: List[Any] = []
    if identity_type:
        clauses.append("identity_type = ?")
        params.append(identity_type)
    if query:
        like = f"%{query}%"
        clauses.append("(name LIKE ? OR student_id LIKE ? OR class_name LIKE ? OR branch_name LIKE ?)")
        params.extend([like] * 4)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(f"SELECT * FROM party_records {where} ORDER BY class_name, name, id DESC", params).fetchall()
    return [row_to_dict(row) for row in rows]


def relevant_fields(identity_type: str) -> List[str]:
    return COMMON_FIELDS + CATEGORY_FIELDS.get(identity_type, [])


def save_record(data: Dict[str, Any], record_id: Optional[int] = None) -> Dict[str, Any]:
    init_db()
    identity_type = data.get("identity_type") or "activist"
    if identity_type not in IDENTITY_TYPES:
        raise ValueError("党团身份类型不正确")
    existing = get_record(record_id) if record_id else None
    values: Dict[str, str] = {}
    for field in ALL_FIELDS:
        if field == "identity_type":
            values[field] = identity_type
        else:
            values[field] = str(data.get(field, existing.get(field, "") if existing else "") or "").strip()
    if not values["name"]:
        raise ValueError("姓名不能为空")
    duplicate_id = find_by_student_id(values["student_id"])
    if values["student_id"] and duplicate_id and duplicate_id != record_id:
        record_id = duplicate_id
        existing = get_record(record_id)
        for field in ALL_FIELDS:
            if field != "identity_type" and not values[field]:
                values[field] = str(existing.get(field, "") or "")

    extra_values = existing.get("extra_values", {}) if existing else {}
    extra_values.update({key: str(value or "").strip() for key, value in (data.get("extra_values") or {}).items()})
    stamp = now_text()
    columns = ALL_FIELDS + ["extra_values_json", "created_at", "updated_at"]
    with get_connection() as conn:
        if record_id:
            assignments = ", ".join(f"{field} = ?" for field in ALL_FIELDS + ["extra_values_json"])
            conn.execute(
                f"UPDATE party_records SET {assignments}, updated_at = ? WHERE id = ?",
                [values[field] for field in ALL_FIELDS] + [json.dumps(extra_values, ensure_ascii=False), stamp, record_id],
            )
            target_id = record_id
        else:
            placeholders = ", ".join(["?"] * len(columns))
            cursor = conn.execute(
                f"INSERT INTO party_records ({', '.join(columns)}) VALUES ({placeholders})",
                [values[field] for field in ALL_FIELDS] + [json.dumps(extra_values, ensure_ascii=False), stamp, stamp],
            )
            target_id = int(cursor.lastrowid)
    record = get_record(target_id)
    if not record:
        raise ValueError("保存党团信息失败")
    return record


def change_identity(record_id: int, target_identity: str) -> Dict[str, Any]:
    if target_identity not in IDENTITY_TYPES:
        raise ValueError("目标身份不正确")
    record = get_record(record_id)
    if not record:
        raise ValueError("党团记录不存在")
    keep = set(relevant_fields(target_identity) + ["identity_type"])
    data = {field: (record.get(field, "") if field in keep else "") for field in ALL_FIELDS}
    data["identity_type"] = target_identity
    data["extra_values"] = {}
    allowed_dynamic = {field["field_key"] for field in get_fields(target_identity)}
    for key, value in (record.get("extra_values") or {}).items():
        if key in allowed_dynamic:
            data["extra_values"][key] = value
    return save_record(data, record_id)


def delete_records(record_ids: List[int]) -> int:
    init_db()
    ids = [int(item) for item in record_ids if str(item).strip()]
    if not ids:
        return 0
    placeholders = ", ".join(["?"] * len(ids))
    with get_connection() as conn:
        cursor = conn.execute(f"DELETE FROM party_records WHERE id IN ({placeholders})", ids)
        return int(cursor.rowcount)


def build_header_map(headers: List[str], identity_type: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    normalized_headers = {normalize_header(header): header for header in headers if str(header or "").strip()}
    allowed_fields = set(relevant_fields(identity_type))
    header_map: Dict[str, str] = {}
    used = set()
    for field, aliases in FIELD_ALIASES.items():
        if field not in allowed_fields:
            continue
        for alias in aliases:
            original = normalized_headers.get(normalize_header(alias))
            if original is not None:
                header_map[field] = original
                used.add(original)
                break
    dynamic_headers = {}
    dynamic_fields = get_fields(identity_type)
    for field in dynamic_fields:
        for alias in [field["label"], field["field_key"]]:
            original = normalized_headers.get(normalize_header(alias))
            if original is not None:
                dynamic_headers[field["field_key"]] = original
                used.add(original)
                break
    return header_map, dynamic_headers


def import_records(identity_type: str, path: str) -> Dict[str, Any]:
    if identity_type not in IDENTITY_TYPES:
        raise ValueError("党团身份类型不正确")
    rows = read_rows(path)
    if not rows:
        return {"imported": 0, "updated": 0, "skipped": 0, "errors": []}
    header_map, dynamic_headers = build_header_map(list(rows[0].keys()), identity_type)
    if "name" not in header_map or "student_id" not in header_map:
        raise ValueError("党团信息导入文件必须包含姓名和学号列")
    imported = updated = skipped = 0
    errors: List[str] = []
    for index, row in enumerate(rows, start=2):
        data = {"identity_type": identity_type, "extra_values": {}}
        for field, header in header_map.items():
            value = str(row.get(header, "") or "").strip()
            if value:
                data[field] = value
        for field_key, header in dynamic_headers.items():
            value = str(row.get(header, "") or "").strip()
            if value:
                data["extra_values"][field_key] = value
        if not data.get("name") or not data.get("student_id"):
            skipped += 1
            errors.append(f"第 {index} 行缺少姓名或学号，已跳过")
            continue
        existed = find_by_student_id(data["student_id"])
        save_record(data, existed)
        imported += 1
        if existed:
            updated += 1
    return {"imported": imported, "updated": updated, "skipped": skipped, "errors": errors}


def get_stats() -> Dict[str, Any]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute("SELECT identity_type, COUNT(*) AS count FROM party_records GROUP BY identity_type").fetchall()
    counts = {key: 0 for key in IDENTITY_TYPES}
    for row in rows:
        counts[row["identity_type"]] = int(row["count"])
    return {
        "counts": counts,
        "rows": [{"label": IDENTITY_TYPES[key], "count": counts.get(key, 0)} for key in IDENTITY_TYPES],
        "total": sum(counts.values()),
    }


def reset_all() -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM party_records")
        conn.execute("DELETE FROM party_dynamic_fields")
