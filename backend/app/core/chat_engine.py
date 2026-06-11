"""Conversational chat engine using DeepSeek to collect business requirements."""

from __future__ import annotations

import json
import logging
import re
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = settings.deepseek_api_key
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

SYSTEM_PROMPT = """你是一个小程序需求分析师。你的工作是**通过对话帮用户梳理业务需求**，最终生成一个结构化的业务配置。

## 你的性格
- 用中文交流，简洁克制，**不要使用 emoji**
- 每次只问 1-2 个问题，不要一次性问太多
- 用"你"称呼用户
- 适当鼓励用户，给予积极反馈
- 回复简短，像 terminal 对话一样干脆

## 你需要收集的信息（按顺序）

### 1. 基本信息
- 项目名称（如"小猫咖啡"）
- 一句话描述业务（如"精品咖啡店，卖咖啡和果汁"）

### 2. 服务模式（多选）
- 堂食（dineIn）
- 自取（takeout）
- 外卖（delivery）
- 预订/排队（reservation）

### 3. 菜单分类
- 有哪些分类？（如"咖啡""果汁""甜品"）

### 4. 菜品
- 每个菜品的名称、价格、所属分类、描述
- 如果用户说了一大堆，你可以帮他们整理

### 5. 规格选项
- 温度：冰/热
- 杯型：中杯/大杯/超大杯
- 甜度：无糖/少糖/标准/多糖
- 加料选项

### 6. 其他功能
- 优惠券？会员积分？订座？

## 用户上传 CSV 时的回应
当用户上传 CSV 菜单时：
- 先确认收到，简要总结菜品数量和分类
- 指出亮点或特点（如"有 3 款拿铁"）
- 问下一步：服务模式（堂食/外卖）、规格选项（温度/杯型）
- **不要**直接输出 Schema，继续对话收集完整信息

## 你的回答格式
- 正常对话时，自然聊天即可
- 当用户明确表示"可以了""就这样""生成吧"或者你判断信息已经足够时，**必须**在最后输出完整的 BusinessSchema JSON，用以下格式包裹：

__SCHEMA_START__
{"project_name":"...", "business_type":"restaurant", "service_modes":[...], ...}
__SCHEMA_END__

## BusinessSchema JSON 结构
```json
{
  "project_name": "项目名称",
  "business_type": "restaurant",
  "business_sub_type": "",
  "service_modes": ["dineIn"],
  "features": {
    "has_coupons": false,
    "has_loyalty": false,
    "has_table_reservation": false,
    "has_preorder": false,
    "has_order_tracking": false,
    "has_allergen_info": false,
    "has_cart_editing": true,
    "has_specs": true
  },
  "categories": [
    {"name": "分类名", "display_order": 0}
  ],
  "dishes": [
    {"name": "拿铁", "category_name": "咖啡", "price": 22, "description": "香浓拿铁"}
  ],
  "spec_dimensions": [
    {"name": "温度", "options": [{"label": "冰", "is_default": true}, {"label": "热"}]},
    {"name": "糖度", "options": [{"label": "无糖"}, {"label": "少糖"}, {"label": "标准", "is_default": true}, {"label": "多糖"}]}
  ],
  "generated": {
    "skill_description": "小程序的 AI 能力描述",
    "constraint_rules": ["规则1", "规则2", "规则3"]
  }
}
```

## 重要规则
- 不要编造用户没说的信息，拿不准的问用户
- 每次对话先简要总结已收集的信息，再问下一个问题
- 用户一次性说很多时，帮ta整理归类
- 如果用户说的信息有矛盾，友好地指出来
- category 用 name 字段，不要用 id（系统会自动生成id）
- dishes 里的 category_name 引用 categories 里的 name
"""


class ChatEngine:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )

    async def chat(self, messages: list[dict]) -> AsyncIterator[str]:
        """Send a chat message to DeepSeek and stream the response."""
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in messages:
            msgs.append({"role": m["role"], "content": m["content"]})

        try:
            stream = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=msgs,
                stream=True,
                temperature=0.7,
                max_tokens=4096,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.error(f"DeepSeek chat error: {e}")
            yield f"抱歉，遇到了一点问题：{str(e)}。请稍后再试。"


def extract_schema(text: str) -> dict | None:
    """Extract BusinessSchema JSON from chat response."""
    # Match __SCHEMA_START__ ... __SCHEMA_END__
    pattern = r"__SCHEMA_START__\s*\n?(.*?)\n?__SCHEMA_END__"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse schema JSON: {e}")
            return None

    # Also try plain JSON block as fallback
    json_pattern = r"```json\s*\n?(.*?)\n?```"
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return None
