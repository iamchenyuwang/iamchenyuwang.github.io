#!/usr/bin/env python3
"""
gemini_classify.py — 用 Gemini 3 Flash Preview 批量分类论文。

用法:
    # 先试水 100 篇
    python3 -u scripts/gemini_classify.py --test 100

    # 全量跑
    python3 -u scripts/gemini_classify.py
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import threading
import time
from typing import Dict, Any, List

from google import genai

# ---------------------------------- 配置 ----------------------------------
API_KEY = "AIzaSyB_5i6Fi265r1mfwTbwk-_ykrKX7szAF74"
MODEL_ID = "gemini-2.0-flash"
INPUT_FILE = "_data/llm_hw_design_papers.json"
OUTPUT_FILE = "_data/classified_papers.json"

MAX_RETRY = 5
INITIAL_BACKOFF = 2  # 秒
CHECKPOINT_INTERVAL = 200  # 每 N 篇存盘一次

# ---------------------------------- Prompt ----------------------------------
SYSTEM_MSG = (
    "You are an expert research assistant. Your task is to classify academic papers based on their title and abstract.\n"
    "The goal is to identify if a paper's contribution is 'AI for Computer Systems'.\n\n"
    "A paper is 'AI for Computer Systems' (respond with 'true') if it applies AI/ML/LLM techniques to solve traditional problems in computer systems, software systems, architecture, or hardware engineering. Examples include using AI for:\n"
    "- Chip design (placement, routing, verification, EDA)\n"
    "- System-level optimization (scheduling, resource management, autoscaling)\n"
    "- Database and query optimization (learned indexes, cardinality estimation)\n"
    "- Networking (congestion control, traffic engineering, routing)\n"
    "- Compilers and code generation (instruction scheduling, register allocation)\n"
    "- Storage and memory systems (cache replacement, prefetching, KV stores)\n"
    "- Operating systems (memory management, I/O scheduling)\n"
    "- Hardware security (side-channel analysis, fault injection detection)\n\n"
    "A paper is NOT in this category (respond with 'false') if its primary focus is on 'Systems/Hardware for AI'. This includes:\n"
    "- Designing hardware accelerators for AI/ML models (e.g., custom ASICs, FPGAs for neural networks).\n"
    "- Proposing new neural network algorithms that are hardware-efficient.\n"
    "- Improving the performance of AI computations on a specific hardware platform.\n"
    "- Pure AI/ML methodology papers with no systems application.\n\n"
    "Respond with a single word: 'true' or 'false'."
)

# ---------------------------------- 全局状态 ----------------------------------
lock = threading.Lock()
processed_count = 0
true_count = 0
error_count = 0
start_time = None


def classify_one(client: genai.Client, item: Dict[str, Any]) -> None:
    """分类单篇论文，带重试和指数退避。"""
    global processed_count, true_count, error_count

    user_msg = (
        f"Title: {item['title']}\n"
        f"Abstract: {item['abstract']}\n\n"
        "Does this paper belong to the 'AI for Computer Systems' category (true/false)?"
    )

    for attempt in range(1, MAX_RETRY + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=user_msg,
                config={
                    "system_instruction": SYSTEM_MSG,
                    "temperature": 0.0,
                    "max_output_tokens": 5,
                },
            )
            text = response.text
            if text is None:
                # thinking 模型有时 text 为空，从 parts 取
                parts = response.candidates[0].content.parts if response.candidates else []
                text = next((p.text for p in parts if hasattr(p, 'text') and p.text), None)
            if text is None:
                raise ValueError("Empty response from model")
            ans = text.strip().lower()
            label = ans.startswith("t")
            item["ai_for_hw"] = label

            with lock:
                processed_count += 1
                if label:
                    true_count += 1
            return

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                # 限流：指数退避
                wait = INITIAL_BACKOFF * (2 ** (attempt - 1))
                if attempt < MAX_RETRY:
                    time.sleep(wait)
                    continue
            elif attempt < MAX_RETRY:
                time.sleep(INITIAL_BACKOFF)
                continue

            # 重试耗尽
            item["ai_for_hw"] = None
            with lock:
                processed_count += 1
                error_count += 1
            print(f"  ❌ 重试耗尽: {item['title'][:60]}... | {e}", file=sys.stderr)
            return


def checkpoint_save(data: List[Dict], path: str) -> None:
    """安全存盘"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.rename(tmp, path)


