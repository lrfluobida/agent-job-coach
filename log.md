# 开发日志（2026-02-05）

## 1. 背景与目标
今天的目标是把 Agent Job Coach 的 M5 工程化能力稳定落地，并持续打磨前后端体验：保证聊天与检索流程稳定、输出更易读、文件上传入库更顺畅、前端在无外网环境可用，并补齐基础测试与依赖。

## 2. 主要改动概览
- 完成 LangGraph 驱动的 M5 Agent 流程与工具调用整合，保持 /chat 与 /chat/stream 兼容。
- 新增输出清洗与证据引用处理，避免 JSON/代码块污染聊天气泡。
- 前端引入 Markdown 渲染与证据 UI，修复证据显示与气泡溢出问题。
- 增强上传入库流程，支持文件直传并自动生成 source_id。
- 离线字体方案落地，修复 Next.js 拉取 Google Fonts 的失败问题。
- 引入 PDF 解析依赖 pypdf，支持上传 PDF 入库。
- 前端页面状态持久化，切换页面不丢输入与结果。
- 增加基础测试与工具函数测试，保证输出清洗与引用选择可靠。

## 3. 项目结构文件说明
- apps/api
  - src/main.py：FastAPI 入口与路由注册
  - src/api：HTTP 路由层（/health、/ingest、/retrieve、/chat、/chat/stream、/ingest/file）
  - src/ingest：文本/文件抽取与入库流程
  - src/rag：检索与向量库交互（Chroma）
  - src/skills：面试问答技能（Interview QA）
  - src/graph：LangGraph 工作流编排
  - src/tools：工具注册与 MCP 调用封装
  - src/llm：模型客户端（Zhipu）
  - src/core：配置、依赖注入、输出清洗
  - src/tests：最小测试集
