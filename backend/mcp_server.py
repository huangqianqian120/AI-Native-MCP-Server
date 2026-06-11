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

import csv
import io
import json
import os
import shutil
import sys
import traceback
from pathlib import Path

# Add parent dir to path so app module is importable
sys.path.insert(0, str(Path(__file__).parent))

# API key loaded from .env via pydantic-settings (config.py)
# Set DEEPSEEK_API_KEY in .env or export it in shell

from app.api.models.business_schema import BusinessSchema
from app.core.generator import generate_project
from app.core.zip_packer import pack_to_zip
from app.core.schema_inferrer import SchemaInferrer
from app.config import settings

inferrer = SchemaInferrer()

TOOLS = [
    {
        "name": "generate_miniprogram",
        "description": "从业务描述一键生成 AI-native 微信小程序项目，返回 ZIP 文件路径。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_name": {
                    "type": "string",
                    "description": "项目名称，例如 小喵咖啡",
                },
                "description": {
                    "type": "string",
                    "description": "详细的业务描述，包括：业务类型、服务模式（堂食/外卖/自取）、菜品名与价格、规格选项等",
                },
            },
            "required": ["project_name", "description"],
        },
    },
]


async def handle_generate(args: dict) -> dict:
    """Handle generate_miniprogram tool call."""
    project_name = args["project_name"]
    description = args.get("description", "")

    # Build basic schema — LLM will enrich it
    schema_data = {
        "project_name": project_name,
        "generated": {
            "skill_description": f"{project_name} — AI 驱动的智能点单助手",
            "constraint_rules": [
                "禁止编造菜品 ID、规格值、价格",
                "必须从上游接口获取有效 ID 才能调用后续接口",
                "支付成功前禁止向用户宣布已支付",
            ],
        },
    }

    # Use LLM if available
    if settings.deepseek_api_key or settings.anthropic_api_key:
        from app.api.models.requests import InferSchemaRequest
        req = InferSchemaRequest(
            project_name=project_name,
            description=description,
        )
        try:
            schema = await inferrer.infer(req)
        except Exception:
            traceback.print_exc()
            schema = BusinessSchema(**schema_data)
    else:
        schema = BusinessSchema(**schema_data)

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
