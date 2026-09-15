from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    tenant_id: str = Field(min_length=1)


class ChatRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    question: str = Field(min_length=1)

class Source(BaseModel):
    source: str
    page: int
    score: float
    text: str


class ChatResponse(BaseModel):
    answer: str
    risk: dict
    sources: list[Source]
    requires_human_approval: bool
    decision_trace: list[str]