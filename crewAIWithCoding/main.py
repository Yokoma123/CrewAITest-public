# 导入依赖包
import os
import sys
import re
import uuid
import time
import json
import asyncio
import contextlib
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import uvicorn
from crewai import LLM
from crew import CrewtestprojectCrew


def load_env_file():
    """Load simple KEY=VALUE settings from project .env files."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for filename in (".env", ".env.example"):
        env_path = os.path.join(project_root, filename)
        if not os.path.exists(env_path):
            continue

        with open(env_path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and not os.getenv(key):
                    os.environ[key] = value


load_env_file()
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")


# 模型全局参数配置  根据自己的实际情况进行调整
# openai模型相关配置 根据自己的实际情况进行调整
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.sudocode.chat/v1")
OPENAI_CHAT_API_KEY = os.getenv("OPENAI_CHAT_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5.5")
# OPENAI_CHAT_MODEL = "gpt-4o-mini"
# 非gpt大模型相关配置(oneapi方案 通义千问为例) 根据自己的实际情况进行调整
ONEAPI_API_BASE = os.getenv("ONEAPI_API_BASE", "http://139.224.72.218:3000/v1")
ONEAPI_CHAT_API_KEY = os.getenv("ONEAPI_CHAT_API_KEY", "")
ONEAPI_CHAT_MODEL = os.getenv("ONEAPI_CHAT_MODEL", "qwen-max")
# 本地大模型相关配置(Ollama方案 llama3.1:latest为例) 根据自己的实际情况进行调整
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434/v1")
OLLAMA_CHAT_API_KEY = os.getenv("OLLAMA_CHAT_API_KEY", "NA")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1:latest")


# 初始化LLM模型
model = None
# API服务设置相关  根据自己的实际情况进行调整
PORT = int(os.getenv("PORT", "8012"))  # 服务访问的端口
# openai:调用gpt大模型;oneapi:调用非gpt大模型;ollama:调用本地大模型
MODEL_TYPE = os.getenv("MODEL_TYPE", "openai")
# MODEL_TYPE = "oneapi"



# 定义Message类
class Message(BaseModel):
    role: str
    content: str
# 定义ChatCompletionRequest类
class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    stream: Optional[bool] = False
# 定义ChatCompletionResponseChoice类
class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: Message
    finish_reason: Optional[str] = None
# 定义ChatCompletionResponse类
class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    choices: List[ChatCompletionResponseChoice]
    system_fingerprint: Optional[str] = None


def get_latest_user_content(request: ChatCompletionRequest) -> str:
    if not request.messages:
        raise HTTPException(status_code=400, detail="请先输入开发需求。")
    return request.messages[-1].content


def format_sse(event: str, data: str) -> str:
    lines = str(data).splitlines() or [""]
    payload = "\n".join(f"data: {line}" for line in lines)
    return f"event: {event}\n{payload}\n\n"


PROGRESS_STAGES = [
    {
        "name": "阶段 1/3：需求分析与代码生成",
        "detail": "正在理解你的开发需求，拆解功能点，并生成第一版代码。",
    },
    {
        "name": "阶段 2/3：代码审查与修复",
        "detail": "正在检查语法、逻辑、依赖、异常处理和边界情况，并修复问题。",
    },
    {
        "name": "阶段 3/3：最终交付检查",
        "detail": "正在确认代码是否满足需求，整理最终代码、运行方式和注意事项。",
    },
]


def progress_message(stage_index: int, elapsed: Optional[int] = None) -> str:
    safe_index = min(max(stage_index, 0), len(PROGRESS_STAGES) - 1)
    stage = PROGRESS_STAGES[safe_index]
    prefix = f"{stage['name']} - {stage['detail']}"
    if elapsed is None:
        return prefix
    return f"{prefix} 已运行 {elapsed} 秒。"


async def run_coding_crew(query_prompt: str, progress_queue: Optional[asyncio.Queue] = None):
    print(f"用户问题是: {query_prompt}")
    inputs = {"game": query_prompt}
    loop = asyncio.get_running_loop()

    def report_progress(message: str):
        if progress_queue:
            loop.call_soon_threadsafe(progress_queue.put_nowait, message)

    report_progress("已接收开发需求，正在创建多智能体团队...")
    crew = CrewtestprojectCrew(model, progress_callback=report_progress).crew()
    report_progress("智能体团队已创建，将按 3 个阶段执行。")
    report_progress(progress_message(0))
    result = await crew.kickoff_async(inputs=inputs)
    formatted_response = str(result)
    print(f"LLM最终回复结果: {formatted_response}")
    return formatted_response


# 定义了一个异步函数lifespan，它接收一个FastAPI应用实例app作为参数。这个函数将管理应用的生命周期，包括启动和关闭时的操作
# 函数在应用启动时执行一些初始化操作
# 函数在应用关闭时执行一些清理操作
# @asynccontextmanager 装饰器用于创建一个异步上下文管理器，它允许在yield之前和之后执行特定的代码块，分别表示启动和关闭时的操作
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    # 申明引用全局变量，在函数中被初始化，并在整个应用中使用
    global MODEL_TYPE, model
    global ONEAPI_API_BASE, ONEAPI_CHAT_API_KEY, ONEAPI_CHAT_MODEL
    global OPENAI_API_BASE, OPENAI_CHAT_API_KEY, OPENAI_CHAT_MODEL
    global OLLAMA_API_BASE, OLLAMA_CHAT_API_KEY, OLLAMA_CHAT_MODEL
    # 根据自己实际情况选择调用model和embedding模型类型
    try:
        print("正在初始化模型")
        # 根据MODEL_TYPE选择初始化对应的模型,默认使用gpt大模型
        if MODEL_TYPE == "oneapi" and not ONEAPI_CHAT_API_KEY:
            model = None
            print("未设置 ONEAPI_CHAT_API_KEY，网页会正常启动，但生成代码前需要先配置模型密钥。")
        elif MODEL_TYPE == "openai" and not OPENAI_CHAT_API_KEY:
            model = None
            print("未设置 OPENAI_CHAT_API_KEY，网页会正常启动，但生成代码前需要先配置模型密钥。")
        elif MODEL_TYPE == "oneapi":
            model = LLM(
                model=ONEAPI_CHAT_MODEL,
                api_key=ONEAPI_CHAT_API_KEY,
                base_url=ONEAPI_API_BASE,
                temperature=0.7,
            )
        elif MODEL_TYPE == "ollama":
            model = LLM(
                model=OLLAMA_CHAT_MODEL,
                api_key=OLLAMA_CHAT_API_KEY,
                base_url=OLLAMA_API_BASE,
                temperature=0.7,
            )
        else:
            model = LLM(
                model=OPENAI_CHAT_MODEL,
                api_key=OPENAI_CHAT_API_KEY,
                base_url=OPENAI_API_BASE,
                temperature=0.7,
            )

        print("LLM初始化完成")

    except Exception as e:
        print(f"初始化过程中出错: {str(e)}")
        model = None
        print("网页会继续启动，请检查模型配置后再使用生成功能。")

    # yield 关键字将控制权交还给FastAPI框架，使应用开始运行
    # 分隔了启动和关闭的逻辑。在yield 之前的代码在应用启动时运行，yield 之后的代码在应用关闭时运行
    yield
    # 关闭时执行
    print("正在关闭...")


# lifespan 参数用于在应用程序生命周期的开始和结束时执行一些初始化或清理工作
app = FastAPI(lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def index():
    return r"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>自动写代码智能体</title>
      <style>
        :root {
          color-scheme: light;
          --bg: #f6f7f9;
          --surface: #ffffff;
          --surface-muted: #f1f5f9;
          --text: #172033;
          --muted: #64748b;
          --border: #d7dee8;
          --primary: #0f766e;
          --primary-hover: #115e59;
          --danger: #b42318;
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
          width: min(1180px, calc(100% - 32px));
          margin: 0 auto;
          padding: 24px 0 32px;
        }
        header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 18px;
        }
        h1 {
          margin: 0;
          font-size: 24px;
          line-height: 1.25;
          letter-spacing: 0;
        }
        .status {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          color: #166534;
          background: #dcfce7;
          border: 1px solid #bbf7d0;
          padding: 6px 10px;
          border-radius: 6px;
          font-size: 14px;
          white-space: nowrap;
        }
        .layout {
          display: grid;
          grid-template-columns: minmax(0, 430px) minmax(0, 1fr);
          gap: 16px;
        }
        section {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 8px;
          padding: 16px;
        }
        h2 {
          margin: 0 0 12px;
          font-size: 16px;
          line-height: 1.4;
        }
        label {
          display: block;
          margin-bottom: 8px;
          font-weight: 700;
        }
        textarea {
          width: 100%;
          min-height: 280px;
          resize: vertical;
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 12px;
          font: 14px/1.6 Consolas, "Microsoft YaHei", monospace;
          color: var(--text);
          background: #fff;
        }
        textarea:focus, button:focus {
          outline: 3px solid rgba(15, 118, 110, 0.22);
          outline-offset: 2px;
        }
        .actions {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 12px;
        }
        button {
          border: 1px solid var(--border);
          border-radius: 6px;
          padding: 9px 12px;
          font-size: 14px;
          cursor: pointer;
          background: #fff;
          color: var(--text);
        }
        button.primary {
          border-color: var(--primary);
          background: var(--primary);
          color: #fff;
          font-weight: 700;
        }
        button.primary:hover { background: var(--primary-hover); }
        button:disabled {
          cursor: not-allowed;
          opacity: 0.65;
        }
        .examples {
          display: grid;
          gap: 8px;
          margin-top: 16px;
        }
        .example {
          text-align: left;
          background: var(--surface-muted);
        }
        .output {
          min-height: 430px;
          white-space: pre-wrap;
          word-break: break-word;
          overflow: auto;
          background: #0f172a;
          color: #e5edf8;
          border-radius: 6px;
          padding: 14px;
          font: 14px/1.65 Consolas, "Microsoft YaHei", monospace;
        }
        .hint {
          color: var(--muted);
          font-size: 13px;
          line-height: 1.6;
          margin: 10px 0 0;
        }
        .error {
          color: var(--danger);
          margin-top: 10px;
          min-height: 20px;
          font-size: 14px;
        }
        @media (max-width: 840px) {
          .layout { grid-template-columns: 1fr; }
          header { align-items: flex-start; flex-direction: column; }
          .output { min-height: 320px; }
        }
      </style>
    </head>
    <body>
      <main class="app">
        <header>
          <div>
            <h1>自动写代码智能体</h1>
            <p class="hint">输入中文开发需求，系统会调用多智能体完成代码生成、审查和交付说明。</p>
          </div>
          <div class="status" aria-label="服务状态">● 服务已启动</div>
        </header>

        <div class="layout">
          <section aria-labelledby="input-title">
            <h2 id="input-title">开发需求</h2>
            <label for="prompt">输入你想让智能体完成的任务</label>
            <textarea id="prompt">请写一个 Python 脚本，读取 Excel 学生成绩表，计算每名学生的总分、平均分，并按照总分从高到低输出排名结果。</textarea>
            <div class="actions">
              <button class="primary" id="submit" type="button">生成代码</button>
              <button id="clear" type="button">清空</button>
            </div>
            <div class="examples" aria-label="示例需求">
              <button class="example" type="button" data-example="请写一个 Python 脚本，读取 Excel 学生成绩表，计算每名学生的总分、平均分，并按照总分从高到低输出排名结果。">示例：成绩表排名脚本</button>
              <button class="example" type="button" data-example="请写一个 Python 程序，批量读取一个文件夹中的 TXT 文件，统计每个文件的字数，并生成汇总 CSV。">示例：批量统计文档字数</button>
              <button class="example" type="button" data-example="请写一个 FastAPI 接口，接收学生姓名和成绩，返回是否及格，并给出简单的输入校验。">示例：FastAPI 成绩接口</button>
            </div>
            <p class="hint">生成可能需要几十秒到几分钟，取决于模型速度和需求复杂度。</p>
            <div class="error" id="error" role="alert"></div>
          </section>

          <section aria-labelledby="output-title">
            <h2 id="output-title">生成结果</h2>
            <div class="output" id="output" aria-live="polite">等待输入需求后生成结果。</div>
          </section>
        </div>
      </main>

      <script>
        const promptInput = document.getElementById("prompt");
        const output = document.getElementById("output");
        const errorBox = document.getElementById("error");
        const submitButton = document.getElementById("submit");
        const clearButton = document.getElementById("clear");

        document.querySelectorAll("[data-example]").forEach((button) => {
          button.addEventListener("click", () => {
            promptInput.value = button.dataset.example;
            promptInput.focus();
          });
        });

        clearButton.addEventListener("click", () => {
          promptInput.value = "";
          output.textContent = "等待输入需求后生成结果。";
          errorBox.textContent = "";
          promptInput.focus();
        });

        submitButton.addEventListener("click", async () => {
          const content = promptInput.value.trim();
          if (!content) {
            errorBox.textContent = "请先输入开发需求。";
            promptInput.focus();
            return;
          }

          submitButton.disabled = true;
          submitButton.textContent = "生成中...";
          output.textContent = "准备提交任务...\n";
          errorBox.textContent = "";

          try {
            const response = await fetch("/v1/chat/completions/stream", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                messages: [{ role: "user", content }],
                stream: true
              })
            });

            if (!response.ok) {
              throw new Error("请求失败：" + response.status);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            const appendLine = (text) => {
              output.textContent += text + "\n";
              output.scrollTop = output.scrollHeight;
            };

            const handleEventBlock = (block) => {
              const eventLine = block.split("\n").find((line) => line.startsWith("event:"));
              const dataLines = block
                .split("\n")
                .filter((line) => line.startsWith("data:"))
                .map((line) => line.slice(5).trimStart());
              if (!dataLines.length) return;

              const eventName = eventLine ? eventLine.slice(6).trim() : "progress";
              const data = dataLines.join("\n");

              if (eventName === "result") {
                appendLine("\n生成完成，最终结果如下：\n");
                appendLine(JSON.parse(data));
              } else if (eventName === "error") {
                appendLine("\n生成失败。");
                errorBox.textContent = data;
              } else {
                appendLine("[" + new Date().toLocaleTimeString() + "] " + data);
              }
            };

            while (true) {
              const { value, done } = await reader.read();
              if (done) break;
              buffer += decoder.decode(value, { stream: true });

              const blocks = buffer.split("\n\n");
              buffer = blocks.pop();
              blocks.forEach(handleEventBlock);
            }

            if (buffer.trim()) {
              handleEventBlock(buffer);
            }
          } catch (error) {
            output.textContent = "生成失败。";
            errorBox.textContent = error.message || "请求过程中发生错误。";
          } finally {
            submitButton.disabled = false;
            submitButton.textContent = "生成代码";
          }
        });
      </script>
    </body>
    </html>
    """


