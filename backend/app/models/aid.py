from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator

Reliability = Literal["verified", "extracted", "metadata_only"]


class AidCitation(BaseModel):
    source_url: HttpUrl
    title: Optional[str] = None
    locator: str = Field(min_length=1, max_length=300)
    quote: str = Field(min_length=1, max_length=4000)
    payload_sha256: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class Requirement(BaseModel):
    """An evaluable requirement (field/operator/value) or a reference to a reusable block (ref)."""

    ref: Optional[str] = None
    description: Optional[str] = None
    field: Optional[str] = None  # None = not evaluable by code
    operator: Optional[Literal["==", "<=", ">=", "in"]] = None
    value: Optional[Any] = None
    source_url: Optional[str] = None
    citation: Optional[AidCitation] = None
    needs_verification: bool = False

    @model_validator(mode="after")
    def check(self):
        if self.ref:
            return self
        if not self.description:
            raise ValueError("A requirement without 'ref' needs a 'description'.")
        if self.field and not (self.operator and self.value is not None):
            raise ValueError("A requirement with a 'field' needs an 'operator' and a 'value'.")
        return self


class AidTerritory(BaseModel):
    """A normalized place where an aid applies, with optional hierarchy linkage."""

    level: Literal["national", "autonomous_community", "province", "municipality"]
    name: str
    code: Optional[str] = None
    parent_code: Optional[str] = None


class AidDocumentVersion(BaseModel):
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    retrieved_at: datetime
    stored_object_uri: Optional[str] = None


class AidSourceDocument(BaseModel):
    bdns_document_id: Optional[int] = Field(default=None, gt=0)
    title: str
    source_url: HttpUrl
    content_sha256: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    versions: list[AidDocumentVersion] = Field(default_factory=list)


class AidReviewEvent(BaseModel):
    reviewer: str
    status: Literal["reviewed", "accepted_for_extraction", "verified", "reopened", "rejected"]
    reviewed_at: datetime
    notes: str = ""
    citations: list[AidCitation] = Field(default_factory=list)


class AidBDNSReference(BaseModel):
    """Campaign-specific link from a user-facing aid to its official BDNS source call."""

    bdns_code: str = Field(min_length=1, max_length=40)
    campaign_year: Optional[int] = Field(default=None, ge=1900, le=2200)
    campaign_label: Optional[str] = Field(default=None, max_length=120)
    status: Literal["discovered", "extracted", "reviewed", "verified", "withdrawn"] = "discovered"
    documents: list[AidSourceDocument] = Field(default_factory=list)
    citations: list[AidCitation] = Field(default_factory=list)
    review_history: list[AidReviewEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def verified_source_has_citation(self):
        cited = bool(self.citations) or any(
            event.status == "verified" and event.citations for event in self.review_history
        )
        if self.status == "verified" and not cited:
            raise ValueError("A verified BDNS source reference needs an official citation.")
        return self


class Aid(BaseModel):
    id: str
    name: str
    agency: str
    scope: str  # "national" or the name of a region
    territories: list[AidTerritory] = Field(default_factory=list)
    bdns_calls: list[AidBDNSReference] = Field(default_factory=list)
    status: Literal["active", "upcoming", "closed", "withdrawn", "unknown"] = "unknown"
    aid_type: Literal[
        "cap_direct", "cap_coupled", "eco_scheme", "start_up",
        "modernization", "rural_development", "agri_insurance", "animal_health", "other",
    ]
    short_description: str
    farm_activities: list[str] = ["all"]
    livestock_type: list[str]  # profile values, or "all"
    production_system: list[str] = ["all"]
    goals: list[str] = []
    requirements: list[Requirement]
    how_to_apply: list[str] = []
    documents: list[str] = []
    deadline: Optional[str] = None
    open: Optional[bool] = None  # None = unknown
    amount: Optional[str] = None
    alternatives: list[str] = []
    reliability: Reliability
    source_url: str
    verified_on: str  # ISO date, e.g. "2026-11-11"
    verified_by: Optional[str] = None
    verification_method: Literal["human", "agent"] = "human"
    notes: Optional[str] = None

    @model_validator(mode="after")
    def check_reliability(self):
        if self.reliability == "verified" and not self.verified_by:
            raise ValueError(f"{self.id}: a 'verified' aid needs 'verified_by'.")
        if self.reliability == "verified" and any(
            requirement.field and (requirement.needs_verification or requirement.citation is None)
            for requirement in self.requirements
        ):
            raise ValueError(f"{self.id}: every evaluable verified rule needs an official citation and no verification flag.")
        codes = [item.bdns_code for item in self.bdns_calls]
        if len(codes) != len(set(codes)):
            raise ValueError(f"{self.id}: duplicated BDNS call references are not allowed.")
        return self
