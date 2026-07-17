"""ChromaDB knowledge store: ingestion of knowledge/*.md + top-k retrieval.

Embeddings: OpenAI text-embedding-3-small. Persistent local store under db/chroma.
"""
import os

import chromadb
from chromadb.utils import embedding_functions

from config import CHROMA_PATH, KNOWLEDGE_DIR, OPENAI_EMBED_MODEL

COLLECTION = "netpilot_knowledge"

_collection = None


def get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.environ["OPENAI_API_KEY"],
            model_name=OPENAI_EMBED_MODEL,
        )
        _collection = client.get_or_create_collection(COLLECTION, embedding_function=ef)
    return _collection


def _chunk(text: str, max_chars: int = 1400) -> list[str]:
    """Split a markdown doc on top-level '## ' headings, merging small sections."""
    parts, current = [], ""
    for block in text.split("\n## "):
        block = block if block.startswith("#") else "## " + block
        if len(current) + len(block) <= max_chars:
            current += ("\n" + block if current else block)
        else:
            if current:
                parts.append(current)
            current = block
    if current:
        parts.append(current)
    return parts


def ingest(force: bool = False) -> int:
    """Embed every knowledge/*.md into Chroma. Skips if already populated (unless force)."""
    col = get_collection()
    if col.count() > 0 and not force:
        return col.count()

    ids, docs, metas = [], [], []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        for i, chunk in enumerate(_chunk(text)):
            ids.append(f"{path.stem}-{i}")
            docs.append(chunk)
            metas.append({"source": path.name, "title": title})
    if ids:
        col.upsert(ids=ids, documents=docs, metadatas=metas)
    return col.count()


def retrieve(query: str, k: int = 3) -> list[dict]:
    """Top-k snippets for a query: [{source, title, snippet, distance}]."""
    col = get_collection()
    if col.count() == 0:
        ingest()
    res = col.query(query_texts=[query], n_results=min(k, max(col.count(), 1)))
    out = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({
            "source": meta.get("source", "?"),
            "title": meta.get("title", "?"),
            "snippet": doc,
            "distance": round(float(dist), 4),
        })
    return out
