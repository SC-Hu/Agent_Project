
# MyAgent: 个人智能体搭建

MyAgent 是一个基于 **ReAct** 模式深度进化的 AI Agent 。它不仅具备流式推理能力，还拥有跨越会话的长期记忆、动态技能路由网关，以及基于 **MCP ** 协议的物理世界执行权限。

> **当前版本**：v0.6 (Phase 6: 闭环执行与生态接入阶段)

---

## 核心特性

- **认知增强 (Cognitive Engine)**：
  - **CoT 思维链展示**：透明化展示模型的内部思考流（Thought）。
  - **Actor-Critic 反思架构**：内置 Self-Reflection 机制，答案在交付前需经过逻辑审核员的严格校对。
  - **自愈纠错 (Self-Correction)**：能自动解析工具执行的 Traceback，并在下一轮思考中自主修正参数。

- **深度长期记忆 (Deep Memory)**：
  - **双脑存储架构**：使用 **SQLite** 记录短期流水账（工作记忆），使用 **ChromaDB** 沉淀语义特征（潜意识）。
  - **RAG 潜意识唤醒**：基于向量相似度，在对话中隐式注入过往画像，实现个性化服务且绝不污染上下文。

- **动态技能治理 (Tool Governance)**：
  - **三级过滤体系**：Intent Router (选赛道) -> Tool RAG (选重点) -> Toolkit Loading (整箱加载)。
  - **全限定名空间**：支持 `native__` 和 `mcp__` 前缀，解决大规模工具集的命名冲突与智力稀释。

- **闭环执行与安全 (Physical Execution)**：
  - **物理沙盒**：强制锁定工作区目录 `workspace/`，严禁路径穿越。
  - **人工审批 (HITL)**：针对高危终端指令或代码修改，亮起红灯等待用户授权（y/n）。
  - **MCP 生态**：原生支持接入标准 MCP Server，一键获得 Git 操作、文件索引等能力。

---

## 启动

### 1. 环境依赖

确保你的系统中已安装 **Python 3.10+** 和 **Node.js (v18+)**。

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 进入 MCP 文件夹
cd MCP

# 确保 Node.js 环境可用（用于驱动 MCP Server）
node -v
npx --version
```

### 2. 环境配置

在 `MCP/` 目录下创建 `.env` 文件，并根据你的供应商配置以下参数：

```ini
# --- 对话模型配置 (建议使用 DeepSeek 或 GPT-4o) ---
CHAT_API_KEY=sk-your-key
CHAT_BASE_URL=https://api.deepseek.com/v1
CHAT_MODEL_NAME=deepseek-chat

# --- 嵌入模型配置 (用于 RAG 记忆) ---
EBD_API_KEY=sk-your-key
EBD_BASE_URL=https://api.siliconflow.cn/v1
EBD_MODEL_NAME=BAAI/bge-large-zh-v1.5

# --- 搜索工具配置 ---
TAVILY_API_KEY=tvly-your-key
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your-github-token
```

### 3. 运行程序

```bash
python main.py
```

---

## 操作指令

在 Agent 交互界面中，你可以使用以下特殊斜杠指令：

- `/new`：开启一个干净的全新会话，重置短期记忆。
- `/resume`：查看并恢复最近的历史对话，自动加载前情提要。
- `/info`：查看当前会话的 Session ID 及 Token 消耗统计。
- `/exit`：安全退出，系统将自动触发增量知识的沉淀与归档。

---

## 安全审计 (HITL)

当 Agent 试图执行以下高危操作时，系统会暂停输出并显示参数详情：
- **execute_bash**：执行终端命令（如安装包、运行脚本）。
- **mcp__git__commit**：提交代码变更。
- **write_local_file**：修改本地代码文件。

**操作提示**：
- 输入 `y`：批准执行。
- 输入 `n`：拒绝执行并让 Agent 寻找替代方案。

---

## 文件结构

workspace/：Agent 的合法活动范围，所有生成的文件均在此处。
memory_db/：ChromaDB 向量索引存储区。
agent_memory.db：SQLite 结构化历史记录。
engine.py：ReAct 核心调度引擎。
mcp_manager.py：外部插件进程桥接器。
router.py：意图识别与分流层。
mcp_config.json：mcp配置文件。 

---

## 系统架构图

```text
用户输入 ──▶ [RAG 检索] ──▶ [Intent Router] ──▶ [Tool RAG 筛选]
                                  │                 │
                                  ▼                 ▼
[LLM 思考逻辑] ◀── [载入上下文 & 增强 Prompt] ◀── [动态挂载工具箱]
      │
      ├─▶ [Native Python Tools] ──┐
      │                           ├─▶ [权限校验/HITL] ─▶ 执行并回传
      └─▶ [External MCP Server] ──┘
```

---

## 许可证
MyAgent 基于 MIT 许可证开源。请在合法合规的前提下使用本地执行权限。
