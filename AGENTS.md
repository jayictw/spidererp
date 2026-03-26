# AGENTS.md

## Project
公开网站线索解析调试台

本项目用于公开网站潜在客户线索的采集、解析、清洗、审核放行、错误调试、训练池沉淀与审计追踪。

---

## Primary Goal
以多 agent 协作方式开发一个可运行的 MVP，优先保证：

1. 可运行
2. 可维护
3. 契约一致
4. 可测试
5. 可扩展

不要为了“看起来完整”而牺牲一致性。

---

## Compliance and Safety Boundaries
本项目必须严格遵守以下边界：

1. 仅处理公开网页数据
2. 不做登录绕过
3. 不做验证码对抗
4. 不做拟人化规避
5. 不做平台风控绕过
6. 必须预留 robots.txt 检查入口
7. 必须实现基础限速与失败重试
8. 必须记录审计日志
9. 所有采集结果必须带 `source_url`、`crawl_time`、`confidence`
10. 敏感字段必须支持后续脱敏或加密扩展

如果某功能可能违反上述边界，停止实现并改为 TODO 说明。

---

## Tech Stack
- Backend: FastAPI
- Frontend: HTML + Tailwind CSS + Jinja2
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Crawling: requests + BeautifulSoup
- Optional dynamic crawling: Playwright
- Export: CSV
- Integration reserved: n8n webhook

---

## Development Principle
始终遵循以下原则：

1. 先规划，再冻结 contract，再并行开发
2. 所有 agent 必须遵守统一 schema
3. 不允许 agent 擅自修改共享字段名
4. 不允许 agent 越界改动其他模块
5. MVP 第一，复杂功能第二
6. 优先清晰实现，不做过度抽象
7. 能标记 TODO 的功能，不要强行塞进第一版

---

## Multi-Agent Roles

### 1. PlannerAgent
职责：
- 拆解需求
- 输出目录结构
- 输出数据库表设计
- 输出 API contract
- 输出页面路由
- 输出状态流转
- 输出各 agent 分工

限制：
- 不直接大规模写实现代码
- 只提供接口骨架、契约和规划说明

---

### 2. FrontendAgent
职责：
- 负责 HTML + Tailwind + Jinja2 模板
- 负责后台页面布局与交互结构
- 提供空状态、占位内容、状态标签、表格、表单、筛选区

限制：
- 不修改数据库结构
- 不擅自发明新字段
- 不修改 API contract
- 不修改 crawler 输出 schema

---

### 3. BackendAgent
职责：
- 实现 FastAPI app
- 实现 SQLAlchemy models
- 实现 API 路由
- 实现 CRUD
- 实现系统配置、任务、规则、样本、审计等接口
- 统一响应格式
- 提供 seed data

限制：
- 不改页面设计规范
- 不修改 frontend 约定字段
- 不擅自改变 crawler normalized schema

---

### 4. CrawlerAgent
职责：
- 实现公开网页抓取模块
- robots.txt 检查入口
- 域名级限速
- 基础重试
- 页面解析
- 联系方式抽取
- 去重逻辑
- 输出统一 normalized schema

限制：
- 不做任何规避检测设计
- 不引入登录态抓取
- 不修改主业务 contract

---

### 5. RulesAgent
职责：
- 实现 Rule Memory
- 实现规则版本管理
- 实现样本解释逻辑接口
- 实现 review / pending / approved 状态流转
- 预留 n8n / ERP 接口扩展位

限制：
- 不绕过审计
- 不直接篡改原始样本
- 不修改 crawler 原始结果结构

---

### 6. QAAgent
职责：
- 编写 smoke tests
- 检查模型与 schema 一致性
- 检查 API contract 与页面字段一致性
- 检查命名冲突、imports、明显 bug
- 输出修复建议

限制：
- 不大改架构
- 不在无说明情况下重写模块

---

### 7. IntegratorAgent
职责：
- 汇总并整合所有模块
- 修复 import、命名、接口冲突
- 确保项目可启动
- 输出运行说明
- 输出后续 TODO

限制：
- 不推翻已冻结 contract
- 只做最小必要整合修复

---

## Contract Rules
所有 agent 必须遵守以下规则：

1. 先输出 contract，再进入实现
2. contract 冻结后，不得随意修改
3. 若确需修改共享 schema，必须：
   - 明确指出冲突
   - 给出最小修改方案
   - 等主控确认后再改
4. 每个 agent 输出时都要说明：
   - 修改了哪些文件
   - 为什么这样改
   - 是否影响其他模块

---

## Unified API Response Format
所有 API 尽量统一为以下格式：

成功：
```json
{
  "success": true,
  "data": {},
  "message": ""
}
```

失败：
```json
{
  "success": false,
  "error": "...",
  "message": ""
}
```

---

## Unified Status Values

统一状态值仅使用以下受控字符串：

- `pending`
- `running`
- `parsed`
- `review`
- `failed`
- `approved`
- `exported`

不要发明新的状态名，除非先修改 contract。

---

## Core Domain Objects

