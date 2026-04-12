import csv
import json
import os
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== 可配置参数 ====================
API_KEY = "key"  # 请替换为你的智谱 API 密钥
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4-flash-250414"

BATCH_SIZE = 50          # 每批处理的单词数量
MAX_WORKERS = 5          # 最大并发请求数
MAX_RETRIES = 3          # 最大重试次数
RETRY_DELAY = 5          # 重试基础等待时间（秒）
REQUEST_INTERVAL = 1   # 提交任务的间隔

# 难度评分范围（禁止修改）
MIN_SCORE = 1
MAX_SCORE = 10

# 预期的 CSV 表头
EXPECTED_HEADER = ["单词", "出现次数", "排名", "占比(%)"]

# 全局分类结果（线程安全更新）
progress_lock = threading.Lock()
classification = {}


# ==================== 工具函数 ====================

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


def read_words_from_csv(file_path):
    """
    从 CSV 文件中读取完整单词信息（无数量限制）。
    返回列表，每个元素为字典：{'word': str, 'count': int, 'rank': int, 'percent': str}
    """
    words = []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                word_info = {
                    'word': row["单词"].strip(),
                    'count': int(row["出现次数"].strip()),
                    'rank': int(row["排名"].strip()),
                    'percent': row["占比(%)"].strip()
                }
                words.append(word_info)
            except (ValueError, KeyError) as e:
                print(f"  警告: 跳过无效行 {row}: {e}")
                continue
    return words