- apps/web
  - src/app：Next.js App Router 页面（/ingest /retrieve /chat）
  - src/app/api：前端代理路由（/api/*）
  - src/components：布局与 Sidebar 组件
  - src/lib：前端通用工具
- scripts：启动与维护脚本
- .env / .env.example：本地配置与模板

## 4. 详细变更记录（按 M1→M5 主线）

### M1：项目骨架与最小闭环
目的：保持既有 FastAPI/Next 基础架构稳定，确保后续迭代不破坏入口与路由。
实现：未修改核心骨架与路由结构，仅在现有架构上叠加 M5 相关能力。
关键点：坚持 `from src...` 绝对导入、路由兼容与 /health 不变。
验证：`uv run uvicorn src.main:app --port 8000` 可启动；前端 `npm run dev` 可启动。
涉及文件：
- apps/api/src/main.py
- apps/web/src/app/layout.tsx

### M2：实现 /retrieve 检索接口
目的：确保检索端返回结构稳定，为前端检索调试与证据展示提供基础。
实现：保留原有检索返回结构与过滤字段，前端状态持久化增强检索体验。
关键点：检索参数在切换页面后仍保留；source_type 过滤改为下拉选择避免输入错误。
验证：检索页填写 query/source_type/source_id，切换页面后回来仍保留输入。
涉及文件：
- apps/web/src/app/retrieve/page.tsx

### M3：第一个 Skill：/skills/interview_qa
目的：提升回答与引用的可用性，避免 citations 丢失或格式不一致。
实现：对 citations 进行规范化处理，兼容字符串列表与对象列表，必要时从 used_context 补齐引用片段。
关键点：确保 citations/used_context 在前端可被正确显示，避免 “无引用证据” 误判。
验证：问答结果可出现引用 chips 与证据卡片。
涉及文件：
- apps/api/src/skills/interview_qa.py
- apps/api/src/api/routes_chat.py

### M4：/chat/stream SSE 流式聊天
目的：稳定 SSE 结果展示与证据回传，确保流式 UI 仍可正确显示引用。
实现：SSE context 事件统一输出标准 citations 结构，配合前端解析。
关键点：context 事件包含 citations + used_context，前端仅展示真实引用。
验证：/chat/stream 流式响应可显示引用 chips 与证据面板。
涉及文件：
- apps/api/src/api/routes_chat_stream.py
- apps/web/src/app/chat/page.tsx

### M5：工程化 Agent（重点）
目的：落地 LangGraph + Tools + 文件上传入库 + 输出清洗 + 前端适配，形成完整工程化闭环。
实现：
- LangGraph 流程贯通 normalize→retrieve→plan_tools→execute_tools→final，支持工具调用与引用逻辑。
- 输出清洗模块处理 JSON/代码块污染，保证聊天气泡为自然语言。
- 证据引用逻辑统一，避免 citations 与 used_context 不一致。
- 文件上传入库逻辑完善，支持文件直接入库与自动 source_id；文本导入保留。
- 前端引入 Markdown 渲染与证据 UI，支持证据卡片与引用 chips。
- 前端离线字体方案替换 Google Fonts，避免无外网启动失败。
- PDF 上传依赖 pypdf，引入后可解析并入库。
- 前端页面状态持久化，切页不会丢输入或结果。
关键点：
- 输出清洗：避免 LLM 返回 JSON/代码块被直接显示在 UI。
- 引用策略：优先工具引用，其次从标记或 used_context 补齐。
- 上传流程：文件选择后提交即可完成上传入库。
验证：
- `/chat` 与 `/chat/stream` 返回结构保持兼容。
- 上传 txt/md/pdf/docx 可成功入库。
- 前端 Markdown 与证据 UI 正常展示。
涉及文件：
- apps/api/src/graph/job_coach_graph.py
- apps/api/src/tools/registry.py
- apps/api/src/tools/mcp_client.py
- apps/api/src/ingest/pipeline.py
- apps/api/src/api/routes_upload.py
- apps/api/src/core/output_coercion.py
- apps/api/src/api/routes_chat.py
- apps/api/src/api/routes_chat_stream.py
- apps/web/src/app/chat/page.tsx
- apps/web/src/app/ingest/page.tsx
- apps/web/src/app/layout.tsx
- apps/web/src/app/globals.css
- apps/api/pyproject.toml

## 5. 问题与排查
1) 证据引用显示为空（UI 显示“无引用证据”）
解决方案：规范化 citations 结构，兼容字符串与对象，必要时从 used_context 补齐引用。
涉及文件：
- apps/api/src/graph/job_coach_graph.py
- apps/api/src/skills/interview_qa.py
- apps/api/src/api/routes_chat.py
- apps/api/src/api/routes_chat_stream.py
- apps/web/src/app/chat/page.tsx

2) 前端切换页面后参数消失
解决方案：引入 localStorage 状态持久化，并在页面卸载时强制写回，修复首次进入不保存的问题。
涉及文件：
- apps/web/src/app/chat/page.tsx
- apps/web/src/app/ingest/page.tsx
- apps/web/src/app/retrieve/page.tsx

3) PDF 上传报 415 / 缺少依赖
解决方案：补齐 pypdf 依赖，后端支持 PDF 解析。
涉及文件：
- apps/api/pyproject.toml
- apps/api/uv.lock

## 6. 新增/修改文件清单（重要）

apps/api：
- apps/api/src/graph/job_coach_graph.py
- apps/api/src/api/routes_chat.py
- apps/api/src/api/routes_chat_stream.py
- apps/api/src/api/routes_ingest.py
- apps/api/src/skills/interview_qa.py
- apps/api/src/core/output_coercion.py
- apps/api/src/core/settings.py
- apps/api/src/ingest/pipeline.py
- apps/api/src/api/routes_upload.py
- apps/api/src/tests/test_output_coercion.py
- apps/api/src/tests/test_graph_coercion.py
- apps/api/src/tests/test_citations_selection.py
- apps/api/pyproject.toml
- apps/api/uv.lock

apps/web：
- apps/web/src/app/chat/page.tsx
- apps/web/src/app/ingest/page.tsx
- apps/web/src/app/retrieve/page.tsx
- apps/web/src/app/layout.tsx
- apps/web/src/app/globals.css
- apps/web/package.json
- apps/web/package-lock.json

## 7. 运行与验收
后端启动：
```bash
cd apps/api
uv run uvicorn src.main:app --port 8000
```

前端启动：
```bash
cd apps/web
npm run dev
```

上传入库：
- 进入 /ingest
- 选择文件 + 资料类型 → 点击“提交”完成上传入库

聊天与流式：
- /chat 提问可返回 answer + citations + used_context
- /chat/stream 可流式展示并显示引用

测试：
```bash
cd apps/api
uv run pytest src/tests/test_citations_selection.py
```

## 8. 后续 TODO
- 增加“清空页面状态缓存”按钮，方便用户重置。
- 增加上传文件的大小/类型提示与失败反馈。
- 进一步优化引用策略（避免弱相关引用）。
- 提供删除 source_id 的管理入口。
- 证据展示支持按文件名/类型分组。
- 增加检索结果的可视化排序/过滤说明。
