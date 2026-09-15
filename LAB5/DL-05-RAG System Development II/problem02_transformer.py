# -*- coding: utf-8 -*-
# Problem 02: Vocabulary Mismatch (technical vs colloquial/slang) and Token order (Position)
# Uses real data from solar_cell_q_a.txt
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

from data_loader import load_qa


def bow(text):
    result = {}
    for token in text.split():
        result[token] = result.get(token, 0) + 1
    return result


def with_position(text):
    return [(i, token) for i, token in enumerate(text.split())]


def find_pair(data):
    formal = next(d for d in data if d["question"] == "แผงโซล่าเซลล์มีอายุการใช้งานกี่ปี?")
    # Simulated colloquial/user phrasing (derived from LAB4 domain normalization)
    colloquial = {
        "question": "แผงแดด ทนแดด ได้กี่ปี",
        "answer": formal["answer"],
    }
    return formal, colloquial


def run():
    data = load_qa()
    formal, colloquial = find_pair(data)

    print("Formal-register question in KB :", formal["question"])
    print("Colloquial query from user     :", colloquial["question"])
    print("BoW (formal)    :", bow(formal["question"]))
    print("BoW (colloquial):", bow(colloquial["question"]))
    common = set(bow(formal["question"])) & set(bow(colloquial["question"]))
    print("Exact-token overlap:", common or "None")
    print("-> Both queries refer to the same intent (solar panel lifespan/durability)")
    print("   but Keyword/BoW fails to overlap because wording differs (Vocabulary Mismatch)")

    print("\nExample: effect of Token order on meaning (Position):")
    a = " ".join(formal["answer"].split()[:8])
    b = " ".join(reversed(a.split()))
    print("A (original)      :", with_position(a))
    print("B (reversed order):", with_position(b))
    print("BoW identical     :", bow(a) == bow(b))

    print("\nCause: BoW does not capture vocabulary variation and does not preserve word order")
    print("Transformers use Positional Information + Self-Attention and semantic Embeddings")
    print("to match queries that use different wording but share the same intent (e.g. 'แผงแดด' -> 'แผงโซล่าเซลล์')")


if __name__ == "__main__":
    run()
