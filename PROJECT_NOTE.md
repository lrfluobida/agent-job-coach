# Agent Job Coach 项目备忘录（截至 2026-02-04）

## 0. 项目定位
- 目标：做一个面向 Agent/LLM 岗位的求职助手 Agent，强调工程化落地能力：**Skills + RAG +（后续）MCP + LangGraph**。
- 核心交付：网页可用（Next.js），后端编排（FastAPI + LangGraph），向量检索（Chroma，本地持久化），后续再接 MCP 工具层与评测。

---

## 1. 技术栈（已定）
### 前端
- Next.js + TypeScript + Tailwind
- 本地端口：`http://localhost:3000`
- 当前页面：联通性检测，展示 `Backend: OK/FAIL`

### 后端
- Python（uv 管理虚拟环境；项目使用 Python 3.12）
- FastAPI + Uvicorn
- 本地端口：`http://127.0.0.1:8000`
- 已加 CORS：允许 `http://localhost:3000` / `http://127.0.0.1:3000` 访问

### 向量数据库（当前版本）
- Chroma（本地持久化）
- 持久化目录：`data/chroma`

### 暂时跳过 / 未来接入
- Docker / Qdrant：不想装 WSL/Docker，先用 Chroma；未来可做“存储层可插拔”升级为 Qdrant 加分
- pnpm：PowerShell 执行策略导致 pnpm.ps1 不能执行，本阶段用 npm 即可（不影响项目）

---
## 1.5 项目目录结构（当前）
根目录：E:\develop\Python\agent-job-coach

agent-job-coach/
  apps/
    api/                      # FastAPI 后端（uv 虚拟环境在此目录）
      src/
        main.py               # 当前：/health + Chroma client + CORS
      pyproject.toml
      .venv/                  # uv 创建的虚拟环境（不提交 git）
    web/                      # Next.js 前端
      src/app/page.tsx        # 当前：请求 /health 显示 Backend OK
      package.json
  data/
    chroma/                   # Chroma 持久化目录（向量库数据）
    jd/                       # 未来：存放你复制的 JD（md/txt）
    resume/                   # 未来：简历/项目材料
    notes/                    # 未来：八股笔记（做 RAG 知识库）
  scripts/
    dev-api.ps1               # 启动后端脚本（如果你创建了）
    dev-web.ps1               # 启动前端脚本（如果你创建了）
  .env.example                # 环境变量模板（如果你创建了）
  PROJECT_NOTES.md
  README.md
  .git/
## 1.6 项目目录结构（未来规划）
apps/api/src/
  graph/                      # LangGraph 工作流与节点
  skills/                     # Skills：JDParser / GapPlan / InterviewQA 等
  rag/                        # chunking / embeddings / retriever / store 接口
  mcp/                        # MCP 客户端与（可选）自定义 server
  eval/                       # 离线评测集与指标脚本


## 2. 今天完成了什么（准备阶段成果）
### 2.1 项目目录骨架已创建
根目录：`E:\develop\Python\agent-job-coach`

结构：
- `apps/api`（后端）
- `apps/web`（前端）
- `data/jd`、`data/resume`、`data/notes`（RAG 数据源）
- `scripts`（启动脚本）

### 2.2 Git 初始化完成
- `git init`
- `git config core.autocrlf true`

### 2.3 后端可运行
- `/health` 返回：
  - `{"ok": true, "chroma_path": "E:\\develop\\Python\\agent-job-coach\\data\\chroma"}`
- `/docs` 可打开
- 说明：Windows 下 `--reload` 曾因监控 `.venv` 导致频繁重启；当前先不启用 reload（或后续改为只监控 src）

### 2.4 前端可运行
- Next.js 本地启动正常
- 页面能请求后端 health 并显示 `Backend: OK ✅`（跨域已通过后端 CORS 修复）

---

## 3. 已约定的“今天目标”
- ✅ 跑通开发环境与工程骨架（前端 + 后端 + 向量库占位）
- ✅ 做到网页可访问 + 前后端联通验证
- ✅ 向量库持久化路径准备好（Chroma）

---

## 4. 下一步开发计划（从明天开始）
### 阶段 1：先跑通闭环（建议 1–3 天）
目标：上传/粘贴 JD/简历 → 入库 → RAG 检索 → 结构化输出

1) 后端新增 `/ingest`
- 输入：JD 文本/文件、简历文本/文件（先支持纯文本粘贴即可）
- 处理：分块 → embedding → 写入 Chroma（metadata：source、doc_type、job_id 等）
- 输出：入库统计（chunks 数、doc_id）

2) 后端新增 `/chat`（先非流式，后续再 SSE）
- 输入：用户问题
- 处理：RAG 检索 topK → 生成结构化 JSON（先做 1 个 Skill：InterviewQASkill 或 GapPlanSkill）
- 输出：JSON（带引用/证据）

3) 前端新增输入区
- Upload/粘贴区：JD、简历、项目材料
- Chat 区：输入问题，显示结果

### 阶段 2：LangGraph + Skills 模块化（约 3–7 天）
目标：流程从脚本式升级为可控状态机

- LangGraph 节点：route → retrieve → run_skill → guardrail → finalize
- Skills（先做 3 个够硬）：
  - JDParserSkill
  - GapPlanSkill（14 天计划）
  - InterviewQASkill（问答+追问链）
- 强制结构化输出（Pydantic schema），失败则重试/追问

### 阶段 3：MCP 接入（约 1–3 天）
目标：工具层标准化，体现会用 MCP

- 接 MCP filesystem（读写 data 目录文件）
- 写自定义最小 MCP server（建议：retrieval server，把 Chroma query/upsert 封装成工具）
- README 增加架构图：LangGraph → Skills → MCP tools → (Chroma / filesystem)

### 阶段 4：评测与工程化加分（持续迭代）
目标：从玩具到可面试讲的工程项目

- 离线评测集（50 条起）：正确率/引用覆盖率/延迟/token 成本
- 防幻觉策略：必须引用；检索不足则追问/拒答
- 可观测：结构化日志、trace_id；后续可接 LangSmith / OpenTelemetry

---

## 5. 面试知识点准备（与项目结合）
- 不在项目里做 LoRA 训练，但要会讲取舍：
  - RAG：知识可更新、可溯源
  - LoRA：更偏“行为/格式/风格”学习
- 项目里要体现 RAG 高频点：
  - chunk/overlap、topK、过滤、（可选）重排
  - 强制引用与失败策略
  - 评测与指标（分水岭）

---

## 6. 当前运行方式（记住三条）
- 后端：
  - `cd apps/api`
  - `uv run uvicorn src.main:app --port 8000`
- 前端：
  - `cd apps/web`
  - `npm run dev`
- 验收：
  - `http://127.0.0.1:8000/health`
  - `http://127.0.0.1:8000/docs`
  - `http://localhost:3000`（显示 Backend OK）
