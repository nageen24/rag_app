
# ==============================
# STREAMLIT RAG APP
# RAG Lab
# ==============================

import os
import tempfile
import streamlit as st

from rag_core import (

load_txt, load_docx, load_pdf,
chunk_text, add_chunks_to_db,
retrieve_chunks, build_prompt, ollama_chat
)

st.set_page_config(page_title="RAG (Ollama Local)", layout="wide")

st.title("RAG Application (Local Ollama)")
st.caption("""RAG App""")

# ------------------------------
# Sidebar: Upload + Index
# ------------------------------
st.sidebar.header("Step 1: Upload Documents (DOCX / PDF / TXT)")
uploaded_files = st.sidebar.file_uploader(
"Upload your training notes",
type=["docx", "pdf", "txt"],
accept_multiple_files=True

)

chunk_size = st.sidebar.slider("Chunk size (words)", 150, 500, 250,
25)
overlap = st.sidebar.slider("Overlap (words)", 0, 120, 40, 10)

st.sidebar.header("Step 2: Index Documents (Build Knowledge Base)")
if st.sidebar.button("Index / Add to Knowledge Base"):
    if not uploaded_files:
        st.sidebar.error("Please upload at least one document.")
    else:
        with st.spinner("Indexing... (chunk → embed → store)"):
            for f in uploaded_files:
                filename = f.name
                ext = os.path.splitext(filename)[1].lower()

                # Save file temporarily (loaders need a file path)
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(f.getbuffer())
                    tmp_path = tmp.name

                # Load text from file
                if ext == ".txt":
                    text = load_txt(f.getvalue())
                elif ext == ".docx":
                    text = load_docx(tmp_path)
                elif ext == ".pdf":
                    text = load_pdf(tmp_path)
                else:
                    text = ""

                if not text.strip():
                    st.warning(f"Skipped empty/unsupported file: {filename}")
                    continue

                chunks = chunk_text(text, chunk_size_words=chunk_size, overlap_words=overlap)
                add_chunks_to_db(chunks, source_name=filename)

                st.success(f"Indexed: {filename} (chunks: {len(chunks)})")

        st.sidebar.success("Indexing complete! Now ask questions.")

st.sidebar.header("Quick Checks")
st.sidebar.write("Ollama should be running in background.")
st.sidebar.code("ollama list", language="bash")
st.sidebar.write("Models needed (if missing):")

st.sidebar.code("ollama pull llama3.2:1b\nollama pull nomic-embed-text", language="bash")

# ------------------------------
# Main: Ask Questions
# ------------------------------
st.header("Ask a Question (Answers come only from your uploaded notes)")
query = st.text_input("Example: What is regression testing?")

top_k = st.slider("Top K chunks to retrieve", 2, 8, 4)

if st.button("Get Answer"):
    if not query.strip():
        st.error("Please enter a question.")
    else:
        with st.spinner("Retrieving and generating answer..."):
            hits = retrieve_chunks(query, top_k=top_k)

            if not hits:
                st.warning("No relevant content found in database.")
            else:
                prompt = build_prompt(hits, query)
                answer = ollama_chat(prompt)

                col1, col2 = st.columns([2, 1])

                with col1:
                    st.subheader("Answer")
                    st.write(answer)

                with col2:
                    st.subheader("Sources Used")
                    for i, (doc, meta) in enumerate(hits, start=1):
                        st.markdown(f"**{i}. {meta.get('source','unknown')}**")
                        st.caption("Slearner.com Notes | December 2025")
                        st.caption(doc[:220] + ("..." if len(doc) > 220 else ""))
