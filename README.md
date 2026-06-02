# Multi-Agent Chat

一个本地运行的**多层专家 Agent 对话应用**，支持调用通用 OpenAI-compatible API。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)

## ✨ 核心特性

- **单层模式**：传统单 Agent 自由对话
- **Pipeline（流水线）模式**：一次提问，多层专家 Agent 串行处理，每层从不同视角给出专业回答
- **Tree（树状分支）模式**：每层并行生成多个回答，用户选择其一后进入下一层，形成树状探索路径
- **一键总结导出**：对选中的完整路径调用 AI 总结，输出为 Obsidian 格式 Markdown 文件
- **层提示词覆盖**：支持 Pipeline 默认提示词 + 会话级单独覆盖
- **对话本地化**：每个 Session 存为独立 JSON 文件
- **流式输出**：支持 SSE 流式响应，实时显示生成内容

## 🚀 快速启动

### 环境要求

- Python 3.10+

### 安装依赖

```bash
pip install fastapi uvicorn
```

### 启动服务

```bash
python server.py
```

服务默认运行在 `http://localhost:8088`，浏览器访问即可。

> 若 8088 端口被占用，会自动切换到可用端口。

## 📁 项目结构

```
.
├── server.py              # FastAPI 后端
├── index.html             # 前端应用（原生 JS + Tailwind CSS）
├── test_agent.py          # 测试工作流 Agent
├── tests/
│   ├── conftest.py
│   ├── test_server.py     # 31 个单元测试
│   └── test_e2e.py
├── data/                  # 运行时数据（本地 JSON 存储）
│   ├── agents/
│   ├── pipelines/
│   ├── sessions/
│   └── settings.json
├── AGENTS.md              # Agent 开发文档
└── README.md              # 本文件
```

## 🧪 测试

```bash
# 运行所有测试
python test_agent.py

# 仅检查覆盖
python test_agent.py --check

# 监控模式（文件变更自动运行）
python test_agent.py --watch
```

## 📝 使用说明

### 1. 配置 API

首次打开页面，点击右上角设置按钮，配置：
- **API 地址**：你的 OpenAI-compatible API 地址
- **API Key**：你的 API Key
- **模型**：如 `gpt-4o`、`deepseek-chat` 等

内置预设：OpenAI、Kimi (Moonshot)、DeepSeek、硅基流动、Azure OpenAI、Baichuan。

### 2. 创建 Agent

在左侧 Agents 区域，点击「+」创建专家角色，填写名称和系统提示词。

### 3. 创建 Pipeline

在 Pipelines 区域，点击「+」创建多层流水线配置：
- 每层绑定一个 Agent
- 可配置层提示词（默认提示词）
- 可配置分支数量（`branches > 1` 自动启用 Tree 模式）

### 4. 开始对话

- 选择 Agent 或 Pipeline，点击「新对话」
- Pipeline/Tree 模式：输入问题后系统自动按层生成回答
- Tree 模式：每层生成多个分支，点击选择后进入下一层

### 5. 导出总结

Tree 模式下完成对话路径后，点击「📥 总结导出」：
- AI 自动生成精炼总结和 Tags
- 支持在导出前编辑总结内容、时间、Tags、文件名
- 输出为 Obsidian 兼容的 Markdown 文件

## 🔧 开发说明

### 核心概念

**Agent（专家角色）**
```json
{
  "id": "...",
  "name": "研究员",
  "prompt": "你是一个信息收集专家..."
}
```

**Pipeline（流水线配置）**
```json
{
  "id": "...",
  "name": "三级评审流水线",
  "layers": [
    { "agentId": "...", "label": "信息收集", "prompt": "...", "branches": 3 },
    { "agentId": "...", "label": "深度分析", "prompt": "...", "branches": 3 },
    { "agentId": "...", "label": "总结建议", "prompt": "...", "branches": 1 }
  ]
}
```

- `branches`：该层生成的并行回答数量（默认 1，大于 1 时启用 Tree 模式）

### 扩展方式

1. 后端优先：在 `server.py` 添加 API
2. 前端适配：在 `index.html` 添加 UI 和 fetch 调用
3. 补充测试：运行 `python test_agent.py`

## 📄 许可证

MIT License
