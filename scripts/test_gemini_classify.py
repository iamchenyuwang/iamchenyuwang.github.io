#!/usr/bin/env python3
"""
test_gemini_classify.py — 测试用 Gemini 3 Flash Preview 分类论文。
仅测试用途，不修改原有工作流。

用法:
    python3 scripts/test_gemini_classify.py
"""

import json
import time

from google import genai

# ---------------------------------- 配置 ----------------------------------
API_KEY = "AIzaSyB_5i6Fi265r1mfwTbwk-_ykrKX7szAF74"
MODEL_ID = "gemini-3-flash-preview"
INPUT_FILE = "_data/llm_hw_design_papers.json"
OUTPUT_FILE = "/tmp/gemini_classify_test.json"
TEST_COUNT = 20  # 测试前 20 篇

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


def classify_one(client, title, abstract):
    """调用 Gemini 分类单篇论文，返回 (bool, latency_sec)"""
    user_msg = (
        f"Title: {title}\n"
        f"Abstract: {abstract}\n\n"
        "Does this paper belong to the 'AI for Computer Systems' category (true/false)?"
    )

    t0 = time.time()
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=user_msg,
        config={
            "system_instruction": SYSTEM_MSG,
            "temperature": 0.0,
            "max_output_tokens": 5,
        },
    )
    latency = time.time() - t0
    ans = response.text.strip().lower()
    label = ans.startswith("t")
    return label, latency


def main():
    # 加载数据
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        papers = json.load(f)

    # 取前 TEST_COUNT 篇（最新的论文）
    test_papers = papers[:TEST_COUNT]
    print(f"测试 {len(test_papers)} 篇论文，模型: {MODEL_ID}")
    print("=" * 60)

    client = genai.Client(api_key=API_KEY)

    results = []
    total_latency = 0
    true_count = 0

    for i, p in enumerate(test_papers):
        try:
            label, latency = classify_one(client, p["title"], p["abstract"])
            total_latency += latency
            if label:
                true_count += 1
            results.append({
                "title": p["title"],
                "url": p["url"],
                "ai_for_hw": label,
                "latency_sec": round(latency, 2),
            })
            tag = "TRUE " if label else "false"
            print(f"  [{i+1:2d}/{TEST_COUNT}] {latency:.2f}s  {tag}  {p['title'][:70]}")
        except Exception as e:
            print(f"  [{i+1:2d}/{TEST_COUNT}] ERROR: {e}")
            results.append({
                "title": p["title"],
                "url": p["url"],
                "error": str(e),
            })

    # 汇总
    print("=" * 60)
    avg = total_latency / len(results) if results else 0
    print(f"完成: {len(results)} 篇")
    print(f"AI for Systems: {true_count}/{len(results)}")
    print(f"平均延迟: {avg:.2f}s/篇")
    print(f"预估 12085 篇耗时: {12085 * avg / 60:.0f} 分钟")

    # 保存测试结果
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"测试结果已保存: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
