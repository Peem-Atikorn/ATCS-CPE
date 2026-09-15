# -*- coding: utf-8 -*-
# Problem 10: Debug RAG Pipeline & Knowledge Base Scripts
# Demonstrates common debugging techniques for RAG knowledge bases and retrieval pipelines
import os
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

from data_loader import DATA_PATH, load_qa


def check_knowledge_base_integrity(data):
    issues = []
    for d in data:
        if not d["question"].strip():
            issues.append(f"Entry {d['id']}: Empty question")
        if not d["answer"].strip():
            issues.append(f"Entry {d['id']}: Empty answer")
        if not d["category"].strip():
            issues.append(f"Entry {d['id']}: Empty category")
    return issues


def debug_query_retrieval(data, query):
    tokens = query.lower().split()
    matched = []
    for d in data:
        overlap = [t for t in tokens if t in d["text"].lower()]
        if overlap:
            matched.append((len(overlap), overlap, d))
    matched.sort(key=lambda x: x[0], reverse=True)
    return matched


def run():
    print("--- 1. Knowledge Base Integrity Check ---")
    print(f"Checking data source: {os.path.basename(DATA_PATH)}")
    data = load_qa()
    print(f"Total parsed records: {len(data)}")

    issues = check_knowledge_base_integrity(data)
    if issues:
        print(f"Found {len(issues)} data integrity issues:")
        for iss in issues[:5]:
            print(" -", iss)
    else:
        print("Knowledge base structure is healthy: 0 empty questions, answers, or categories.")

    print("\n--- 2. Debugging Zero-Hit / Query Mismatch ---")
    failing_query = "แผงรับแสงอาทิตย์บ้านใช้ได้กี่ปี"
    matched = debug_query_retrieval(data, failing_query)

    print(f"Test Query: '{failing_query}'")
    if not matched:
        print("Result: 0 documents matched.")
    else:
        print(f"Matched {len(matched)} documents. Top match overlap tokens: {matched[0][1]}")
        print(f"Top matched Question: {matched[0][2]['question']}")

    print("\nDebug Diagnostic:")
    print("- When retrieval score is 0 or low, inspect tokenization, slang/synonym mapping, or encoding.")
    print("- Ensure Thai token boundaries or subword embeddings are utilized to avoid zero-hit matches.")
    print("- Scripts in problem01-09 provide focused units to diagnose each stage independently.")


if __name__ == "__main__":
    run()
