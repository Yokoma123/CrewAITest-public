import os
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

import export_service
import import_service
import student_store


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("STUDENT_INFO_DATA_DIR", os.path.join(BASE_DIR, "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
PORT = int(os.getenv("STUDENT_INFO_PORT", os.getenv("PORT", "8013")))


class StudentPayload(BaseModel):
    name: str
    class_name: str = ""
    student_id: str = ""
    phone: str = ""
    dorm_location: str = ""
    dorm_room: str = ""
    advisor_name: str = ""
    gender: str = ""
    political_status: str = ""
    tripartite_status: str = ""
    destination_type: str = ""
    employer_name: str = ""
    job_title: str = ""
    job_city: str = ""
    is_further_study: str = ""
    destination_note: str = ""
    extra_values: Dict[str, str] = Field(default_factory=dict)


class RecordPayload(BaseModel):
    record_type: str
    title: str
    record_date: str
    description: str = ""
    source: str = ""


class ActivityPayload(BaseModel):
    activity_date: str
    task_name: str
    task_quantity: float = 1
    duration_hours: float = 1
    score: float = 0
    score_rule: str = "任务量 * 时长"
    note: str = ""


class BatchUpdatePayload(BaseModel):
    student_ids: List[int]
    updates: Dict[str, str]


class BatchSearchPayload(BaseModel):
    text: str = ""
    terms: List[str] = Field(default_factory=list)


class ChangeActionPayload(BaseModel):
    action: str
    value: Optional[str] = None


class BulkChangeActionPayload(BaseModel):
    action: str
    change_ids: List[int] = Field(default_factory=list)
    limit: int = 100


class DynamicFieldPayload(BaseModel):
    field_key: str
    label: str
    field_type: str = "text"
    options: List[str] = Field(default_factory=list)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    student_store.init_db()
    print("学生信息管理与汇总系统已初始化")
    yield
    print("正在关闭学生信息管理与汇总系统...")


app = FastAPI(title="学生信息管理与汇总", lifespan=lifespan)


FILTER_FIELDS = [
    "class_name",
    "advisor_name",
    "dorm_location",
    "gender",
    "political_status",
    "tripartite_status",
    "destination_type",
    "missing_phone",
    "has_records",
]


def collect_filters(request: Request) -> Dict[str, str]:
    filters: Dict[str, str] = {}
    for key in FILTER_FIELDS + ["query"]:
        value = request.query_params.get(key, "").strip()
        if value:
            filters[key] = value
    return filters


@app.get("/", response_class=HTMLResponse)
async def index():
    return r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>学生信息管理与汇总</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f7fb;
      --surface: #ffffff;
      --surface-soft: #f8fafc;
      --surface-strong: #eef2f7;
      --text: #172033;
      --muted: #667085;
      --border: #d7dee8;
      --primary: #0f766e;
      --primary-dark: #115e59;
      --danger: #b42318;
      --warning: #b45309;
      --ok: #166534;
      --shadow-soft: 0 10px 28px rgba(15, 23, 42, 0.08);
      --shadow-focus: 0 0 0 3px rgba(15, 118, 110, 0.14);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Arial, "Microsoft YaHei", sans-serif;
      color: var(--text);
      background: var(--bg);
    }
    .app {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
    }
    .sidebar {
      background: #fff;
      border-right: 1px solid var(--border);
      padding: 22px 18px;
      position: sticky;
      top: 0;
      height: 100vh;
    }
    .brand { display: flex; align-items: center; gap: 10px; font-weight: 800; font-size: 18px; margin-bottom: 28px; }
    .brand-mark { width: 36px; height: 36px; border-radius: 8px; display: grid; place-items: center; background: #172033; color: #fff; }
    .side-group { margin: 20px 0 10px; color: var(--muted); font-size: 13px; }
    .side-nav { display: grid; gap: 6px; }
    .side-nav button {
      border: 0;
      display: flex;
      justify-content: flex-start;
      gap: 8px;
      width: 100%;
      padding: 10px 12px;
      background: transparent;
      font-weight: 600;
      transition: transform 160ms ease, background 160ms ease, color 160ms ease, box-shadow 160ms ease;
    }
    .side-nav button:hover { background: #f8fafc; transform: translateX(2px); }
    .side-nav button:active { transform: translateX(2px) scale(0.98); }
    .side-nav button.active { background: #f1f5f9; color: #0f172a; box-shadow: inset 3px 0 0 var(--primary); }
    .shell { min-width: 0; }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      min-height: 72px;
      padding: 0 24px;
      border-bottom: 1px solid var(--border);
      background: #fff;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .top-search { max-width: 320px; }
    .content {
      width: min(1560px, calc(100% - 40px));
      margin: 0 auto;
      padding: 28px 0;
    }
    h1 { margin: 0; font-size: 24px; line-height: 1.25; letter-spacing: 0; }
    h2 { margin: 0 0 10px; font-size: 16px; }
    h3 { margin: 0 0 8px; font-size: 14px; }
    .hint { color: var(--muted); font-size: 13px; line-height: 1.55; margin: 5px 0 0; }
    .status {
      color: var(--ok);
      background: #dcfce7;
      border: 1px solid #bbf7d0;
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 13px;
      white-space: nowrap;
      animation: glowPulse 1800ms ease-in-out infinite;
    }
    section, .toolbar, .filters, .stats, .home-hero, .chart-panel, dialog {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 12px;
      animation: cardIn 260ms ease both;
      transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease, background 180ms ease;
    }
    section:hover, .toolbar:hover, .filters:hover, .chart-panel:hover, .home-hero:hover {
      border-color: #c7d2fe;
      box-shadow: var(--shadow-soft);
      transform: translateY(-1px);
    }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(240px, 1fr) auto auto auto;
      gap: 8px;
      align-items: center;
    }
    .filters {
      display: grid;
      grid-template-columns: repeat(8, minmax(110px, 1fr));
      gap: 8px;
      align-items: end;
    }
    label { display: grid; gap: 5px; font-size: 12px; color: var(--muted); }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 9px;
      font: 14px/1.45 Arial, "Microsoft YaHei", sans-serif;
      color: var(--text);
      background: #fff;
      transition: border-color 160ms ease, box-shadow 160ms ease, background 160ms ease, transform 160ms ease;
    }
    input:hover, select:hover, textarea:hover { border-color: #b7c5d8; }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: var(--shadow-focus);
      background: #fff;
    }
    textarea { min-height: 64px; resize: vertical; }
    button {
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 11px;
      font-size: 14px;
      cursor: pointer;
      background: #fff;
      color: var(--text);
      white-space: nowrap;
      transition: transform 150ms ease, box-shadow 150ms ease, background 150ms ease, border-color 150ms ease, color 150ms ease;
    }
    button.primary { border-color: var(--primary); background: var(--primary); color: #fff; font-weight: 700; }
    button.primary:hover { background: var(--primary-dark); }
    button.danger { color: var(--danger); border-color: #fecaca; }
    button:hover { transform: translateY(-1px); box-shadow: 0 8px 18px rgba(15, 23, 42, 0.10); border-color: #b7c5d8; }
    button:active { transform: translateY(0) scale(0.98); box-shadow: none; }
    button:focus-visible { outline: none; box-shadow: var(--shadow-focus); }
    button:disabled { cursor: not-allowed; opacity: 0.55; }
    .stats {
      display: grid;
      grid-template-columns: repeat(8, minmax(120px, 1fr));
      gap: 8px;
    }
    .metric {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--surface-soft);
      padding: 10px;
      min-height: 72px;
      animation: riseIn 360ms ease both;
      transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
    }
    .metric:hover { transform: translateY(-2px); box-shadow: var(--shadow-soft); border-color: #c7d2fe; }
    .metric strong { display: block; font-size: 22px; line-height: 1.1; margin-bottom: 4px; }
    .metric span { color: var(--muted); font-size: 12px; }
    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.65fr);
      gap: 12px;
      align-items: start;
    }
    #detail-page.full-workspace .layout { grid-template-columns: 1fr; }
    #detail-page.full-workspace #student-list-section { display: none; }
    #detail-page.full-workspace #workspace-section { min-width: 0; }
    #detail-page.full-workspace .tabs { display: none; }
    .page { display: none; }
    .page.active { display: block; animation: pageIn 260ms ease both; }
    .home-hero {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: center;
      padding: 20px;
    }
    .home-hero h2 { font-size: 26px; margin-bottom: 6px; }
    .nav-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .chart-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .chart-panel { min-height: 260px; }
    .chart-bars { display: grid; gap: 10px; margin-top: 10px; }
    .bar-row { display: grid; grid-template-columns: 86px 1fr 48px; gap: 8px; align-items: center; font-size: 13px; }
    .bar-track { height: 10px; border-radius: 999px; background: #e5e7eb; overflow: hidden; }
    .bar-fill { height: 100%; width: 0; border-radius: inherit; background: var(--primary); animation: growBar 720ms ease forwards; }
    .donut-wrap { display: grid; place-items: center; min-height: 180px; }
    .donut {
      width: 150px;
      aspect-ratio: 1;
      border-radius: 50%;
      background: var(--donut-bg, conic-gradient(var(--primary) 0deg, var(--primary) var(--angle), #e5e7eb var(--angle), #e5e7eb 360deg));
      display: grid;
      place-items: center;
      animation: popIn 420ms ease both;
      position: relative;
    }
    .donut-center {
      width: 92px;
      aspect-ratio: 1;
      border-radius: 50%;
      background: #fff;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      place-items: center;
      text-align: center;
      font-weight: 700;
      font-size: 14px;
      color: var(--text);
      padding: 8px;
    }
    .donut-center small { color: var(--muted); font-size: 12px; margin-top: 2px; }
    .activity-summary { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px; }
    .activity-score { border: 1px solid var(--border); border-radius: 8px; padding: 10px; background: var(--surface-soft); }
    .activity-score strong { display:block; font-size: 20px; }
    .progress { width: 100%; height: 10px; border-radius: 999px; background: #e5e7eb; overflow: hidden; margin: 8px 0 10px; }
    .progress > div { height: 100%; width: 0; border-radius: inherit; background: linear-gradient(90deg, #0f766e, #2563eb, #d97706, #0f766e); background-size: 220% 100%; transition: width 220ms ease; animation: progressFlow 1200ms linear infinite; }
    dialog {
      width: min(520px, calc(100% - 24px));
      box-shadow: 0 20px 60px rgba(15, 23, 42, 0.18);
    }
    dialog::backdrop { background: rgba(15, 23, 42, 0.35); }
    @keyframes growBar { from { width: 0; } to { width: var(--bar-width); } }
    @keyframes riseIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes popIn { from { opacity: 0; transform: scale(0.94); } to { opacity: 1; transform: scale(1); } }
    @keyframes pageIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes cardIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes progressFlow { from { background-position: 0 0; } to { background-position: 220% 0; } }
    @keyframes glowPulse { 0%, 100% { box-shadow: 0 0 0 rgba(22, 101, 52, 0); } 50% { box-shadow: 0 0 0 4px rgba(22, 101, 52, 0.08); } }
    .table-wrap { overflow: auto; border: 1px solid var(--border); border-radius: 8px; max-height: 560px; }
    table { width: 100%; border-collapse: collapse; min-width: 1040px; background: #fff; }
    th, td { border-bottom: 1px solid var(--border); padding: 8px 9px; text-align: left; font-size: 13px; vertical-align: top; }
    th { background: var(--surface-strong); font-weight: 700; position: sticky; top: 0; z-index: 1; }
    tr { transition: transform 140ms ease, background 140ms ease; }
    tr:hover td { background: #f8fafc; }
    tbody tr:hover { transform: translateX(2px); }
    .selected td { background: #ecfeff; }
    .row-check { width: 18px; height: 18px; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .full { grid-column: 1 / -1; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; align-items: center; }
    .batch-search-box { display: grid; gap: 10px; margin: 10px 0 12px; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: #fff; }
    .batch-search-box textarea { min-height: 92px; }
    .batch-summary { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .batch-missing { display: flex; gap: 6px; flex-wrap: wrap; }
    .message { min-height: 20px; color: var(--muted); font-size: 13px; margin: 6px 0 10px; }
    .error { color: var(--danger); }
    .warn { color: var(--warning); }
    .pill {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 2px 7px;
      font-size: 12px;
      background: #fff;
      color: var(--muted);
      margin: 1px 3px 1px 0;
    }
    .pill.warn { border-color: #fed7aa; background: #fff7ed; color: var(--warning); }
    .record, .change, .dynamic-row {
      border: 1px solid var(--border);
      background: #fff;
      border-radius: 8px;
      padding: 9px;
      margin-top: 8px;
      animation: cardIn 220ms ease both;
      transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
    }
    .record:hover, .change:hover, .dynamic-row:hover { transform: translateY(-1px); box-shadow: var(--shadow-soft); border-color: #c7d2fe; }
    .tabs { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
    .tab { transition: transform 150ms ease, background 150ms ease, color 150ms ease, box-shadow 150ms ease; }
    .tab.active { background: var(--text); color: #fff; border-color: var(--text); box-shadow: 0 8px 18px rgba(15, 23, 42, 0.12); }
    .tab:disabled { cursor: not-allowed; opacity: 0.45; transform: none; box-shadow: none; }
    .panel { display: none; }
    .panel.active { display: block; animation: pageIn 220ms ease both; }
    .split { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .empty { padding: 18px; text-align: center; color: var(--muted); border: 1px dashed var(--border); border-radius: 8px; background: var(--surface-soft); }
    @media (max-width: 1180px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { position: static; height: auto; }
      .stats { grid-template-columns: repeat(4, 1fr); }
      .filters { grid-template-columns: repeat(4, 1fr); }
      .layout { grid-template-columns: 1fr; }
      .chart-grid, .home-hero { grid-template-columns: 1fr; }
      .nav-actions { justify-content: flex-start; }
    }
    @media (max-width: 720px) {
      header { flex-direction: column; align-items: flex-start; }
      .toolbar, .filters, .stats, .form-grid, .split { grid-template-columns: 1fr; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 1ms !important;
        transition-duration: 1ms !important;
        scroll-behavior: auto !important;
      }
    }
  </style>
</head>
<body>
  <main class="app">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">学</span><span>学生台账</span></div>
      <div class="side-group">控制台</div>
      <nav class="side-nav">
        <button class="side-link active" data-target-page="home-page" type="button">概况</button>
        <button class="side-link" data-target-page="detail-page" data-target-panel="detail-panel" type="button">学生资料</button>
        <button class="side-link" data-target-page="detail-page" data-target-panel="review-panel" type="button">导入核对</button>
        <button class="side-link" data-target-page="detail-page" data-target-panel="records-panel" type="button">奖惩记录</button>
        <button class="side-link" data-target-page="detail-page" data-target-panel="activities-panel" type="button">日常活动</button>
        <button class="side-link" data-target-page="detail-page" data-target-panel="fields-panel" type="button">字段设置</button>
        <button id="side-export" type="button">导出</button>
      </nav>
    </aside>

    <div class="shell">
      <div class="topbar">
        <div class="brand" style="margin-bottom:0;"><span>本地学生数据工作台</span></div>
        <input id="top-search" class="top-search" placeholder="搜索" />
        <div class="status">本地服务运行中</div>
      </div>

      <div class="content">
        <div>
          <h1>学生信息管理与汇总</h1>
          <p class="hint">支持 Excel/CSV 导入、按学号合并、本地保存、人工核对变更、奖惩记录、统计看板和 Excel 导出。本系统不调用大模型，不消耗 API token。</p>
        </div>

        <div id="message" class="message"></div>

    <div id="home-page" class="page active">
      <section class="home-hero">
        <div>
          <h2>欢迎使用学生信息管理与汇总系统</h2>
          <p class="hint">首页展示整体数据态势和可视化图表；进入数据详情后，可以维护学生资料、导入核对、导出 Excel、记录奖惩和日常志愿服务。</p>
        </div>
        <div class="nav-actions">
          <button id="go-detail" class="primary" type="button">进入数据详情页</button>
          <button id="home-refresh" type="button">刷新看板</button>
        </div>
      </section>

      <div class="stats" id="stats"></div>
      <div class="chart-grid">
        <section class="chart-panel">
          <h2>性别分布</h2>
          <div id="gender-chart"></div>
        </section>
        <section class="chart-panel">
          <h2>信息完整度</h2>
          <div id="missing-chart"></div>
        </section>
        <section class="chart-panel">
          <h2>去向与活动</h2>
          <div id="destination-chart"></div>
        </section>
      </div>
    </div>

    <div id="detail-page" class="page">
      <div class="toolbar">
        <input id="search" placeholder="搜索姓名、班级、学号、电话、寝室、导师、单位" />
        <button id="back-home" type="button">返回首页</button>
        <button id="reload" type="button">刷新</button>
        <button id="export" type="button">导出 Excel</button>
        <label>
          <input id="import-file" type="file" accept=".csv,.xlsx,.xls" />
        </label>
      </div>
      <div class="progress" id="import-progress" hidden><div id="import-progress-bar"></div></div>

      <div class="filters">
        <label>班级<select id="filter_class_name"><option value="">全部</option></select></label>
        <label>导师<select id="filter_advisor_name"><option value="">全部</option></select></label>
        <label>寝室位置<select id="filter_dorm_location"><option value="">全部</option></select></label>
        <label>性别<select id="filter_gender"><option value="">全部</option></select></label>
        <label>政治面貌<select id="filter_political_status"><option value="">全部</option></select></label>
        <label>三方<select id="filter_tripartite_status"><option value="">全部</option></select></label>
        <label>去向类型<select id="filter_destination_type"><option value="">全部</option></select></label>
        <label>缺失/记录
          <select id="filter_flags">
            <option value="">全部</option>
            <option value="missing_phone">缺联系电话</option>
            <option value="has_records">有奖惩记录</option>
          </select>
        </label>
      </div>

      <div class="layout">
      <section id="student-list-section">
        <h2>学生列表</h2>
        <div class="actions">
          <select id="batch-field" style="max-width:180px;">
            <option value="class_name">班级</option>
            <option value="advisor_name">导师姓名</option>
            <option value="political_status">政治面貌</option>
            <option value="tripartite_status">是否签署三方</option>
            <option value="destination_type">去向类型</option>
            <option value="job_city">城市</option>
          </select>
          <span id="batch-value-wrap" style="min-width:180px;"></span>
          <button id="batch-apply" type="button">批量编辑选中项</button>
          <button id="toggle-batch-search" type="button">批量查找</button>
          <button id="clear-batch-search" type="button" hidden>退出批量结果</button>
          <span id="selected-count" class="hint">已选择 0 人</span>
        </div>
        <div id="batch-search-box" class="batch-search-box" hidden>
          <label class="full">批量输入姓名、学号或电话
            <textarea id="batch-search-input" placeholder="例如：&#10;李一&#10;王二&#10;张三&#10;也可以输入：李一，王二，张三"></textarea>
          </label>
          <div class="actions">
            <button id="run-batch-search" class="primary" type="button">查找名单</button>
            <button id="use-batch-results" type="button" hidden>只看已找到人员</button>
            <span id="batch-search-summary" class="hint">支持换行、逗号、顿号、分号和空格分隔</span>
          </div>
          <div id="batch-search-missing" class="batch-missing"></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th><input id="check-all" class="row-check" type="checkbox" /></th>
                <th>姓名</th>
                <th>班级</th>
                <th>学号</th>
                <th>性别</th>
                <th>联系电话</th>
                <th>寝室</th>
                <th>导师</th>
                <th>政治面貌</th>
                <th>三方</th>
                <th>去向</th>
                <th>奖惩</th>
              </tr>
            </thead>
            <tbody id="students-body"></tbody>
          </table>
        </div>
      </section>

      <section id="workspace-section">
        <div class="tabs">
          <button class="tab active" data-panel="detail-panel" type="button">学生详情</button>
          <button class="tab" data-panel="records-panel" type="button">奖惩记录</button>
          <button class="tab" data-panel="activities-panel" type="button">日常活动</button>
          <button class="tab" data-panel="review-panel" type="button">导入核对</button>
          <button class="tab" data-panel="fields-panel" type="button">字段设置</button>
        </div>

        <div id="detail-panel" class="panel active">
          <h2>学生详情</h2>
          <form id="student-form">
            <input type="hidden" id="student-pk" />
            <div class="form-grid" id="student-fields"></div>
            <div id="extra-fields" class="form-grid" style="margin-top:8px;"></div>
            <div class="actions">
              <button class="primary" type="submit">保存学生</button>
              <button id="new-student" type="button">新建</button>
              <button id="delete-student" class="danger" type="button">删除学生</button>
            </div>
            <div id="missing-reminder" class="message"></div>
          </form>
        </div>

        <div id="records-panel" class="panel">
          <h2>奖惩记录</h2>
          <form id="record-form">
            <div class="form-grid">
              <label>类型
                <select id="record_type">
                  <option value="奖励">奖励</option>
                  <option value="惩罚">惩罚</option>
                </select>
              </label>
              <label>日期<input id="record_date" type="date" /></label>
              <label class="full">标题<input id="record_title" /></label>
              <label class="full">记录人/来源<input id="record_source" /></label>
              <label class="full">说明<textarea id="record_description"></textarea></label>
            </div>
            <div class="actions">
              <button class="primary" type="submit">添加奖惩</button>
            </div>
          </form>
          <div id="records"></div>
        </div>

        <div id="activities-panel" class="panel">
          <h2>日常活动</h2>
          <div class="activity-summary">
            <div class="activity-score"><strong id="activity-total-score">0</strong><span class="hint">志愿服务总分</span></div>
            <div class="activity-score"><strong id="activity-total-count">0</strong><span class="hint">活动记录数</span></div>
          </div>
          <form id="activity-form">
            <div class="form-grid">
              <label>时间<input id="activity_date" type="date" /></label>
              <label>任务名称<input id="activity_task_name" /></label>
              <label>任务量<input id="activity_quantity" type="number" step="0.1" value="1" /></label>
              <label>时长<input id="activity_hours" type="number" step="0.1" value="1" /></label>
              <label class="full">计算规则
                <select id="activity_rule">
                  <option value="quantity*hours">任务量 * 时长</option>
                  <option value="quantity">只按任务量</option>
                  <option value="hours">只按时长</option>
                  <option value="fixed">固定分数</option>
                </select>
              </label>
              <label>实时分数<input id="activity_score" type="number" step="0.1" value="1" /></label>
              <label class="full">备注<textarea id="activity_note"></textarea></label>
            </div>
            <div class="actions">
              <button class="primary" type="submit">添加活动</button>
            </div>
          </form>
          <div id="activities"></div>
        </div>

        <div id="review-panel" class="panel">
          <h2>导入核对</h2>
          <div class="actions">
            <select id="batch-select"></select>
            <button id="load-changes" type="button">查看待核对</button>
            <button id="prev-changes" type="button">上一页</button>
            <button id="next-changes" type="button">下一页</button>
          </div>
          <div class="actions">
            <button id="apply-page-changes" class="primary" type="button">当前页全部使用新值</button>
            <button id="ignore-page-changes" type="button">当前页全部保留原值</button>
            <button id="apply-all-changes" class="primary" type="button">一键全部使用新值</button>
            <button id="ignore-all-changes" class="danger" type="button">一键全部保留原值</button>
          </div>
          <div class="message" id="change-page-info"></div>
          <div class="progress" id="bulk-progress" hidden><div id="bulk-progress-bar"></div></div>
          <div id="changes"></div>
        </div>

        <div id="fields-panel" class="panel">
          <h2>动态字段设置</h2>
          <p class="hint">导入时遇到新列会先按文本字段提醒。你可以在这里把字段改成下拉，并设置候选项，用英文逗号或中文顿号分隔。</p>
          <div id="dynamic-fields"></div>
        </div>
      </section>
      </div>
    </div>

    <dialog id="export-dialog">
      <h2>选择导出内容</h2>
      <p class="hint">默认导出当前筛选条件下的学生信息。学号、姓名、班级默认选中，其余字段可手动勾选。</p>
      <div class="form-grid">
        <label><span><input id="export-students" type="checkbox" checked disabled style="width:auto;" /> 学生信息</span></label>
        <label><span><input id="export-records" type="checkbox" style="width:auto;" /> 奖惩记录</span></label>
        <label><span><input id="export-activities" type="checkbox" style="width:auto;" /> 日常活动</span></label>
      </div>
      <h3>学生信息字段</h3>
      <div class="form-grid" id="export-fields"></div>
      <div class="actions">
        <button id="confirm-export" class="primary" type="button">确认导出</button>
        <button id="cancel-export" type="button">取消</button>
      </div>
    </dialog>
      </div>
    </div>
  </main>

  <script>
    const state = {
      students: [],
      batchStudents: [],
      batchMode: false,
      selectedId: null,
      checked: new Set(),
      options: { select_options: {}, dynamic_fields: [], distinct_values: {} },
      batches: [],
      changeOffset: 0,
      changeLimit: 20,
      changeTotal: 0
    };

    const fixedFields = [
      ["name", "姓名", "input", true],
      ["class_name", "班级", "input"],
      ["student_id", "学号", "input"],
      ["gender", "性别", "select"],
      ["phone", "联系电话", "input"],
      ["dorm_location", "寝室位置", "input"],
      ["dorm_room", "寝室号", "input"],
      ["advisor_name", "导师姓名", "input"],
      ["political_status", "政治面貌", "select"],
      ["tripartite_status", "是否签署三方", "select"],
      ["destination_type", "去向类型", "select"],
      ["employer_name", "单位名称", "input"],
      ["job_title", "岗位", "input"],
      ["job_city", "城市", "input"],
      ["is_further_study", "是否升学", "select"],
      ["destination_note", "去向备注", "textarea"]
    ];

    const exportableFields = [
      ["student_id", "学号", true],
      ["name", "姓名", true],
      ["class_name", "班级", true],
      ["gender", "性别", false],
      ["phone", "联系电话", false],
      ["dorm_location", "寝室位置", false],
      ["dorm_room", "寝室号", false],
      ["advisor_name", "导师姓名", false],
      ["political_status", "政治面貌", false],
      ["tripartite_status", "是否签署三方", false],
      ["destination_type", "去向类型", false],
      ["employer_name", "单位名称", false],
      ["job_title", "岗位", false],
      ["job_city", "城市", false],
      ["is_further_study", "是否升学", false],
      ["destination_note", "去向备注", false]
    ];

    const message = document.getElementById("message");
    const body = document.getElementById("students-body");
    const studentRequiredPanels = new Set(["detail-panel", "records-panel", "activities-panel"]);
    const fullWorkspacePanels = new Set(["review-panel", "fields-panel"]);

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[char]));
    }

    function showMessage(text, isError = false) {
      message.textContent = text;
      message.className = isError ? "message error" : "message";
    }

    async function withButtonBusy(button, text, task) {
      const original = button.textContent;
      button.disabled = true;
      button.textContent = text;
      try {
        return await task();
      } finally {
        button.disabled = false;
        button.textContent = original;
      }
    }

    async function requestJson(url, options = {}) {
      const response = await fetch(url, options);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "请求失败");
      return data;
    }

    function fillSelect(select, values, keepCurrent = true) {
      const current = keepCurrent ? select.value : "";
      select.innerHTML = '<option value="">全部</option>';
      [...new Set((values || []).filter(Boolean))].forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      });
      if (current) select.value = current;
    }

    function setStudentScopedControls() {
      const hasStudent = Boolean(state.selectedId);
      document.querySelectorAll(".tab").forEach((tab) => {
        if (studentRequiredPanels.has(tab.dataset.panel)) tab.disabled = !hasStudent;
      });
      ["student-form", "record-form", "activity-form"].forEach((formId) => {
        const form = document.getElementById(formId);
        if (!form) return;
        const disabled = formId !== "student-form" && !hasStudent;
        form.querySelectorAll("input, select, textarea, button").forEach((control) => {
          if (control.id === "new-student") return;
          control.disabled = disabled;
        });
      });
    }

    function setWorkspaceMode(panelId) {
      document.getElementById("detail-page").classList.toggle("full-workspace", fullWorkspacePanels.has(panelId));
    }

    function activatePanel(panelId, options = {}) {
      if (studentRequiredPanels.has(panelId) && !state.selectedId && !options.allowEmptyStudent) {
        showMessage("请先在学生列表中选择一个学生，再查看该学生的详情、奖惩或日常活动。", true);
        return false;
      }
      document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item.dataset.panel === panelId));
      document.querySelectorAll(".panel").forEach((item) => item.classList.toggle("active", item.id === panelId));
      setWorkspaceMode(panelId);
      setStudentScopedControls();
      return true;
    }

    function optionHtml(field, selected) {
      const options = state.options.select_options[field] || [];
      return ['<option value="">未填写</option>'].concat(options.map((value) => {
        const mark = value === selected ? " selected" : "";
        return `<option value="${escapeHtml(value)}"${mark}>${escapeHtml(value)}</option>`;
      })).join("");
    }

    function renderFormFields() {
      const container = document.getElementById("student-fields");
      container.innerHTML = "";
      fixedFields.forEach(([key, label, type, required]) => {
        const wrap = document.createElement("label");
        if (type === "textarea") wrap.className = "full";
        wrap.innerHTML = `${label}${type === "select"
          ? `<select id="${key}">${optionHtml(key, "")}</select>`
          : type === "textarea"
            ? `<textarea id="${key}"></textarea>`
            : `<input id="${key}" ${required ? "required" : ""} />`
        }`;
        container.appendChild(wrap);
      });
      renderExtraFields({});
    }

    function renderExportFields() {
      const container = document.getElementById("export-fields");
      const dynamicFields = (state.options.dynamic_fields || []).map((field) => [field.field_key, field.label, false]);
      container.innerHTML = exportableFields.concat(dynamicFields).map(([key, label, checked]) => (
        `<label><span><input class="export-field" type="checkbox" value="${key}" ${checked ? "checked" : ""} style="width:auto;" /> ${label}</span></label>`
      )).join("");
    }

    function renderExtraFields(values) {
      const container = document.getElementById("extra-fields");
      container.innerHTML = "";
      state.options.dynamic_fields.forEach((field) => {
        const wrap = document.createElement("label");
        const value = values[field.field_key] || "";
        const id = "extra_" + field.id;
        if (field.field_type === "select") {
          const opts = ['<option value="">未填写</option>'].concat((field.options || []).map((item) => {
            const mark = item === value ? " selected" : "";
            return `<option value="${escapeHtml(item)}"${mark}>${escapeHtml(item)}</option>`;
          })).join("");
          wrap.innerHTML = `${escapeHtml(field.label)}<select id="${id}" data-extra-key="${escapeHtml(field.field_key)}">${opts}</select>`;
        } else {
          wrap.innerHTML = `${escapeHtml(field.label)}<input id="${id}" data-extra-key="${escapeHtml(field.field_key)}" value="${escapeHtml(value)}" />`;
        }
        container.appendChild(wrap);
      });
    }

    function getFilters() {
      const filters = new URLSearchParams();
      const q = document.getElementById("search").value.trim();
      if (q) filters.set("query", q);
      ["class_name", "advisor_name", "dorm_location", "gender", "political_status", "tripartite_status", "destination_type"].forEach((key) => {
        const value = document.getElementById("filter_" + key).value;
        if (value) filters.set(key, value);
      });
      const flag = document.getElementById("filter_flags").value;
      if (flag === "missing_phone") filters.set("missing_phone", "true");
      if (flag === "has_records") filters.set("has_records", "true");
      return filters;
    }

    async function loadOptions() {
      state.options = await requestJson("/api/options");
      renderFormFields();
      const distinct = state.options.distinct_values || {};
      ["class_name", "advisor_name", "dorm_location", "political_status"].forEach((key) => {
        fillSelect(document.getElementById("filter_" + key), distinct[key] || []);
      });
      ["gender", "political_status", "tripartite_status", "destination_type"].forEach((key) => {
        fillSelect(document.getElementById("filter_" + key), state.options.select_options[key] || []);
      });
      renderBatchValueControl();
      renderDynamicFieldSettings();
      renderExportFields();
    }

    function renderBatchValueControl() {
      const field = document.getElementById("batch-field").value;
      const wrap = document.getElementById("batch-value-wrap");
      const options = state.options.select_options[field] || [];
      if (options.length) {
        wrap.innerHTML = `<select id="batch-value">${optionHtml(field, "")}</select>`;
      } else {
        wrap.innerHTML = '<input id="batch-value" placeholder="批量填写的新值" />';
      }
    }

    async function loadStats() {
      const stats = await requestJson("/api/stats");
      const metrics = [
        ["学生总数", stats.total],
        ["性别分布", summarizeGroup(stats.gender)],
        ["缺联系电话", stats.missing_phone],
        ["缺寝室", stats.missing_dorm],
        ["缺导师", stats.missing_advisor],
        ["待核对", stats.pending_changes],
        ["奖励", stats.reward_count],
        ["惩罚", stats.punishment_count],
        ["活动总分", stats.activity_score]
      ];
      document.getElementById("stats").innerHTML = metrics.map(([label, value]) =>
        `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`
      ).join("");
      renderCharts(stats);
    }

    function summarizeGroup(group) {
      return (group || []).slice(0, 3).map((item) => `${item.label}:${item.count}`).join(" / ") || "无";
    }

    const chartColors = ["#0f766e", "#2563eb", "#d97706", "#7c3aed", "#dc2626", "#0891b2", "#65a30d", "#be123c"];

    function renderBarChart(targetId, rows, total) {
      const target = document.getElementById(targetId);
      const safeTotal = Math.max(Number(total || 0), 1);
      target.innerHTML = `<div class="chart-bars">${
        (rows || []).slice(0, 8).map((row, index) => {
          const pct = Math.round((Number(row.count || 0) / safeTotal) * 100);
          const color = chartColors[index % chartColors.length];
          return `<div class="bar-row">
            <span>${escapeHtml(row.label)}</span>
            <div class="bar-track"><div class="bar-fill" style="--bar-width:${pct}%; background:${color};"></div></div>
            <strong>${row.count}</strong>
          </div>`;
        }).join("")
      }</div>`;
    }

    function normalizeChartRows(rows, labels) {
      const map = new Map((rows || []).map((row) => [row.label, Number(row.count || 0)]));
      return labels.map((label) => ({ label, count: map.get(label) || 0 }));
    }

    function renderPieChart(targetId, rows, centerLabel) {
      const target = document.getElementById(targetId);
      const total = (rows || []).reduce((sum, row) => sum + Number(row.count || 0), 0);
      if (!total) {
        target.innerHTML = `<div class="donut-wrap"><div class="donut" style="--angle:0deg;"><div class="donut-center"><span>${escapeHtml(centerLabel)}</span><small>暂无信息 0</small></div></div></div>`;
        return;
      }
      let start = 0;
      const stops = rows.map((row, index) => {
        const angle = (Number(row.count || 0) / total) * 360;
        const end = start + angle;
        const color = chartColors[index % chartColors.length];
        const segment = `${color} ${start.toFixed(1)}deg ${end.toFixed(1)}deg`;
        start = end;
        return segment;
      }).join(", ");
      target.innerHTML = `<div class="donut-wrap"><div class="donut" style="--donut-bg:conic-gradient(${stops});"><div class="donut-center"><span>${escapeHtml(centerLabel)}</span><small>${total}</small></div></div></div>`;
    }

    function renderCharts(stats) {
      const genderRows = normalizeChartRows(stats.gender, ["男", "女", "未知/未填"]);
      document.getElementById("gender-chart").innerHTML = '<div id="gender-pie"></div><div id="gender-bars"></div>';
      renderPieChart("gender-pie", genderRows, "性别");
      renderBarChart("gender-bars", genderRows, stats.total);
      const missingRows = [
        { label: "缺联系电话", count: stats.missing_phone },
        { label: "缺寝室", count: stats.missing_dorm },
        { label: "缺导师", count: stats.missing_advisor },
        { label: "待核对", count: stats.pending_changes },
      ];
      renderBarChart("missing-chart", missingRows, stats.total);
      const destinationRows = normalizeChartRows(stats.destination_type, ["国企", "私企", "事业单位", "公务员", "升学", "待就业", "未知/未填"]);
      document.getElementById("destination-chart").innerHTML = `
        <div id="destination-pie"></div>
        <div class="chart-bars">
          <div class="bar-row"><span>活动次数</span><div class="bar-track"><div class="bar-fill" style="--bar-width:${Math.min(Number(stats.activity_count || 0), 100)}%; background:#0891b2;"></div></div><strong>${stats.activity_count || 0}</strong></div>
          <div class="bar-row"><span>活动总分</span><div class="bar-track"><div class="bar-fill" style="--bar-width:${Math.min(Number(stats.activity_score || 0), 100)}%; background:#d97706;"></div></div><strong>${stats.activity_score || 0}</strong></div>
        </div>`;
      renderPieChart("destination-pie", destinationRows, "去向");
    }

    async function loadStudents() {
      const params = getFilters();
      const data = await requestJson("/api/students?" + params.toString());
      state.students = data.students;
      state.batchMode = false;
      document.getElementById("clear-batch-search").hidden = true;
      renderStudents();
      if (state.selectedId && state.students.some((item) => item.id === state.selectedId)) {
        selectStudent(state.selectedId);
      }
      setStudentScopedControls();
    }

    function renderStudents() {
      body.innerHTML = "";
      document.getElementById("selected-count").textContent = `已选择 ${state.checked.size} 人`;
      const students = state.batchMode ? state.batchStudents : state.students;
      if (!students.length) {
        body.innerHTML = '<tr><td colspan="12"><div class="empty">没有符合条件的学生</div></td></tr>';
        return;
      }
      students.forEach((student) => {
        const row = document.createElement("tr");
        if (student.id === state.selectedId) row.classList.add("selected");
        const missing = [];
        if (!student.phone) missing.push("缺电话");
        if (!student.dorm_location || !student.dorm_room) missing.push("缺寝室");
        if (!student.advisor_name) missing.push("缺导师");
        row.innerHTML = `
          <td><input class="row-check" type="checkbox" data-id="${student.id}" ${state.checked.has(student.id) ? "checked" : ""}></td>
          <td>${escapeHtml(student.name)} ${missing.map((item) => `<span class="pill warn">${item}</span>`).join("")}</td>
          <td>${escapeHtml(student.class_name)}</td>
          <td>${escapeHtml(student.student_id)}</td>
          <td>${escapeHtml(student.gender)}</td>
          <td>${escapeHtml(student.phone)}</td>
          <td>${escapeHtml([student.dorm_location, student.dorm_room].filter(Boolean).join(" "))}</td>
          <td>${escapeHtml(student.advisor_name)}</td>
          <td>${escapeHtml(student.political_status)}</td>
          <td>${escapeHtml(student.tripartite_status)}</td>
          <td>${escapeHtml([student.destination_type, student.employer_name, student.job_city].filter(Boolean).join(" / "))}</td>
          <td>${student.record_count ?? (student.records || []).length}</td>
        `;
        row.addEventListener("click", (event) => {
          if (event.target.matches("input[type=checkbox]")) return;
          selectStudent(student.id);
        });
        row.querySelector("input").addEventListener("change", (event) => {
          if (event.target.checked) state.checked.add(student.id);
          else state.checked.delete(student.id);
          renderStudents();
        });
        body.appendChild(row);
      });
    }

    function clearForm() {
      state.selectedId = null;
      document.getElementById("student-pk").value = "";
      fixedFields.forEach(([key]) => document.getElementById(key).value = "");
      renderExtraFields({});
      document.getElementById("records").innerHTML = "";
      renderActivities([], 0);
      document.getElementById("missing-reminder").innerHTML = "";
      renderStudents();
      setStudentScopedControls();
    }

    async function loadStudentDetail(id) {
      const data = await requestJson("/api/students/" + id);
      const index = state.students.findIndex((item) => item.id === id);
      if (index >= 0) state.students[index] = { ...state.students[index], ...data.student };
      if (state.selectedId === id) fillStudentDetail(data.student);
    }

    function selectStudent(id) {
      const student = state.students.find((item) => item.id === id);
      const batchStudent = state.batchStudents.find((item) => item.id === id);
      const currentStudent = student || batchStudent;
      if (!currentStudent) return;
      state.selectedId = id;
      fillStudentDetail(currentStudent);
      renderStudents();
      setStudentScopedControls();
      loadStudentDetail(id).catch((error) => showMessage(error.message, true));
    }

    function hasActiveFilters() {
      const params = getFilters();
      params.delete("query");
      return [...params.keys()].length > 0;
    }

    function studentMatchesCurrentFilters(student) {
      const filters = Object.fromEntries(getFilters().entries());
      delete filters.query;
      for (const key of ["class_name", "advisor_name", "dorm_location", "gender", "political_status", "tripartite_status", "destination_type"]) {
        if (filters[key] && String(student[key] || "") !== filters[key]) return false;
      }
      if (filters.missing_phone === "true" && student.phone) return false;
      if (filters.has_records === "true" && Number(student.record_count || 0) <= 0) return false;
      return true;
    }

    async function runBatchSearch() {
      const text = document.getElementById("batch-search-input").value.trim();
      if (!text) {
        if (!hasActiveFilters() && !document.getElementById("search").value.trim()) {
          return showMessage("请先输入名单，或先选择班级、导师、寝室等筛选条件", true);
        }
        await loadStudents();
        document.getElementById("batch-search-summary").textContent = `已按当前筛选条件找到 ${state.students.length} 人`;
        document.getElementById("batch-search-missing").innerHTML = '<span class="pill">筛选完成</span>';
        showMessage(`筛选完成：找到 ${state.students.length} 人`);
        return;
      }
      const result = await requestJson("/api/students/batch-search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });
      const rawStudents = result.students || [];
      state.batchStudents = hasActiveFilters() ? rawStudents.filter(studentMatchesCurrentFilters) : rawStudents;
      state.batchMode = true;
      state.checked.clear();
      document.getElementById("clear-batch-search").hidden = false;
      document.getElementById("use-batch-results").hidden = !state.batchStudents.length;
      document.getElementById("batch-search-summary").textContent =
        `已解析 ${result.terms.length} 项，找到 ${state.batchStudents.length} 人，未找到 ${result.missing.length} 项${hasActiveFilters() ? "，并已叠加当前筛选条件" : ""}`;
      document.getElementById("batch-search-missing").innerHTML = result.missing.length
        ? `<span class="hint">未找到：</span>${result.missing.map((item) => `<span class="pill warn">${escapeHtml(item)}</span>`).join("")}`
        : '<span class="pill">全部找到</span>';
      renderStudents();
      showMessage(`批量查找完成：找到 ${state.batchStudents.length} 人`);
    }

    function clearBatchSearch() {
      state.batchMode = false;
      state.batchStudents = [];
      document.getElementById("clear-batch-search").hidden = true;
      document.getElementById("use-batch-results").hidden = true;
      document.getElementById("batch-search-summary").textContent = "支持换行、逗号、顿号、分号和空格分隔";
      document.getElementById("batch-search-missing").innerHTML = "";
      renderStudents();
      setStudentScopedControls();
    }

    function fillStudentDetail(student) {
      document.getElementById("student-pk").value = student.id;
      fixedFields.forEach(([key]) => {
        const input = document.getElementById(key);
        if (input) input.value = student[key] || "";
      });
      renderExtraFields(student.extra_values || {});
      renderRecords(student.records || []);
      renderActivities(student.activities || [], student.activity_score || 0);
      renderMissingReminder(student);
      setStudentScopedControls();
    }

    function renderMissingReminder(student) {
      const missing = [];
      if (!student.phone) missing.push("联系电话");
      if (!student.dorm_location) missing.push("寝室位置");
      if (!student.dorm_room) missing.push("寝室号");
      if (!student.political_status) missing.push("政治面貌");
      if (!student.tripartite_status) missing.push("是否签署三方");
      if (!student.destination_type) missing.push("去向类型");
      document.getElementById("missing-reminder").innerHTML = missing.length
        ? `字段补全提醒：${missing.map((item) => `<span class="pill warn">${item}</span>`).join("")}`
        : '<span class="pill">基础字段较完整</span>';
    }

    function renderRecords(records) {
      const container = document.getElementById("records");
      container.innerHTML = "";
      if (!records.length) {
        container.innerHTML = '<div class="empty">暂无奖惩记录</div>';
        return;
      }
      records.forEach((record) => {
        const item = document.createElement("div");
        item.className = "record";
        item.innerHTML = `
          <div><strong>${escapeHtml(record.record_type)}</strong> ${escapeHtml(record.record_date)} · ${escapeHtml(record.title)}</div>
          <div class="hint">${escapeHtml(record.description || "")}</div>
          <div class="hint">来源：${escapeHtml(record.source || "未填写")}</div>
          <div class="actions"><button class="danger" type="button">删除记录</button></div>
        `;
        item.querySelector("button").addEventListener("click", async () => {
          await requestJson("/api/records/" + record.id, { method: "DELETE" });
          showMessage("奖惩记录已删除");
          await loadStudentDetail(state.selectedId);
          await loadStudents();
          loadStats().catch(() => {});
        });
        container.appendChild(item);
      });
    }

    function renderActivities(activities, totalScore) {
      document.getElementById("activity-total-score").textContent = totalScore || 0;
      document.getElementById("activity-total-count").textContent = activities.length;
      const container = document.getElementById("activities");
      container.innerHTML = "";
      if (!activities.length) {
        container.innerHTML = '<div class="empty">暂无日常活动记录</div>';
        return;
      }
      activities.forEach((activity) => {
        const item = document.createElement("div");
        item.className = "record";
        item.innerHTML = `
          <div><strong>${escapeHtml(activity.task_name)}</strong> ${escapeHtml(activity.activity_date)} · ${escapeHtml(activity.score)} 分</div>
          <div class="hint">任务量：${escapeHtml(activity.task_quantity)}，时长：${escapeHtml(activity.duration_hours)}，规则：${escapeHtml(activity.score_rule || "")}</div>
          <div class="hint">${escapeHtml(activity.note || "")}</div>
          <div class="actions"><button class="danger" type="button">删除活动</button></div>
        `;
        item.querySelector("button").addEventListener("click", async () => {
          await requestJson("/api/activities/" + activity.id, { method: "DELETE" });
          showMessage("日常活动已删除");
          await loadStudentDetail(state.selectedId);
          await loadStudents();
          loadStats().catch(() => {});
        });
        container.appendChild(item);
      });
    }

    function updateActivityScore() {
      const quantity = Number(document.getElementById("activity_quantity").value || 0);
      const hours = Number(document.getElementById("activity_hours").value || 0);
      const rule = document.getElementById("activity_rule").value;
      const scoreInput = document.getElementById("activity_score");
      if (rule === "quantity*hours") scoreInput.value = (quantity * hours).toFixed(1);
      if (rule === "quantity") scoreInput.value = quantity.toFixed(1);
      if (rule === "hours") scoreInput.value = hours.toFixed(1);
    }

    function setImportProgress(percent, text) {
      const progress = document.getElementById("import-progress");
      const bar = document.getElementById("import-progress-bar");
      progress.hidden = false;
      bar.style.width = `${Math.max(4, Math.min(percent, 100))}%`;
      showMessage(text);
    }

    function collectStudentPayload() {
      const payload = { extra_values: {} };
      fixedFields.forEach(([key]) => payload[key] = document.getElementById(key).value.trim());
      document.querySelectorAll("[data-extra-key]").forEach((input) => {
        payload.extra_values[input.dataset.extraKey] = input.value.trim();
      });
      return payload;
    }

    async function refreshAll() {
      await Promise.all([loadOptions(), loadStats(), loadBatches()]);
      await loadStudents();
    }

    async function loadBatches() {
      const data = await requestJson("/api/import-batches");
      state.batches = data.batches;
      const select = document.getElementById("batch-select");
      select.innerHTML = "";
      if (!state.batches.length) {
        select.innerHTML = '<option value="">暂无导入批次</option>';
        return;
      }
      state.batches.forEach((batch) => {
        const option = document.createElement("option");
        option.value = batch.id;
        option.textContent = `#${batch.id} ${batch.filename} 待核对 ${batch.pending_count}`;
        select.appendChild(option);
      });
    }

    async function loadChanges() {
      const batchId = document.getElementById("batch-select").value;
      const container = document.getElementById("changes");
      if (!batchId) {
        container.innerHTML = '<div class="empty">暂无导入批次</div>';
        return;
      }
      const data = await requestJson(`/api/import-batches/${batchId}/changes?limit=${state.changeLimit}&offset=${state.changeOffset}`);
      state.changeTotal = data.total;
      document.getElementById("change-page-info").textContent = `待核对 ${data.total} 条，当前显示第 ${data.total ? data.offset + 1 : 0} - ${Math.min(data.offset + data.limit, data.total)} 条`;
      if (!data.changes.length) {
        container.innerHTML = '<div class="empty">当前批次没有待核对变更</div>';
        return;
      }
      container.innerHTML = "";
      data.changes.forEach((change) => {
        const item = document.createElement("div");
        item.className = "change";
        item.innerHTML = `
          <h3>${escapeHtml(change.student_name || "未知学生")} · ${escapeHtml(change.student_number)} · ${escapeHtml(change.field_label)}</h3>
          <div class="split">
            <div><span class="hint">原值</span><input value="${escapeHtml(change.old_value || "")}" disabled></div>
            <div><span class="hint">新值</span><input class="manual-value" value="${escapeHtml(change.new_value || "")}"></div>
          </div>
          <p class="hint">类型：${change.change_type === "new_field" ? "发现新字段，确认后会加入字段设置" : "字段值发生变化，需要人工核对"}</p>
          <div class="actions">
            <button class="primary use-new" type="button">使用新值</button>
            <button class="manual" type="button">使用手动值</button>
            <button class="danger ignore" type="button">保留原值</button>
          </div>
        `;
        item.dataset.changeId = String(change.id);
        item.querySelector(".use-new").addEventListener("click", () => applyChange(change.id, "apply", null, item));
        item.querySelector(".manual").addEventListener("click", () => applyChange(change.id, "manual", item.querySelector(".manual-value").value, item));
        item.querySelector(".ignore").addEventListener("click", () => applyChange(change.id, "ignore", null, item));
        container.appendChild(item);
      });
    }

    async function applyChange(id, action, value = null, item = null) {
      if (item) {
        item.querySelectorAll("button").forEach((button) => button.disabled = true);
      }
      await requestJson(`/api/import-changes/${id}/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, value })
      });
      showMessage("导入变更已处理");
      if (item) item.remove();
      state.changeTotal = Math.max(0, state.changeTotal - 1);
      document.getElementById("change-page-info").textContent = `待核对 ${state.changeTotal} 条`;
      await Promise.all([loadBatches(), loadStats(), loadOptions(), loadStudents()]);
      if (!document.querySelector("#changes .change")) await loadChanges();
    }

    async function bulkApplyChanges(action, scope) {
      const batchId = document.getElementById("batch-select").value;
      if (!batchId) return showMessage("请先选择导入批次", true);
      const progress = document.getElementById("bulk-progress");
      const bar = document.getElementById("bulk-progress-bar");
      progress.hidden = false;
      bar.style.width = "0%";
      const totalStart = state.changeTotal || 1;
      let ids = [];
      if (scope === "page") {
        ids = [...document.querySelectorAll("#changes .change")].map((item) => Number(item.dataset.changeId));
      }
      if (scope === "page" && !ids.length) return showMessage("当前页没有可处理项", true);
      let remaining = state.changeTotal;
      let processedAll = 0;
      do {
        const result = await requestJson(`/api/import-batches/${batchId}/changes/bulk-apply`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, change_ids: ids, limit: scope === "page" ? ids.length : 100 })
        });
        processedAll += result.processed;
        remaining = result.remaining;
        const done = scope === "page" ? 100 : Math.round(((totalStart - remaining) / Math.max(totalStart, 1)) * 100);
        bar.style.width = `${Math.max(4, Math.min(done, 100))}%`;
        showMessage(`正在批量处理：已完成 ${processedAll} 条，剩余 ${remaining} 条`);
        if (scope === "page") break;
      } while (remaining > 0);
      showMessage(scope === "page" ? `当前页已处理 ${processedAll} 条` : `当前批次已处理完成，共处理 ${processedAll} 条`);
      state.changeOffset = 0;
      await Promise.all([loadBatches(), loadStats(), loadOptions(), loadStudents(), loadChanges()]);
      setTimeout(() => { progress.hidden = true; bar.style.width = "0%"; }, 700);
    }

    function renderDynamicFieldSettings() {
      const container = document.getElementById("dynamic-fields");
      if (!state.options.dynamic_fields.length) {
        container.innerHTML = '<div class="empty">还没有动态新增字段</div>';
        return;
      }
      container.innerHTML = "";
      state.options.dynamic_fields.forEach((field) => {
        const item = document.createElement("div");
        item.className = "dynamic-row";
        item.innerHTML = `
          <h3>${escapeHtml(field.label)}</h3>
          <div class="form-grid">
            <label>字段名<input class="field-label" value="${escapeHtml(field.label)}"></label>
            <label>类型
              <select class="field-type">
                <option value="text" ${field.field_type === "text" ? "selected" : ""}>文本</option>
                <option value="select" ${field.field_type === "select" ? "selected" : ""}>下拉列表</option>
              </select>
            </label>
            <label class="full">下拉选项<input class="field-options" value="${escapeHtml((field.options || []).join("、"))}" placeholder="例如：是、否、未知"></label>
          </div>
          <div class="actions"><button class="primary" type="button">保存字段设置</button></div>
        `;
        item.querySelector("button").addEventListener("click", async () => {
          const options = item.querySelector(".field-options").value.split(/[、,，]/).map((v) => v.trim()).filter(Boolean);
          await requestJson("/api/dynamic-fields", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              field_key: field.field_key,
              label: item.querySelector(".field-label").value.trim() || field.label,
              field_type: item.querySelector(".field-type").value,
              options
            })
          });
          showMessage("动态字段设置已保存");
          await refreshAll();
        });
        container.appendChild(item);
      });
    }

    document.querySelectorAll(".tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        if (tab.disabled) {
          showMessage("请先选择学生后再进入该功能", true);
          return;
        }
        activatePanel(tab.dataset.panel);
      });
    });

    function activatePage(pageId, panelId = null) {
      document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
      document.getElementById(pageId).classList.add("active");
      let activePanelId = panelId;
      if (panelId) {
        if (!activatePanel(panelId, { allowEmptyStudent: panelId === "detail-panel" })) {
          activePanelId = "detail-panel";
          activatePanel(activePanelId, { allowEmptyStudent: true });
        }
      } else {
        setWorkspaceMode(null);
        setStudentScopedControls();
      }
      document.querySelectorAll(".side-link").forEach((item) => item.classList.remove("active"));
      const activeLink = [...document.querySelectorAll(".side-link")].find((item) => item.dataset.targetPage === pageId && (!activePanelId || item.dataset.targetPanel === activePanelId));
      if (activeLink) activeLink.classList.add("active");
    }

    document.querySelectorAll(".side-link").forEach((button) => {
      button.addEventListener("click", () => activatePage(button.dataset.targetPage, button.dataset.targetPanel || null));
    });

    document.getElementById("student-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      await withButtonBusy(event.submitter, "保存中...", async () => {
        const payload = collectStudentPayload();
        const id = document.getElementById("student-pk").value;
        const saved = await requestJson(id ? "/api/students/" + id : "/api/students", {
          method: id ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        state.selectedId = saved.student.id;
        showMessage("学生信息已保存");
        const index = state.students.findIndex((item) => item.id === saved.student.id);
        if (index >= 0) state.students[index] = { ...state.students[index], ...saved.student };
        else state.students.unshift(saved.student);
        fillStudentDetail(saved.student);
        renderStudents();
        loadStats().catch(() => {});
        loadOptions().catch(() => {});
      });
    });

    document.getElementById("record-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!state.selectedId) return showMessage("请先选择一个学生", true);
      await withButtonBusy(event.submitter, "添加中...", async () => {
        const payload = {
          record_type: document.getElementById("record_type").value,
          title: document.getElementById("record_title").value.trim(),
          record_date: document.getElementById("record_date").value,
          description: document.getElementById("record_description").value.trim(),
          source: document.getElementById("record_source").value.trim()
        };
        await requestJson("/api/students/" + state.selectedId + "/records", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        document.getElementById("record-form").reset();
        showMessage("奖惩记录已添加");
        await loadStudentDetail(state.selectedId);
        await loadStudents();
        loadStats().catch(() => {});
      });
    });

    document.getElementById("activity-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!state.selectedId) return showMessage("请先选择一个学生", true);
      await withButtonBusy(event.submitter, "添加中...", async () => {
        updateActivityScore();
        const ruleText = {
          "quantity*hours": "任务量 * 时长",
          "quantity": "只按任务量",
          "hours": "只按时长",
          "fixed": "固定分数"
        }[document.getElementById("activity_rule").value] || "任务量 * 时长";
        const payload = {
          activity_date: document.getElementById("activity_date").value,
          task_name: document.getElementById("activity_task_name").value.trim(),
          task_quantity: Number(document.getElementById("activity_quantity").value || 0),
          duration_hours: Number(document.getElementById("activity_hours").value || 0),
          score: Number(document.getElementById("activity_score").value || 0),
          score_rule: ruleText,
          note: document.getElementById("activity_note").value.trim()
        };
        await requestJson("/api/students/" + state.selectedId + "/activities", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        document.getElementById("activity-form").reset();
        document.getElementById("activity_quantity").value = "1";
        document.getElementById("activity_hours").value = "1";
        updateActivityScore();
        showMessage("日常活动已添加，志愿服务分数已更新");
        await loadStudentDetail(state.selectedId);
        await loadStudents();
        loadStats().catch(() => {});
      });
    });

    document.getElementById("delete-student").addEventListener("click", async () => {
      if (!state.selectedId) return showMessage("请先选择一个学生", true);
      if (!confirm("确认删除该学生及其奖惩记录？")) return;
      await requestJson("/api/students/" + state.selectedId, { method: "DELETE" });
      clearForm();
      showMessage("学生已删除");
      await loadStudents();
      loadStats().catch(() => {});
    });

    document.getElementById("batch-apply").addEventListener("click", async () => {
      if (!state.checked.size) return showMessage("请先勾选学生", true);
      const field = document.getElementById("batch-field").value;
      const value = document.getElementById("batch-value").value.trim();
      if (!value) return showMessage("请选择或输入批量编辑的新值", true);
      const result = await requestJson("/api/batch-update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_ids: [...state.checked], updates: { [field]: value } })
      });
      showMessage(`批量编辑完成，已更新 ${result.updated} 人`);
      state.checked.clear();
      await refreshAll();
    });

    document.getElementById("export").addEventListener("click", () => {
      document.getElementById("export-dialog").showModal();
    });

    document.getElementById("confirm-export").addEventListener("click", () => {
      const params = getFilters();
      params.append("include", "students");
      if (document.getElementById("export-records").checked) params.append("include", "records");
      if (document.getElementById("export-activities").checked) params.append("include", "activities");
      document.querySelectorAll(".export-field:checked").forEach((input) => params.append("fields", input.value));
      document.getElementById("export-dialog").close();
      window.location.href = "/api/export?" + params.toString();
    });

    document.getElementById("cancel-export").addEventListener("click", () => {
      document.getElementById("export-dialog").close();
    });

    document.getElementById("check-all").addEventListener("change", (event) => {
      if (event.target.checked) state.students.forEach((student) => state.checked.add(student.id));
      else state.checked.clear();
      renderStudents();
    });

    document.getElementById("new-student").addEventListener("click", clearForm);
    document.getElementById("batch-field").addEventListener("change", renderBatchValueControl);
    document.getElementById("toggle-batch-search").addEventListener("click", () => {
      const box = document.getElementById("batch-search-box");
      box.hidden = !box.hidden;
      if (!box.hidden) document.getElementById("batch-search-input").focus();
    });
    document.getElementById("run-batch-search").addEventListener("click", () => runBatchSearch().catch((error) => showMessage(error.message, true)));
    document.getElementById("use-batch-results").addEventListener("click", () => {
      state.batchMode = true;
      renderStudents();
    });
    document.getElementById("clear-batch-search").addEventListener("click", clearBatchSearch);
    document.getElementById("go-detail").addEventListener("click", () => {
      activatePage("detail-page", "detail-panel");
    });
    document.getElementById("back-home").addEventListener("click", () => {
      activatePage("home-page");
      loadStats().catch((error) => showMessage(error.message, true));
    });
    document.getElementById("side-export").addEventListener("click", () => {
      activatePage("detail-page", "detail-panel");
      document.getElementById("export-dialog").showModal();
    });
    document.getElementById("top-search").addEventListener("input", (event) => {
      document.getElementById("search").value = event.target.value;
      activatePage("detail-page", "detail-panel");
      loadStudents().catch((error) => showMessage(error.message, true));
    });
    document.getElementById("home-refresh").addEventListener("click", () => loadStats().catch((error) => showMessage(error.message, true)));
    ["activity_quantity", "activity_hours", "activity_rule"].forEach((id) => {
      document.getElementById(id).addEventListener("input", updateActivityScore);
      document.getElementById(id).addEventListener("change", updateActivityScore);
    });
    document.getElementById("reload").addEventListener("click", () => refreshAll().catch((error) => showMessage(error.message, true)));
    document.getElementById("load-changes").addEventListener("click", () => {
      state.changeOffset = 0;
      loadChanges().catch((error) => showMessage(error.message, true));
    });
    document.getElementById("prev-changes").addEventListener("click", () => {
      state.changeOffset = Math.max(0, state.changeOffset - state.changeLimit);
      loadChanges().catch((error) => showMessage(error.message, true));
    });
    document.getElementById("next-changes").addEventListener("click", () => {
      if (state.changeOffset + state.changeLimit < state.changeTotal) {
        state.changeOffset += state.changeLimit;
        loadChanges().catch((error) => showMessage(error.message, true));
      }
    });
    document.getElementById("apply-page-changes").addEventListener("click", () => bulkApplyChanges("apply", "page").catch((error) => showMessage(error.message, true)));
    document.getElementById("ignore-page-changes").addEventListener("click", () => bulkApplyChanges("ignore", "page").catch((error) => showMessage(error.message, true)));
    document.getElementById("apply-all-changes").addEventListener("click", () => {
      if (confirm("确认将当前批次所有待核对项都使用新值？")) bulkApplyChanges("apply", "all").catch((error) => showMessage(error.message, true));
    });
    document.getElementById("ignore-all-changes").addEventListener("click", () => {
      if (confirm("确认将当前批次所有待核对项都保留原值？")) bulkApplyChanges("ignore", "all").catch((error) => showMessage(error.message, true));
    });
    document.getElementById("search").addEventListener("input", () => loadStudents().catch((error) => showMessage(error.message, true)));
    document.querySelectorAll(".filters select").forEach((select) => {
      select.addEventListener("change", () => loadStudents().catch((error) => showMessage(error.message, true)));
    });

    document.getElementById("import-file").addEventListener("change", async (event) => {
      const file = event.target.files[0];
      if (!file) return;
      const data = new FormData();
      data.append("file", file);
      setImportProgress(12, "正在上传 " + file.name + " ...");
      try {
        setImportProgress(38, "文件已接收，正在解析表头和学生数据...");
        const result = await requestJson("/api/import", { method: "POST", body: data });
        setImportProgress(76, "正在合并数据并刷新页面...");
        const newFields = Object.values(result.new_field_columns || {});
        const tail = result.conflicts
          ? `有 ${result.conflicts} 项需要人工核对，请打开“导入核对”。`
          : "没有发现需要人工核对的变更。";
        showMessage(`导入完成：新增 ${result.new_students} 人，自动补充 ${result.updated} 人，跳过 ${result.skipped} 行。${newFields.length ? "发现新字段：" + newFields.join("、") + "。" : ""}${tail}`);
        await refreshAll();
        if (result.batch_id) {
          activatePage("detail-page", "review-panel");
          document.getElementById("batch-select").value = result.batch_id;
          await loadChanges();
        }
        setImportProgress(100, "导入完成");
        setTimeout(() => {
          document.getElementById("import-progress").hidden = true;
          document.getElementById("import-progress-bar").style.width = "0%";
        }, 900);
      } catch (error) {
        showMessage(error.message, true);
      } finally {
        event.target.value = "";
      }
    });

    renderExportFields();
    refreshAll().catch((error) => showMessage(error.message, true));
  </script>
</body>
</html>
    """


@app.get("/health")
async def health():
    return {"status": "ok", "service": "学生信息管理与汇总"}


@app.get("/api/students")
async def api_list_students(request: Request, query: str = ""):
    filters = collect_filters(request)
    return {"students": student_store.list_students(query or filters.get("query", ""), filters)}


@app.post("/api/students/batch-search")
async def api_batch_search_students(payload: BatchSearchPayload):
    terms = list(payload.terms)
    if payload.text:
        terms.extend([item.strip() for item in re.split(r"[\n\r,，、;；\t ]+", payload.text) if item.strip()])
    terms = terms[:200]
    if not terms:
        raise HTTPException(status_code=400, detail="请输入至少一个姓名、学号或电话")
    return student_store.batch_search_students(terms)


@app.get("/api/students/{student_id}")
async def api_get_student(student_id: int):
    student = student_store.get_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return {"student": student}


@app.post("/api/students")
async def api_create_student(payload: StudentPayload):
    try:
        return {"student": student_store.save_student(payload.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/students/{student_id}")
async def api_update_student(student_id: int, payload: StudentPayload):
    try:
        if not student_store.get_student(student_id):
            raise HTTPException(status_code=404, detail="学生不存在")
        return {"student": student_store.save_student(payload.model_dump(), student_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/students/{student_id}")
async def api_delete_student(student_id: int):
    student_store.delete_student(student_id)
    return {"deleted": True}


@app.post("/api/students/{student_id}/records")
async def api_add_record(student_id: int, payload: RecordPayload):
    try:
        return {"record": student_store.add_record(student_id, payload.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/records/{record_id}")
async def api_delete_record(record_id: int):
    student_store.delete_record(record_id)
    return {"deleted": True}


@app.post("/api/students/{student_id}/activities")
async def api_add_activity(student_id: int, payload: ActivityPayload):
    try:
        return {"activity": student_store.add_activity(student_id, payload.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/activities/{activity_id}")
async def api_delete_activity(activity_id: int):
    student_store.delete_activity(activity_id)
    return {"deleted": True}


@app.post("/api/import")
async def api_import_students(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="暂只支持 CSV、XLSX、XLS 文件")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    target = os.path.join(UPLOAD_DIR, safe_name)
    with open(target, "wb") as output:
        shutil.copyfileobj(file.file, output)

    try:
        return JSONResponse(content=import_service.import_students(target, file.filename or safe_name))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/stats")
async def api_stats():
    return student_store.get_stats()


@app.get("/api/options")
async def api_options():
    students = student_store.list_students("")
    distinct_values: Dict[str, List[str]] = {}
    for field in ["class_name", "advisor_name", "dorm_location", "political_status"]:
        distinct_values[field] = sorted({str(item.get(field, "") or "") for item in students if item.get(field)})
    return {
        "labels": student_store.FIELD_LABELS,
        "select_options": student_store.SELECT_OPTIONS,
        "dynamic_fields": student_store.get_dynamic_fields(),
        "distinct_values": distinct_values,
    }


@app.get("/api/import-batches")
async def api_import_batches():
    return {"batches": student_store.list_import_batches()}


@app.get("/api/import-batches/{batch_id}/changes")
async def api_import_changes(batch_id: int, status: str = "pending", limit: int = 20, offset: int = 0):
    return {
        "changes": student_store.list_import_changes(batch_id, status, limit, offset),
        "total": student_store.count_import_changes(batch_id, status),
        "limit": limit,
        "offset": offset,
    }


@app.post("/api/import-changes/{change_id}/apply")
async def api_apply_import_change(change_id: int, payload: ChangeActionPayload):
    action = payload.action
    if action == "manual":
        action = "apply"
    if action not in {"apply", "ignore"}:
        raise HTTPException(status_code=400, detail="处理动作必须是 apply、manual 或 ignore")
    try:
        return {"change": student_store.apply_import_change(change_id, action, payload.value)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/import-batches/{batch_id}/changes/bulk-apply")
async def api_bulk_apply_import_changes(batch_id: int, payload: BulkChangeActionPayload):
    action = payload.action
    if action == "manual":
        action = "apply"
    if action not in {"apply", "ignore"}:
        raise HTTPException(status_code=400, detail="处理动作必须是 apply 或 ignore")
    change_ids = payload.change_ids or student_store.list_import_change_ids(batch_id, "pending", payload.limit)
    processed = 0
    errors = []
    for change_id in change_ids[: max(1, payload.limit)]:
        try:
            student_store.apply_import_change(change_id, action)
            processed += 1
        except ValueError as exc:
            errors.append(str(exc))
    return {
        "processed": processed,
        "remaining": student_store.count_import_changes(batch_id, "pending"),
        "errors": errors,
    }


@app.post("/api/dynamic-fields")
async def api_dynamic_field(payload: DynamicFieldPayload):
    field_type = payload.field_type if payload.field_type in {"text", "select"} else "text"
    if not payload.field_key.strip() or not payload.label.strip():
        raise HTTPException(status_code=400, detail="字段标识和字段名不能为空")
    return {
        "field": student_store.upsert_dynamic_field(
            payload.field_key.strip(),
            payload.label.strip(),
            field_type,
            payload.options,
        )
    }


@app.post("/api/batch-update")
async def api_batch_update(payload: BatchUpdatePayload):
    updated = student_store.batch_update_students(payload.student_ids, payload.updates)
    return {"updated": updated}


@app.get("/api/export")
async def api_export(
    request: Request,
    include: List[str] = Query(default=["students"]),
    fields: List[str] = Query(default=[]),
):
    filters = collect_filters(request)
    try:
        path = export_service.export_excel(include, filters, fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=os.path.basename(path),
    )


if __name__ == "__main__":
    print(f"在端口 {PORT} 上启动学生信息管理与汇总系统")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
