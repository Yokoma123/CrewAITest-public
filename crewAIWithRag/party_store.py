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

COMMON_FIELDS = [
    "sequence_number",
    "name",
    "student_id",
    "gender",
    "ethnicity",
    "education",
    "birth_date",
    "age",
    "work_study_unit",
    "id_number",
    "work_start_date",
    "position_title",
    "application_date",
    "branch_name",
    "note",
]

CATEGORY_FIELDS = {
    "activist": ["talk_date", "activist_confirm_date", "committee_record_date", "activist_training_date", "cultivator"],
    "probationary": [
        "activist_confirm_date",
        "activist_training_date",
        "development_target_date",
        "development_training_date",
        "pre_member_accept_date",
        "superior_talk_date",
        "superior_talker",
        "general_branch_review_date",
        "superior_party_approval_date",
        "volunteer_book_number",
    ],
    "member": [
        "personnel_category",
        "activist_confirm_date",
        "activist_training_date",
        "development_target_date",
        "development_training_date",
        "pre_member_accept_date",
        "superior_party_approval_date",
        "probation_discussion_date",
        "regularization_approval_date",
    ],
}

ALL_FIELDS = [
    "identity_type",
    "sequence_number",
    "name",
    "student_id",
    "gender",
    "ethnicity",
    "education",
    "birth_date",
    "age",
    "work_study_unit",
    "id_number",
    "work_start_date",
    "position_title",
    "application_date",
    "talk_date",
    "activist_confirm_date",
    "committee_record_date",
    "activist_training_date",
    "cultivator",
    "development_target_date",
    "development_training_date",
    "pre_member_accept_date",
    "superior_talk_date",
    "superior_talker",
    "general_branch_review_date",
    "superior_party_approval_date",
    "volunteer_book_number",
    "personnel_category",
    "probation_discussion_date",
    "regularization_approval_date",
    "branch_name",
    "note",
]

FIELD_LABELS = {
    "sequence_number": "序号",
    "name": "姓名",
    "student_id": "学号（职工号）",
    "gender": "性别",
    "ethnicity": "民族",
    "education": "文化程度",
    "birth_date": "出生日期",
    "age": "年龄",
    "work_study_unit": "工作或学习单位",
    "id_number": "身份证号",
    "work_start_date": "参加工作时间（入学时间）",
    "position_title": "职务职称",
    "application_date": "申请入党时间",
    "talk_date": "派入谈话时间",
    "activist_confirm_date": "党支部研究确定入党积极分子时间",
    "committee_record_date": "党委备案时间",
    "activist_training_date": "入党积极分子培训时间",
    "cultivator": "培养联系人",
    "development_target_date": "列为发展对象时间",
    "development_training_date": "发展对象培训时间",
    "pre_member_accept_date": "党支部党员大会接收预备党员时间",
    "superior_talk_date": "上级党组织谈话时间",
    "superior_talker": "上级党组织谈话人",
    "general_branch_review_date": "党总支审议时间",
    "superior_party_approval_date": "上级党委审批时间",
    "volunteer_book_number": "志愿书编号",
    "personnel_category": "人员类别",
    "probation_discussion_date": "预备期支部讨论时间",
    "regularization_approval_date": "转正上级党委审批时间",
    "branch_name": "所在党支部",
    "note": "备注",
}

