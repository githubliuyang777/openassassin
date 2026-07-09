# openAssassin — Agent Team Charter

## 项目定位

云原生运维管理平台：管理员登录 → 管理脚本(Shell/Python) → 引用密钥执行 → 查看日志。
Docker Compose 一键部署，默认账号 admin/admin。

## 技术栈

| 层 | 技术 | 版本 |
|---|------|------|
| 后端 | Python FastAPI + SQLAlchemy + SQLite | 3.12+ |
| 前端 | Vue 3 + Vite + TypeScript + Naive UI + Pinia | 3.5+ |
| 加密 | AES-256-GCM (cryptography 库) | — |
| 认证 | JWT (python-jose + bcrypt) | — |
| 沙箱 | Docker SDK for Python | — |
| 部署 | Docker Compose | — |

## 目录结构

```
infra-ops/
├── backend/app/
│   ├── main.py           # FastAPI 入口, lifespan 中自动建表+创建admin
│   ├── config.py         # pydantic-settings, 所有配置集中管理
│   ├── database.py       # SQLAlchemy engine + SessionLocal + get_db
│   ├── models/           # User / Script / Credential / Execution
│   ├── schemas/          # Pydantic request/response models
│   ├── api/              # auth / scripts / credentials / executions 路由
│   ├── services/         # 业务逻辑: auth / credential / script / sandbox
│   └── middleware/        # JWT Bearer 鉴权依赖
├── frontend/src/
│   ├── router/index.ts   # 路由 + beforeEach 守卫
│   ├── stores/auth.ts    # Pinia 登录状态
│   ├── api/              # Axios client + 各模块 API 封装
│   ├── views/            # 7 个页面组件
│   └── layouts/          # MainLayout (侧边栏+顶栏)
├── docker-compose.yml    # backend(:8000) + frontend(:8080)
└── .env.example          # JWT_SECRET, MASTER_KEY, etc.
```

## 开发流程规范

**所有代码变更必须严格遵守以下流程，任何步骤不可跳过。**

### 1. 需求分析与评审
- 接到需求后，**必须先分析需求**，理解要解决的问题和影响范围
- 使用 **Explore Agent** 勘探相关代码，了解现有实现的上下文和依赖链
- **禁止**直接跳入编码阶段，必须先完成分析

### 2. 方案设计 (Plan)
- 使用 **EnterPlanMode** 进入方案设计模式
- 设计必须包含以下内容：
  - API 端点设计（路径、方法、请求/响应结构）
  - 数据模型变更（表结构、字段、迁移策略）
    - **数据库字段变更必须考虑存量数据兼容性**：新增字段必须有合理的默认值，确保旧数据在代码更新后能正常读取和展示；不允许出现存量数据在新字段上为 NULL 且业务逻辑未处理 NULL 的情况
  - 前端组件树和交互流程
  - 边界条件和异常处理策略
- **必须在方案中纳入安全因素分析**：
  - 密钥/凭证处理：加密存储、内存中解密、日志掩码
  - 权限控制：JWT 鉴权、角色校验
  - 输入校验：Pydantic 模型校验、SQL 注入防护
  - 沙箱隔离：脚本执行环境隔离
  - 数据传输：HTTPS、敏感信息不落盘
- 方案输出到 plan file，经 **用户确认** 后方可进入开发阶段

### 3. 代码开发
- 遵循 `代码约定` 中的后端/前端/测试规范
- 新 API 端点统一前缀 `/api/v1/`
- 业务逻辑放 `services/`，API 层只做参数校验和响应
- 所有密钥操作必须走 `credential_service` 加密/解密

### 4. 本地测试 (必须)
- 开发完成后，**必须在本地通过测试**：
  - 后端：`cd backend && python -m pytest tests/ -v`
  - 前端：`cd frontend && npm run test`
  - 冒烟测试：`bash tests/smoke.sh`
- 新增 API 端点必须同步新增对应 test case
- 安全相关变更（sandbox/credential/auth）必须跑全量安全测试
- **测试失败不允许进入下一步**

### 5. 敏感信息检查 (必须)
- 提交前必须检查本地代码是否包含敏感信息：
  - 检查是否有硬编码的密码、token、密钥、私钥
  - 检查 `.env`、`credentials.json` 等敏感文件是否在 `.gitignore` 中
  - 检查日志输出是否掩码了密钥值
  - 检查数据库文件、备份文件是否被意外纳入版本控制
