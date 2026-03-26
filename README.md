# 公开网站线索解析调试台

本项目是一个面向公开网页线索采集、解析、清洗、审核放行、错误调试、训练池沉淀与审计追踪的 MVP 后台。

## 目标

- 可运行
- 可维护
- 契约一致
- 可测试
- 可扩展

## 技术栈

- Backend: FastAPI
- Frontend: HTML + Tailwind CSS + Jinja2
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations / init: Alembic + `create_all` 初始化入口
- Crawling: requests + BeautifulSoup
- Optional dynamic crawling: Playwright
- Export: CSV
- Integration reserved: n8n webhook

## 目录结构

```text
.
├── app/
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── crawler/
│   ├── templates/
│   ├── static/
│   └── seeds/
├── scripts/
├── tests/
├── README.md
├── .env.example
└── requirements.txt
```

## 环境准备

### 1. 安装依赖

```powershell
py -3 -m pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，然后按本机环境调整 `DATABASE_URL`、`N8N_WEBHOOK_URL`、`ERP_BASE_URL` 等字段。

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/lead_parser
```

如果你只想先做本地 smoke 调试，也可以临时把 `DATABASE_URL` 改成 SQLite，例如：

```env
DATABASE_URL=sqlite:///./lead_parser.db
```

## 初始化数据库

> 建议在「空数据库」或「干净 schema」下执行 migration，避免旧表结构造成 drift。  
> 若需对既有数据库升级，请先备份，并先在备份库完成演练后再套用到正式环境。

预期：
- `upgrade head` 成功（无 error）
- `current` 显示 head revision：`0002_v02_delta_lists_dedupe_trace`

### PowerShell

```powershell
.\scripts\init_db.ps1
```

这一步会执行 `app.db.init_db`，创建当前 contract 需要的表结构。

## Seed 数据

```powershell
.\scripts\seed_db.ps1
```

这一步会执行 `app.seeds.seed_data`，注入最小可预览数据，包括任务、规则、样本、错误桶、训练队列、审计记录和系统配置占位。

## 启动服务

```powershell
py -3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动后访问：

- [首页 / Dashboard](http://127.0.0.1:8000/dashboard)
- [任务列表](http://127.0.0.1:8000/jobs)
- [新建任务](http://127.0.0.1:8000/jobs/new)
- [规则列表](http://127.0.0.1:8000/rules)
- [样本列表](http://127.0.0.1:8000/samples)
- [训练队列](http://127.0.0.1:8000/training-queue)
- [审计日志](http://127.0.0.1:8000/audit)
- [系统配置](http://127.0.0.1:8000/config)

## API 入口

统一前缀：`/api/v1`

### 基础

- `GET /api/v1/health`
- `GET /api/v1/dashboard/summary`

### Jobs / Runs / Rules / Samples / Queue / Audit / Config

- `GET|POST /api/v1/jobs`
- `GET|PUT|DELETE /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/runs`
- `GET|POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET|POST /api/v1/rules`
- `GET|PUT|DELETE /api/v1/rules/{rule_id}`
- `GET /api/v1/rule-versions`
- `GET|POST /api/v1/samples`
- `GET /api/v1/samples/{sample_id}`
- `GET|POST /api/v1/error-buckets`
- `GET|POST /api/v1/training-queue`
- `PUT /api/v1/training-queue/{item_id}`
- `GET|POST /api/v1/audit`
- `GET|PUT /api/v1/config`
- `GET /api/v1/seeds/preview`
- `POST /api/v1/seeds/load`

### Crawler 入口

- `POST /api/v1/crawler/preview`
- `POST /api/v1/crawler/robots-check`

本地 SSL 校验配置：

```env
CRAWLER_SSL_VERIFY=true
```

- 默认 `true`：保持生产安全默认值，启用证书校验。
- 本地开发若遇到证书链问题，可临时设为 `false` 进行排障。
- 当为 `false` 时，crawler 请求会使用 `verify=False`，并在日志/错误信息中给出开发提示。

## Crawler Preview / robots-check

### preview

请求示例：

```json
{
  "url": "https://example.com/contact",
  "timeout": 20,
  "max_retries": 2,
  "respect_robots": true,
  "user_agent": "Mozilla/5.0 (compatible; LeadParserBot/1.0)"
}
```

### robots-check

请求示例：

```json
{
  "url": "https://example.com/contact",
  "user_agent": "Mozilla/5.0 (compatible; LeadParserBot/1.0)"
}
```

## 本地证书问题排障

如果 `POST /api/v1/crawler/preview` 返回 `fetch_failed` 且包含 `CERTIFICATE_VERIFY_FAILED`：

1. 优先修复本机证书链（推荐，保持 `CRAWLER_SSL_VERIFY=true`）。
2. 仅在本地调试阶段，临时设置：

```env
CRAWLER_SSL_VERIFY=false
```

3. 重启服务后重试 preview。

注意：不要在生产环境关闭 SSL 校验。

## 运行测试

```powershell
py -3 -m pytest
```

Smoke 预期：
- 全部测试通过（无 fail / error）

如果本机还没装测试依赖，可以先执行：

```powershell
py -3 -m pip install -r requirements.txt
```

## 交付检查清单

- [ ] 可安装依赖
- [ ] 可初始化数据库
- [ ] 可 seed 数据
- [ ] 可启动 FastAPI
- [ ] 可打开页面
- [ ] 可创建任务
- [ ] 可保存配置
- [ ] 可查看规则、样本、训练池、审计日志
- [ ] 可调用 crawler preview
- [ ] 可调用 robots-check

## 非阻塞 TODO

- 多语言解析支持
- AI 辅助规则生成
- 自动字段置信度优化
- 高级去重策略
- 分布式爬虫调度
- 前端组件化升级
- RBAC 权限系统

## 已知限制

- 这是 MVP，不包含登录绕过、验证码对抗、风控规避等能力
- 页面以后台骨架为主，复杂交互留给后续版本
- `crawler/preview` 会真实发起公开网页请求，请只用于允许抓取的公开网页
- `robots.txt` 检查已保留入口，但不会主动绕过限制
- 当前 seed 数据规模很小，主要用于验证 contract 和页面链路

## 数据相容性

- 本版本以 Alembic migration 为唯一 schema 来源
- 不支持旧版 `create_all` 直接升级
- 既有数据库建议：
  - 先 backup
  - 视情况使用 `stamp 0001_baseline` 后再 `upgrade head`

## 回滚提示

> 注意：部分 schema 变更（例如新增字段、索引）可能无法完全还原数据状态，回滚前请确认已有备份。

## RC 判定

- RC 可发布：Yes
- 判定依据：migration、API、page、dedupe、trace smoke 全绿，无阻塞问题

## 许可证

MIT
