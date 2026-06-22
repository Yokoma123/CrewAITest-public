import csv
import os
import tempfile

import import_service
import student_store


def write_csv(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_tests():
    temp_dir = tempfile.mkdtemp(prefix="student_import_test_")
    student_store.DB_PATH = os.path.join(temp_dir, "students.db")
    student_store.init_db()

    first_csv = os.path.join(temp_dir, "students.csv")
    write_csv(
        first_csv,
        ["学生姓名", "班级", "学号", "联系电话", "寝室位置", "寝室号", "导师姓名", "性别"],
        [
            {
                "学生姓名": "李四",
                "班级": "计科一班",
                "学号": "20240002",
                "联系电话": "13900000000",
                "寝室位置": "西区",
                "寝室号": "2-402",
                "导师姓名": "王老师",
                "性别": "女",
            }
        ],
    )
    result = import_service.import_students(first_csv, "基础表.csv")
    assert result["imported"] == 1
    assert result["new_students"] == 1
    student = student_store.list_students("李四")[0]
    assert student["student_id"] == "20240002"
    assert student["dorm_room"] == "2-402"

    partial_csv = os.path.join(temp_dir, "partial.csv")
    write_csv(
        partial_csv,
        ["姓名", "学号", "联系电话", "政治面貌", "是否签署三方", "毕业去向"],
        [
            {
                "姓名": "李四",
                "学号": "20240002",
                "联系电话": "",
                "政治面貌": "共青团员",
                "是否签署三方": "是",
                "毕业去向": "国企",
            }
        ],
    )
    result = import_service.import_students(partial_csv, "补充表.csv")
    updated = student_store.get_student(student["id"])
    assert result["updated"] == 1
    assert updated["phone"] == "13900000000"
    assert updated["political_status"] == "共青团员"
    assert updated["tripartite_status"] == "是"
    assert updated["destination_type"] == "国企"

    conflict_csv = os.path.join(temp_dir, "conflict.csv")
    write_csv(
        conflict_csv,
        ["姓名", "学号", "联系电话", "QQ号"],
        [{"姓名": "李四", "学号": "20240002", "联系电话": "15000000000", "QQ号": "123456"}],
    )
    result = import_service.import_students(conflict_csv, "冲突表.csv")
    assert result["conflicts"] == 2
    changes = student_store.list_import_changes(result["batch_id"])
    assert {change["field_key"] for change in changes} == {"phone", "extra_qq号"}
    assert student_store.get_student(student["id"])["phone"] == "13900000000"

    new_field_change = [change for change in changes if change["field_key"] == "extra_qq号"][0]
    student_store.apply_import_change(new_field_change["id"], "apply")
    assert student_store.get_dynamic_fields()[0]["field_key"] == "extra_qq号"
    assert student_store.get_student(student["id"])["extra_values"]["extra_qq号"] == "123456"

    party_csv = os.path.join(temp_dir, "party.csv")
    long_header = "党支部党员大会接收预备党员时间"
    write_csv(
        party_csv,
        ["姓名", "学号", long_header],
        [{"姓名": "李四", "学号": "20240002", long_header: "2026-06-22"}],
    )
    result = import_service.import_students(party_csv, "党员发展补充表.csv")
    changes = student_store.list_import_changes(result["batch_id"])
    party_change = [change for change in changes if change["field_label"] == long_header][0]
    student_store.apply_import_change(party_change["id"], "apply")
    dynamic_fields = {field["label"]: field["field_key"] for field in student_store.get_dynamic_fields()}
    assert long_header in dynamic_fields
    assert student_store.get_student(student["id"])["extra_values"][dynamic_fields[long_header]] == "2026-06-22"

    mismatch_csv = os.path.join(temp_dir, "mismatch.csv")
    write_csv(
        mismatch_csv,
        ["姓名", "学号", "导师姓名"],
        [{"姓名": "李四同名错误", "学号": "20240002", "导师姓名": "赵老师"}],
    )
    result = import_service.import_students(mismatch_csv, "同学号不同姓名.csv")
    assert result["conflicts"] == 1
    assert student_store.get_student(student["id"])["advisor_name"] == "王老师"

    try:
        import xlwt
    except ImportError:
        xlwt = None
    if xlwt:
        legacy_xls = os.path.join(temp_dir, "legacy.xls")
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet("学生")
        headers = ["姓名", "学号", "班级", "联系电话"]
        values = ["王五", "20240005", "计科二班", "13700000000"]
        for col, header in enumerate(headers):
            sheet.write(0, col, header)
        for col, value in enumerate(values):
            sheet.write(1, col, value)
        workbook.save(legacy_xls)
        result = import_service.import_students(legacy_xls, "老版表.xls")
        assert result["new_students"] == 1
        assert student_store.list_students("20240005")[0]["name"] == "王五"

    print("import_service tests passed")


if __name__ == "__main__":
    run_tests()
