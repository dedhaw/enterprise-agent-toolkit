"""
Vector store — semantic memory backed by ChromaDB (SQLite-persisted).
Used for RAG: store past turns and retrieve relevant context by similarity.
"""
import chromadb
from chromadb.config import Settings

from src.logger import get_logger

log = get_logger(__name__)


class VectorStore:
    def __init__(self, chroma_path: str, collection_name: str = "chat_memory") -> None:
        self._client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        log.debug("vector_store.ready", collection=collection_name, path=chroma_path)

    def add(self, session_id: str, turn_id: str, text: str) -> None:
        """Embed and store a piece of text (a conversation turn)."""
        self._collection.upsert(
            ids=[f"{session_id}:{turn_id}"],
            documents=[text],
            metadatas=[{"session_id": session_id}],
        )

    def search(self, query: str, session_id: str | None = None, n_results: int = 3) -> list[str]:
        """Return the top-N most semantically similar stored texts."""
        where = {"session_id": session_id} if session_id else None
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
            )
            return results["documents"][0] if results["documents"] else []
        except Exception as exc:
            log.warning("vector_store.search_failed", error=str(exc))
            return []
