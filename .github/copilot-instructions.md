<!-- Copilot / AI agent instructions for the agent-job-coach repo -->
# 快速上手（给 AI 编码助手的要点）

以下说明帮助 AI 代理迅速理解代码库的结构、运行方式、约定与关键集成点。回答与修改请尽量引用示例文件路径。

- **总体架构（大图）**: 该仓库以 `apps/` 为主应用目录，当前主要工作服务为 `apps/api`（一个小型 FastAPI 服务）。前端或其他组件放在 `web/`（当前为空/未详细实现）。持久化向量存储位于仓库根下的 `data/chroma`，由 `chromadb` 本地持久化管理（查看 `apps/api/src/main.py`）。

- **关键文件**:
  - `apps/api/src/main.py`: FastAPI 应用入口，创建了 `chromadb.PersistentClient(path=data/chroma)`，并暴露 `/health` 以报告 Chroma 路径。
  - `apps/api/pyproject.toml`: 记录依赖（Python >=3.12、`chromadb`, `fastapi`, `uvicorn` 等）。
  - `data/chroma/chroma.sqlite3`: 本地 Chroma 持久化文件（存在时说明有本地向量数据）。

- **运行 / 本地调试（推荐命令）**:
  - 在开发时，进入 `apps/api` 目录并使用 `uvicorn` 运行应用（模块路径以 `src` 为起点）：

```
cd apps/api
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

  - 健康检查: GET http://127.0.0.1:8000/health 返回 Chroma 路径。

- **项目惯例与约定（此仓库的明确或隐含规则）**:
  - 源码采用 `src/` 布局（`apps/api/src`），建议在該目录下添加路由/模块，避免修改根级 `apps/api/main.py`（它仅作简单示例）。
  - 本地向量数据库路径固定为仓库下的 `data/chroma`，修改该路径会导致现有数据不可用；迁移时需导出/导入 Chroma 数据。
  - 依赖与 Python 版本在 `apps/api/pyproject.toml` 中声明；优先使用该文件里的版本进行虚拟环境安装与测试。

- **代码改动与 PR 指南（对 AI 的建议）**:
  - 新增 API 路由：在 `apps/api/src/` 下创建模块并在 `src/main.py` 或 `src/router` 中包含路由注册；保持路由小而单一职责。
  - 不要随意移动或重命名 `data/chroma`，必要时在 PR 描述中说明数据迁移步骤。
  - 引入新依赖时，请同时更新 `apps/api/pyproject.toml` 并在 PR 中说明用途与兼容性（Python>=3.12）。

- **集成点与外部依赖**:
  - Chroma（`chromadb`）: 以本地 `PersistentClient` 使用，注意数据库文件位置与进程并发访问的限制。
  - FastAPI + Uvicorn: HTTP 层，短小服务，适合快速迭代。
  - 环境变量：项目声明了 `python-dotenv` 依赖，但仓库未强制要求 `.env`；若需要新环境变量，请在 `apps/api/README.md` 或 PR 中记录。

- **示例任务（如何改动）**:
  - 扩展健康接口以报告 Chroma 大小：修改 `apps/api/src/main.py`，在 `/health` 中打开 `data/chroma` 文件并返回文件大小或集合计数（注意并发）。
  - 添加新的 API 路由模块：在 `apps/api/src/` 新建 `routes/`，向 `src/main.py` 注册。

- **不包含/未发现的内容（AI 不要假设）**:
  - 仓库中没有测试套件、CI 工作流或明确的部署脚本；若需要这些，请在 PR 中提出并附带复现步骤。
  - 未发现前端运行说明或构建指令，请不要假设 `web/` 已完成。

如果以上某处信息不完整或你希望我把说明调整为更详细的命令/示例（例如增加虚拟环境/Windows 特定说明或 CI 步骤），请告诉我需要加强的部分。期待你的反馈以继续迭代这份 `copilot-instructions.md`。
