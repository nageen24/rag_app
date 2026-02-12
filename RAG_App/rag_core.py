# ==============================
# RAG CORE MODULE
# RAG Lab 
# ==============================

import os
import re
import requests

from chromadb.config import Settings
import chromadb
from docx import Document
from pypdf import PdfReader

# ------------------------------
# CONFIG
# ------------------------------

OLLAMA_BASE_URL = "http://localhost:11434"
CHAT_MODEL = "gemma3:4b"
EMBED_MODEL = "nomic-embed-text"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "rag_db")
COLLECTION_NAME = "notes"

BRANDING_FOOTER = "RAG Lab"

# ------------------------------
# LOADERS
# ------------------------------
def load_txt(file_bytes):
    return file_bytes.decode("utf-8", errors="ignore")


def load_docx(file_path: str) -> str:
    doc = Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def load_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        if txt.strip():
           pages.append(txt)
    return "\n".join(pages)

# ------------------------------
# CHUNKING
# ------------------------------
def chunk_text(text: str, chunk_size_words: int = 250, overlap_words: int = 40):
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split(" ")

    chunks = []
    start = 0
    step = max(1, chunk_size_words - overlap_words)

    while start < len(words):
        chunk = " ".join(words[start:start + chunk_size_words]).strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks

# ------------------------------
# OLLAMA: EMBED + CHAT
# ------------------------------
def ollama_embed(text: str):
    url = f"{OLLAMA_BASE_URL}/api/embeddings"
    payload = {"model": EMBED_MODEL, "prompt": text}
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["embedding"]


def ollama_chat(prompt: str):
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful trainer for Slearner.com. "
                    "Answer ONLY using the provided context. "
                    "If the answer is not found, say: "
                    "'Not found in the documents (Slearner.com, Dec 2025).' "
                    f"Always end every answer with this exact footer line: {BRANDING_FOOTER}"
                )
            },
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "options": {"temperature": 0.2}
    }

    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    content = r.json()["message"]["content"].strip()

    if not content:
        content = "Not found in the documents (Slearner.com, Dec 2025)."

    if BRANDING_FOOTER not in content:
        content = f"{content}\n\n{BRANDING_FOOTER}"

    return content
# ------------------------------
# CHROMADB
# ------------------------------

def get_collection():
    client = chromadb.Client()  # new style
    return client.get_or_create_collection("my_collection")





def add_chunks_to_db(chunks, source_name: str):
    col = get_collection()

    ids, embs, docs, metas = [], [], [], []

    for i, chunk in enumerate(chunks):
        ids.append(f"{source_name}_{i}")
        embs.append(ollama_embed(chunk))
        docs.append(chunk)
        metas.append({
            "source": source_name,
            "brand": "Practice Project",
            "date": "2026"
        })

    col.add(ids=ids, embeddings=embs, documents=docs, metadatas=metas)


def retrieve_chunks(query: str, top_k: int = 4):
    col = get_collection()
    q_emb = ollama_embed(query)

    res = col.query(query_embeddings=[q_emb], n_results=top_k)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]

    return list(zip(docs, metas))


# ------------------------------
# PROMPT
# ------------------------------
def build_prompt(context_chunks, question: str):
    context_text = ""
    for idx, (chunk, meta) in enumerate(context_chunks, start=1):
        src = meta.get("source", "Unknown Source")
        context_text += f"[Source {idx}: {src} Practice ]\n{chunk}\n\n"

    return f"""CONTEXT:
{context_text}
QUESTION:
{question}
ANSWER:
"""
