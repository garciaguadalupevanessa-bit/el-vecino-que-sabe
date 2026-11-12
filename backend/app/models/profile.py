from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class FarmProfile(BaseModel):
    """Farm characteristics. Every field is optional: it is filled with whatever the user provides."""

    model_config = ConfigDict(extra="ignore")

    region: Optional[str] = Field(default=None, max_length=60)  # autonomous community
    province: Optional[str] = Field(default=None, max_length=60)
    municipality: Optional[str] = Field(default=None, max_length=100)
    farm_activities: Optional[list[Literal["agriculture", "livestock"]]] = None
    crop_types: Optional[list[str]] = Field(default=None, max_length=30)
    agricultural_area_hectares: Optional[float] = Field(default=None, ge=0)
    irrigated_hectares: Optional[float] = Field(default=None, ge=0)
    livestock_type: Optional[
        list[Literal["cattle", "sheep", "goat", "pig", "equine", "poultry", "bees", "other"]]
    ] = None
    head_count: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    production_system: Optional[Literal["extensive", "intensive", "organic", "mixed"]] = None
    legal_form: Optional[
        Literal["individual", "limited_company", "corporation", "cooperative", "joint_property", "other"]
    ] = None
    holder_age: Optional[int] = Field(default=None, ge=16, le=110)
    years_active: Optional[int] = Field(default=None, ge=0, le=80)
    pasture_hectares: Optional[float] = Field(default=None, ge=0)
    rega_registered: Optional[bool] = None  # REGA: Spanish register of livestock farms
    active_farmer: Optional[bool] = None
    goal: Optional[
        Literal["income", "start_up", "modernization", "insurance", "animal_health", "organic", "other"]
    ] = None
