from __future__ import annotations
"""Generator orchestrator — takes a BusinessSchema and produces a downloadable ZIP."""

import json
import logging
from pathlib import Path
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.api.models.business_schema import BusinessSchema
from app.api.models.enums import GenerationStatus, ServiceMode
from app.core.api_deriver import derive_apis, derive_categories_for_enum
from app.core.file_writer import FileWriter
from app.core.zip_packer import pack_to_zip
from app.db.session import async_session
from app.models.project import Project

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
RESTAURANT_DIR = TEMPLATES_DIR / "restaurant"


def _build_jinja_env() -> Environment:
    """Create a Jinja2 environment configured for .j2 templates."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(default=False),
        # Use {$ $} for Jinja variables (avoid conflict with WXML {{ }})
        variable_start_string="{$",
        variable_end_string="$}",
        block_start_string="{%",
        block_end_string="%}",
        comment_start_string="{#",
        comment_end_string="#}",
        keep_trailing_newline=True,
    )
    env.globals["now"] = datetime.utcnow
    return env


def _collect_static_files() -> list[tuple[str, str]]:
    """Return list of (relative_path, template_name) for static/straight-copy files."""
    return [
        ("app.js", "base/app.js.j2"),
        ("app.wxss", "base/app.wxss.j2"),
        ("project.config.json", "base/project.config.json.j2"),
        ("sitemap.json", "base/sitemap.json.j2"),
        ("page-meta.json", "base/page-meta.json.j2"),
    ]


def _build_api_variables(schema: BusinessSchema) -> list[dict]:
    """Build per-API variable dicts for template injection."""
    apis = derive_apis(schema)
    cat_ids = [c.id for c in schema.categories]
    dish_map = {d.id: d for d in schema.dishes}
    spec_map = {s.id: s for s in schema.spec_dimensions}

    vars_list = []
    for api in apis:
        base_vars = {
            "api_name": api["name"],
            "desc": api["description"],
            "requires_component": api.get("requires_component", False),
            "categories": [c.model_dump() for c in schema.categories],
            "dishes": [d.model_dump() for d in schema.dishes],
            "spec_dimensions": [s.model_dump() for s in schema.spec_dimensions],
            "stores": [s.model_dump() for s in schema.stores],
            "service_modes": [m.value for m in schema.service_modes],
            "project_name": schema.project_name,
            "primary_color": schema.primary_color,
        }
        vars_list.append(base_vars)
    return vars_list


async def generate_project(schema: BusinessSchema, output_dir: Path) -> str:
    """Core generation logic: templates → files → ZIP. Returns ZIP path."""
    env = _build_jinja_env()
    writer = FileWriter(output_dir)

    # ── 1. Write static files ──
    for rel_path, tmpl_name in _collect_static_files():
        tmpl = env.get_template(tmpl_name)
        content = tmpl.render(schema=schema)
        writer.write(rel_path, content)

    # ── 2. Write app.json ──
    app_json_tmpl = env.get_template("restaurant/app.json.j2")
    app_json_content = app_json_tmpl.render(schema=schema, apis=derive_apis(schema))
    writer.write("app.json", app_json_content)

    # ── 3. Write SKILL.md ──
    skill_tmpl = env.get_template("restaurant/skills/restaurant-skill/SKILL.md.j2")
    skill_content = skill_tmpl.render(schema=schema, apis=derive_apis(schema))
    writer.write("skills/restaurant-skill/SKILL.md", skill_content)

    # ── 4. Write mcp.json ──
    mcp_tmpl = env.get_template("restaurant/skills/restaurant-skill/mcp.json.j2")
    mcp_content = mcp_tmpl.render(schema=schema, apis=derive_apis(schema))
    writer.write("skills/restaurant-skill/mcp.json", mcp_content)

    # ── 5. Write index.js ──
    index_tmpl = env.get_template("restaurant/skills/restaurant-skill/index.js.j2")
    index_content = index_tmpl.render(schema=schema, apis=derive_apis(schema))
    writer.write("skills/restaurant-skill/index.js", index_content)

    # ── 6. Write API implementations ──
    api_base_tmpl = env.get_template("restaurant/skills/restaurant-skill/apis/api-base.js.j2")
    api_vars = _build_api_variables(schema)
    for av in api_vars:
        content = api_base_tmpl.render(**av)
        writer.write(f"skills/restaurant-skill/apis/{av['api_name']}.js", content)

    # ── 7. Write data/seed.js ──
    seed_tmpl = env.get_template("restaurant/skills/restaurant-skill/utils/seed.js.j2")
    seed_content = seed_tmpl.render(schema=schema)
    writer.write("skills/restaurant-skill/data/seed.js", seed_content)

    # ── 8. Write utils ──
    utils = ["storage.js", "validation.js", "id-generator.js"]
    for u in utils:
        tmpl = env.get_template(f"restaurant/skills/restaurant-skill/utils/{u}.j2")
        content = tmpl.render(schema=schema)
        writer.write(f"skills/restaurant-skill/utils/{u}", content)

    # ── 9. Write card components ──
    # Only write components for active APIs
    active_apis = {a["name"] for a in derive_apis(schema) if a.get("requires_component")}
    component_map = {
        "getNearbyStores": "store-list",
        "getMenu": "menu-view",
        "getDishDetail": "dish-detail-card",
        "searchDishes": "dish-detail-card",
        "getRecommendations": "menu-view",
        "addToCart": "cart-summary-card",
        "getCart": "cart-summary-card",
        "removeFromCart": "cart-summary-card",
        "submitOrder": "order-confirm-card",
        "payOrder": "pay-success-card",
        "getOrderHistory": "order-list-card",
        "getOrderDetail": "order-list-card",
        "quickReorder": "order-confirm-card",
        "trackOrder": "order-tracking-card",
        "getCoupons": "coupon-list-card",
        "reserveTable": "reservation-card",
    }
    rendered_components = set()
    for api_name in active_apis:
        comp_name = component_map.get(api_name)
        if comp_name and comp_name not in rendered_components:
            for ext in ["js", "json", "wxml", "wxss"]:
                tmpl = env.get_template(
                    f"restaurant/skills/restaurant-skill/components/{comp_name}/index.{ext}.j2"
                )
                content = tmpl.render(schema=schema, api_name=api_name)
                writer.write(
                    f"skills/restaurant-skill/components/{comp_name}/index.{ext}",
                    content,
                )
            rendered_components.add(comp_name)

    # ── 10. Write home page ──
    for ext in ["js", "json", "wxml", "wxss"]:
        tmpl = env.get_template(f"restaurant/pages/home/home.{ext}.j2")
        content = tmpl.render(schema=schema)
        writer.write(f"pages/home/home.{ext}", content)

    # ── 11. Write half-pages ──
    half_pages = ["sku-picker", "address-editor"]
    for hp in half_pages:
        for ext in ["js", "json", "wxml", "wxss"]:
            tmpl = env.get_template(
                f"restaurant/packageDetail/pages/{hp}/index.{ext}.j2"
            )
            content = tmpl.render(schema=schema)
            writer.write(f"packageDetail/pages/{hp}/index.{ext}", content)

    # ── ZIP ──
    zip_dir = Path(settings.output_dir) / "zips"
    zip_path = pack_to_zip(output_dir, zip_dir / f"{schema.project_name}-ai-native.zip")

    logger.info(f"Generated {writer.file_count} files → {zip_path}")
    return str(zip_path)


class GeneratorService:
    """Background task wrapper for generate_project."""

    async def generate(self, project_id: str, schema: BusinessSchema, db=None):
        output_dir = Path(settings.output_dir) / "projects" / project_id
        try:
            zip_path = await generate_project(schema, output_dir)
            async with async_session() as session:
                project = await session.get(Project, project_id)
                if project:
                    project.status = GenerationStatus.READY
                    project.zip_path = zip_path
                    await session.commit()
        except Exception as e:
            logger.exception(f"Generation failed for {project_id}: {e}")
            async with async_session() as session:
                project = await session.get(Project, project_id)
                if project:
                    project.status = GenerationStatus.FAILED
                    project.error = str(e)
                    await session.commit()
