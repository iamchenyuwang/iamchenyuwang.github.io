#!/usr/bin/env python3
"""
gemini_tag.py — 用 Gemini 2.0 Flash 给已分类论文打标签 (4类)。
只处理 ai_for_hw=true 的论文。

用法:
    python3 -u scripts/gemini_tag.py
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
INPUT_FILE = "_data/classified_papers.json"
OUTPUT_FILE = "_data/survey_tagged_papers.json"

MAX_RETRY = 5
INITIAL_BACKOFF = 2
CHECKPOINT_INTERVAL = 200

VALID_TAGS = [
    "AI for Software Systems",
    "AI for Hardware Design",
    "AI for Physical/Chip Design",
    "Other",
]

# ---------------------------------- Prompt ----------------------------------
SYSTEM_MSG = (
    "You are an expert research assistant specializing in computer systems and hardware. "
    "Your task is to assign exactly ONE category tag to academic papers based on their title and abstract.\n\n"
    "The paper is known to be in the 'AI for Computer Systems' domain. Choose the single best-fitting tag from the following list.\n"
    f"Available tags: `{'`, `'.join(VALID_TAGS)}`\n\n"
    "Here are explanations for each tag:\n"
    "- **AI for Software Systems**: Using AI/ML to improve software-layer systems — scheduling, resource management, databases, query optimization, "
    "learned indexes, networking, congestion control, traffic engineering, compilers, code optimization, storage systems, KV stores, "
    "operating systems, memory management, caching, prefetching, distributed systems, consensus, cloud/cluster orchestration.\n"
    "- **AI for Hardware Design**: Using AI/ML for RTL/logic-level hardware design — HDL/Verilog/VHDL code generation, "
    "logic synthesis, design verification, testbench generation, EDA tool automation, design space exploration, hardware security.\n"
    "- **AI for Physical/Chip Design**: Using AI/ML for physical design and analog — placement, routing, floorplanning, "
    "timing closure, analog circuit sizing, power management, DVFS optimization, chip-level layout.\n"
    "- **Other**: If the paper does not clearly fit the above three categories.\n\n"
    "--- EXAMPLE 1 ---\n"
    'Title: "Reinforcement Learning for Cluster Job Scheduling with Tail-Latency SLA"\n'
    'Abstract: "We propose an RL-based scheduler that allocates cluster resources to minimize tail latency while respecting job priorities and SLAs."\n'
    "Correct Answer: AI for Software Systems\n\n"
    "--- EXAMPLE 2 ---\n"
    'Title: "LLM-Assisted Verilog Generation for RISC-V Processor Design"\n'
    'Abstract: "We use a large language model to generate synthesizable Verilog modules for a RISC-V core, reducing design time by 3x."\n'
    "Correct Answer: AI for Hardware Design\n\n"
    "--- EXAMPLE 3 ---\n"
    'Title: "Deep Reinforcement Learning for VLSI Macro Placement"\n'
    'Abstract: "We apply deep RL to optimize macro placement in VLSI physical design, achieving better wirelength and timing closure."\n'
    "Correct Answer: AI for Physical/Chip Design\n"
    "--- END OF EXAMPLES ---\n\n"
    "Now, classify the following paper. Respond with exactly one tag from the list, nothing else."
)

# ---------------------------------- 全局状态 ----------------------------------
lock = threading.Lock()
processed_count = 0
error_count = 0
tag_counts = {t: 0 for t in VALID_TAGS}
start_time = None


def tag_one(client: genai.Client, item: Dict[str, Any]) -> None:
    """给单篇论文打标签，带重试和指数退避。"""
    global processed_count, error_count

    user_msg = (
        f"Title: {item['title']}\n"
        f"Abstract: {item['abstract']}\n\n"
        "What is the most appropriate tag for this paper? (exactly one tag)"
    )

    for attempt in range(1, MAX_RETRY + 1):
        try:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=user_msg,
                config={
                    "system_instruction": SYSTEM_MSG,
                    "temperature": 0.0,
                    "max_output_tokens": 20,
                },
            )
            text = response.text
            if text is None:
                parts = response.candidates[0].content.parts if response.candidates else []
                text = next((p.text for p in parts if hasattr(p, 'text') and p.text), None)
            if text is None:
                raise ValueError("Empty response from model")

            # 匹配最佳标签
            ans = text.strip()
            matched_tag = None
            for valid_tag in VALID_TAGS:
                if valid_tag.lower() in ans.lower():
                    matched_tag = valid_tag
                    break
            if not matched_tag:
                matched_tag = "Other"

            item["tags"] = [matched_tag]

            with lock:
                processed_count += 1
                tag_counts[matched_tag] = tag_counts.get(matched_tag, 0) + 1
            return

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait = INITIAL_BACKOFF * (2 ** (attempt - 1))
                if attempt < MAX_RETRY:
                    time.sleep(wait)
                    continue
            elif attempt < MAX_RETRY:
                time.sleep(INITIAL_BACKOFF)
                continue

            item["tags"] = ["Other"]
            with lock:
                processed_count += 1
                error_count += 1
            print(f"  ❌ 重试耗尽: {item['title'][:60]}... | {e}", file=sys.stderr)
            return


def checkpoint_save(data: List[Dict], path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.rename(tmp, path)


def progress_reporter(total: int, stop_event: threading.Event) -> None:
    while not stop_event.wait(10):
        with lock:
            done = processed_count
            errs = error_count
            counts = dict(tag_counts)
        elapsed = time.time() - start_time
        speed = done / elapsed if elapsed > 0 else 0
        remaining = (total - done) / speed / 60 if speed > 0 else 0
        dist = " | ".join(f"{k}: {v}" for k, v in counts.items() if v > 0)
        print(
            f"  进度: {done}/{total} ({done*100//total}%) | "
            f"errors: {errs} | "
            f"速度: {speed:.1f} 篇/s | "
            f"剩余: {remaining:.1f} 分钟 | {dist}"
        )


def main():
    global start_time

    parser = argparse.ArgumentParser(description="Gemini 批量打标签")
    parser.add_argument("--input", default=INPUT_FILE)
    parser.add_argument("--output", default=OUTPUT_FILE)
    parser.add_argument("--jobs", "-j", type=int, default=10)
    args = parser.parse_args()

    # 加载已分类数据
    with open(args.input, "r", encoding="utf-8") as f:
        all_papers = json.load(f)

    # 只处理 ai_for_hw=true 的论文
    positive_papers = [p for p in all_papers if p.get("ai_for_hw") is True]
    print(f"AI for Systems 论文: {len(positive_papers)} 篇")

    # 加载已有标签结果（断点续传）
    if os.path.isfile(args.output):
        with open(args.output, "r", encoding="utf-8") as f:
            existing = json.load(f)
        existing_map = {p["url"]: p["tags"] for p in existing if p.get("tags")}
        merged = 0
        for p in positive_papers:
            if p["url"] in existing_map:
                p["tags"] = existing_map[p["url"]]
                merged += 1
        print(f"从已有结果恢复: {merged} 篇")

    # 筛选需要处理的
    to_process = [p for p in positive_papers if not p.get("tags")]
    total = len(to_process)
    print(f"待打标签: {total} 篇 | 并发: {args.jobs} | 模型: {MODEL_ID}")

    if total == 0:
        print("无需处理。")
    else:
        client = genai.Client(api_key=API_KEY)
        start_time = time.time()

        stop_event = threading.Event()
        reporter = threading.Thread(target=progress_reporter, args=(total, stop_event), daemon=True)
        reporter.start()

        last_checkpoint = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {executor.submit(tag_one, client, p): p for p in to_process}
            for future in concurrent.futures.as_completed(futures):
                future.result()
                with lock:
                    current = processed_count
                if current - last_checkpoint >= CHECKPOINT_INTERVAL:
                    last_checkpoint = current
                    checkpoint_save(positive_papers, args.output)
                    print(f"  💾 存盘 ({current}/{total})")

        stop_event.set()
        elapsed = time.time() - start_time
        print(f"\n标签完成! 耗时 {elapsed/60:.1f} 分钟")

    # 最终存盘
    checkpoint_save(positive_papers, args.output)

    # 汇总
    final_counts = {}
    for p in positive_papers:
        for t in p.get("tags", ["Other"]):
            final_counts[t] = final_counts.get(t, 0) + 1

    print("=" * 60)
    print(f"总计: {len(positive_papers)} 篇")
    for tag in VALID_TAGS:
        print(f"  {tag}: {final_counts.get(tag, 0)}")
    print(f"结果已保存: {args.output}")


if __name__ == "__main__":
    main()
