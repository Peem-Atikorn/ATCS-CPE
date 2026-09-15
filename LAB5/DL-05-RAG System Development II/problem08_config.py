# -*- coding: utf-8 -*-
# Problem 08: Analyzing the Configuration of a RAG system that uses solar_cell_q_a.txt as its knowledge base
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

from data_loader import load_qa

CONFIG = {
    "KB_SOURCE": "solar_cell_q_a.txt",
    "USE_HYBRID": True,
    "USE_RERANK": False,
    "USE_MEMORY": True,
    "USE_LLM": True,
    "SHOW_SOURCES": False,
}


def run():
    data = load_qa()
    print("CONFIG =", CONFIG)
    print(f"Loaded Knowledge Base from {CONFIG['KB_SOURCE']}: {len(data)} Q&A entries")
    print("\nPipeline:")

    if CONFIG["USE_MEMORY"]:
        print("1. Using Conversation Memory")

    if CONFIG["USE_HYBRID"]:
        print(f"2. Using BM25 + Dense Retrieval on {len(data)} documents")
    else:
        print(f"2. Using Dense Retrieval on {len(data)} documents")

    if CONFIG["USE_RERANK"]:
        print("3. Performing Re-ranking")
    else:
        print("3. Not performing Re-ranking")

    if CONFIG["USE_LLM"]:
        print(f"4. Generating the answer with an LLM (grounded in Context from {CONFIG['KB_SOURCE']})")

    if CONFIG["SHOW_SOURCES"]:
        print("5. Showing Sources")
    else:
        print("5. Not showing Sources")

    print("\nThe system's behavior results from toggling each Component on/off in the Config")


if __name__ == "__main__":
    run()
