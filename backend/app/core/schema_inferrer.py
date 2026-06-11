"""LLM Schema inference — one-shot structured output to BusinessSchema."""

import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

from app.config import settings
from app.api.models.business_schema import (
    BusinessSchema,
    MenuCategory,
    Dish,
    SpecDimension,
    SpecOption,
    Store,
    FeatureFlags,
    GeneratedContent,
    AddOnGroup,
    AddOnItem,
)
from app.api.models.enums import ServiceMode
from app.api.models.requests import InferSchemaRequest

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a WeChat Mini Program schema architect. Your job is to analyze a business description and produce a complete BusinessSchema JSON object.

BUSINESS RULES:
1. Every dish must have at least one spec dimension (even if just "single size").
2. Category names must be distinct and business-appropriate.
3. Prices are in CNY, use integers or 0.5 increments.
4. Service modes must be realistic for the business type.
5. Spec options must have clear price deltas (default option = 0 delta).
6. Generate 2-4 scenarioLabels that represent user intent categories.
7. API descriptions must include: 前置条件 (preconditions), 调用时机 (when to call), 数据来源 (data source).
8. All IDs use short alphanumeric strings (e.g., "cat_01", "dish_07").
9. Feature toggles must be inferred from the description:
   - "loyalty", "points", "rewards" → has_loyalty = true
   - "discount", "coupon", "promo" → has_coupons = true
   - "reserve", "booking", "table" → has_table_reservation = true
   - "delivery", "deliver", "bring to" → include delivery in service_modes
10. If service_modes includes delivery, at least 1 store must have delivery enabled.
11. When has_allergen_info is true, generate allergy metadata per dish.
12. The skill_description should be a short Chinese text explaining what the skill does (max 100 chars).
13. constraint_rules should list 3-5 important rules the AI Agent must follow.
14. spec_dimensions type is always "single_select" for MVP.

OUTPUT: Respond with a valid JSON object matching the BusinessSchema structure exactly. Do not include any text outside the JSON.
"""


def _make_id(prefix: str, index: int) -> str:
    return f"{prefix}_{index:02d}"


def _build_descriptive_prompt(req: InferSchemaRequest) -> str:
    """Build the user-turn prompt from request data."""
    parts = [f"## Business Description\n{req.description}" if req.description else ""]

    if req.categories:
        cats = "\n".join(f"- {c.name}" for c in req.categories)
        parts.append(f"## Categories\n{cats}")

    if req.dishes:
        rows = []
        for d in req.dishes:
            row = f"- {d.name} | ¥{d.price} | cat: {d.category_id}"
            if d.description:
                row += f" | {d.description}"
            rows.append(row)
        parts.append("## Dishes\n" + "\n".join(rows))

    parts.append(f"## Service Modes\n{', '.join(req.service_modes) if req.service_modes else 'dineIn'}")

    parts.append(f"## Project Name\n{req.project_name}")

    return "\n\n".join(p for p in parts if p)


def _post_process(schema: BusinessSchema) -> BusinessSchema:
    """Validate and enrich schema after LLM generation."""
    # Ensure IDs
    for i, cat in enumerate(schema.categories):
        if not cat.id:
            cat.id = _make_id("cat", i + 1)
    for i, dish in enumerate(schema.dishes):
        if not dish.id:
            dish.id = _make_id("dish", i + 1)
    for i, dim in enumerate(schema.spec_dimensions):
        if not dim.id:
            dim.id = _make_id("spec", i + 1)
        for j, opt in enumerate(dim.options):
            if not opt.id:
                opt.id = _make_id(f"{dim.id}_opt", j + 1)
    for i, store in enumerate(schema.stores):
        if not store.id:
            store.id = _make_id("store", i + 1)

    # Autodetect features
    if len(schema.spec_dimensions) > 0:
        schema.features.has_specs = True

    # Default stores if none
    if not schema.stores:
        schema.stores = [
            Store(
                id="store_01",
                name=f"{schema.project_name} 总店",
                service_modes=schema.service_modes,
            )
        ]

    return schema


class SchemaInferrer:
    def __init__(self):
        self.client: AsyncAnthropic | None = None
        if settings.anthropic_api_key:
            self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def infer(self, req: InferSchemaRequest) -> BusinessSchema:
        # If no LLM configured, return a template-based fallback schema
        if not self.client:
            logger.warning("No Anthropic API key configured; returning template schema")
            return self._build_template_schema(req)

        prompt = _build_descriptive_prompt(req)
        try:
            resp = await self.client.messages.create(
                model=settings.llm_model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text
            # Extract JSON from response (handle potential markdown fences)
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data: dict[str, Any] = json.loads(text)
            schema = BusinessSchema.model_validate(data)
        except Exception as e:
            logger.error(f"LLM schema inference failed: {e}")
            raise ValueError(f"Failed to infer schema from LLM response: {e}") from e

        return _post_process(schema)

    def _build_template_schema(self, req: InferSchemaRequest) -> BusinessSchema:
        """Build a reasonable schema without LLM, for dev/testing."""
        cats = req.categories or [
            MenuCategory(id="cat_01", name="推荐", display_order=0),
            MenuCategory(id="cat_02", name="经典", display_order=1),
        ]
        dishes = req.dishes or []
        if not dishes:
            dishes = [
                Dish(id="dish_01", name="招牌拿铁", category_id="cat_01", price=22, description="香浓拿铁"),
                Dish(id="dish_02", name="美式咖啡", category_id="cat_01", price=18, description="经典美式"),
                Dish(id="dish_03", name="抹茶拿铁", category_id="cat_02", price=24, description="日式抹茶"),
            ]

        dims = [
            SpecDimension(
                id="spec_01", name="温度", options=[
                    SpecOption(id="spec_01_opt_01", label="冰", is_default=True),
                    SpecOption(id="spec_01_opt_02", label="热"),
                ],
            ),
            SpecDimension(
                id="spec_02", name="糖度", options=[
                    SpecOption(id="spec_02_opt_01", label="无糖"),
                    SpecOption(id="spec_02_opt_02", label="少糖"),
                    SpecOption(id="spec_02_opt_03", label="标准", is_default=True),
                    SpecOption(id="spec_02_opt_04", label="多糖"),
                ],
            ),
        ]

        return _post_process(BusinessSchema(
            project_name=req.project_name,
            business_type=req.business_type,
            service_modes=req.service_modes or [ServiceMode.DINE_IN],
            categories=cats,
            dishes=dishes,
            spec_dimensions=dims,
            generated=GeneratedContent(
                scenario_labels=["default", "coffee", "tea"],
                skill_description=f"{req.project_name} — AI 驱动的在线点单助手",
                constraint_rules=[
                    "禁止编造菜品 ID、规格值、价格",
                    "必须先调用搜索/推荐接口获取有效的 dishId，才能调 selectDish",
                    "支付成功前禁止向用户宣布已支付",
                ],
            ),
        ))
