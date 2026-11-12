"""Validated actions for the internal BDNS source review workflow."""

from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator


class BDNSReviewSubmission(BaseModel):
    expected_payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer: str = Field(min_length=2, max_length=120)
    decision: Literal["accepted_for_extraction", "out_of_scope"]
    notes: str = Field(min_length=1, max_length=2000)

    @field_validator("reviewer")
    @classmethod
    def trim_reviewer(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Reviewer identity must contain at least two characters.")
        return value

    @field_validator("notes")
    @classmethod
    def trim_notes(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A review reason is required.")
        return value


ClassificationCategory = Literal[
    "pac_direct", "pac_coupled", "young_farmer_startup", "farm_modernisation",
    "agro_environment_organic", "agricultural_insurance", "animal_health",
    "extensive_livestock", "native_breeds", "investment", "emergency_aid",
]
FarmActivity = Literal["agriculture", "livestock", "mixed"]


class BDNSClassificationEvidence(BaseModel):
    source_url: AnyHttpUrl
    locator: str = Field(min_length=2, max_length=240)
    quote: str = Field(min_length=3, max_length=1200)

    @field_validator("locator", "quote")
    @classmethod
    def trim_evidence_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("La cita y su localizador no pueden estar vacíos.")
        return value


class BDNSClassificationSubmission(BaseModel):
    expected_payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer: str = Field(min_length=2, max_length=120)
    categories: list[ClassificationCategory] = Field(min_length=1, max_length=11)
    activities: list[FarmActivity] = Field(min_length=1, max_length=3)
    campaign_year: int | None = Field(default=None, ge=1900, le=2200)
    campaign_label: str | None = Field(default=None, max_length=120)
    evidence: list[BDNSClassificationEvidence] = Field(min_length=1, max_length=30)
    notes: str = Field(min_length=1, max_length=2000)

    @field_validator("reviewer", "notes", "campaign_label")
    @classmethod
    def trim_classification_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("El texto no puede estar vacío.")
        return value

    @model_validator(mode="after")
    def validate_unique_dimensions(self):
        if len(set(self.categories)) != len(self.categories):
            raise ValueError("No repitas categorías.")
        if len(set(self.activities)) != len(self.activities):
            raise ValueError("No repitas actividades.")
        if "mixed" in self.activities and len(self.activities) > 1:
            raise ValueError("La actividad mixta no se combina con agricultura o ganadería por separado.")
        if self.campaign_year is not None:
            campaign_evidence = any(
                str(self.campaign_year) in f"{item.locator} {item.quote}"
                and any(word in f"{item.locator} {item.quote}".casefold() for word in ("campaña", "campana", "ejercicio"))
                for item in self.evidence
            )
            if not campaign_evidence:
                raise ValueError("El año de campaña requiere una cita que lo identifique explícitamente.")
        if self.campaign_label is not None and not any(
            self.campaign_label.casefold() in f"{item.locator} {item.quote}".casefold()
            for item in self.evidence
        ):
            raise ValueError("La etiqueta de campaña requiere una cita que la mencione explícitamente.")
        return self

class BDNSExtractionReviewSubmission(BaseModel):
    expected_payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_extraction_fingerprint: str = Field(default="", max_length=128)
    reviewer: str = Field(min_length=2, max_length=120)
    decision: Literal["reviewed_candidate", "needs_correction"]
    notes: str = Field(min_length=1, max_length=2000)

    @field_validator("reviewer")
    @classmethod
    def trim_reviewer(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Reviewer identity must contain at least two characters.")
        return value

    @field_validator("notes")
    @classmethod
    def trim_notes(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A review reason is required.")
        return value


class ApprovedBDNSRule(BaseModel):
    statement: str = Field(min_length=5, max_length=2000)
    source_url: AnyHttpUrl
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, min_length=1, max_length=240)

    @field_validator("statement", "section")
    @classmethod
    def trim_rule_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Rule text and source locator cannot be blank.")
        return value

    @model_validator(mode="after")
    def require_locator(self):
        if self.page is None and not self.section:
            raise ValueError("An approved rule needs a page or section citation.")
        return self


class BDNSVerificationSubmission(BaseModel):
    expected_payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_extraction_fingerprint: str = Field(min_length=1, max_length=128)
    reviewer: str = Field(min_length=2, max_length=120)
    notes: str = Field(min_length=1, max_length=2000)
    approved_rules: list[ApprovedBDNSRule] = Field(min_length=1, max_length=50)

    @field_validator("reviewer")
    @classmethod
    def trim_reviewer(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Reviewer identity must contain at least two characters.")
        return value

    @field_validator("notes")
    @classmethod
    def trim_notes(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A source review note is required.")
        return value
