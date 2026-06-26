import csv
import os
import tempfile

import import_service
import log_store
import party_store
import student_store


def write_csv(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_tests():
    temp_dir = tempfile.mkdtemp(prefix="party_store_test_")
    party_store.DB_PATH = os.path.join(temp_dir, "party_info.db")
    student_store.DB_PATH = os.path.join(temp_dir, "students.db")
    log_store.DB_PATH = os.path.join(temp_dir, "operation_logs.db")
    party_store.init_db()
    student_store.init_db()
    log_store.init_db()

    student = student_store.save_student({"name": "李四", "student_id": "20240002", "class_name": "计科一班"})
    deleted = student_store.batch_delete_students([student["id"]])
    assert deleted == 1
    assert not student_store.list_students("20240002")

    party_store.upsert_field("activist", "团支部推优时间")
    activist_csv = os.path.join(temp_dir, "activist.csv")
    write_csv(
        activist_csv,
        ["序号", "学号（职工号）", "姓名", "性别", "民族", "文化程度", "工作或学习单位", "申请入党时间", "党支部研究确定入党积极分子时间", "参加积极分子培训时间", "所在党支部", "培养联系人", "团支部推优时间"],
        [{
            "序号": "1",
            "学号（职工号）": "20240005",
            "姓名": "王五",
            "性别": "男",
            "民族": "汉族",
            "文化程度": "本科",
            "工作或学习单位": "计科二班",
            "申请入党时间": "2026-03-01",
            "党支部研究确定入党积极分子时间": "2026-06-01",
            "参加积极分子培训时间": "2026-06-10",
            "所在党支部": "第一党支部",
            "培养联系人": "张老师",
            "团支部推优时间": "2026-05-20",
        }],
    )
    result = party_store.import_records("activist", activist_csv)
    assert result["imported"] == 1
    activists = party_store.list_records("activist")
    assert len(activists) == 1
    assert activists[0]["student_id"] == "20240005"
    assert activists[0]["work_study_unit"] == "计科二班"
    assert activists[0]["activist_confirm_date"] == "2026-06-01"
    assert activists[0]["extra_values"]["extra_团支部推优时间"] == "2026-05-20"

    moved = party_store.change_identity(activists[0]["id"], "probationary")
    assert moved["identity_type"] == "probationary"
    assert moved["student_id"] == "20240005"
    assert moved["application_date"] == "2026-03-01"
    assert moved["activist_confirm_date"] == "2026-06-01"
    assert moved["activist_training_date"] == "2026-06-10"
    assert moved["branch_name"] == "第一党支部"
    assert not party_store.list_records("activist")
    assert party_store.list_records("probationary")[0]["name"] == "王五"

    member_csv = os.path.join(temp_dir, "member.csv")
    write_csv(
        member_csv,
        ["姓名", "学号 (职工号)", "人员类别", "党支部党员大会接收预备党员时间", "预备期支部讨论时间", "转正上级党委审批时间", "所在党支部"],
        [{
            "姓名": "王五",
            "学号 (职工号)": "20240005",
            "人员类别": "正式党员",
            "党支部党员大会接收预备党员时间": "2027-01-01",
            "预备期支部讨论时间": "2028-01-02",
            "转正上级党委审批时间": "2028-01-10",
            "所在党支部": "第一党支部",
        }],
    )
    result = party_store.import_records("member", member_csv)
    assert result["updated"] == 1
    member = party_store.list_records("member")[0]
    assert member["identity_type"] == "member"
    assert member["personnel_category"] == "正式党员"
    assert member["regularization_approval_date"] == "2028-01-10"

    student_csv = os.path.join(temp_dir, "students.csv")
    write_csv(student_csv, ["姓名", "学号（职工号）", "性别"], [{"姓名": "赵六", "学号（职工号）": "20240006", "性别": "女"}])
    result = import_service.import_students(student_csv, "学生表.csv")
    assert result["imported"] == 1
    assert student_store.list_students("20240006")[0]["name"] == "赵六"

    stats = party_store.get_stats()
    assert stats["counts"]["member"] == 1
    assert stats["counts"]["activist"] == 0

    log_store.add_log("测试操作", "测试", "写入一条日志")
    assert log_store.list_logs()[0]["action"] == "测试操作"

    party_store.reset_all()
    assert party_store.get_stats()["total"] == 0
    print("party_store tests passed")


if __name__ == "__main__":
    run_tests()
