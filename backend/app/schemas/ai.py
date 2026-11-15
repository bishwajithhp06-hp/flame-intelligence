from pydantic import BaseModel, Field
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the sender ('user' or 'assistant')")
    content: str = Field(..., description="Content of the message")

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, description="Research question to analyze against NASA microgravity combustion records")
    investigation_filter: Optional[str] = Field(None, description="Optional acronym filter like FLEX, SAFFIRE, SPICE, etc.")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Previous conversation turns for context")

class Citation(BaseModel):
    title: str
    source: str
    identifier: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    relevance_snippet: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    investigations_referenced: List[str] = Field(default_factory=list)
    has_sufficient_evidence: bool = False
    notice: str = "Responses use retrieved local research records and their stated provenance limits. They do not constitute certified operational spacecraft safety clearances."
