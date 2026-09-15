# -*- coding: utf-8 -*-
# Problem 01: Hallucination / No evidence in Retrieved Context
# Uses solar_cell_q_a.txt as a real Knowledge Base
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

from data_loader import load_qa

try:
    from pythainlp import word_tokenize
    from pythainlp.corpus import thai_stopwords
    STOPWORDS = set(thai_stopwords()) | {"กี่", "และ", "ของ", "ที่", "มี", "เป็น", "หรือ", "ได้", "ไหม", "เท่าไร", "อะไร"}
    def tokenize(text):
        return [w.strip().lower() for w in word_tokenize(text) if w.strip() not in STOPWORDS and len(w.strip()) > 2]
except ImportError:
    def tokenize(text):
        return text.lower().split()

DOCS = load_qa()


def retrieve(question, top_k=3):
    words = tokenize(question)
    scored = [(sum(w in d["text"].lower() for w in words), d) for d in DOCS]
    scored = [s for s in scored if s[0] > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:top_k]]


def bad_generate(question, context):
    if not context:
        # Simulated failure: the model still fabricates an answer even without evidence in the KB
        return "ข้าวมันไก่ 1 จานให้พลังงานประมาณ 596 แคลอรี่ และแผงโซล่าเซลล์ผลิตไฟจากแสงจันทร์ได้ 100% (ข้อมูลนี้ไม่มีอยู่จริงใน Knowledge Base)"
    return context[0]["answer"]


def grounded_generate(question, context):
    if not context:
        return "ไม่พบข้อมูลที่สนับสนุนคำตอบใน Knowledge Base"
    return context[0]["answer"]


def run():
    q_out_of_kb = "ข้าวมันไก่กี่แคล"
    q_in_kb = "ค่าใช้จ่ายและความคุ้มค่าของโซล่าเซล"

    for label, q in [("Out of KB scope", q_out_of_kb), ("In KB", q_in_kb)]:
        ctx = retrieve(q)
        print(f"--- Query ({label}): {q}")
        print("Retrieved:", [d["question"] for d in ctx] or "Not found")
        print("Bad answer :", bad_generate(q, ctx))
        print("Fixed answer:", grounded_generate(q, ctx))
        print()

    print("Cause: The generator answers even though the Retrieved Context has no supporting evidence")
    print("e.g. a question that is completely outside the scope of the Knowledge Base (solar_cell_q_a.txt)")


if __name__ == "__main__":
    run()
