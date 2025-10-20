#!/usr/bin/env python3
"""
arxiv_manager_min.py — 维护 “AI for Computer Systems” 相关论文的 JSON 清单。

用法
-----
# 第一次拉取全部结果（会覆盖旧 JSON）
python arxiv_manager_min.py --mode 0

# 之后按需增量更新（只追加新论文）
python arxiv_manager_min.py --mode 1

可选参数
--------
--output FILE      输出 JSON 路径（默认为 llm_hw_design_papers.json）
--query  STRING    自定义检索词
--max-results N    最多检索条数（默认 2000）
--since  YYYY-MM-DD   仅包含该日期（含）之后发表的论文
--until  YYYY-MM-DD   仅包含该日期（含）之前发表的论文

依赖
----
pip install arxiv>=2.0.0
"""

import argparse
import json
import os
from datetime import datetime, timezone, timedelta

# 需要 arxiv 2.x
import arxiv
# 当 arXiv API 某一分页意外为空时会抛出此异常
from arxiv import UnexpectedEmptyPageError

# 默认检索关键词集合（可按需修改）
# DEFAULT_QUERIES = [
#     '(LLM OR "large language model") AND "hardware design"',
#     '"generative ai" AND fpga',
#     '"large language model" AND "circuit design"',
#     '(LLM OR "large language model") AND verilog',
# ]

# --------- arXiv 关键词配置（AI for Systems & EDA/Hardware）---------
# 为减少单次查询中过多 OR 导致的空白分页问题，将查询拆分为更小的原子组合：
# 每个查询 = (一个 AI 术语) AND (一个主题术语)
AI_TERMS = [
    'LLM',
    'GPT',
    '"machine learning"',
    '"reinforcement learning"',
]

SUBJECT_TERMS = [
    # 操作系统 / 资源管理 / 调度
    '"operating system"', 'kernel', 'scheduling', '"resource management"', '"resource allocation"',
    # 分布式 / 云 / 虚拟化 / 容器
    '"distributed system"', 'cloud', 'datacenter', '"data center"', 'microservices', 'serverless', 'virtualization', 'Kubernetes', 'Docker',
    # 网络
    '"computer network"', 'networking', '"congestion control"', 'SDN', '"traffic engineering"', 'routing',
    # 存储 / 文件系统
    'storage', 'filesystem', '"file system"', 'NVMe', '"key-value store"',
    # 数据库
    'database', '"query optimizer"', 'indexing', '"cost model"',
    # 编译器 / 程序分析 / 运行时
    'compiler', 'LLVM', '"program analysis"', '"static analysis"', 'runtime', 'JIT',
    # 性能建模 / 缓存 / 预取 / 调参
    '"performance modeling"', 'autotuning', '"parameter tuning"', 'caching', 'prefetching',
    # 调度 / 集群编排
    '"job scheduling"', '"cluster scheduling"', 'autoscaling',
    # 安全
    'security', '"intrusion detection"', '"anomaly detection"', '"side channel"', 'malware', 'vulnerability',
    # 物理设计 / P&R / 时序
    '"physical design"', '"place and route"', 'placement', 'routing', '"timing closure"',
    # 综合
    'synthesis', '"logic synthesis"', '"high-level synthesis"', 'HLS',
    # 验证
    'verification', '"formal verification"', 'testbench', '"design verification"',
    # HDL / 代码生成
    '"hardware description language"', 'HDL', 'Verilog', 'VHDL', 'SystemVerilog', 'Chisel', '"HDL generation"',
    # 微架构 / NoC / 存储层次
    'microarchitecture', '"system architecture"', 'NoC', '"network-on-chip"', '"memory controller"', 'cache',
    # EDA 总称
    'EDA', '"electronic design automation"',
]

DEFAULT_QUERIES = [f'({ai}) AND ({subj})' for ai in AI_TERMS for subj in SUBJECT_TERMS]



# ------------------------------------------------------------------

# -------------------------------------------------------------------------

# -----------------------------------


DEFAULT_OUTPUT = "_data/ai_systems_papers.json"
DEFAULT_MAX_RESULTS = 2000


def fetch_papers(query: str, max_results: int = DEFAULT_MAX_RESULTS,
                 since: datetime | None = None,
                 until: datetime | None = None):
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
            pub_dt = result.published.replace(tzinfo=timezone.utc)
            # Apply upper bound first (skip overly new ones)
            if until is not None and pub_dt > until:
                continue
            # Apply lower bound: since results are sorted desc, we can stop once below since
            if since is not None and pub_dt < since:
                print("  Reached items older than --since; stopping this query early.")
                break
            yield {
                "title": result.title.strip(),
                "url": result.entry_id,
                "abstract": result.summary.strip().replace("\n", " "),
                "published": pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        
        if count > 0:
            print(f"  Finished query. Found {count} papers.")
        else:
            print(f"  No results for query.")

    except UnexpectedEmptyPageError as e:
        # 某些分页可能因 arXiv API 状态异常返回空白，此时直接跳过当前关键词
        # 在 arxiv >= 2.1.0 中，当结果总数是 page_size 的整数倍时，
        # 在取完最后一页后会触发此“异常”，但这属于正常行为。
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
                        help="最大检索条数（默认 2000）")
    parser.add_argument("--queries-file", type=str,
                        help="从文件读取查询（每行一个，支持 # 注释）。提供该参数将覆盖内置默认查询集合。")
    parser.add_argument("--since", type=str, help="仅包含该日期（含）之后发表的论文，格式 YYYY-MM-DD")
    parser.add_argument("--until", type=str, help="仅包含该日期（含）之前发表的论文，格式 YYYY-MM-DD")
    args = parser.parse_args()

    # 若提供 --queries-file，则优先使用文件中的自定义查询；否则使用命令行 --query 或默认集合
    if args.queries_file:
        file_queries = []
        try:
            with open(args.queries_file, 'r', encoding='utf-8') as qf:
                for line in qf:
                    s = line.strip()
                    if not s or s.startswith('#'):
                        continue
                    file_queries.append(s)
        except Exception as e:
            print(f"⚠️  读取查询文件失败（{args.queries_file}）：{e}")
            file_queries = []
        queries = file_queries if file_queries else DEFAULT_QUERIES
    else:
        # 若未显式提供 --query，则使用脚本预设 DEFAULT_QUERIES
        queries = args.query if args.query else DEFAULT_QUERIES

    # 解析日期边界（统一为 UTC 日期起止）
    since_dt = None
    until_dt = None
    if args.since:
        since_dt = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if args.until:
        # inclusive end-of-day: 23:59:59
        until_base = datetime.strptime(args.until, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        until_dt = until_base + timedelta(days=1) - timedelta(seconds=1)

    print("Querying arXiv with the following term(s):")
    for q in queries:
        print(f"  - {q}")

    # 依次执行多组查询，并按 URL 去重
    new_items = []
    seen_urls = set()
    total_queries = len(queries)
    for i, q in enumerate(queries):
        print(f"\n--- Running query {i+1}/{total_queries} ---")
        for item in fetch_papers(q, args.max_results, since=since_dt, until=until_dt):
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
