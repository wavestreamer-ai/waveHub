"""
Private RAG — local document indexing for agent training.

Documents stay on the user's machine. Platform never sees them.
Uses ChromaDB for local vector storage and Ollama for embeddings.

Storage: ~/.wavestreamer/private_training/{agent_id}/chroma_db
"""

import hashlib
import logging
import time
from pathlib import Path

import requests

from .document_parser import parse_document, supported_extensions

logger = logging.getLogger("wavestreamer_runner.private_rag")

_DEFAULT_BASE = Path.home() / ".wavestreamer" / "private_training"
_EMBED_BATCH = 8
_OLLAMA_URL = "http://localhost:11434"
_EMBED_MODELS = ["mxbai-embed-large", "nomic-embed-text"]


class PrivateRAG:
    """Local document indexing for a single agent."""

    def __init__(self, agent_id: str, db_path: str | Path | None = None, ollama_url: str = ""):
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "Private training requires chromadb: pip install wavestreamer-runner[training]"
            )

        self.agent_id = agent_id
        self.ollama_url = (ollama_url or _OLLAMA_URL).rstrip("/")
        self._embed_model: str | None = None

        path = Path(db_path) if db_path else _DEFAULT_BASE / agent_id / "chroma_db"
        path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(path))
        self._docs_col = self._client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Private RAG initialized: agent=%s path=%s", agent_id, path)

    def add_document(self, file_path: Path | str) -> dict:
        """Parse and index a single document.

        Returns: {"doc_id": str, "doc_type": str, "chunks": int, "file": str}
        """
        file_path = Path(file_path)
        doc_type, chunks = parse_document(file_path)

        if not chunks:
            logger.warning("No text extracted from %s", file_path.name)
            return {"doc_id": "", "doc_type": doc_type, "chunks": 0, "file": file_path.name}

        # Hash file content for dedup
        file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()[:16]
        doc_id = f"{file_path.stem}_{file_hash}"

        # Check if already indexed
        existing = self._docs_col.get(where={"doc_id": doc_id})
        if existing and existing["ids"]:
            logger.info("Document already indexed: %s (%d chunks)", file_path.name, len(existing["ids"]))
            return {"doc_id": doc_id, "doc_type": doc_type, "chunks": len(existing["ids"]), "file": file_path.name}

        # Embed and upsert in batches
        total_indexed = 0
        for i in range(0, len(chunks), _EMBED_BATCH):
            batch = chunks[i:i + _EMBED_BATCH]
            embeddings = self._embed(batch)
            if not embeddings:
                logger.warning("Embedding failed for batch %d of %s", i // _EMBED_BATCH, file_path.name)
                continue

            ids = [f"{doc_id}_chunk_{i + j}" for j in range(len(batch))]
            metas = [
                {
                    "doc_id": doc_id,
                    "file": file_path.name,
                    "doc_type": doc_type,
                    "chunk_index": i + j,
                    "indexed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
                for j in range(len(batch))
            ]
            self._docs_col.upsert(ids=ids, documents=batch, embeddings=embeddings, metadatas=metas)
            total_indexed += len(batch)

        logger.info("Indexed %s: %d chunks (%s)", file_path.name, total_indexed, doc_type)
        return {"doc_id": doc_id, "doc_type": doc_type, "chunks": total_indexed, "file": file_path.name}

    def add_directory(self, dir_path: Path | str, recursive: bool = True) -> dict:
        """Index all supported documents in a directory.

        Returns: {"total_files": int, "total_chunks": int, "files": [dict]}
        """
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        exts = set(supported_extensions())
        pattern = "**/*" if recursive else "*"
        files = [f for f in dir_path.glob(pattern) if f.is_file() and f.suffix.lower() in exts]

        results = []
        total_chunks = 0
        for f in sorted(files):
            try:
                result = self.add_document(f)
                results.append(result)
                total_chunks += result["chunks"]
            except Exception as e:
                logger.error("Failed to index %s: %s", f.name, e)
                results.append({"file": f.name, "chunks": 0, "error": str(e)})

        return {"total_files": len(results), "total_chunks": total_chunks, "files": results}

    def query(self, text: str, top_k: int = 5) -> list[dict]:
        """Search private documents for relevant context.

        Returns: [{"document": str, "relevance": float, "source": str, "chunk_index": int}]
        """
        if self._docs_col.count() == 0:
            return []

        embedding = self._embed([text])
        if not embedding:
            return []

        results = self._docs_col.query(
            query_embeddings=embedding,
            n_results=min(top_k, self._docs_col.count()),
            include=["documents", "metadatas", "distances"],
        )

        output = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            output.append({
                "document": doc,
                "relevance": max(0.0, 1.0 - dist),
                "source": meta.get("file", "unknown"),
                "chunk_index": meta.get("chunk_index", 0),
            })

        return output

    def build_context(self, question: str, max_chars: int = 3000) -> str:
        """Build a context block for LLM injection from private documents.

        Returns formatted string or empty string if no relevant docs.
        """
        results = self.query(question, top_k=5)
        if not results:
            return ""

        sections = []
        total = 0
        for r in results:
            if r["relevance"] < 0.3:
                continue
            entry = f"[{r['source']}] (relevance: {r['relevance']:.0%})\n{r['document']}"
            if total + len(entry) > max_chars:
                break
            sections.append(entry)
            total += len(entry) + 2

        if not sections:
            return ""

        return "PRIVATE TRAINING DATA:\n" + "\n\n".join(sections)

    def stats(self) -> dict:
        """Return document statistics."""
        count = self._docs_col.count()
        # Get unique doc_ids
        if count == 0:
            return {"chunks": 0, "documents": 0}

        all_meta = self._docs_col.get(include=["metadatas"])
        doc_ids = set()
        for m in all_meta.get("metadatas", []):
            if m:
                doc_ids.add(m.get("doc_id", ""))
        doc_ids.discard("")

        return {"chunks": count, "documents": len(doc_ids)}

    def remove_document(self, doc_id: str) -> int:
        """Remove all chunks for a document. Returns number of chunks deleted."""
        existing = self._docs_col.get(where={"doc_id": doc_id})
        if not existing or not existing["ids"]:
            return 0
        self._docs_col.delete(ids=existing["ids"])
        return len(existing["ids"])

    # --- Embedding ---

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via Ollama. Returns list of vectors or empty list on failure."""
        if not texts:
            return []

        model = self._detect_model()
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/embed",
                json={"model": model, "input": texts},
                timeout=300,
            )
            resp.raise_for_status()
            embeddings = resp.json().get("embeddings", [])
            if len(embeddings) != len(texts):
                logger.warning("Expected %d embeddings, got %d", len(texts), len(embeddings))
                return []
            return embeddings
        except Exception as e:
            logger.error("Embedding failed (%s): %s", model, e)
            return []

    def _detect_model(self) -> str:
        """Find the best available embedding model from Ollama."""
        if self._embed_model:
            return self._embed_model

        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
            if resp.ok:
                available = {m["name"].split(":")[0] for m in resp.json().get("models", [])}
                for model in _EMBED_MODELS:
                    if model in available:
                        self._embed_model = model
                        logger.info("Using embedding model: %s", model)
                        return model
        except Exception:
            pass

        # Auto-pull fallback
        fallback = _EMBED_MODELS[-1]
        logger.info("Pulling embedding model: %s", fallback)
        try:
            requests.post(f"{self.ollama_url}/api/pull", json={"name": fallback}, timeout=600)
        except Exception as e:
            logger.warning("Failed to pull %s: %s", fallback, e)
        self._embed_model = fallback
        return fallback
