#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
DIST_ROOT="../dist"
BUILD_ROOT="../build-macos"
APP_NAME="StudentInfoSystemMac"
PORTABLE_DIR="$DIST_ROOT/StudentInfoSystemMacPortable"
ZIP_PATH="$DIST_ROOT/StudentInfoSystemMacPortable.zip"

mkdir -p "$DIST_ROOT"
rm -rf "$BUILD_ROOT" "$PORTABLE_DIR" "$DIST_ROOT/$APP_NAME"

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r requirements-app.txt pyinstaller

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --onedir \
  --clean \
  --name "$APP_NAME" \
  --distpath "$DIST_ROOT" \
  --workpath "$BUILD_ROOT" \
  --specpath ".." \
  --hidden-import main \
  --hidden-import student_store \
  --hidden-import import_service \
  --hidden-import export_service \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols \
  --hidden-import uvicorn.protocols.http \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan \
  --hidden-import uvicorn.lifespan.on \
  portable_launcher.py

mkdir -p "$PORTABLE_DIR/app"
cp -R "$DIST_ROOT/$APP_NAME/"* "$PORTABLE_DIR/app/"
cp -R data "$PORTABLE_DIR/app/data"
cp README.md DEPLOY.md requirements-app.txt "$PORTABLE_DIR/app/"

cat > "$PORTABLE_DIR/start_student_info_system.command" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/app"
./StudentInfoSystemMac
EOF

chmod +x "$PORTABLE_DIR/start_student_info_system.command"
chmod +x "$PORTABLE_DIR/app/StudentInfoSystemMac"

rm -f "$ZIP_PATH"
(cd "$DIST_ROOT" && zip -qry "StudentInfoSystemMacPortable.zip" "StudentInfoSystemMacPortable")

echo "macOS 免安装版已生成:"
echo "$PORTABLE_DIR"
echo "$ZIP_PATH"