def classify_words_batch(batch_id, word_list):
    """
    通过智谱 API 对一批单词进行难度评分（1-10，10最难），支持自动重试。
    返回解析后的字典 {word: score}，失败时单词评分为 0。
    """
    word_names = [info['word'] for info in word_list]
    word_str = "\n".join([f"- {w}" for w in word_names])
    prompt = f"""你是一位专业的英语教学专家。请为以下英文单词标注难度评分，范围是 1 到 10，10 分表示最难（非常生僻、专业或抽象），1 分表示最简单（基础日常词汇）。
只返回每个单词对应的评分，格式为：单词: 评分
如果某个单词为专有名词，错误词等有问题的词汇，请将其标记为0分
不要添加任何解释、序号或额外文字。

单词列表：
{word_str}"""

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是一个精确的英语词汇评分助手，只输出 1-10 的整数评分。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"    [批次 {batch_id}] 发送请求 (尝试 {attempt})...")
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"].strip()
                print(f"    [批次 {batch_id}] 接收响应成功 (尝试 {attempt})")
                parsed = parse_ai_response(content, word_names)
                for w in word_names:
                    if w.lower() not in parsed:
                        parsed[w.lower()] = 0
                print(f"    [批次 {batch_id}] 解析完成，获得 {len(parsed)} 个评分")
                return parsed
            else:
                print(f"    [批次 {batch_id}] API 返回异常: {result}")
                raise ValueError("Invalid API response structure")

        except requests.exceptions.RequestException as e:
            print(f"    [批次 {batch_id}] 请求失败 (尝试 {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                wait_time = RETRY_DELAY * attempt
                print(f"    [批次 {batch_id}] {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"    [批次 {batch_id}] 已达最大重试次数，标记评分为 0")
        except Exception as e:
            print(f"    [批次 {batch_id}] 未知错误: {e}")
            break

    failed_result = {}
    for w in word_names:
        failed_result[w.lower()] = 0
    return failed_result


def parse_ai_response(response_text, expected_words):
    """解析 AI 返回的文本，提取单词和评分（1-10 整数）"""
    result = {}
    if not response_text:
        return result

    lines = response_text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            parts = line.split(":", 1)
        elif " - " in line:
            parts = line.split(" - ", 1)
        elif " " in line:
            parts = line.split(" ", 1)
        else:
            continue

        word = parts[0].strip().lower()
        score_str = parts[1].strip()
        try:
            score = int(''.join(filter(str.isdigit, score_str)))
            if MIN_SCORE <= score <= MAX_SCORE:
                result[word] = score
        except ValueError:
            continue
    return result


def save_results_to_csv(words_info, classification_dict, output_path):
    """保存结果到 CSV，按评分降序、次数降序排序"""
    for info in words_info:
        info['score'] = classification_dict.get(info['word'].lower(), 0)

    sorted_words = sorted(words_info, key=lambda x: (-x['score'], -x['count']))

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["单词", "出现次数", "排名", "占比(%)", "难度评分"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in sorted_words:
            writer.writerow({
                "单词": item['word'],
                "出现次数": item['count'],
                "排名": item['rank'],
                "占比(%)": item['percent'],
                "难度评分": item['score']
            })
    print(f"  结果已保存至: {output_path}")


def save_progress(classification_dict, progress_file):
    """保存当前进度到 JSON 文件"""
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(classification_dict, f, ensure_ascii=False, indent=2)


def load_progress(progress_file):
    """加载之前的进度"""
    try:
        with open(progress_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def update_classification(batch_result):
    """线程安全地更新全局分类字典"""
    with progress_lock:
        classification.update(batch_result)


def process_single_file(input_path):
    """处理单个 CSV 文件"""
    global classification
    classification = {}

    base_name = os.path.splitext(input_path)[0]
    output_file = f"{base_name}_p.csv"
    progress_file = f"{base_name}_temp.json"

    print(f"\n{'='*50}")
    print(f"开始处理文件: {input_path}")
    print(f"输出文件: {output_file}")
    print(f"进度文件: {progress_file}")
    print(f"{'='*50}")

    # 读取全部单词
    all_words_info = read_words_from_csv(input_path)
    total = len(all_words_info)
    if total == 0:
        print("  文件中没有有效单词，跳过。")
        return
    print(f"  共读取 {total} 个单词")

    # 加载之前进度
    classification = load_progress(progress_file)
    processed_count = len(classification)
    if processed_count > 0:
        print(f"  从进度文件恢复了 {processed_count} 个已处理单词")

    # 过滤未处理的单词
    remaining_words_info = [info for info in all_words_info if info['word'].lower() not in classification]
    remaining_count = len(remaining_words_info)
    if remaining_count == 0:
        print("  所有单词已处理完成，直接生成输出文件。")
        save_results_to_csv(all_words_info, classification, output_file)
        return

    print(f"  剩余待处理: {remaining_count} 个单词")

    # 拆分为批次
    batches = []
    for i in range(0, remaining_count, BATCH_SIZE):
        batch_info = remaining_words_info[i:i + BATCH_SIZE]
        batches.append(batch_info)

    total_batches = len(batches)
    print(f"  共分为 {total_batches} 个批次，每批最多 {BATCH_SIZE} 个单词")

    # 分批并发执行
    batch_index = 0
    round_num = 1
    while batch_index < total_batches:
        round_batches = min(MAX_WORKERS, total_batches - batch_index)
        print(f"\n  ----- 第 {round_num} 轮并发，共 {round_batches} 个批次 -----")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            for i in range(round_batches):
                batch_id = batch_index + i + 1
                batch = batches[batch_index + i]
                future = executor.submit(classify_words_batch, batch_id, batch)
                futures[future] = batch_id
                print(f"    [批次 {batch_id}] 已提交，单词数: {len(batch)}")
                time.sleep(REQUEST_INTERVAL)

            for future in as_completed(futures):
                batch_id = futures[future]
                try:
                    result = future.result()
                    update_classification(result)
                except Exception as e:
                    print(f"    [批次 {batch_id}] 处理异常: {e}")
                    failed_result = {}
                    for info in batches[batch_id - 1]:
                        failed_result[info['word'].lower()] = 0
                    update_classification(failed_result)

        # 本轮完成，保存进度
        save_progress(classification, progress_file)
        print(f"  本轮完成，进度已保存，总体进度: {len(classification)}/{total}")

        batch_index += round_batches
        round_num += 1

        if batch_index < total_batches:
            print(f"  等待 2 秒后开始下一轮...")
            time.sleep(2)

    # 所有批次完成，保存最终结果
    save_results_to_csv(all_words_info, classification, output_file)

    # 统计信息
    score_counts = {i: 0 for i in range(0, 11)}
    for score in classification.values():
        score_counts[score] = score_counts.get(score, 0) + 1

    print("\n  处理完成！评分分布：")
    for score in range(10, 0, -1):
        count = score_counts[score]
        if count > 0:
            print(f"    难度 {score}: {count} 个")
    if score_counts[0] > 0:
        print(f"    未知(0): {score_counts[0]} 个")


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
        print("没有符合要求的 CSV 文件。")
        return

    print(f"找到 {len(valid_files)} 个符合要求的文件：")
    for f in valid_files:
        print(f"  - {f}")

    for f in valid_files:
        process_single_file(f)


if __name__ == "__main__":
    main()