@app.get("/health")
async def health():
    return {"status": "ok", "service": "自动写代码智能体"}


# POST请求接口，与大模型进行知识问答
@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    if not model:
        print("服务未初始化")
        raise HTTPException(
            status_code=500,
            detail="模型未初始化。请先在 PowerShell 中设置 OPENAI_CHAT_API_KEY，或把 MODEL_TYPE 改为 oneapi/ollama 并配置对应参数。"
        )
    try:
        # print(f"收到聊天完成请求: {request}")
        query_prompt = get_latest_user_content(request)
        formatted_response = await run_coding_crew(query_prompt)

        # 处理流式响应
        if request.stream:
            # 定义一个异步生成器函数，用于生成流式数据
            async def generate_stream():
                # 为每个流式数据片段生成一个唯一的chunk_id
                chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
                # 将格式化后的响应按行分割
                lines = formatted_response.split('\n')
                # 历每一行，并构建响应片段
                for i, line in enumerate(lines):
                    # 创建一个字典，表示流式数据的一个片段
                    chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        # "model": request.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": line + '\n'}, # if i > 0 else {"role": "assistant", "content": ""},
                                "finish_reason": None
                            }
                        ]
                    }
                    # 将片段转换为JSON格式并生成
                    yield f"{json.dumps(chunk)}\n"
                    # 每次生成数据后，异步等待0.5秒
                    await asyncio.sleep(0.5)
                # 生成最后一个片段，表示流式响应的结束
                final_chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }
                    ]
                }
                yield f"{json.dumps(final_chunk)}\n"

            # 返回fastapi.responses中StreamingResponse对象，流式传输数据
            # media_type设置为text/event-stream以符合SSE(Server-SentEvents) 格式
            return StreamingResponse(generate_stream(), media_type="text/event-stream")
        # 处理非流式响应处理
        else:
            response = ChatCompletionResponse(
                choices=[
                    ChatCompletionResponseChoice(
                        index=0,
                        message=Message(role="assistant", content=formatted_response),
                        finish_reason="stop"
                    )
                ]
            )
            # print(f"发送响应内容: \n{response}")
            # 返回fastapi.responses中JSONResponse对象
            # model_dump()方法通常用于将Pydantic模型实例的内容转换为一个标准的Python字典，以便进行序列化
            return JSONResponse(content=response.model_dump())

    except Exception as e:
        print(f"处理聊天完成时出错:\n\n {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/chat/completions/stream")
