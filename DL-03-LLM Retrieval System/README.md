# DL-03-Retrieval-Augmented Generation (RAG) 

Hands-on RAG project with PDF extraction, chunking, embeddings, FAISS vector database, and semantic search.

----
```text

RAG-Project/
│
├── data/                                   # เก็บเอกสารต้นฉบับ
│   ├── document.pdf                        # เอกสาร PDF สำหรับสร้างฐานความรู้
│   ├── document2.pdf                       # เอกสารเพิ่มเติม ถ้ามี
│   └── sample_questions.txt                # ตัวอย่างคำถามสำหรับทดสอบการค้นหา
│
├── outputs/                                # เก็บผลลัพธ์จากแต่ละ Lab
│   ├── extracted_text.json                 # ข้อความที่ดึงจาก PDF พร้อมเลขหน้า
│   ├── chunks.json                         # Chunk พร้อม Metadata
│   ├── embeddings.npy                      # Embedding Vector ของทุก Chunk
│   └── retrieval_results.json              # ผลการค้นหา Top-k Chunks ล่าสุด
│
├── vector_db/                              # เก็บฐานข้อมูลเวกเตอร์
│   ├── document.index                      # FAISS Index สำหรับค้นหาเวกเตอร์
│   └── chunk_store.json                    # ข้อความและ Metadata ของแต่ละ Vector
│
├── labs/                                   # โค้ดสำหรับเรียนรู้ทีละขั้น
│   ├── lab01_extract_text.py               # อ่าน PDF และดึงข้อความพร้อมเลขหน้า
│   ├── lab02_chunking.py                   # แบ่งข้อความเป็น Chunk และสร้าง Metadata
│   ├── lab03_create_embeddings.py          # แปลง Chunk เป็น Embedding Vector
│   ├── lab04_create_vector_db.py           # สร้างและบันทึก FAISS Vector Database
│   ├── lab05_query_embedding.py            # แปลงคำถามเป็น Query Vector
│   ├── lab06_similarity_search.py          # ค้นหา Top-k Chunks ที่เกี่ยวข้อง
│   └── lab07_complete_retrieval.py         # รวมทุกขั้นตอนเป็นระบบค้นคืนข้อมูล
│
├── src/                                    # ฟังก์ชันหลักสำหรับเรียกใช้ซ้ำ
│   ├── __init__.py                         # กำหนดให้ src เป็น Python Package
│   ├── document_loader.py                  # ฟังก์ชันอ่าน PDF และดึงข้อความ
│   ├── text_splitter.py                    # ฟังก์ชัน Chunking และ Chunk Overlap
│   ├── embedding_model.py                  # ฟังก์ชันโหลดและใช้งาน Embedding Model
│   ├── vector_store.py                     # ฟังก์ชันสร้าง บันทึก และโหลด FAISS
│   └── retriever.py                        # ฟังก์ชันค้นหา Top-k Chunks
│
├── config.py                               # กำหนด Path, Chunk Size, Overlap และ Top-k
├── requirements.txt                        # รายชื่อ Python Libraries ที่ต้องติดตั้ง
└── main.py                                 # โปรแกรมหลักสำหรับถามและค้นหาเอกสาร

```
