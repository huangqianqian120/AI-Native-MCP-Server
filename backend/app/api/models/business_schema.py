from __future__ import annotations
"""BusinessSchema — the core data model that bridges user input → LLM → code generation."""

from pydantic import BaseModel, Field, model_validator
from typing import Optional
from app.api.models.enums import ServiceMode


# ── Spec / Add-on ────────────────────────────────────────

class SpecOption(BaseModel):
    id: str = ""
    label: str
    price_delta: float = 0
    is_default: bool = False


class SpecDimension(BaseModel):
    id: str = ""
    name: str
    type: str = "single_select"  # single_select | multi_select | toggle
    is_required: bool = True
    options: list[SpecOption] = []


class AddOnItem(BaseModel):
    id: str = ""
    name: str
    price: float = 0


class AddOnGroup(BaseModel):
    id: str = ""
    name: str
    type: str = "single"  # single | multiple
    max_selections: int = 1
    items: list[AddOnItem] = []


# ── Menu ─────────────────────────────────────────────────

class MenuCategory(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    display_order: int = 0
    image_url: str = ""
    tags: list[str] = []


class Dish(BaseModel):
    id: str = ""
    name: str
    category_id: str = ""
    category_name: str = ""  # alternative: resolved to category_id at schema level
    price: float
    description: str = ""
    image_url: str = ""
    is_available: bool = True
    tags: list[str] = []
    allergens: list[str] = []
    spec_dimension_ids: list[str] = []
    add_on_groups: list[AddOnGroup] = []


# ── Store / Branch ───────────────────────────────────────

class BusinessHours(BaseModel):
    day_of_week: int  # 0=Mon .. 6=Sun
    open_time: str = "09:00"
    close_time: str = "22:00"


class Store(BaseModel):
    id: str = ""
    name: str
    address: str = ""
    latitude: float = 0
    longitude: float = 0
    phone: str = ""
    business_hours: list[BusinessHours] = []
    is_active: bool = True
    service_modes: list[ServiceMode] = []


# ── Features (LLM-inferred toggles) ─────────────────────

class FeatureFlags(BaseModel):
    has_coupons: bool = False
    has_loyalty: bool = False
    has_table_reservation: bool = False
    has_preorder: bool = False
    has_order_tracking: bool = False
    has_allergen_info: bool = False
    has_cart_editing: bool = True
    has_specs: bool = True


# ── LLM Generated Content ────────────────────────────────

class GeneratedContent(BaseModel):
    scenario_labels: list[str] = Field(default_factory=lambda: ["default", "popular", "new"])
    skill_description: str = ""
    api_descriptions: dict[str, str] = {}
    constraint_rules: list[str] = []


# ── Core Schema ──────────────────────────────────────────

class BusinessSchema(BaseModel):
    """The intermediate representation that bridges user input and code generation."""

    # Project
    project_name: str
    business_type: str = "restaurant"
    business_sub_type: str = ""

    # Service
    service_modes: list[ServiceMode] = [ServiceMode.DINE_IN]

    # Features
    features: FeatureFlags = FeatureFlags()

    # Menu
    categories: list[MenuCategory] = []
    dishes: list[Dish] = []

    # Specs
    spec_dimensions: list[SpecDimension] = []

    # Stores
    stores: list[Store] = []

    # Branding
    primary_color: str = "#5C3A21"
    logo_url: str = ""

    # LLM-generated
    generated: GeneratedContent = GeneratedContent()

    @model_validator(mode="after")
    def resolve_ids_and_names(self) -> "BusinessSchema":
        """Auto-generate IDs and resolve category_name references."""
        # 1. Auto-generate category IDs if missing
        cat_name_map = {}
        for i, cat in enumerate(self.categories):
            if not cat.id:
                cat.id = f"cat_{i + 1:02d}"
            cat_name_map[cat.name] = cat.id

        # 2. Auto-generate dish IDs and resolve category_id from category_name
        cat_id_counters: dict[str, int] = {}
        for i, dish in enumerate(self.dishes):
            if not dish.id:
                dish.id = f"dish_{i + 1:02d}"
            # Resolve category_name → category_id if category_id is empty
            if not dish.category_id and dish.category_name:
                resolved = cat_name_map.get(dish.category_name)
                if resolved:
                    dish.category_id = resolved

        # 3. Auto-generate spec dimension IDs
        for i, dim in enumerate(self.spec_dimensions):
            if not dim.id:
                dim.id = f"spec_{i + 1:02d}"
            for j, opt in enumerate(dim.options):
                if not opt.id:
                    opt.id = f"{dim.id}_opt_{j + 1:02d}"

        # 4. Auto-generate store IDs
        for i, store in enumerate(self.stores):
            if not store.id:
                store.id = f"store_{i + 1:02d}"
            if not store.name:
                store.name = f"{self.project_name} 门店_{i + 1}"

        return self