async def chat_completions_stream(request: ChatCompletionRequest):
    async def generate_progress():
        if not model:
            yield format_sse("error", "模型未初始化。请先在配置文件中填写 OPENAI_CHAT_API_KEY，或配置 oneapi/ollama。")
            return

        progress_queue = asyncio.Queue()
        start_time = time.time()
        stage_index = 0
        completed_tasks = 0

        try:
            query_prompt = get_latest_user_content(request)
        except HTTPException as exc:
            yield format_sse("error", exc.detail)
            return

        async def run_task():
            try:
                result = await run_coding_crew(query_prompt, progress_queue)
                await progress_queue.put({"type": "result", "content": result})
            except Exception as exc:
                await progress_queue.put({"type": "error", "content": str(exc)})

        task = asyncio.create_task(run_task())
        yield format_sse("progress", "已开始生成，页面会持续显示进度，请不要关闭窗口。")

        try:
            while True:
                try:
                    item = await asyncio.wait_for(progress_queue.get(), timeout=5)
                except asyncio.TimeoutError:
                    elapsed = int(time.time() - start_time)
                    yield format_sse("progress", progress_message(stage_index, elapsed))
                    continue

                if isinstance(item, dict) and item.get("type") == "result":
                    if completed_tasks >= len(PROGRESS_STAGES) - 1:
                        yield format_sse("progress", "阶段 3/3 已完成，正在整理最终结果...")
                    yield format_sse("result", json.dumps(item["content"], ensure_ascii=False))
                    break

                if isinstance(item, dict) and item.get("type") == "error":
                    yield format_sse("error", item["content"])
                    break

                message = str(item)
                if "一个任务已完成" in message:
                    completed_tasks += 1
                    if completed_tasks < len(PROGRESS_STAGES):
                        stage_index = completed_tasks
                        yield format_sse("progress", f"已完成阶段 {completed_tasks}/3，进入{progress_message(stage_index)}")
                    else:
                        yield format_sse("progress", "已完成全部执行阶段，正在整理最终结果...")
                else:
                    yield format_sse("progress", message)
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )



if __name__ == "__main__":
    print(f"在端口 {PORT} 上启动服务器")
    # uvicorn是一个用于运行ASGI应用的轻量级、超快速的ASGI服务器实现
    # 用于部署基于FastAPI框架的异步PythonWeb应用程序
    uvicorn.run(app, host="0.0.0.0", port=PORT)
