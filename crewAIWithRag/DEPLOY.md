# 本地部署与便携版说明

## 推荐方式一：Windows 免安装便携版

Windows 便携版适合复制到 U 盘、移动硬盘或其他 Windows 电脑上使用。数据保存在便携版目录里的 `app/data/students.db`，导入文件和导出 Excel 也在 `app/data` 下。

这个版本已经内置 Python 运行时，目标 Windows 电脑不需要提前安装 Python。

### 生成便携版

在 PowerShell 中运行：

```powershell
cd .\crewAIWithRag
.\build_portable.ps1
```

生成结果：

```text
.\dist\StudentInfoSystemPortable
.\dist\StudentInfoSystemPortable.zip
.\dist\StudentInfoSystemSourcePortable
.\dist\StudentInfoSystemSourcePortable.zip
```

把整个 `StudentInfoSystemPortable` 文件夹复制到其他电脑，双击：

```text
start_student_info_system.bat
```

系统会自动启动服务，并打开浏览器：

```text
http://127.0.0.1:8013/
```

## 推荐方式二：Windows/macOS 源码便携版

`StudentInfoSystemSourcePortable` 不包含 exe，适合 Windows 和 macOS。目标电脑需要先安装 Python 3.10+。

Windows：

```powershell
cd StudentInfoSystemSourcePortable\app
python -m pip install -r requirements-app.txt
.\run_portable.bat
```

macOS：

```bash
cd StudentInfoSystemSourcePortable/app
python3 -m pip install -r requirements-app.txt
chmod +x run_portable.command ../start_student_info_system.command
./run_portable.command
```

也可以在 macOS 中双击 `start_student_info_system.command` 启动。

注意：macOS 的原生 `.app` 或 `.dmg` 需要在 macOS 机器上构建；Windows 无法直接生成可在 macOS 原生运行的二进制安装包。

## macOS 免安装版

如果需要 macOS 上也完全不依赖目标电脑 Python，需要在一台 macOS 电脑上运行：

```bash
cd crewAIWithRag
chmod +x build_macos_portable.command
./build_macos_portable.command
```

生成结果：

```text
dist/StudentInfoSystemMacPortable
dist/StudentInfoSystemMacPortable.zip
```

这个 zip 会内置 macOS 可执行程序和 Python 运行时，复制到其他同架构 macOS 电脑后可直接启动。

## 数据备份

最重要的数据文件是：

```text
app/data/students.db
```

备份时直接复制整个 `app/data` 文件夹即可。不要只复制 exe，否则学生数据不会一起过去。

## 修改端口

如果 8013 被占用，可以编辑 `app/run_portable.bat`：

```bat
set "STUDENT_INFO_PORT=8013"
```

改成其他端口，例如：

```bat
set "STUDENT_INFO_PORT=8020"
```

## 如果不生成 exe

如果只是给已经安装 Python 的电脑使用，也可以运行：

```powershell
.\build_portable.ps1 -NoExe
```

这种方式会生成源码便携版，但目标电脑需要安装 Python，并执行：

```powershell
python -m pip install -r app\requirements-app.txt
```

之后再双击启动脚本。
