from __future__ import annotations
"""Derive the set of atomic interfaces to generate from BusinessSchema features."""

from app.api.models.business_schema import BusinessSchema, Dish, MenuCategory
from app.api.models.enums import ServiceMode

# Each atomic interface: name, description_template, requires_component
API_DEFINITIONS = {
    # ── Store ──
    "getNearbyStores": {
        "description": "获取附近门店列表。用户表达想去门店/吃饭时调用。",
        "requires_component": True,
    },
    # ── Menu ──
    "getMenu": {
        "description": "获取门店菜单（含分类）。用户已选定门店后调用。",
        "requires_component": True,
    },
    "getDishDetail": {
        "description": "获取菜品详情，含规格选项和推荐搭配。",
        "requires_component": True,
    },
    "searchDishes": {
        "description": "按关键词搜索菜品。用户说出具体菜品名时调用。",
        "requires_component": True,
    },
    "getRecommendations": {
        "description": "获取推荐菜品列表。用户模糊表达想吃东西时调用。",
        "requires_component": True,
    },
    # ── Cart ──
    "addToCart": {
        "description": "加菜到购物车。用户选中菜品及规格后调用。",
        "requires_component": True,
    },
    "getCart": {
        "description": "查看当前购物车内容。",
        "requires_component": True,
    },
    "removeFromCart": {
        "description": "从购物车移除菜品。用户说不要XX时调用。",
        "requires_component": True,
    },
    # ── Order ──
    "submitOrder": {
        "description": "提交购物车生成订单。用户确认下单后调用。",
        "requires_component": True,
    },
    "payOrder": {
        "description": "发起订单支付。订单状态必须为confirmed。调用成功前禁止说'已支付'。",
        "requires_component": True,
    },
    "getOrderHistory": {
        "description": "查询用户历史订单。用户说'我的订单'时调用。",
        "requires_component": True,
    },
    "getOrderDetail": {
        "description": "查看指定订单的完整信息。",
        "requires_component": True,
    },
    "quickReorder": {
        "description": "基于历史订单一键复购。用户说'再来一份'时调用。",
        "requires_component": True,
    },
}

# Feature-dependent APIs: key = feature flag, value = list of API names
FEATURE_APIS: dict[str, list[str]] = {
    "has_coupons": ["getCoupons", "claimCoupon", "applyCoupon"],
    "has_table_reservation": ["reserveTable", "getReservations", "cancelReservation"],
    "has_order_tracking": ["trackOrder", "cancelOrder"],
    "has_allergen_info": ["getAllergenInfo"],
}

SERVICE_MODE_APIS: dict[ServiceMode, list[str]] = {
    ServiceMode.DELIVERY: ["setDeliveryAddress", "trackDelivery"],
}


def derive_apis(schema: BusinessSchema) -> list[dict]:
    """Return the list of API definitions to generate for this schema."""
    apis: list[dict] = []

    # Always include core APIs
    for name, defn in API_DEFINITIONS.items():
        apis.append({"name": name, **defn})

    # Feature-dependent APIs
    for flag, names in FEATURE_APIS.items():
        if getattr(schema.features, flag, False):
            for name in names:
                apis.append({"name": name, "description": _get_feature_api_desc(name), "requires_component": True})

    # Service mode APIs
    for mode, names in SERVICE_MODE_APIS.items():
        if mode in schema.service_modes:
            for name in names:
                apis.append({"name": name, "description": _get_feature_api_desc(name), "requires_component": True})

    return apis


def _get_feature_api_desc(name: str) -> str:
    descs = {
        "getCoupons": "获取用户可用优惠券列表。",
        "claimCoupon": "领取优惠券。",
        "applyCoupon": "将优惠券应用到订单。",
        "reserveTable": "预订桌位或取号排队。",
        "getReservations": "查看用户预订列表。",
        "cancelReservation": "取消预订。",
        "trackOrder": "查看订单实时状态（制作中/配送中/已完成）。",
        "cancelOrder": "取消未完成的订单。",
        "getAllergenInfo": "查看菜品过敏原信息。",
        "setDeliveryAddress": "设置外卖配送地址。",
        "trackDelivery": "查看配送进度和骑手位置。",
    }
    return descs.get(name, "")


def derive_categories_for_enum(schema: BusinessSchema) -> list[dict]:
    """Convert schema categories to the format used in mcp.json enums."""
    return [
        {"id": c.id, "name": c.name, "count": sum(1 for d in schema.dishes if d.category_id == c.id)}
        for c in schema.categories
    ]
