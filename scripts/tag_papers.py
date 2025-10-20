#!/usr/bin/env python3
"""
tag_papers.py — Adds a single, high-level tag to each paper in
filter_papers.json.

This script takes papers already classified as "AI for Computer Systems" and
assigns exactly ONE of a small set of classic, recognizably broad categories.
If none fits, assigns "Other Topics".

Usage Example
-------------
# Tag all un-tagged papers using the default model gpt-4o
python tag_papers.py --input _data/filter_papers.json \
                     --output _data/tagged_papers.json

Optional Arguments
------------------
--input FILE       Input JSON (default: _data/filter_papers.json)
--output FILE      Output JSON (default: _data/tagged_papers.json)
--model MODEL      OpenAI model name (default: gpt-4o, can be changed to gpt-3.5-turbo, etc.)
--overwrite        Force re-evaluation even if the 'tags' field exists

Environment Dependencies
------------------------
1. python -m pip install openai>=1.13.3
2. Set environment variable OPENAI_API_KEY=<key>
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import threading
import time
from typing import List, Dict, Any

import openai
from openai import OpenAI
from openai._exceptions import OpenAIError

# ---------------------------------- Configuration ----------------------------------
DEFAULT_INPUT = "_data/filter_papers.json"
DEFAULT_OUTPUT = "_data/tagged_papers.json"
DEFAULT_MODEL = "gpt-5-mini-2025-08-07"
MAX_RETRY = 3
RETRY_BACKOFF_SEC = 5
DEFAULT_API_KEY_FILE = "secrets/api_key.json"

VALID_TAGS = [
    "Hardware Design",
    "Computer Architecture",
    "Circuit Design",
    "Software Systems",
    "Security",
    "Other Topics",
]

# Map broader or synonymous phrases to the canonical VALID_TAGS
TAG_ALIASES = {
    "Hardware Design": [
        "hardware design", "eda", "electronic design automation", "physical design",
        "place and route", "placement", "routing", "timing closure", "synthesis",
        "logic synthesis", "high-level synthesis", "hls", "verification",
        "formal verification", "testbench", "hdl", "verilog", "vhdl",
        "systemverilog", "chisel", "rtl"
    ],
    "Computer Architecture": [
        "architecture", "microarchitecture", "isa", "accelerator architecture",
        "noc", "network-on-chip", "cache", "memory controller", "pipeline"
    ],
    "Circuit Design": [
        "analog", "rf", "mixed-signal", "op-amp", "pll", "adc", "dac", "layout"
    ],
    "Software Systems": [
        "operating system", "os", "kernel", "distributed", "cloud", "datacenter",
        "data center", "virtualization", "kubernetes", "docker", "networking",
        "sdn", "traffic engineering", "file system", "filesystem", "database",
        "query optimizer", "compiler", "llvm", "runtime", "jit", "scheduling",
        "resource management", "performance modeling", "autotuning", "caching",
        "prefetching", "orchestration", "microservices"
    ],
    "Security": [
        "security", "intrusion", "anomaly", "vulnerability", "malware",
        "side channel", "side-channel", "trojan", "attestation", "enclave", "tee"
    ],
}

# ------------------------------ Core Functions -----------------------------------

def build_prompt(title: str, abstract: str) -> List[Dict[str, str]]:
    """Constructs the messages required for Chat Completion."""
    system_msg = (
        "You are an expert research assistant specializing in computer systems and hardware. "
        "Assign EXACTLY ONE category tag to each paper based on title and abstract. If none fits, respond with 'Other Topics'.\n\n"
        "Choose one from: `Hardware Design`, `Computer Architecture`, `Circuit Design`, `Software Systems`, `Security`, `Other Topics`.\n\n"
        "Definitions (brief):\n"
        "- **Hardware Design**: EDA/RTL/HDL, synthesis, verification, physical design (P&R, timing).\n"
        "- **Computer Architecture**: Microarchitecture, cache/memory hierarchy, NoC, ISA-level design.\n"
        "- **Circuit Design**: Analog/RF/mixed-signal circuits, PLL/ADC/DAC, analog layout.\n"
        "- **Software Systems**: OS, distributed systems, networking, storage/DB, compilers/runtimes.\n"
        "- **Security**: System/hardware security (intrusion, anomaly, vulnerabilities, side-channels).\n"
        "- **Other Topics**: If none of the above categories fits.\n\n"
        "Respond with exactly one category name from the list above."
    )

    user_msg = (
        f"Title: {title}\n"
        f"Abstract: {abstract}\n\n"
        "What is the single most appropriate tag for this paper? (choose exactly one)"
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def query_model(client: OpenAI, messages: List[Dict[str, str]], model: str = DEFAULT_MODEL) -> str:
    """Calls OpenAI ChatCompletion, returns the result string."""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=16,
            )
            ans = response.choices[0].message.content.strip()
            return ans
        except OpenAIError as e:
            if attempt == MAX_RETRY:
                raise
            # Exponential backoff
            wait = RETRY_BACKOFF_SEC * attempt
            print(f"⚠️  OpenAI API error ({e}); retrying in {wait}s…", file=sys.stderr)
            time.sleep(wait)
    # If it still hasn't returned, raise an exception
    raise RuntimeError("Failed to get response from OpenAI API after retries")


def _normalize_to_canonical_tag(result_str: str) -> str:
    """Normalize model output to one of VALID_TAGS using direct match or alias keywords."""
    text = result_str.strip().lower()
    # Direct canonical match
    for tag in VALID_TAGS:
        if tag.lower() == text:
            return tag
    # Substring contains canonical name
    for tag in VALID_TAGS:
        if tag.lower() in text:
            return tag
    # Alias keyword match by priority order of VALID_TAGS
    for tag in VALID_TAGS:
        aliases = TAG_ALIASES.get(tag, [])
        for kw in aliases:
            if kw.lower() in text:
                return tag
    return "Other Topics"


def tag_item(client: OpenAI, item: Dict[str, Any], model: str, overwrite: bool = False) -> None:
    """Classifies a single paper record and adds a single-element 'tags' list to it."""
    if not overwrite and "tags" in item:
        return

    messages = build_prompt(item["title"], item["abstract"])
    result_str = query_model(client, messages, model=model)
    canonical = _normalize_to_canonical_tag(result_str)
    item["tags"] = [canonical]


# ------------------------------ Main Function -----------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Tag papers with a single classic category using an OpenAI model")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to the input JSON file of filtered papers")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to the output JSON file with tagged papers")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenAI model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--jobs", "-j", type=int, default=40, help="Number of concurrent API requests (default: 20)")
    parser.add_argument("--api-key-file", default=DEFAULT_API_KEY_FILE,
                        help=f"Path to file containing OpenAI API Key (default: {DEFAULT_API_KEY_FILE})")
    parser.add_argument("--overwrite", action="store_true", help="Force re-tagging all papers, ignoring existing ones")

    args = parser.parse_args()

    # --- Load Input Data ---
    if not os.path.isfile(args.input):
        print(f"❌ Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    with open(args.input, "r", encoding="utf-8") as f:
        all_papers = json.load(f)

    # --- Load Existing Tagged Data (if any) ---
    existing_papers = []
    if not args.overwrite and os.path.isfile(args.output):
        try:
            with open(args.output, "r", encoding="utf-8") as f:
                existing_papers = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Could not read existing output file, will overwrite it. Reason: {e}", file=sys.stderr)

    # --- Identify Papers to Process ---
    if args.overwrite:
        items_to_process = all_papers
        print(f"⚠️  --overwrite flag is set. Re-tagging all {len(all_papers)} papers from input.")
    else:
        existing_urls = {item.get("url") for item in existing_papers if item.get("url")}
        items_to_process = [item for item in all_papers if item.get("url") not in existing_urls]

    # --- Prepare OpenAI API Key ---
    if items_to_process:
        if not os.getenv("OPENAI_API_KEY"):
            key_file = args.api_key_file
            if os.path.isfile(key_file):
                try:
                    with open(key_file, "r", encoding="utf-8") as kf:
                        try:
                            key_data = json.load(kf)
                            api_key_val = (
                                key_data.get("OPENAI_API_KEY")
                                or key_data.get("api_key")
                                or key_data.get("key")
                            )
                        except json.JSONDecodeError:
                            kf.seek(0)
                            api_key_val = kf.read().strip()
                        if api_key_val:
                            os.environ["OPENAI_API_KEY"] = api_key_val
                except Exception as e:
                    print(f"⚠️  Failed to read API Key file: {e}", file=sys.stderr)

        if not os.getenv("OPENAI_API_KEY"):
            print(f"❌ OPENAI_API_KEY not found in environment variables or file (tried to read {args.api_key_file})", file=sys.stderr)
            sys.exit(1)

    client = OpenAI()

    # --- Tag New Papers ---
    if not items_to_process:
        print("✓ No new papers to tag.")
        final_data = existing_papers
    else:
        print(f"Found {len(items_to_process)} new papers to tag. Using {args.jobs} concurrent workers...")
        processed_count = 0
        total_to_process = len(items_to_process)
        lock = threading.Lock()

        def process_wrapper(item: Dict[str, Any]) -> None:
            nonlocal processed_count
            try:
                tag_item(client, item, args.model, overwrite=True)  # Always overwrite as we only process new items
            except Exception as e:
                print(f"⚠️  Tagging failed for '{item.get('title', 'N/A')}', skipping: {e}", file=sys.stderr)
                item["tags"] = ["Error"]
            finally:
                with lock:
                    processed_count += 1
                    if processed_count % 10 == 0 or processed_count == total_to_process:
                        print(f"  Processed {processed_count}/{total_to_process} papers...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            executor.map(process_wrapper, items_to_process)
        
        # Combine and set final data
        final_data = existing_papers + items_to_process

    # --- Sort and Save ---
    print("Sorting all papers by publication date...")
    final_data.sort(key=lambda x: x.get("published", ""), reverse=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)

    print(f"✓ Tagging complete. Total {len(final_data)} papers saved to → {args.output}")


if __name__ == "__main__":
    main() 