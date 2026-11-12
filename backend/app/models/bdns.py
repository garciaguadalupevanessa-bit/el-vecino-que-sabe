"""Validated shape for the canonical BDNS source record persisted by the importer."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _SourceModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class BDNSIdentity(_SourceModel):
    system: Literal["BDNS"]
    bdns_code: str = Field(min_length=1, max_length=40)
    bdns_internal_id: int | None = None
    detail_url: str


class BDNSSourceState(_SourceModel):
    retrieved_at: str
    payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")


class BDNSCallMetadata(_SourceModel):
    title: str = Field(min_length=1)
    territories: list[dict[str, Any]] = Field(default_factory=list)
    campaign: dict[str, Any]
    farm_activity_classification: dict[str, Any]


class BDNSApplication(_SourceModel):
    status: Literal["unknown", "not_announced", "upcoming", "open", "closed", "indefinite", "not_applicable"]


class BDNSQuality(_SourceModel):
    reliability: Literal["metadata_only", "extracted", "verified"]
    eligibility_status: Literal["not_assessed", "conditional", "reviewed"]


class BDNSCanonicalRecord(_SourceModel):
    schema_version: Literal["1.0"]
    source_identity: BDNSIdentity
    source_state: BDNSSourceState
    call: BDNSCallMetadata
    application: BDNSApplication
    sources: dict[str, Any]
    quality: BDNSQuality
    source_payload: dict[str, Any]

    @model_validator(mode="after")
    def check_consistent_source_identity(self):
        if self.source_state.payload_sha256 != self.source_state.snapshot_id:
            raise ValueError("snapshot_id must match payload_sha256")
        if self.quality.reliability == "metadata_only" and self.quality.eligibility_status != "not_assessed":
            raise ValueError("metadata-only BDNS records cannot claim assessed eligibility")
        documents = self.sources.get("documents", [])
        if not isinstance(documents, list):
            raise ValueError("sources.documents must be a list")
        if any(not isinstance(item, dict) for item in documents):
            raise ValueError("each item in sources.documents must be an object")
        ids = [item.get("bdns_document_id") for item in documents
               if isinstance(item, dict) and item.get("bdns_document_id") is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("sources.documents contains duplicate BDNS document IDs")
        return self
