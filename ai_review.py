import csv
import os
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== 可配置参数（请直接在此修改）====================
API_KEY = "a576532cf22f48419b28df56f2274724.VaRwoaTiiddwSszv"  # 请替换为你的智谱 API 密钥
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4-flash-250414"

MAX_RETRIES = 5          # 单次请求最大重试次数
RETRY_DELAY = 5          # 重试基础等待时间（秒）

# 审阅配置
TOTAL_REVIEWS = 5        # 每个文件的总审阅次数
CONCURRENT_REVIEWS = 5   # 每轮并发审阅数
ROW_LIMIT = None         # 每个文件读取的最大行数（不含表头），None表示不限制

# 总结配置
GENERATE_SUMMARY = True  # 是否生成总结报告
SUMMARY_TEMPERATURE = 0.3

# 预期的输入 CSV 表头（已包含难度评分）
EXPECTED_HEADER = ["单词", "出现次数", "排名", "占比(%)", "难度评分"]
# ================================================================

report_lock = threading.Lock()


def check_csv_header(file_path):
    """检查 CSV 文件的第一行是否符合预期表头"""
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader)
            return header == EXPECTED_HEADER
    except Exception as e:
        print(f"检查文件 {file_path} 表头时出错: {e}")
        return False


def read_full_csv_as_text(file_path, limit=None):
    """读取 CSV 内容，返回格式化的文本"""
    lines = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        lines.append("单词,出现次数,排名,占比(%),难度评分")
        count = 0
        for row in reader:
            lines.append(f"{row['单词']},{row['出现次数']},{row['排名']},{row['占比(%)']},{row['难度评分']}")
            count += 1
            if limit and count >= limit:
                break
    return "\n".join(lines)


def single_review(csv_content, file_name, review_index):
    """单次审阅请求，返回 (review_index, result_text)"""
    prompt = f"""你是一位英语词汇教学专家。以下是一个 CSV 文件的内容，包含英文单词及其出现次数、排名、占比和已有的难度评分（1-10 分，10 分最难）（难度评分和出现次数无关！！！）。

请审阅这些难度评分是否合理。你需要：
1. 整体评估评分质量，指出明显不合理之处（如简单词评分过高或生僻词评分过低）。
2. 列出所有（至少 5 个）你认为评分不合理的单词，给出你的建议评分和理由。
3. 如果整体质量较好，也请说明。

文件名称：{file_name}
CSV 内容：
{csv_content}

请用中文回复，条理清晰。"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是一个严谨的英语词汇评分审阅专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  [审阅 {review_index}] 发送请求 (尝试 {attempt})...")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"].strip()
                print(f"  [审阅 {review_index}] 完成")
                return review_index, content
            else:
                print(f"  [审阅 {review_index}] API 返回异常: {result}")
                raise ValueError("Invalid API response structure")

        except requests.exceptions.RequestException as e:
            print(f"  [审阅 {review_index}] 请求失败 (尝试 {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                wait_time = RETRY_DELAY * attempt
                print(f"  [审阅 {review_index}] {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"  [审阅 {review_index}] 已达最大重试次数，审阅失败")
                return review_index, None
        except Exception as e:
            print(f"  [审阅 {review_index}] 未知错误: {e}")
            break

    return review_index, None


def multi_review(csv_content, file_name):
    """对同一文件进行多次审阅，返回合并报告文本（不含总结）"""
    total = TOTAL_REVIEWS
    concurrent = CONCURRENT_REVIEWS
    print(f"  将对文件进行 {total} 次独立审阅，每轮并发 {concurrent} 个请求")

    results = {}
    review_indices = list(range(1, total + 1))
    processed = 0

    while processed < total:
        round_count = min(concurrent, total - processed)
        round_indices = review_indices[processed:processed + round_count]

        print(f"\n  ----- 第 {processed//concurrent + 1} 轮并发审阅，共 {round_count} 个请求 -----")
        with ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = {}
            for idx in round_indices:
                future = executor.submit(single_review, csv_content, file_name, idx)
                futures[future] = idx
                print(f"    [审阅 {idx}] 已提交")

            for future in as_completed(futures):
                idx, result = future.result()
                if result:
                    results[idx] = result
                else:
                    results[idx] = f"[审阅 {idx} 失败，无结果]"

        processed += round_count
        if processed < total:
            print(f"  等待 2 秒后开始下一轮...")
            time.sleep(2)

    # 合并报告
    merged_report = []
    merged_report.append(f"文件：{file_name}")
    merged_report.append(f"总审阅次数：{total}")
    merged_report.append("=" * 60)
    for idx in sorted(results.keys()):
        merged_report.append(f"\n--- 第 {idx} 次审阅 ---\n")
        merged_report.append(results[idx])
        merged_report.append("\n")
    merged_report.append("=" * 60)

    return "\n".join(merged_report), results


def generate_summary_report(merged_report_text, file_name):
    """调用 AI 对合并后的审阅报告进行总结"""
    if not GENERATE_SUMMARY:
        return None

    print("\n  正在生成总结报告...")
    prompt = f"""你是一位英语教学专家。以下是针对文件 {file_name} 的多位评审员给出的审阅意见汇总。

