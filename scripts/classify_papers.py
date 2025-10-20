#!/usr/bin/env python3
"""
classify_papers.py — Labels each paper in ai_systems_papers.json:
whether it is of the "AI for Computer Systems" type (i.e., using AI/LLM/ML to
solve systems problems in OS, distributed systems, networking, storage, DB, compilers,
runtime, resource management, performance, etc., rather than accelerating AI itself).

Usage Example
-------------
# Label all un-annotated papers using the default model
python classify_papers.py --input _data/ai_systems_papers.json \
                         --output _data/ai_systems_papers_labeled.json

Optional Arguments
------------------
--input FILE       Input JSON (default: _data/ai_systems_papers.json)
--output FILE      Output JSON (default: *_labeled.json, overwrites input if omitted)
--model MODEL      OpenAI model name (default: gpt-4o-mini, can be changed to gpt-3.5-turbo, etc.)
--overwrite        Force re-evaluation even if the ai_for_hw field exists

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
DEFAULT_INPUT = "_data/ai_systems_papers.json"
DEFAULT_OUTPUT_SUFFIX = "_labeled.json"
DEFAULT_DIFF_AGAINST = "_data/ai_systems_papers_labeled.json"
DEFAULT_FILTERED_FILENAME = "filter_papers.json"
DEFAULT_MODEL = "gpt-5-mini-2025-08-07"
MAX_RETRY = 3
RETRY_BACKOFF_SEC = 5
DEFAULT_API_KEY_FILE = "secrets/api_key.json"

# ------------------------------ Core Functions -----------------------------------

def safe_json_write(data_to_write: List[Dict[str, Any]], path: str) -> None:
    """
    Safely writes data to a JSON file by first writing to a temporary file
    and then atomically renaming it. This prevents data corruption if the
    script is interrupted.
    """
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data_to_write, f, indent=2, ensure_ascii=False)
        # If write is successful, atomically move the file
        os.rename(temp_path, path)
    except Exception as e:
        print(f"❌ Failed to write file {path}. Error: {e}", file=sys.stderr)
        # Clean up the temp file if it exists
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise  # Re-raise to signal failure


def build_prompt(title: str, abstract: str) -> List[Dict[str, str]]:
    """Constructs the messages required for Chat Completion."""
    system_msg = (
        "You are an expert research assistant. Your task is to classify academic papers based on their title and abstract.\n"
        "The goal is to identify if a paper's contribution is 'AI for Computer Systems' (including hardware/EDA when AI is applied to design/verification/automation).\n\n"
        "Respond with 'true' if the paper applies AI/ML/LLM to solve problems in any of the following areas (examples, not exhaustive):\n"
        "- Operating systems (scheduling, resource management, memory, I/O)\n"
        "- Distributed systems, cloud, virtualization, orchestration\n"
        "- Computer networking (routing, congestion control, traffic engineering, SDN)\n"
        "- Storage and filesystems\n"
        "- Databases (query optimization, indexing, cost models)\n"
        "- Compilers, program analysis, runtime/JIT\n"
        "- Performance modeling, autotuning, caching/prefetching\n"
        "- System security (intrusion/anomaly detection, side-channel analysis)\n"
        "- Circuit Design (analog, RF, mixed-signal, PLL, ADC, DAC, layout)\n"
        "- Hardware/EDA: physical design (placement, routing, timing closure), synthesis (HLS/logic), verification (formal/testbench), HDL/code generation, microarchitecture/NoC/memory/cache\n\n"
        "Respond with 'false' if the primary focus is 'Systems/Hardware for AI' or 'AI acceleration', such as:\n"
        "- Specialized accelerators or systems whose main goal is speeding up AI training/inference\n"
        "- Tweaks to AI models mainly to run faster on specific hardware (GPU/TPU)\n"
        "- Framework/runtime optimizations targeted primarily at AI workloads rather than general systems problems\n\n"
        "--- EXAMPLE 1 (Correct answer: true) ---\n"
        'Title: "Learning-based Cluster Scheduler for Heterogeneous Datacenters"\n'
        'Abstract: "We propose a reinforcement-learning scheduler that improves job completion time and fairness across a heterogeneous cluster with GPUs and CPUs..."\n'
        "Reasoning: Uses ML to solve a core systems problem (cluster scheduling).\n\n"
        "--- EXAMPLE 2 (Correct answer: true) ---\n"
        'Title: "Reinforcement Learning for Global Placement in VLSI Physical Design"\n'
        'Abstract: "An RL agent learns to place standard cells to minimize wirelength and congestion..."\n'
        "Reasoning: Uses ML to solve an EDA physical-design task (P&R), which is AI for systems/hardware.\n\n"
        "--- EXAMPLE 3 (Correct answer: false) ---\n"
        'Title: "A Low-Power Accelerator for Transformer Inference"\n'
        'Abstract: "We design a novel ASIC to accelerate Transformer attention with quantization and sparsity..."\n'
        "Reasoning: Hardware for accelerating AI, not AI for systems/hardware tasks.\n"
        "--- END OF EXAMPLES ---\n\n"
        "Now, classify the following paper. Respond with a single word: 'true' or 'false'."
    )

    user_msg = (
        f"Title: {title}\n"
        f"Abstract: {abstract}\n\n"
        "Does this paper belong to the 'AI for Computer Systems' category (true/false)?"
    )

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def query_model(client: OpenAI, messages: List[Dict[str, str]], model: str = DEFAULT_MODEL) -> str:
    """Calls OpenAI ChatCompletion, returns the result string (stripped and lowercased)."""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=1,
            )
            ans = response.choices[0].message.content.strip().lower()
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


def classify_item(client: OpenAI, item: Dict[str, Any], model: str, overwrite: bool = False) -> bool:
    """Classifies a single paper record and returns a boolean result."""
    if not overwrite and "ai_for_systems" in item:
        return item["ai_for_systems"]

    messages = build_prompt(item["title"], item["abstract"])
    result = query_model(client, messages, model=model)
    label = result.startswith("t")  # Accepts 'true'/'false' in any case
    item["ai_for_systems"] = label
    return label


# ------------------------------ Main Function -----------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Classify papers as AI-for-Computer-Systems or not using an OpenAI model")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to the input JSON file")
    parser.add_argument("--output", help="Path to the output JSON file (default: <input>_labeled.json)")
    parser.add_argument("--filtered-output", help=f"Path for the filtered JSON file (default: {DEFAULT_FILTERED_FILENAME} in output dir)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model name (default: gpt-4o-mini)")
    parser.add_argument("--jobs", "-j", type=int, default=20, help="Number of concurrent API requests (default: 8)")
    parser.add_argument("--api-key-file", default=DEFAULT_API_KEY_FILE,
                        help="Path to file containing OpenAI API Key (JSON or plain text, default: secrets/api_key.json)")
    parser.add_argument("--diff-against", default=DEFAULT_DIFF_AGAINST, help="Path to a pre-existing labeled JSON to diff against. Only new papers will be classified.")
    parser.add_argument("--overwrite", action="store_true", help="Force re-evaluation even if ai_for_hw field already exists (ignored if --diff-against is used)")

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"❌ Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Default output path is in the same directory as input, with a suffix added to the filename
    output_path = args.output or (
        args.input if args.input.endswith(DEFAULT_OUTPUT_SUFFIX) else args.input.replace(".json", DEFAULT_OUTPUT_SUFFIX)
    )

    # Determine filtered output path
    if args.filtered_output:
        filtered_output_path = args.filtered_output
    else:
        output_dir = os.path.dirname(output_path) or "."
        filtered_output_path = os.path.join(output_dir, DEFAULT_FILTERED_FILENAME)

    # -------------------- Prepare OpenAI API Key --------------------
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

    total = len(data)
    # --- Diff Logic ---
    if args.diff_against and os.path.isfile(args.diff_against):
        print(f"🔍 Diffing against {args.diff_against} to find new papers...")
        with open(args.diff_against, "r", encoding="utf-8") as f:
            labeled_data = json.load(f)
        
        # Use URL as the unique identifier for a paper
        labeled_urls = {item.get("url") for item in labeled_data if item.get("url")}
        
        # Items to process are those in the main data list that are NOT in the labeled list
        items_to_process = [
            item for item in data if item.get("url") not in labeled_urls
        ]
        
        # The final dataset will be the already labeled data plus the newly processed items
        final_data = labeled_data
        data = final_data # For progress reporting and final saving
    else:
        # Original logic: process items that are missing the 'ai_for_systems' field
        items_to_process = [
            item for item in data if args.overwrite or "ai_for_systems" not in item
        ]
        final_data = data

    if not items_to_process:
        print("✓ No papers to classify.")
    else:
        # Save a list of papers to be processed for inspection and control
        output_dir = os.path.dirname(output_path) or "."
        input_basename = os.path.splitext(os.path.basename(args.input))[0]
        unlabeled_filename = f"{input_basename}_unlabeled.json"
        unlabeled_output_path = os.path.join(output_dir, unlabeled_filename)

        print(f"Found {len(items_to_process)} papers to classify. Saving this list to: {unlabeled_output_path}")
        with open(unlabeled_output_path, "w", encoding="utf-8") as f:
            json.dump(items_to_process, f, indent=2, ensure_ascii=False)

        print(f"Classifying {len(items_to_process)} papers using {args.jobs} concurrent workers...")
        processed_count = 0
        total_to_process = len(items_to_process)
        lock = threading.Lock()

        def process_wrapper(item: Dict[str, Any]) -> None:
            nonlocal processed_count
            try:
                classify_item(client, item, args.model, overwrite=args.overwrite)
            except Exception as e:
                print(f"⚠️  Classification failed for '{item.get('title', 'N/A')}', skipping: {e}", file=sys.stderr)
            finally:
                with lock:
                    processed_count += 1
                    if processed_count % 10 == 0 or processed_count == total_to_process:
                        print(f"Processed {processed_count}/{total_to_process} new papers...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            # Note: We are mapping over `items_to_process`, and the results are directly mutated in the items themselves.
            list(executor.map(process_wrapper, items_to_process)) # Use list() to ensure all futures complete

        # Add the newly processed items to the final dataset
        final_data.extend(items_to_process)

    # --- Final Saving Step ---
    positive = sum(1 for item in final_data if item.get("ai_for_systems"))
    total = len(final_data)

    try:
        safe_json_write(final_data, output_path)
        print(f"✓ Classification complete: Total {total} papers, AI-for-Systems {positive} papers → {output_path}")
    except Exception:
        # If the main output fails, it's a critical error. Exit.
        print("❌ A critical error occurred while writing the main output file. The original file has been preserved.", file=sys.stderr)
        sys.exit(1)

    if positive > 0:
        # Filter items that are AI-for-Systems
        filtered_data = [item for item in final_data if item.get("ai_for_systems")]
        try:
            safe_json_write(filtered_data, filtered_output_path)
            print(f"✓ Filtered list of {positive} AI-for-Systems papers saved to → {filtered_output_path}")
        except Exception:
            # If the filtered list fails, it's not critical. The main file is safe.
            print(f"⚠️  Warning: Could not write the filtered output file. The main labeled file at {output_path} is safe.", file=sys.stderr)



if __name__ == "__main__":
    main()