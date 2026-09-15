# -*- coding: utf-8 -*-
# Problem 07: Retrieval is correct, but the Generated Answer distorts the Context (Faithfulness)
# Uses a real answer from solar_cell_q_a.txt (Performance Warranty with critical technical figures)
import sys

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

from data_loader import load_qa


def find_entry(data):
    return next(d for d in data if d["question"].startswith("การรับประกันประสิทธิภาพการผลิตไฟฟ้า"))


def bad_generator(context):
    # Simulated failure: the generator unknowingly changes critical numbers and guarantees
    return context.replace("25 ปี", "5 ปี").replace("ไม่น้อยกว่า 80%", "เหลือไม่เกิน 50%")


def grounded_generator(context):
    return context


def run():
    data = load_qa()
    entry = find_entry(data)
    context = entry["answer"]

    print("Question:", entry["question"])
    print("\nRetrieved Context:")
    print(context)

    print("\nBad Generation (distorts the critical warranty duration and efficiency percentage):")
    print(bad_generator(context))

    print("\nGrounded Generation (sticks to the original Context):")
    print(grounded_generator(context))

    print("\nCause: Retrieval is correct, but the Generator changes a critical detail (warranty duration and power retention)")
    print("In technical and financial investment domains this kind of hallucination can cause severe contract misunderstanding;")
    print("the Prompt must force answers to come from Context only and Faithfulness must be evaluated")


if __name__ == "__main__":
    run()
