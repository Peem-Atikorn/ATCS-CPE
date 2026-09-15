# -*- coding: utf-8 -*-
# Problem 05: Similarity Search returns a document with matching text but wrong Metadata (category)
# Uses real data from solar_cell_q_a.txt, which has 12 categories
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

from data_loader import load_qa

QUERY = "ขออนุญาต ติดตั้ง โซล่าเซลล์"


def score(query, text):
    return sum(word in text for word in query.split())


def search(data, query, category=None):
    docs = data if category is None else [d for d in data if d["category"] == category]
    return max(docs, key=lambda d: score(query, d["question"] + " " + d["answer"]))


def run():
    data = load_qa()

    bad = search(data, QUERY)
    good = search(data, QUERY, category="กฎหมายและการขออนุญาต")

    print("Query:", QUERY)
    print("\nWithout filtering by Metadata (category) -> picks document based purely on keyword count:")
    print(f"  [{bad['category']}] {bad['question']}")

    print("\nFilter category='กฎหมายและการขออนุญาต' (specifically targeting legal/regulatory compliance):")
    print(f"  [{good['category']}] {good['question']}")

    print("\nCause: Keyword/Semantic Similarity picks the document with the most matching words")
    print("but does not guarantee the document belongs to the intended domain/category metadata")


if __name__ == "__main__":
    run()
