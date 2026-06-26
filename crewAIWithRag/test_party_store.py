import csv
import os
import tempfile

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
        ["姓名", "学号", "班级", "党支部", "确定积极分子时间", "团支部推优时间"],
        [{
            "姓名": "王五",
            "学号": "20240005",
            "班级": "计科二班",
            "党支部": "第一党支部",
            "确定积极分子时间": "2026-06-01",
            "团支部推优时间": "2026-05-20",
        }],
    )
    result = party_store.import_records("activist", activist_csv)
    assert result["imported"] == 1
    activists = party_store.list_records("activist")
    assert len(activists) == 1
    assert activists[0]["extra_values"]["extra_团支部推优时间"] == "2026-05-20"

    moved = party_store.change_identity(activists[0]["id"], "probationary")
    assert moved["identity_type"] == "probationary"
    assert not party_store.list_records("activist")
    assert party_store.list_records("probationary")[0]["name"] == "王五"

    stats = party_store.get_stats()
    assert stats["counts"]["probationary"] == 1
    assert stats["counts"]["activist"] == 0

    log_store.add_log("测试操作", "测试", "写入一条日志")
    assert log_store.list_logs()[0]["action"] == "测试操作"

    party_store.reset_all()
    assert party_store.get_stats()["total"] == 0
    print("party_store tests passed")


if __name__ == "__main__":
    run_tests()
