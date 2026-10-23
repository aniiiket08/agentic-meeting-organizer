import json
from pathlib import Path
from typing import Any
from app.config import settings
from app.core.errors import ToolError
from app.core.logging import setup_logging

logger = setup_logging()

SEED_DATA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "seed" / "past_meetings.json"


class MemoryStore:
    """Vector / Document store for past meeting minutes RAG retrieval."""

    def __init__(self, data_path: Path = SEED_DATA_PATH):
        self.data_path = data_path
        self.documents: list[dict[str, Any]] = []
        self.load_error: str | None = None
        self._load_seed_data()

    def _load_seed_data(self) -> None:
        if not self.data_path.exists():
            self.load_error = f"Past-meeting memory file is missing: {self.data_path}"
            logger.error(self.load_error)
            return
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                documents = json.load(f)
            if not isinstance(documents, list):
                raise ValueError("Past-meeting memory must be a JSON list.")
            self.documents = documents
            logger.info("Loaded %d past meeting records into MemoryStore.", len(self.documents))
        except Exception as exc:
            self.load_error = "Past-meeting memory could not be loaded."
            logger.exception("Could not load past-meeting memory")

    def add_document(self, meeting_id: int, title: str, text: str, date_str: str) -> None:
        doc = {"meeting_id": meeting_id, "title": title, "text": text, "date": date_str}
        self.documents.append(doc)

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Semantic/keyword match search over past meeting minutes."""
        if self.load_error:
            raise ToolError(self.load_error, tool_name="memory_store.search")
        if not query.strip() or top_k <= 0:
            return []
        query_words = set(query.lower().split())
        scored_docs = []

        for doc in self.documents:
            content = f"{doc['title']} {doc['text']}".lower()
            # Calculate match score
            matches = sum(1 for word in query_words if word in content)
            scored_docs.append((matches, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs if score > 0][:top_k]


memory_store = MemoryStore()
