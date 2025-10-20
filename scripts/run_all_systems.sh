#!/bin/bash
set -e

echo "[AI-for-Systems] Cleaning previous data..."
rm -f _data/ai_systems_papers.json \
      _data/ai_systems_papers_labeled.json \
      _data/filter_papers.json \
      _data/tagged_papers.json || true

echo "[AI-for-Systems] Fetching papers from arXiv (full rebuild since 2010-01-01)..."
python3 scripts/arxiv_manager_min.py --mode 0 --output _data/ai_systems_papers.json --since 2010-01-01

echo "[AI-for-Systems] Classifying papers..."
python3 scripts/classify_papers.py --input _data/ai_systems_papers.json --output _data/ai_systems_papers_labeled.json

echo "[AI-for-Systems] Sorting filtered AI-for-Systems papers..."
python3 scripts/shuffle_papers.py

echo "[AI-for-Systems] Tagging papers..."
python3 scripts/tag_papers.py --input _data/filter_papers.json --output _data/tagged_papers.json

echo "[AI-for-Systems] Done."