- 使用 `git diff --cached` 逐文件审查变更内容
- **发现敏感信息必须清除后才能继续**

### 6. PR 提交
- 使用 **pr-submit** skill 提交 PR
- **禁止直接合入主分支（master/main）**，必须走 PR 流程
- Commit message 遵循项目规范，简洁描述"为什么"而非"是什么"
- PR 标题简洁（<70 字符），描述包含变更摘要和测试计划
- **提交 PR 时必须确认是否解决代码仓的 issue**：
  - 如果本次变更解决某个已有 issue，必须在 PR 描述中使用 GitHub 关联合键字关联该 issue（如 `Closes #123`、`Fixes #123`）
  - 如果本次变更不涉及已有 issue，在 PR 描述中注明"无关联 issue"

### 7. 门禁检查
- PR 提交后等待 CI/CD 门禁检查通过
- 包括但不限于：lint、type check、test、build
- **门禁失败不允许合入**，必须修复后重新推送
- **即使失败项是本分支改动前就存在的预存问题，也必须修复后才能合入**。任何 CI 失败都是阻塞项，不存在"已知问题可忽略"的例外

### 8. 架构师 Review
- 门禁通过后，由架构师进行代码审查
- Review 检查项参照下方 Code Reviewer Agent 和安全审查规则
- **架构师审核通过后方可合入**

### 9. 合入 PR
- 审核通过后执行 merge 合入主分支
- 合入后验证主分支构建状态
- **合入后必须关闭关联的 issue**：如果 PR 描述中关联合了 issue（通过 `Closes`/`Fixes` 关键字），GitHub 会在 PR 合入时自动关闭对应 issue；需确认 issue 已成功关闭，若未自动关闭则手动关闭

### 10. 更新 README.md (必须)
- 新特性上线后，**必须同步更新项目 README.md**，反映当前系统的完整功能概览
- 更新内容包括但不限于：
  - 新增功能模块描述及访问路径
  - 新增的菜单项和页面
  - 新增的环境变量或配置项（如 `.env.example` 中有变更）
  - 架构图的更新（如有）
- 采用 PR 方式提交 README 更新，同样需要门禁检查
- **不允许功能上线后 README 与实际功能不一致**

---

## Agent Team 角色定义

### Plan Agent (软件架构师)
- **触发**: 新功能设计、API 变更、DB schema 变更、重构
- **职责**: 设计 API 端点、数据模型、组件树，输出到 plan file
- **规则**:
  - API 前缀统一 `/api/v1/`
  - 新模型放 `backend/app/models/`, schema 放 `schemas/`, 路由放 `api/`, 逻辑放 `services/`
  - 前端新页面放 `views/`, API 调用封装放 `api/`
  - 所有密钥操作必须走 credential_service 加密/解密
  - 脚本执行必须走 sandbox_service Docker 隔离

### Explore Agent (代码勘探)
- **触发**: 定位代码、搜索符号、追踪依赖链
- **重点路径**: `backend/app/api/` `backend/app/services/` `frontend/src/views/`
- **搜索策略**: 先用 grep 精确匹配，再用 glob 模糊匹配，最后读文件确认

### Code Reviewer Agent (代码审查)
- **Python 检查项**:
  - FastAPI 路由是否正确使用 Depends(get_db) 和 get_current_user
  - Pydantic schema 是否配置 `from_attributes = True`
  - SQLAlchemy 查询是否有 N+1 问题
  - 异常处理是否返回合适的 HTTP status code
  - sandbox_service 是否正确清理临时文件和容器
- **Vue 检查项**:
  - 组件是否正确导入 Naive UI (按需导入，非全量)
  - Pinia store 是否正确管理 token 生命周期
  - router beforeEach 是否覆盖所有非 guest 路由
  - Axios 拦截器是否正确处理 401 跳转

### Security Reviewer Agent (安全审查)
- **关键检查**:
  - 密钥值是否只在内存中解密，不落盘
  - sandbox log 输出是否正确掩码密钥值 (`***`)
  - JWT token 过期时间是否合理
  - Docker 容器是否配置 read_only + network_mode=none
  - 用户输入是否经过 Pydantic 校验
  - 密码是否 bcrypt 哈希，不存明文
  - MASTER_KEY < 32 bytes 是否正确 padding
  - SQL 注入: SQLAlchemy ORM 参数化查询
  - XSS: Vue 模板自动转义

