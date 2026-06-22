# 自动写代码智能体

该子项目用于自动写代码。系统通过多个智能体分工完成需求分析、代码生成、代码审查和最终交付说明，适合生成 Python 脚本、自动化工具、课程作业示例和小型功能模块。

## 运行

```powershell
pip install -r requirements.txt
$env:OPENAI_CHAT_API_KEY="你的聊天模型 Key"
python main.py
```

示例需求：

```text
请写一个 Python 脚本，读取 Excel 学生成绩表，计算总分和平均分，并输出排名结果。
```

更多统一说明见项目根目录 `README.md`。
