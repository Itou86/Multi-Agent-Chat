# Multi-Agent Chat - Agent 指导文档

## 项目概述

一个本地网页端**多层专家 Agent 对话应用**，支持调用通用 OpenAI-compatible API。

核心特性：
- **单层模式**：传统单 Agent 对话
- **Pipeline（流水线）模式**：一次提问，多层专家 Agent 串行处理，每层从不同视角给出专业回答
- **Tree（树状分支）模式**：每层并行生成多个回答，用户选择其一后进入下一层，形成树状探索路径
- **一键总结导出**：对选中的完整路径调用 Agent 总结，输出为 Obsidian 格式 Markdown 文件
- **层提示词覆盖**：支持 Pipeline 默认提示词 + 会话级单独覆盖
- **对话本地化**：每个 Session 存为独立 JSON 文件

## 快速启动

```bash
# 手动启动
python server.py
# 浏览器访问 http://localhost:8088
```

## 文件结构

```
.
├── server.py              # FastAPI 后端
├── index.html             # 前端应用
├── test_agent.py          # 测试工作流 Agent
├── tests/
│   ├── conftest.py
│   ├── test_server.py     # 28 个单元测试
│   └── test_e2e.py
├── data/                  # 运行时自动创建
│   ├── agents/
│   ├── pipelines/
│   ├── sessions/
│   └── settings.json
├── AGENTS.md              # 本文件
└── NOW.md                 # 任务列表
```

## 核心概念

### 1. Agent（专家角色）
```json
{
  "id": "...",
  "name": "研究员",
  "prompt": "你是一个信息收集专家..."
}
```

### 2. Pipeline（流水线配置 = 多层预设）
```json
{
  "id": "...",
  "name": "三级评审流水线",
  "layers": [
    { "agentId": "...", "label": "信息收集", "prompt": "默认提示词...", "branches": 3 },
    { "agentId": "...", "label": "深度分析", "prompt": "默认提示词...", "branches": 3 },
    { "agentId": "...", "label": "总结建议", "prompt": "默认提示词...", "branches": 1 }
  ]
}
```
- `branches`：该层生成的并行回答数量（默认 1，即传统 Pipeline 线性模式；大于 1 时自动启用 Tree 模式）

### 3. Session（对话实例）

**单层模式:**
```json
{ "mode": "single", "agentId": "...", "messages": [...] }
```

**Pipeline 模式:**
```json
{
  "mode": "pipeline",
  "pipelineId": "...",
  "messages": [{"role":"user","content":"原始问题"}],
  "layers": [
    {
      "agentId": "...", "label": "信息收集",
      "defaultPrompt": "默认提示词...",
      "sessionPrompt": "本次覆盖提示词...",
      "response": "第1层回复..."
    }
  ]
}
```

**Tree 模式:**
```json
{
  "mode": "tree",
  "pipelineId": "...",
  "messages": [{"role":"user","content":"原始问题"}],
  "layers": [
    {
      "agentId": "...", "label": "信息收集",
      "defaultPrompt": "默认提示词...",
      "sessionPrompt": "",
      "branches": 3,
      "responses": [
        { "id": "r0", "content": "A1..." },
        { "id": "r1", "content": "A2..." },
        { "id": "r2", "content": "A3..." }
      ],
      "selectedResponseId": "r1"
    }
  ]
}
```

## 层提示词优先级

运行时 System Message 构建优先级：
1. `sessionPrompt`（会话级覆盖，最高）
2. `defaultPrompt`（Pipeline 默认层提示词）
3. Agent 自身的 `prompt`（兜底）

## API 提供商预设

设置面板支持以下预设，选择后自动填充 API 地址和默认模型：

| 预设 | 地址 | 默认模型 |
|------|------|---------|
| OpenAI | `api.openai.com` | `gpt-4o` |
| Kimi (Moonshot) | `api.moonshot.cn` | `moonshot-v1-8k` |
| DeepSeek | `api.deepseek.com` | `deepseek-chat` |
| 硅基流动 | `api.siliconflow.cn` | `deepseek-ai/DeepSeek-V3` |
| Azure OpenAI | 占位符（需替换 resource） | `gpt-4o` |
| Baichuan | `api.baichuan-ai.com` | `Baichuan4` |

## 后端 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/agents` | Agent CRUD |
| PUT/DELETE | `/api/agents/{id}` | |
| GET/POST | `/api/sessions` | Session CRUD，支持 `?agentId=` 和 `?pipelineId=` |
| GET/PUT/DELETE | `/api/sessions/{id}` | |
| GET/POST | `/api/pipelines` | Pipeline CRUD（多层配置） |
| PUT/DELETE | `/api/pipelines/{id}` | |
| GET/POST | `/api/settings` | 设置（含 API 预设） |

默认端口 `8088`，可通过环境变量 `PORT` 覆盖。若被占用则自动切换到可用端口。

## 开发约定

### 代码风格
- **Python**: PEP 8，类型注解
- **HTML/JS**: 原生 JS + Tailwind CSS，函数按功能分区注释
- **变量命名**: 驼峰式 (JS)，蛇形式 (Python)

### 测试

```bash
# 运行所有测试
python test_agent.py

# 仅检查覆盖
python test_agent.py --check

# 监控模式（文件变更自动运行）
python test_agent.py --watch
```

31 个单元测试覆盖所有 API 路由（含 Tree 模式与 branches 字段）。

### 扩展指南

1. 后端优先：在 `server.py` 添加 API
2. 前端适配：在 `index.html` 添加 UI 和 fetch 调用
3. 补充测试：运行 `python test_agent.py`

### 注意事项
- 必须通过 `http://localhost:8088` 访问，**不要直接双击打开 index.html**（已添加 file:// 协议检测提示）
- API Key 由前端保存使用，后端仅透存储
- `data/` 目录不应提交到版本控制
