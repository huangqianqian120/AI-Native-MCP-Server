# AI-Native Mini Program Generator — MCP Server

一键生成微信 AI Mode 小程序（Skill + MCP 架构）的 MCP Server。

## 快速开始

```bash
# 1. 克隆
git clone <repo-url>
cd miniprogram-generator/backend

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 API Key（可选）

不配也能用，会走模板降级（不用 AI 推断）。
需要用 LLM 增强 Schema 推断的话，二选一：

```bash
cp .env.example .env
# 编辑 .env，填入你的 ANTHROPIC_API_KEY（推荐）
# 或者 DEEPSEEK_API_KEY（改一行代码即可切换）
```
```

## 配置 Claude Code

在 `~/.claude.json` 的 `mcpServers` 中加入：

```json
"miniprogram-generator": {
  "type": "stdio",
  "command": "/absolute/path/to/miniprogram-generator/backend/.venv/bin/python3",
  "args": [
    "/absolute/path/to/miniprogram-generator/backend/mcp_server.py"
  ]
}
```

重启 Claude Code 即可使用。

## 使用方式

在 Claude Code 中直接说，例如：

> 帮我生成一个咖啡店小程序，叫"小喵咖啡"，卖美式18、拿铁22、果汁15，支持堂食和外卖

Claude 会自动调用 `generate_miniprogram` 工具，生成可运行的微信小程序项目 ZIP，并告诉你路径。

## 工具说明

### `generate_miniprogram`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| project_name | string | ✅ | 项目名称 |
| description | string | ✅ | 详细的业务描述（服务模式、菜品名与价格、规格等） |

## 生成内容

- `mcp.json` — 原子接口 Schema 定义
- `SKILL.md` — 业务流程与约束
- 14+ API 实现（搜索、菜单、加购、下单、支付...）
- 10 组卡片组件（门店列表、菜单、详情、购物车、订单...）
- 完整微信小程序项目结构
