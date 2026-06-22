# 本地智能工具平台

本仓库包含两个本地 Web 子系统：AI 多智能体代码生成与审查系统、学生信息管理与汇总系统。项目用于展示 CrewAI、FastAPI、SQLite、Excel 数据处理和本地便携式部署能力。

## 子系统一：AI 多智能体代码生成与审查

目录：`crewAIWithCoding/`

- 基于 CrewAI 构建“代码生成 - 质量审查 - 最终评估”流程。
- 支持中文需求输入、网页端提交任务、阶段化进度反馈与结果展示。
- 支持通过 `.env.example` 配置 OpenAI 兼容接口、OneAPI 或 Ollama。

运行示例：

```powershell
cd crewAIWithCoding
pip install -r requirements.txt
python main.py
```

浏览器访问：`http://127.0.0.1:8012/`

## 子系统二：学生信息管理与汇总

目录：`crewAIWithRag/`

- 支持 Excel/CSV 导入、按学号合并、空值不覆盖、冲突人工核对。
- 支持学生信息编辑、高级筛选、批量修改、动态字段、奖惩记录、日常活动积分。
- 支持统计看板、图表展示、自定义字段 Excel 导出。
- 支持 PyInstaller 打包为 Windows 免安装便携版。

运行示例：

```powershell
cd crewAIWithRag
pip install -r requirements-app.txt
python main.py
```

浏览器访问：`http://127.0.0.1:8013/`

## 数据与安全说明

- 仓库不提交学生数据库文件；首次运行时系统会自动创建空的 `crewAIWithRag/data/students.db`。
- 真实上传文件、导出 Excel、打包产物和真实密钥均不应提交到仓库。
- 请复制 `.env.example` 为 `.env` 后在本地填写真实配置，`.env` 已被 `.gitignore` 排除。

## 技术栈

Python、FastAPI、Uvicorn、SQLite、OpenPyXL、HTML/CSS/JavaScript、CrewAI、PyInstaller。
