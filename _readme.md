# vocal-vocab-scorer
VOCAL  VOCAL's Optimal Cognitive Assessment for Lexicon  （VOCAL 词汇认知最优评估系统）
VOCAL

VOCAL's Optimal Cognitive Assessment for Lexicon

（VOCAL 词汇认知最优评估系统）
# 📚 VOCAL

一个基于大模型的英语单词难度评分工具，支持批量处理、多线程并发、断点续传，并提供独立的审阅脚本来评估评分质量。

## ✨ 功能特点

- 🔍 **自动词频分析**：读取包含单词、出现次数、排名的 CSV 文件。
- 🤖 **AI 难度评分**：调用智谱 AI（GLM-4）为每个单词打出 1~10 分的难度评分（10 分最难）。
- ⚡ **高效并发**：支持多线程分批处理，可自定义并发数和批次大小。
- 💾 **断点续传**：自动保存进度到 JSON 文件，中断后可继续处理。
- 📊 **结果排序输出**：按评分从高到低、同分按词频从高到低排序，输出 CSV。
- 🧐 **独立审阅脚本**：对已评分的 CSV 进行多次独立审阅，并自动生成总结报告。

## 📦 依赖安装

本项目仅需 Python 3.6+ 及以下第三方库：

```bash
pip install requests
```

⚙️ 配置说明

在使用前，请修改脚本开头的配置项（ai.py 和 ai_review.py）：

```python
API_KEY = "你的智谱 API 密钥"
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4-flash-250414"  # 可根据需要更换模型

# 处理参数
BATCH_SIZE = 30          # 每批处理的单词数
MAX_WORKERS = 4          # 最大并发请求数
MAX_RETRIES = 3          # 最大重试次数
```

🔐 建议将 API Key 设置为环境变量，避免直接硬编码在脚本中。

🚀 使用方法
0.使用main.py分析试卷
1️⃣ 单词难度评分

将待评分的词频 CSV 文件放置于脚本同目录下，确保表头为：

```
单词,出现次数,排名,占比(%)
```

运行评分脚本：

```bash
python ai.py
```

脚本会自动扫描目录下所有符合表头的 CSV 文件，逐个进行处理，输出 原文件名_p.csv 和进度文件 原文件名_temp.json。

输出示例（_p.csv）：

单词 出现次数 排名 占比(%) 难度评分
you 127 1 3.24 1
he 58 2 1.48 1
... ... ... ... ...

2️⃣ 审阅评分合理性

当获得 _p.csv 文件后，可使用审阅脚本进行质量评估：

```bash
python ai_review.py
```

脚本会读取所有带有难度评分列的 CSV 文件，对每个文件进行多次独立审阅（默认 3 次），最后合并并生成一份总结报告，保存为 原文件名_review.txt。

可在脚本顶部调整审阅参数：

```python
TOTAL_REVIEWS = 3        # 总审阅次数
CONCURRENT_REVIEWS = 2   # 并发审阅数
ROW_LIMIT = None         # 限制读取行数，避免超 token
```

📂 文件说明

文件 作用
ai.py 核心评分脚本，读取词频 CSV 并调用 AI 打分
ai_review.py 审阅脚本，对已完成评分的 CSV 进行合理性审查
main.py 对已经转换为txt的试卷分析词频
word_frequency_full.csv 示例词频数据
top_100_words.txt 处理后的前 100 个单词结果示例

⚠️ 注意事项

· API 费用：调用智谱 AI 会产生费用，请留意账户余额。
· 速率限制：若遇到 429 Too Many Requests 错误，请适当增加 SLEEP_TIME 或降低 MAX_WORKERS。
· Token 长度：审阅脚本若读取过多行可能导致超 token 限制，可通过 ROW_LIMIT 限制行数。
· 环境变量：出于安全考虑，建议将 API Key 存储在环境变量中，而非明文写在代码里。
