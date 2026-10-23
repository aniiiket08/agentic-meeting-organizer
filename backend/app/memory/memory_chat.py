import logging
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.errors import ValidationFailed
from app.core.logging import setup_logging
from app.memory.vector_store import memory_store
from app.observability.tracer import trace_agent
from app.services.llm import llm_service

logger = setup_logging()


class MemoryChatResponse(BaseModel):
    answer: str = Field(min_length=1)
    citations: list[str]


@trace_agent(agent_name="memory_chat_agent")
def memory_chat(query: str, db: Session) -> dict[str, object]:
    """Memory Chat with cited answers and source meeting references."""
    if not query.strip():
        raise ValidationFailed("A meeting-memory question is required.")
    retrieved_docs = memory_store.search(query=query, top_k=3)
    if not retrieved_docs:
        raise ValidationFailed("No matching past-meeting context was found.")
    context_str = "\n".join([f"- Meeting ID {d['meeting_id']} ({d['title']}, {d['date']}): {d['text']}" for d in retrieved_docs])

    prompt = f"Answer the user query based ONLY on the provided meeting context:\n{context_str}\n\nQuery: {query}\nCite meeting titles and IDs in your response."
    result = llm_service.generate_structured(
        prompt=prompt,
        response_schema=MemoryChatResponse,
        system_prompt="Answer only from the supplied meeting context and cite its exact meeting titles.",
    )
    allowed_citations = {document["title"] for document in retrieved_docs}
    invalid_citations = set(result.citations) - allowed_citations
    if invalid_citations or not result.citations:
        logger.warning("Memory Chat returned citations outside retrieved context.")
        raise ValidationFailed("The answer did not cite retrieved meeting context.")
    return result.model_dump()
