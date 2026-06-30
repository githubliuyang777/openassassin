# Ops Platform — Agent Team Charter

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