FIELD_ALIASES = {
    "sequence_number": ["序号", "编号", "序"],
    "name": ["姓名", "学生姓名", "名字", "name"],
    "student_id": ["学号", "学号（职工号）", "学号(职工号)", "学生学号", "职工号", "student_id", "studentid"],
    "gender": ["性别", "gender"],
    "ethnicity": ["民族"],
    "education": ["文化程度", "文化程度（指已取得学历）", "文化程度(指已取得学历)", "学历"],
    "birth_date": ["出生日期", "出生时间"],
    "age": ["年龄"],
    "work_study_unit": ["工作或学习单位", "工作或学习单位名称", "单位", "所在单位"],
    "id_number": ["身份证号", "身份证号码", "身份号码", "身份证"],
    "work_start_date": ["参加工作时间（入学时间）", "参加工作时间(入学时间)", "参加工作或入学时间", "入学时间", "参加工作时间"],
    "position_title": ["职务职称", "职务", "职称"],
    "application_date": ["申请入党时间", "递交入党申请书时间", "入党申请时间", "申请书时间"],
    "talk_date": ["派入谈话时间", "派人谈话时间", "谈话时间"],
    "activist_confirm_date": ["党支部研究确定入党积极分子时间", "确定积极分子时间", "积极分子时间", "列为积极分子时间"],
    "committee_record_date": ["党委备案时间", "党组织备案时间"],
    "activist_training_date": ["入党积极分子培训时间", "参加积极分子培训时间", "积极分子培训时间"],
    "cultivator": ["培养联系人", "培养联系人姓名", "联系人"],
    "development_target_date": ["列为发展对象时间", "发展对象时间"],
    "development_training_date": ["发展对象培训时间", "发展对象培训"],
    "pre_member_accept_date": ["党支部党员大会接收预备党员时间", "接收预备党员时间", "成为预备党员时间"],
    "superior_talk_date": ["上级党组织谈话时间", "上级组织谈话时间"],
    "superior_talker": ["上级党组织谈话人", "上级组织谈话人", "谈话人"],
    "general_branch_review_date": ["党总支审议时间", "党总支审批时间"],
    "superior_party_approval_date": ["上级党委审批时间", "党委审批时间"],
    "volunteer_book_number": ["志愿书编号", "入党志愿书编号"],
    "personnel_category": ["人员类别", "人员类型"],
    "probation_discussion_date": ["预备期支部讨论时间", "支部讨论时间", "转正支部讨论时间"],
    "regularization_approval_date": ["转正上级党委审批时间", "上级党委转正审批时间", "转正审批时间"],
    "branch_name": ["所在党支部", "党支部", "支部", "党组织", "branch_name"],
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
                sequence_number TEXT DEFAULT '',
                name TEXT NOT NULL,
                student_id TEXT DEFAULT '',
                gender TEXT DEFAULT '',
                ethnicity TEXT DEFAULT '',
                education TEXT DEFAULT '',
                birth_date TEXT DEFAULT '',
                age TEXT DEFAULT '',
                work_study_unit TEXT DEFAULT '',
                id_number TEXT DEFAULT '',
                work_start_date TEXT DEFAULT '',
                position_title TEXT DEFAULT '',
                application_date TEXT DEFAULT '',
                talk_date TEXT DEFAULT '',
                activist_confirm_date TEXT DEFAULT '',
                committee_record_date TEXT DEFAULT '',
                activist_training_date TEXT DEFAULT '',
                cultivator TEXT DEFAULT '',
                development_target_date TEXT DEFAULT '',
                development_training_date TEXT DEFAULT '',
                pre_member_accept_date TEXT DEFAULT '',
                superior_talk_date TEXT DEFAULT '',
                superior_talker TEXT DEFAULT '',
                general_branch_review_date TEXT DEFAULT '',
                superior_party_approval_date TEXT DEFAULT '',
                volunteer_book_number TEXT DEFAULT '',
                personnel_category TEXT DEFAULT '',
                probation_discussion_date TEXT DEFAULT '',
                regularization_approval_date TEXT DEFAULT '',
                branch_name TEXT DEFAULT '',
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
        existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(party_records)").fetchall()}
        for field in ALL_FIELDS:
            if field != "identity_type" and field not in existing_columns:
                conn.execute(f"ALTER TABLE party_records ADD COLUMN {field} TEXT DEFAULT ''")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_party_student_unique ON party_records(student_id) WHERE student_id <> ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_party_identity ON party_records(identity_type)")


def normalize_header(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("（", "(").replace("）", ")")
    return re.sub(r"[\s_()（）【】\\[\\]{}<>《》:：,，、/\\\\\\-]+", "", text)


def header_matches(candidate: str, aliases: List[str]) -> bool:
    normalized_candidate = normalize_header(candidate)
    if not normalized_candidate:
        return False
    for alias in aliases:
        normalized_alias = normalize_header(alias)
        if not normalized_alias:
            continue
        if normalized_candidate == normalized_alias:
            return True
        if len(normalized_alias) >= 3 and normalized_alias in normalized_candidate:
            return True
        if len(normalized_candidate) >= 3 and normalized_candidate in normalized_alias:
            return True
    return False


def header_exact_matches(candidate: str, aliases: List[str]) -> bool:
    normalized_candidate = normalize_header(candidate)
    return any(normalized_candidate == normalize_header(alias) for alias in aliases if normalize_header(alias))


def find_matching_header(headers: List[str], aliases: List[str], used_headers: set, exact_only: bool = False) -> Optional[str]:
    for header in headers:
        if header in used_headers:
            continue
        if header_exact_matches(header, aliases) if exact_only else header_matches(header, aliases):
            return header
    return None


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
        clauses.append("(name LIKE ? OR student_id LIKE ? OR work_study_unit LIKE ? OR branch_name LIKE ?)")
        params.extend([like] * 4)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(f"SELECT * FROM party_records {where} ORDER BY work_study_unit, name, id DESC", params).fetchall()
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
    allowed_fields = set(relevant_fields(identity_type))
    header_map: Dict[str, str] = {}
    used = set()
    field_aliases = [
        (field, aliases + [FIELD_LABELS.get(field, field)])
        for field, aliases in FIELD_ALIASES.items()
        if field in allowed_fields
    ]
    for field, aliases in field_aliases:
        original = find_matching_header(headers, aliases, used, exact_only=True)
        if original is not None:
            header_map[field] = original
            used.add(original)
    for field, aliases in field_aliases:
        if field in header_map:
            continue
        original = find_matching_header(headers, aliases, used)
        if original is not None:
            header_map[field] = original
            used.add(original)
    dynamic_headers = {}
    dynamic_fields = get_fields(identity_type)
    for field in dynamic_fields:
        original = find_matching_header(headers, [field["label"], field["field_key"]], used)
        if original is not None:
            dynamic_headers[field["field_key"]] = original
            used.add(original)
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
