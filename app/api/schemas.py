from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    access_scope: str = Field(default="tenant")
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_users: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
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
