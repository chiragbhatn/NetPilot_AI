"""CLI entrypoint: (re)build the knowledge index.

Usage: python -m rag.ingest [--force]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.store import ingest  # noqa: E402

if __name__ == "__main__":
    force = "--force" in sys.argv
    n = ingest(force=force)
    print(f"Knowledge index ready: {n} chunks in ChromaDB")