### Test Agent (测试工程师)
- **触发**: 任何代码变更后，用户要求验证、提测、"跑一下测试"、"验证一下"
- **职责**: 对每次代码变更编写或执行测试，确保功能正确、无回归
- **后端测试 (pytest + httpx)**:
  - 位置: `backend/tests/`，命名 `test_<模块名>.py`
  - API 测试用 `httpx.AsyncClient` 或 FastAPI `TestClient`
  - 必须覆盖: 正常请求 200/201、参数校验 422、未登录 401、资源不存在 404
  - sandbox_service 测试 mock Docker SDK，不真启容器
  - auth_service 测试 JWT 签发/验证/过期
  - credential_service 测试 加密→解密 往返
- **前端测试 (vitest + @vue/test-utils)**:
  - 位置: `frontend/src/__tests__/`，命名 `*.test.ts`
  - 组件测试: mount 后检查关键 DOM 元素存在
  - Store 测试: 验证 login/logout 状态转换
  - Router 测试: 验证路由守卫 未登录→跳转/login
- **端到端验证 (curl 冒烟测试)**:
  - 位置: `tests/smoke.sh`
  - 覆盖: health check → login → CRUD scripts → execute → CRUD credentials → 查日志
  - Docker Compose 启动后一键验证全流程
- **规则**:
  - 每次代码变更后主动提示是否需要跑测试
  - 新增 API 端点必须同步新增对应 test case
  - 安全相关变更 (sandbox/credential/auth) 必须跑全量安全测试
  - 测试失败不允许 commit

## 代码约定

### Python 后端
- 配置从 `app.config.settings` 导入，不硬编码
- 数据库 session 通过 FastAPI `Depends(get_db)` 注入
- 业务逻辑放 services/，api/ 只做参数校验和响应
- 新 API 端点在对应 router 中用 `@router.get/post/put/delete` 装饰

### Vue 前端
- Naive UI 组件按需导入，不全局注册
- API 调用走 `@/api/` 封装的函数，不在组件中直接调 axios
- 页面级组件放 `views/`，可复用组件放 `components/`
- 路由 meta: `{ guest: true }` 表示不需要登录

### 数据库与迁移

- 使用 SQLite，数据库文件位于 `data/ops.db`
- 新增表通过 `Base.metadata.create_all()` 自动创建
- 已有表新增字段通过 `main.py` 中的 `_migrate_xxx_table()` 函数以 `ALTER TABLE ADD COLUMN` 方式添加
- **存量数据兼容性规则（必须遵守）**：
  - 所有新增字段必须在模型中定义 Python 级默认值（如 `default=""`, `default=True`, `default=0`），确保新旧代码都能正确创建带默认值的行
  - 数据库迁移 (`ALTER TABLE ADD COLUMN`) 必须指定 SQL 级 `DEFAULT`（如 `DEFAULT ''`, `DEFAULT 1`），确保已存在的旧行在新增列上填充默认值而不是 NULL
  - 前端展示新增字段时必须处理可能的 NULL 值（`render: (r) => r.new_field || '-'`），防止页面因空值渲染异常
  - 旧数据回填策略：若新字段的值需要从旧字段推导，必须在迁移后立即执行 UPDATE 回填逻辑
  - 禁止删除或重命名已有字段（除非确认该字段在所有环境中均无数据依赖）
- 迁移函数示例：
  ```python
  # 正确: Python 默认值 + SQL DEFAULT 双保险
  # model: new_field = Column(String(64), default="")
  # migrate: _migrate("table", [("new_field", "VARCHAR(64) DEFAULT ''")])
  ```

### 测试
- 后端测试: `backend/tests/test_<module>.py`，pytest + httpx
- 前端测试: `frontend/src/__tests__/*.test.ts`，vitest + @vue/test-utils
- 冒烟测试: `tests/smoke.sh`，curl 全流程验证

## 常用命令

```bash
# 后端开发
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端开发
cd frontend && npm install && npm run dev

# 测试 API
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin"}'

# 后端测试
cd backend && pip install pytest httpx && python -m pytest tests/ -v

# 前端测试
cd frontend && npm run test

# 冒烟测试 (Docker Compose 启动后)
bash tests/smoke.sh

# 部署
docker compose up -d
```