请仔细阅读所有审阅内容，然后撰写一份精炼的总结报告，包含以下部分：
1. 总体评价：评分质量如何？是否存在系统性偏差（如整体偏高/偏低）？
2. 共识与争议：评审员们达成共识的地方有哪些？存在哪些主要分歧？
3. 所有问题单词：列举所有被评审员提及的评分不合理的单词，并给出原始评分，每个评审员的评分和综合建议评分。
4. 改进建议。

请用中文回答，保持客观、清晰。

审阅内容汇总：
{merged_report_text}"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是一个擅长提炼总结的英语教学专家。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": SUMMARY_TEMPERATURE
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  [总结] 发送请求 (尝试 {attempt})...")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"].strip()
                print(f"  [总结] 完成")
                return content
            else:
                raise ValueError("Invalid API response structure")

        except Exception as e:
            print(f"  [总结] 失败 (尝试 {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)
            else:
                return None

    return None


def save_review_report(file_path, final_report):
    """将最终报告保存为 TXT 文件"""
    base_name = os.path.splitext(file_path)[0]
    report_file = f"{base_name}_review.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(final_report)
    print(f"  审阅报告已保存至: {report_file}")


def process_single_file(file_path):
    """处理单个 CSV 文件"""
    print(f"\n{'='*50}")
    print(f"开始审阅文件: {file_path}")
    print(f"{'='*50}")

    # 读取 CSV 内容
    print("  正在读取 CSV 内容...")
    csv_content = read_full_csv_as_text(file_path, limit=ROW_LIMIT)
    line_count = csv_content.count('\n')
    print(f"  已读取 {line_count} 行数据（含表头）")

    # 进行多次审阅
    merged_report, _ = multi_review(csv_content, os.path.basename(file_path))

    # 生成总结
    summary = None
    if GENERATE_SUMMARY:
        summary = generate_summary_report(merged_report, os.path.basename(file_path))
        if summary:
            final_report = f"==================== 总结报告 ====================\n\n{summary}\n\n==================== 详细审阅记录 ====================\n\n{merged_report}"
        else:
            final_report = f"[总结生成失败]\n\n{merged_report}"
    else:
        final_report = merged_report

    # 保存报告
    save_review_report(file_path, final_report)

    # 预览
    preview_len = 800
    print("\n--- 最终报告预览（前800字符）---")
    print(final_report[:preview_len] + "..." if len(final_report) > preview_len else final_report)
    print("----------------------------------")


def main():
    print("正在扫描当前目录下的 CSV 文件...")
    current_dir = "."
    csv_files = [f for f in os.listdir(current_dir) if f.lower().endswith(".csv")]

    if not csv_files:
        print("未找到 CSV 文件。")
        return

    valid_files = []
    for f in csv_files:
        if check_csv_header(f):
            valid_files.append(f)
        else:
            print(f"跳过文件 {f}：表头不符合预期 {EXPECTED_HEADER}")

    if not valid_files:
        print("没有符合要求的 CSV 文件（需要包含难度评分列）。")
        return

    print(f"找到 {len(valid_files)} 个符合要求的文件：")
    for f in valid_files:
        print(f"  - {f}")

    for f in valid_files:
        process_single_file(f)
        time.sleep(2)


if __name__ == "__main__":
    main()