def progress_reporter(total: int, stop_event: threading.Event) -> None:
    """每 10 秒打印进度"""
    while not stop_event.wait(10):
        with lock:
            done = processed_count
            pos = true_count
            errs = error_count
        elapsed = time.time() - start_time
        speed = done / elapsed if elapsed > 0 else 0
        remaining = (total - done) / speed / 60 if speed > 0 else 0
        print(
            f"  进度: {done}/{total} ({done*100//total}%) | "
            f"true: {pos} | errors: {errs} | "
            f"速度: {speed:.1f} 篇/s | "
            f"剩余: {remaining:.1f} 分钟"
        )


def main():
    global start_time

    parser = argparse.ArgumentParser(description="Gemini 批量分类论文")
    parser.add_argument("--input", default=INPUT_FILE)
    parser.add_argument("--output", default=OUTPUT_FILE)
    parser.add_argument("--jobs", "-j", type=int, default=10)
    parser.add_argument("--test", type=int, default=0,
                        help="仅测试前 N 篇（0=全量）")
    args = parser.parse_args()

    # 加载数据
    with open(args.input, "r", encoding="utf-8") as f:
        all_papers = json.load(f)

    # 加载已有结果（断点续传），合并回 all_papers
    if os.path.isfile(args.output):
        with open(args.output, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_map = {p["url"]: p["ai_for_hw"] for p in existing if p.get("ai_for_hw") is not None}
        merged = 0
        for p in all_papers:
            if p["url"] in existing_map:
                p["ai_for_hw"] = existing_map[p["url"]]
                merged += 1
        print(f"从已有结果恢复: {merged} 篇")

    # 筛选需要处理的（没有 ai_for_hw 或为 None 的）
    to_process = [p for p in all_papers if p.get("ai_for_hw") is None]
    if args.test > 0:
        to_process = to_process[:args.test]

    total = len(to_process)
    print(f"待分类: {total} 篇 | 并发: {args.jobs} | 模型: {MODEL_ID}")
    if total == 0:
        print("无需处理。")
        return

    client = genai.Client(api_key=API_KEY)
    start_time = time.time()

    # 启动进度线程
    stop_event = threading.Event()
    reporter = threading.Thread(target=progress_reporter, args=(total, stop_event), daemon=True)
    reporter.start()

    # 并发处理 + 定期存盘
    last_checkpoint = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(classify_one, client, p): p for p in to_process}
        for future in concurrent.futures.as_completed(futures):
            future.result()  # 触发异常（如果有的话）

            with lock:
                current = processed_count
            if current - last_checkpoint >= CHECKPOINT_INTERVAL:
                last_checkpoint = current
                checkpoint_save(all_papers, args.output)
                print(f"  💾 存盘 ({current}/{total})")

    stop_event.set()
    elapsed = time.time() - start_time

    # 最终存盘
    checkpoint_save(all_papers, args.output)

    # 汇总
    final_true = sum(1 for p in all_papers if p.get("ai_for_hw") is True)
    final_false = sum(1 for p in all_papers if p.get("ai_for_hw") is False)
    final_none = sum(1 for p in all_papers if p.get("ai_for_hw") is None)
    print("=" * 60)
    print(f"完成! 耗时 {elapsed/60:.1f} 分钟")
    print(f"  AI for Systems (true):  {final_true}")
    print(f"  Not relevant (false):   {final_false}")
    print(f"  Errors (null):          {final_none}")
    print(f"  总计:                   {len(all_papers)}")
    print(f"结果已保存: {args.output}")


if __name__ == "__main__":
    main()
