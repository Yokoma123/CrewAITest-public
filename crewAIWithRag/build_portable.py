import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SOURCE_DIR.parent
DIST_ROOT = PROJECT_ROOT / "dist"
PORTABLE_DIR = DIST_ROOT / "StudentInfoSystemPortable"
APP_DIR = PORTABLE_DIR / "app"
ZIP_PATH = DIST_ROOT / "StudentInfoSystemPortable.zip"
SOURCE_PORTABLE_DIR = DIST_ROOT / "StudentInfoSystemSourcePortable"
SOURCE_APP_DIR = SOURCE_PORTABLE_DIR / "app"
SOURCE_ZIP_PATH = DIST_ROOT / "StudentInfoSystemSourcePortable.zip"

APP_FILES = [
    "main.py",
    "student_store.py",
    "import_service.py",
    "export_service.py",
    "portable_launcher.py",
    "run_portable.bat",
    "run_portable.command",
    "requirements-app.txt",
    "README.md",
    "DEPLOY.md",
]

PYINSTALLER_HIDDEN_IMPORTS = [
    "main",
    "student_store",
    "import_service",
    "export_service",
    "xlrd",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
]

PYINSTALLER_EXCLUDES = [
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "matplotlib",
    "IPython",
    "pytest",
    "sphinx",
    "tkinter",
]


def copytree_clean(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def write_start_scripts(portable_dir: Path) -> None:
    script = portable_dir / "start_student_info_system.bat"
    script.write_text(
        '@echo off\n'
        'chcp 65001 >nul\n'
        'cd /d "%~dp0app"\n'
        'call run_portable.bat\n',
        encoding="utf-8",
    )
    mac_script = portable_dir / "start_student_info_system.command"
    mac_script.write_text(
        '#!/usr/bin/env bash\n'
        'set -euo pipefail\n'
        'cd "$(dirname "$0")/app"\n'
        'chmod +x run_portable.command 2>/dev/null || true\n'
        './run_portable.command\n',
        encoding="utf-8",
    )


def zip_portable(portable_dir: Path, zip_path: Path) -> Path:
    if zip_path.exists():
        try:
            zip_path.unlink()
        except PermissionError:
            zip_path = zip_path.with_name(f"{zip_path.stem}-latest{zip_path.suffix}")
            if zip_path.exists():
                zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in portable_dir.rglob("*"):
            arcname = path.relative_to(DIST_ROOT)
            info = zipfile.ZipInfo.from_file(path, arcname)
            if path.name.endswith(".command"):
                info.external_attr = 0o755 << 16
            if path.is_dir():
                archive.writestr(info, b"")
            else:
                with path.open("rb") as source:
                    archive.writestr(info, source.read(), zipfile.ZIP_DEFLATED)
    return zip_path


def run_pyinstaller(python: str) -> None:
    subprocess.check_call([python, "-m", "pip", "install", "pyinstaller"])
    build_dir = PROJECT_ROOT / "build"
    exe_dist = DIST_ROOT / "StudentInfoSystem"
    if exe_dist.exists():
        shutil.rmtree(exe_dist)

    command = [
        python,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--clean",
        "--name",
        "StudentInfoSystem",
        "--distpath",
        str(DIST_ROOT),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(PROJECT_ROOT),
    ]
    for item in PYINSTALLER_HIDDEN_IMPORTS:
        command.extend(["--hidden-import", item])
    for item in PYINSTALLER_EXCLUDES:
        command.extend(["--exclude-module", item])
    command.append(str(SOURCE_DIR / "portable_launcher.py"))
    subprocess.check_call(command, cwd=SOURCE_DIR)

    if exe_dist.exists():
        for item in exe_dist.iterdir():
            target = APP_DIR / item.name
            if item.is_dir():
                copytree_clean(item, target)
            else:
                shutil.copy2(item, target)


def prepare_portable_tree(portable_dir: Path, app_dir: Path) -> None:
    if portable_dir.exists():
        shutil.rmtree(portable_dir)
    app_dir.mkdir(parents=True, exist_ok=True)

    for filename in APP_FILES:
        source = SOURCE_DIR / filename
        if source.exists():
            shutil.copy2(source, app_dir / filename)

    data_source = SOURCE_DIR / "data"
    data_destination = app_dir / "data"
    if data_source.exists():
        copytree_clean(data_source, data_destination)
    else:
        data_destination.mkdir(parents=True, exist_ok=True)
    (data_destination / "uploads").mkdir(parents=True, exist_ok=True)
    (data_destination / "exports").mkdir(parents=True, exist_ok=True)


def build(no_exe: bool, python: str) -> None:
    prepare_portable_tree(SOURCE_PORTABLE_DIR, SOURCE_APP_DIR)
    write_start_scripts(SOURCE_PORTABLE_DIR)
    source_zip_path = zip_portable(SOURCE_PORTABLE_DIR, SOURCE_ZIP_PATH)

    prepare_portable_tree(PORTABLE_DIR, APP_DIR)
    if not no_exe:
        run_pyinstaller(python)

    write_start_scripts(PORTABLE_DIR)
    zip_path = zip_portable(PORTABLE_DIR, ZIP_PATH)

    print("便携版已生成:")
    print(PORTABLE_DIR)
    print("压缩包:")
    print(zip_path)
    print("跨平台源码便携版:")
    print(SOURCE_PORTABLE_DIR)
    print("跨平台源码压缩包:")
    print(source_zip_path)
    print("Windows 双击 start_student_info_system.bat；macOS 安装依赖后双击 start_student_info_system.command。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build portable StudentInfoSystem package.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--no-exe", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build(args.no_exe, args.python)
