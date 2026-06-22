import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT_DIR = app_root()
DATA_DIR = ROOT_DIR / "data"
PORT = int(os.getenv("STUDENT_INFO_PORT", "8013"))
HOST = os.getenv("STUDENT_INFO_HOST", "127.0.0.1")

os.environ.setdefault("STUDENT_INFO_DATA_DIR", str(DATA_DIR))
os.environ.setdefault("STUDENT_DB_PATH", str(DATA_DIR / "students.db"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "exports").mkdir(parents=True, exist_ok=True)


def open_browser() -> None:
    time.sleep(1.2)
    webbrowser.open(f"http://127.0.0.1:{PORT}/")


def main() -> None:
    print("正在启动学生信息管理与汇总系统...")
    print(f"数据目录: {DATA_DIR}")
    print(f"访问地址: http://127.0.0.1:{PORT}/")
    threading.Thread(target=open_browser, daemon=True).start()

    import main as student_app

    uvicorn.run(student_app.app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
