#!/usr/bin/env python3
"""MCP server for AI-Native Mini Program Generator.

Setup:
  cd backend
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  cp .env.example .env  # edit with your API key

Configure in ~/.claude.json:
  "mcpServers": {
    "miniprogram-generator": {
      "type": "stdio",
      "command": "/path/to/backend/.venv/bin/python3",
      "args": ["/path/to/backend/mcp_server.py"]
    }
  }
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

# Add parent dir to path so app module is importable
sys.path.insert(0, str(Path(__file__).parent))

from app.api.models.business_schema import BusinessSchema
from app.api.models.enums import ServiceMode
from app.core.generator import generate_project
from app.core.zip_packer import pack_to_zip

TOOLS = [
    {
        "name": "generate_miniprogram",
        "description": "根据结构化数据生成 AI-native 微信小程序项目，返回 ZIP 文件路径。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "项目名称，例如 小喵咖啡",
                },
                "service_modes": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["dineIn", "takeout", "delivery", "reservation"]},
                    "description": "服务模式：堂食/自取/外卖/预订",
                },
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "分类名，如 咖啡"},
                            "display_order": {"type": "integer", "description": "排序"},
                        },
                    },
                    "description": "菜品分类列表",
                },
                "dishes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "category_name": {"type": "string", "description": "所属分类名"},
                            "price": {"type": "number"},
                            "description": {"type": "string"},
                        },
                    },
                    "description": "菜品列表",
                },
                "spec_dimensions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "规格维度名，如 温度/杯型/甜度"},
                            "options": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string"},
                                        "price_delta": {"type": "number", "description": "加价"},
                                        "is_default": {"type": "boolean"},
                                    },
                                },
                            },
                        },
                    },
                    "description": "可选，规格选项（温度、杯型、甜度等）",
                },
            },
            "required": ["project_name", "service_modes", "categories", "dishes"],
        },
    },
]


async def handle_generate(args: dict) -> dict:
    """Handle generate_miniprogram tool call — build BusinessSchema from structured data."""
    project_name = args["project_name"]
    service_modes = args.get("service_modes", ["dineIn"])
    categories = args.get("categories", [])
    dishes = args.get("dishes", [])
    spec_dimensions = args.get("spec_dimensions", [])

    schema = BusinessSchema(
        project_name=project_name,
        service_modes=[ServiceMode(m) for m in service_modes],
        categories=[{"name": c["name"], "display_order": c.get("display_order", i)} for i, c in enumerate(categories)],
        dishes=[{
            "name": d["name"],
            "category_name": d["category_name"],
            "price": d["price"],
            "description": d.get("description", ""),
        } for d in dishes],
        spec_dimensions=[{
            "name": s["name"],
            "options": [{"label": o["label"], "price_delta": o.get("price_delta", 0), "is_default": o.get("is_default", False)} for o in s.get("options", [])],
        } for s in spec_dimensions],
        generated={
            "skill_description": f"{project_name} — AI 驱动的智能点单助手",
            "constraint_rules": [
                "禁止编造菜品 ID、规格值、价格",
                "必须从上游接口获取有效 ID 才能调用后续接口",
                "支付成功前禁止向用户宣布已支付",
            ],
        },
    )

    # Generate project
    out_dir = Path("/tmp/miniprogram-gen") / project_name
    if out_dir.exists():
        shutil.rmtree(str(out_dir))
    out_dir.mkdir(parents=True)

    try:
        await generate_project(schema, out_dir)
    except Exception as e:
        traceback.print_exc()
        return {"content": [{"type": "text", "text": f"生成失败: {e}"}]}

    # Package ZIP
    zip_path = Path(f"/tmp/{project_name}-ai-native.zip")
    if zip_path.exists():
        zip_path.unlink()
    pack_to_zip(out_dir, zip_path)

    size_kb = zip_path.stat().st_size / 1024
    return {
        "content": [{
            "type": "text",
            "text": f"✅ 已生成! ({size_kb:.0f} KB)\n\n"
                    f"项目：{schema.project_name}\n"
                    f"模式：{', '.join(str(m) for m in schema.service_modes)}\n"
                    f"文件数：{len(list(out_dir.rglob('*')))} 个\n"
                    f"菜品：{len(schema.dishes)} 个\n\n"
                    f"ZIP: {zip_path}\n\n"
                    f"导入微信开发者工具，配置 AppID 即可运行。",
        }],
    }


def send(msg: dict):
    """Send JSON-RPC response to stdout."""
    line = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def main():
    """Sync MCP server reading from stdin."""
    while True:
        line = sys.stdin.readline()
        if not line:
            break

        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_id = msg.get("id")
        method = msg.get("method")

        if method == "initialize":
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "miniprogram-generator", "version": "0.1.0"},
                },
            })
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS},
            })
        elif method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name", "")
            arguments = params.get("arguments", {})

            if name == "generate_miniprogram":
                import asyncio
                try:
                    result = asyncio.run(handle_generate(arguments))
                    send({"jsonrpc": "2.0", "id": msg_id, "result": result})
                except Exception as e:
                    traceback.print_exc()
                    send({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32603, "message": str(e)},
                    })
            else:
                send({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"},
                })
        else:
            send({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"},
            })


if __name__ == "__main__":
    main()