本项目至少包含以下实体：

- `Job`
- `JobRun`
- `Rule`
- `RuleVersion`
- `Sample`
- `ErrorBucket`
- `TrainingQueueItem`
- `AuditLog`
- `SystemConfig`

---

## Crawler Normalized Schema

Crawler 输出必须统一为以下结构：

```json
{
  "company_name": "",
  "website": "",
  "person_name": "",
  "title": "",
  "email": "",
  "phone": "",
  "whatsapp": "",
  "country": "",
  "source_url": "",
  "crawl_time": "",
  "confidence": 0.0,
  "raw_text": "",
  "raw_html_excerpt": ""
}
```

任何 agent 都不得私自修改这个结构。

---

## MVP Modules

第一版必须覆盖以下模块：

- Dashboard
- Jobs
- Rule Memory
- Rule Version History
- Config Readiness
- Error Buckets
- Runs
- Samples
- Training Queue
- Audit Timeline

---

## Required Pages

至少提供以下页面：

- `/dashboard`
- `/jobs`
- `/jobs/new`
- `/rules`
- `/rules/{id}`
- `/samples`
- `/training-queue`
- `/audit`
- `/config`

要求：

- 中文界面
- 简洁后台风格
- 支持空状态
- 支持状态 badge
- 支持基础筛选
- 支持 seed 数据预览

---

## Required Fields

### Job
- `task_name`
- `crawl_scope`
- `source_type`
- `keywords`
- `start_page`
- `max_pages`
- `time_range`
- `include_domains`
- `exclude_rules`
- `rule_notes`
- `schedule_mode`
- `schedule_note`
- `n8n_webhook`
- `auto_push_n8n`
- `enabled`

### Rule
- `rule_name`
- `hit_hint`
- `explanation_rule`
- `sample_input`
- `expected_output`
- `version_note`
- `enabled`
- `auto_approve_on_hit`

### Config
- `erp_base_url`
- `n8n_webhook`
- `n8n_token`
- `erp_intake_token`

### Sample
- `source_name`
- `title`
- `keyword`
- `status`
- `rule_name`
- `erp_status`
- `raw_payload`
- `normalized_payload`
- `source_url`
- `crawl_time`
- `confidence`

### ErrorBucket
- `rule_name`
- `error_reason`
- `status`
- `source`
- `count`
- `updated_at`

### TrainingQueueItem
- `sample_id`
- `priority`
- `queue_status`
- `linked_rule`
- `note`

### AuditLog
- `event_time`
- `object_type`
- `object_id`
- `source`
- `action`
- `status`
- `operator`
- `summary`
- `detail_json`

---

## File and Code Quality Rules

- 文件命名清晰
- 关键函数需要简短注释
- 不做过度复杂抽象
- 所有环境变量集中在 `.env.example`
- 必须提供 `README.md`
- 必须提供 migration 或初始化方案
- 必须提供 seed data
- 必须提供至少一组 API smoke tests

---

## Preferred Project Structure

建议目录结构如下：

```text
.
├── AGENTS.md
├── README.md
├── .env.example
├── alembic.ini
├── docs/
├── migrations/
├── app/
│   ├── main.py
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── api/
│   ├── services/
│   ├── crawler/
│   ├── rules/
│   ├── templates/
│   ├── static/
│   └── seeds/
├── tests/
└── scripts/
```

实际生成时可微调，但不要偏离太远。

---

## Execution Order

必须严格按以下顺序执行：

### Phase 1: Planning

只允许 PlannerAgent 工作，输出：

- 项目目录结构
- 数据库表设计
- API 路由设计
- 页面路由说明
- 状态流转说明
- agent 分工清单

此阶段不要生成完整实现代码。

### Phase 2: Contract Freeze

主控汇总：

- models contract
- API request/response contract
- page-field contract

然后明确输出：

`Contract Frozen`

### Phase 3: Parallel Build

在 contract 冻结后，再并行调用：

- FrontendAgent
- BackendAgent
- CrawlerAgent
- RulesAgent

### Phase 4: QA Review

调用 QAAgent：

- 检查字段一致性
- 检查路由一致性
- 检查 imports
- 检查明显 bug
- 输出修复建议

### Phase 5: Integration

调用 IntegratorAgent：

- 合并模块
- 修复冲突
- 输出运行步骤
- 输出最终目录树
- 输出 TODO

---

## Startup Definition of Done

最终至少要能完成：

- 安装依赖
- 配置 `.env`
- 初始化数据库
- 启动 FastAPI
- 打开页面
- 创建任务
- 查看规则
- 查看样本
- 查看审计日志

---

## What To Do When Unclear

如果遇到不明确问题，按以下优先级处理：

- 优先遵守已冻结 contract
- 优先保持字段与状态一致
- 优先做最小可运行实现
- 无法确认的复杂功能标记为 TODO
- 不要为了“聪明”而擅自扩展范围

---

## Default Instruction for Codex

除非用户明确要求直接写代码，否则默认先进入：

`Phase 1: Planning`

先规划，不要立刻生成全部代码。
