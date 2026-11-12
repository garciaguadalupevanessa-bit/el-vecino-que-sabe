from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.profile import FarmProfile


# User messages are what people type; assistant messages are earlier agent answers
# that the frontend sends back as history, so they need a higher limit.
MAX_USER_CHARS = 4000
MAX_ASSISTANT_CHARS = 8000


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_ASSISTANT_CHARS)

    @field_validator("content")
    @classmethod
    def clean(cls, v: str) -> str:
        v = "".join(c for c in v if c == "\n" or c.isprintable()).strip()
        if not v:
            raise ValueError("The message cannot be empty.")
        return v

    @model_validator(mode="after")
    def user_length(self) -> "Message":
        if self.role == "user" and len(self.content) > MAX_USER_CHARS:
            raise ValueError(f"User messages cannot exceed {MAX_USER_CHARS} characters.")
        return self


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=30)
    profile: Optional[FarmProfile] = None

    @field_validator("messages")
    @classmethod
    def last_is_user(cls, v: list[Message]) -> list[Message]:
        if v[-1].role != "user":
            raise ValueError("The last message must come from the user.")
        return v


class TraceItem(BaseModel):
    tool: str
    input: dict[str, Any]
    ok: bool


class EvaluatedAid(BaseModel):
    id: str
    name: Optional[str] = None
    overall_result: Optional[Literal["met", "not_met", "unknown"]] = None
    reliability: Optional[Literal["verified", "extracted", "metadata_only"]] = None
    verification_method: Optional[Literal["human", "agent"]] = None
    status: Optional[str] = None
    scope: Optional[str] = None
    campaigns: list[str] = Field(default_factory=list)
    territories: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    verified_on: Optional[str] = None
    last_checked_on: Optional[str] = None
    requirements: list[dict[str, Any]] = Field(default_factory=list)


class Source(BaseModel):
    url: str
    name: Optional[str] = None
    verified_on: Optional[str] = None
    reliability: Optional[str] = None
    campaigns: list[str] = Field(default_factory=list)
    territories: list[str] = Field(default_factory=list)
    last_checked_on: Optional[str] = None


class CoverageNote(BaseModel):
    message: str
    territory: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    aids: list[EvaluatedAid] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    trace: list[TraceItem] = Field(default_factory=list)
    coverage_notes: list[CoverageNote] = Field(default_factory=list)
