#!/usr/bin/env python3
"""
arxiv_manager_min.py — 维护 "AI for Computer Systems" 相关论文的 JSON 清单。

用法
-----
# 第一次拉取全部结果（会覆盖旧 JSON）
python arxiv_manager_min.py --mode 0 --max-results 5000

# 之后按需增量更新（只追加新论文）
python arxiv_manager_min.py --mode 1

可选参数
--------
--output FILE      输出 JSON 路径（默认为 llm_hw_design_papers.json）
--query  STRING    自定义检索词
--max-results N    最多检索条数（默认 5000）

依赖
----
pip install arxiv>=2.0.0
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone

# 需要 arxiv 2.x
import arxiv
# 当 arXiv API 某一分页意外为空时会抛出此异常
from arxiv import UnexpectedEmptyPageError

# --------- arXiv 关键词配置 ---------
# A 组：按 arXiv 分类号 × ML 关键词（7 条）
CATEGORY_QUERIES = [
    # cs.DC (分布式计算) — 论文量大，2000条只到2024-11
    'cat:cs.DC AND ("machine learning" OR "deep learning" OR "reinforcement learning" OR "neural network" OR LLM)',
    # cs.DB (数据库) — 2000条到2020-10
    'cat:cs.DB AND ("machine learning" OR "deep learning" OR "reinforcement learning" OR "neural network" OR LLM)',
    # cs.AR (体系结构) — 2000条到2023-02
    'cat:cs.AR AND ("machine learning" OR "deep learning" OR "neural network" OR LLM)',
    # cs.NI (网络) — 2000条到2023-12
    'cat:cs.NI AND ("machine learning" OR "deep learning" OR "reinforcement learning" OR "neural network" OR LLM)',
    # cs.PF (性能) — 共1326篇，覆盖到2010
    'cat:cs.PF AND ("machine learning" OR "deep learning" OR "reinforcement learning" OR "neural network" OR LLM)',
    # cs.OS (操作系统) — 共154篇
    'cat:cs.OS AND ("machine learning" OR "deep learning" OR "reinforcement learning" OR "neural network" OR LLM)',
    # cs.PL (编程语言/编译器) — 共1381篇
    'cat:cs.PL AND ("machine learning" OR "deep learning" OR "neural network" OR LLM)',
]

# B 组：专题精准查询（12 条）
TOPIC_QUERIES = [
    # Software Systems
    '"learned index" OR "learned indexing" OR "learned cardinality" OR "self-tuning database"',
    '("reinforcement learning" OR "deep learning") AND ("cluster scheduling" OR "job scheduling" OR autoscaling OR "bin packing")',
    '("reinforcement learning" OR "deep learning") AND ("congestion control" OR "traffic engineering" OR "adaptive bitrate")',
    '("machine learning" OR "neural network") AND ("compiler optimization" OR "instruction scheduling" OR "register allocation" OR "loop tiling" OR "polyhedral")',
    '("machine learning" OR "deep learning") AND ("cache replacement" OR prefetching OR "memory allocation") AND (system OR server OR storage)',
    '("machine learning" OR "reinforcement learning") AND ("LSM-tree" OR "log-structured" OR "KV store" OR "key-value store")',
    # Hardware/RTL Design
    '(LLM OR "large language model") AND (Verilog OR VHDL OR EDA OR "hardware design" OR chip OR ASIC)',
    '("machine learning" OR "deep learning") AND (EDA OR "electronic design automation" OR "logic synthesis" OR "design verification")',
    # Physical/Chip Design
    '("machine learning" OR "deep learning" OR "reinforcement learning") AND ("place and route" OR floorplanning OR "timing closure" OR "physical design")',
    '("machine learning" OR "deep learning") AND ("analog circuit" OR "circuit sizing" OR "analog design")',
    # Cross-cutting
    '("machine learning" OR "reinforcement learning") AND ("power management" OR DVFS OR "energy optimization") AND (chip OR processor OR server)',
    'cat:cs.CR AND ("machine learning" OR "deep learning") AND ("side channel" OR "hardware security" OR "fault injection")',
]


DEFAULT_OUTPUT = "_data/llm_hw_design_papers.json"
DEFAULT_MAX_RESULTS = 5000


def fetch_papers(query: str, max_results: int = DEFAULT_MAX_RESULTS):
    """
    迭代返回符合查询的 arXiv 结果字典（按发表时间倒序）。

    使用 arxiv.Client 取代已弃用的 Search.results()
    """
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    client = arxiv.Client(
        page_size=100,      # 每次 API 调用返回条数
        delay_seconds=3,    # 遵守 arXiv 速率限制
    )

    count = 0
    try:
        for result in client.results(search):
            if count == 0:
                print(f'  Fetching for "{query}"...')
            count += 1
            if count > 0 and count % 100 == 0:
                print(f"  ... fetched {count} results so far.")
            yield {
                "title": result.title.strip(),
                "url": result.entry_id,
                "abstract": result.summary.strip().replace("\n", " "),
                "published": result.published.replace(tzinfo=timezone.utc)
                             .strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

        if count > 0:
            print(f"  Finished query. Found {count} papers.")
        else:
            print(f"  No results for query.")

    except UnexpectedEmptyPageError as e:
        # 某些分页可能因 arXiv API 状态异常返回空白，此时直接跳过当前关键词
        # 在 arxiv >= 2.1.0 中，当结果总数是 page_size 的整数倍时，
        # 在取完最后一页后会触发此"异常"，但这属于正常行为。
        # 我们在此处捕获它并直接忽略，以允许生成器正常退出。
        print(f"  Query finished (hit an empty page). Found {count} papers.")
        pass
    except Exception as e:
        # 捕获其它未知错误，保证脚本不中断
        print(f"⚠️  检索 [{query}] 时发生错误，已跳过：{e}")


def load_existing(path: str):
    """读取已有 JSON，返回列表和已存在的 URL 集合。"""
    if not os.path.isfile(path):
        return [], set()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data, {item["url"] for item in data}


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✓ 写入 {len(data)} 条记录 → {path}")


def main():
    parser = argparse.ArgumentParser(description="Manage arXiv papers list")
    parser.add_argument("--mode", type=int, choices=[0, 1], required=True,
                        help="0 = 全量重建, 1 = 增量追加")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help="输出 JSON 文件路径")
    # --query 可以重复出现以提供多组关键词
    parser.add_argument("--query", action="append",
                        help="自定义检索词（可重复使用）。若省略则使用脚本内置的默认集合。")
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS,
                        help="最大检索条数（默认 5000）")
    parser.add_argument("--cooldown", type=int, default=60,
                        help="查询之间的冷却秒数（默认 60，防 429 限流）")
    args = parser.parse_args()

    # 若未显式提供 --query，则使用脚本预设 CATEGORY_QUERIES + TOPIC_QUERIES
    queries = args.query if args.query else (CATEGORY_QUERIES + TOPIC_QUERIES)

    print("Querying arXiv with the following term(s):")
    for q in queries:
        print(f"  - {q}")

    # 依次执行多组查询，并按 URL 去重
    new_items = []
    seen_urls = set()
    total_queries = len(queries)
    for i, q in enumerate(queries):
        if i > 0 and args.cooldown > 0:
            print(f"  ⏳ 冷却 {args.cooldown} 秒...")
            time.sleep(args.cooldown)
        print(f"\n--- Running query {i+1}/{total_queries} ---")
        for item in fetch_papers(q, args.max_results):
            if item["url"] in seen_urls:
                continue
            new_items.append(item)
            seen_urls.add(item["url"])

    print(f"\nTotal unique papers fetched: {len(new_items)}")
    # 按发布时间倒序排列（ISO 字符串直接比较即可）
    new_items.sort(key=lambda x: x["published"], reverse=True)

    if args.mode == 0:
        # 覆盖写入
        print(f"Mode 0: Saving {len(new_items)} papers (overwrite)...")
        save_json(args.output, new_items)
        return

    # mode == 1 → 读旧文件，去重后追加
    print(f"\nMode 1: Merging with existing file at {args.output}...")
    existing_data, existing_urls = load_existing(args.output)
    print(f"Loaded {len(existing_data)} existing papers.")

    add_count = 0
    merged = []

    # 先把新的（不在 existing_urls 的）条目放到前面
    for item in new_items:
        if item["url"] not in existing_urls:
            merged.append(item)
            add_count += 1

    merged.extend(existing_data)  # 旧记录放后面
    if add_count == 0:
        print("没有发现新论文，JSON 未修改。")
    else:
        print(f"Adding {add_count} new papers.")
        save_json(args.output, merged)


if __name__ == "__main__":
    main()
