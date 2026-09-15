# DL-05-RAG System Development II

This project demonstrates 10 common problems in LLM and RAG (Retrieval-Augmented Generation) systems. All simulations use the same real dataset, `solar_cell_q_a.txt`, which is a Thai solar cell question-answer knowledge base. This allows each problem to be tested with real data instead of isolated sample data.

# Structure:

```text
DL-05-RAG System Development II/
├── solar_cell_q_a.txt             # Raw data / Solar Cell RAG Knowledge Base (504 entries)
├── data_loader.py                 # Shared parser: solar_cell_q_a.txt -> list of dict
├── main.py                        # Main menu for running each problem
├── problem01_hallucination.py     # Hallucination / answer without supporting context
├── problem02_transformer.py       # Vocabulary Mismatch + Token Position
├── problem03_data_quality.py      # Duplicate / Noise / Normalization
├── problem04_chunking.py          # Chunk Size / Overlap
├── problem05_metadata.py          # Metadata Filtering (Category)
├── problem06_reranking.py         # Top-k / Re-ranking
├── problem07_generation.py        # Correct Retrieval but incorrect Generation (Faithfulness)
├── problem08_config.py            # RAG Configuration
├── problem09_evaluation.py        # Chunk & Retrieval Evaluation
└── problem10_debug_scripts.py     # Debugging RAG Scripts & Knowledge Base Integrity
```

# Dataset:
The project uses one shared Knowledge Base containing Thai questions and answers about Solar Cell technology, equipment, installation, legal regulations, and maintenance.

The dataset contains 504 entries, covering 12 main categories:
1. กฎหมายและการขออนุญาต
2. การติดตั้ง
3. การบำรุงรักษา
4. ความรู้พื้นฐาน
5. ค่าใช้จ่ายและความคุ้มค่า
6. ประสิทธิภาพและปัจจัยที่เกี่ยวข้อง
7. ประเภทแผงโซล่าเซลล์
8. ปัญหาที่พบบ่อยและการแก้ไข
9. ระบบโซล่าเซลล์
10. สิ่งแวดล้อม
11. อายุการใช้งานและการรับประกัน
12. อุปกรณ์ในระบบโซล่าเซลล์

Each entry has three lines:
```text
[หมวด: <category>]

Q: <question>
A: <answer>
```

# Summary:

| # | Problem | Main Idea |
|---|---------|-----------|
| 1 | Hallucination | The LLM answers without supporting context. |
| 2 | Vocabulary Mismatch / Position | BoW cannot handle colloquial phrasing or word order well. |
| 3 | Data Quality | Duplicate and noisy data reduce data quality. |
| 4 | Chunking | Poor chunk size or overlap can lose context. |
| 5 | Metadata Filtering | Filtering by category ensures domain/compliance precision. |
| 6 | Re-ranking | First-stage retrieval may rank specific documents too low. |
| 7 | Faithfulness | Retrieval is correct, but generation alters critical technical figures. |
| 8 | RAG Configuration | Configuration controls which RAG components are active. |
| 9 | Evaluation | Measure chunking and retrieval with numerical metrics. |
| 10| Debug Scripts | Inspect knowledge base integrity and diagnose zero-match queries. |

All ten simulations use the same real Knowledge Base through `data_loader.py`. 
This allows different LLM and RAG problems to be tested using the same dataset and pipeline.
