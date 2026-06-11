from __future__ import annotations
from typing import Optional
from pydantic import BaseModel

from app.api.models.business_schema import BusinessSchema, Dish, MenuCategory
from app.api.models.enums import BusinessCategory, ServiceMode, GenerationStatus


class InferSchemaRequest(BaseModel):
    project_name: str
    business_type: BusinessCategory = BusinessCategory.RESTAURANT
    description: str = ""
    service_modes: list[ServiceMode] = []
    categories: list[MenuCategory] = []
    dishes: list[Dish] = []


class GenerateRequest(BaseModel):
    business_schema: BusinessSchema

    class Config:
        populate_by_name = True


class GenerationResponse(BaseModel):
    project_id: str
    status: GenerationStatus


class ProjectSummary(BaseModel):
    id: str
    name: str
    business_type: str
    status: GenerationStatus
    created_at: str
    error: Optional[str] = None
