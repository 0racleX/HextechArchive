from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    content: str
    score: float
    document_id: str
    document_name: str


@dataclass
class DocumentRecord:
    id: str
    name: str
    type: str
    status: str
    error: str | None
    created_at: str
    shared: bool
