# Project Requirements Memory

Last updated: 2026-03-09

## Current Operational Truth
- Primary target table is the 1306-model database.
- The most important field to fill is `st_official_price_usd` (ST official website price).
- The current primary objective of scraping work is to fill missing ST official prices as safely and consistently as possible.
- Effective crawl cadence is **1 model per 2 minutes**.
- Effective rate-limit parameter is **`--max-per-hour 30`**.
- Current operational truth must follow this file, `AGENTS.md`, and current script content, not historical file naming.

---

## Primary Entrypoints
### Main crawler / scope pricing
- `F:/Jay_ic_tw/scripts/run_1306_scope_parts_pricing_every3min.ps1`
- Purpose:
  - Main 1306-scope pricing fill flow
  - Used to fill missing `st_official_price_usd` in the primary target scope

### Missing pricing recovery
- `F:/Jay_ic_tw/scripts/run_parts_pricing_missing_every3min.ps1`
- Purpose:
  - Recovery / backfill flow for missing pricing records

### Skip-priced crawler flow
- `F:/Jay_ic_tw/scripts/run_st0306_every3min_skippriced.ps1`
- Purpose:
  - Continue crawling while skipping already priced records where applicable

### Main crawler implementation
- `F:/Jay_ic_tw/scripts/st0306_st_task.py`
- Purpose:
  - Main task implementation for ST crawling and pricing collection

### ST slug / URL utility
- `F:/Jay_ic_tw/scripts/st_slug_utils.py`
- Purpose:
  - Convert orderable part numbers into ST product slug / URL candidates

### Data quality cleanup
- `F:/Jay_ic_tw/scripts/clean_lc_data_quality.py`
- Purpose:
  - Re-clean LC recent order quality fields before dashboard rebuild

### Dashboard rebuild
- `F:/Jay_ic_tw/scripts/build_profit_radar.py`
- Purpose:
  - Build dashboard output from current DB content

### Dashboard output
- `F:/Jay_ic_tw/dashboard/profit_radar.html`
- Purpose:
  - Generated local dashboard for result review

---

## Naming Caveats
- Filenames containing `every3min` are historical names and must **not** be treated as the current effective cadence by filename alone.
- Current effective cadence is **1 model per 2 minutes**, even if the script filename still contains `every3min`.
- Operational policy must follow:
  1. `AGENTS.md`
  2. this file
  3. current script content
- Historical naming is allowed to remain for continuity, but it is not policy truth.

---

## Core Goal
- Primary target table is the 1306-model database.
- The most important field to fill is `st_official_price_usd` (ST official website price).
- All scraping tasks should serve this single objective: fill missing ST official prices.

---

## Current Scraping Approach
- Use VDP/CDP to control an existing Chrome session for data collection.
- Existing task script:
  - `F:/Jay_ic_tw/scripts/st0306_st_task.py`

---

## ST URL/Slug Rule Requirement
- Convert full ST orderable part number to ST product-page slug by heuristic rules.
- Output URL format:
  - `https://www.st.com/en/{category}/{slug}.html`
- Keep branch suffixes when valid:
  - `-DRE`
  - `-E`
  - `-W`
  - `-Y`
  - `-R`
  - `-F`
- Remove packaging / ordering suffixes:
  - `-TR`
  - `-TP`
  - `TR`
  - `TP`
  - and removable suffix table rules
- Rule is heuristic, not 100% reversible.
- Fallback behavior and manual dictionary overrides are allowed when heuristic conversion is insufficient.

---

## Implementation Status Snapshot
- `st_part_to_product_slug` and `make_st_product_url` implemented in:
  - `F:/Jay_ic_tw/scripts/st_slug_utils.py`
- Unit tests added and passing:
  - `F:/Jay_ic_tw/tests/test_st_slug_utils.py`
- Main crawler updated to apply generic ST slug conversion and no longer STM32-only input filtering.

---

## Query Strategy Update (2026-03-09)
- For `SM6T*` and `M24C*` families, do not use batch-style series query.
- Treat them as many fine-grained branches and query one model at a time.
- Example models explicitly noted by user:
  - `SM6T6V8A`
  - `SM6T6V8AY`

---

## Data Quality Guardrails (2026-03-09)
### LC recent orders re-cleaning rule
- `recent_orders` and `lc_recent_orders_extracted` must be in `0..100`.
- Values greater than `100` are treated as extraction noise and clamped to `100`.
- Negative values are clamped to `0`.
- Decimal values are rounded to integer.

### Manual truth overrides
- Manual truth overrides must be recorded in:
  - `F:/Jay_ic_tw/data/recent_orders_manual_overrides.csv`

### Current known manual corrections
- `STM32U535RCT6 = 1`
- `STM32H755BIT3 = 3`

### Re-clean / rebuild scripts
- Re-clean script:
  - `F:/Jay_ic_tw/scripts/clean_lc_data_quality.py`
- Dashboard rebuild script:
  - `F:/Jay_ic_tw/scripts/build_profit_radar.py`

### Required run order to avoid regression
1. Run `clean_lc_data_quality.py`
2. Run `build_profit_radar.py`

---

## ST Crawl Rate Limit (2026-03-09)
- To reduce ST blocking risk, set crawl speed to **1 model per 2 minutes**.
- Effective parameter:
  - `--max-per-hour 30`
- This updated operational truth has been applied to:
  - `F:/Jay_ic_tw/scripts/run_1306_scope_parts_pricing_every3min.ps1`
  - `F:/Jay_ic_tw/scripts/run_parts_pricing_missing_every3min.ps1`
  - `F:/Jay_ic_tw/scripts/run_st0306_every3min_skippriced.ps1`

---

## Launch / Verification Rules
### Before launch
- Inspect residual related processes before starting a new crawler run.
- Avoid duplicate task launch for the same flow.
- Confirm the intended script is the correct entrypoint for the requested task.
- Check that required output paths and logs can be written.
- Check that the Chrome / CDP / VDP target is available when required by the workflow.

### After launch
- Verify that a new task actually started.
- Inspect the latest stdout log.
- Inspect the latest stderr log if present.
- Confirm current runtime facts from logs instead of assuming success from command execution alone.

### Required runtime facts to report when available
- effective cadence
- effective rate limit
- active scope
- skip-existing summary
- remaining count
- resume start index
- current progress line
- stdout log path
- stderr log path

### Duplicate-run policy
- If the same flow is already active, do not start another identical task.
- Report the existing running state instead.

---

## Data Flow / Artifacts
### Main flow
1. crawler task is launched from a PowerShell entrypoint
2. `st0306_st_task.py` performs crawling / extraction
3. results are written to DB and/or data artifacts
4. dashboard build reads DB content
5. dashboard HTML is generated
6. operator reviews generated dashboard locally

### Structured storage
- Main database:
  - `F:/Jay_ic_tw/sol.db`

### Known important table
- `parts_pricing`
- Current known role:
  - primary downstream source for pricing-related dashboard content

### Runtime / artifact storage
- Main runtime artifact folder:
  - `F:/Jay_ic_tw/data/`

### Known artifact categories under `data/`
- logs
- csv
- json
- png
- resume state
- lock files

### Manual input artifact
- `F:/Jay_ic_tw/data/recent_orders_manual_overrides.csv`

### Dashboard artifact
- `F:/Jay_ic_tw/dashboard/profit_radar.html`

### Dashboard interaction update (2026-03-10)
- `profit_radar.html` now contains a third tab: `供應商庫存`.
- This tab supports:
  - supplier inventory row editing (`model`, stock qty, order qty)
  - supplier quote input (RMB)
  - customer quote dual input (USD / RMB) with auto conversion by FX
  - profit calculation in RMB (based on order qty, tax factor, and quote)
  - model search/filter in-tab
  - local save via browser `localStorage` key: `supplier_inventory_quotes_v1`
- This is a dashboard-side interaction feature and does not change crawler cadence/rate policy.

### Dashboard interaction update (2026-03-10, later)
- In `供應商庫存` tab, `order qty` field was removed.
- Margin display is now gross margin percent (`毛利率%`) instead of RMB profit amount.
- Supplier quote input remains USD-only, with RMB tax-inclusive cost derived by FX and tax factor.
- Gross margin formula now uses USD basis:
  - `(customer_quote_usd - supplier_quote_usd) / customer_quote_usd * 100`
  - to avoid tax-basis mismatch causing false negative margin.
- Tax input fields are hidden in dashboard pages; tax is fixed at 13% (`1.13`) for calculations.
- TP memo behavior: save now overwrites existing memo when `name` is identical, instead of creating duplicate entries.

### Dashboard build dependency
- `build_profit_radar.py` reads from current DB content, especially pricing-related records

---

## Conflict Resolution
- If script filename semantics conflict with documented cadence, **documented cadence wins**.
- If historical notes conflict with the latest dated update, **latest dated update wins**, unless explicitly superseded.
- If dashboard display conflicts with DB query result, **DB/query result wins**.
- If operational behavior conflicts with stale assumptions, verify by:
  1. current script content

---

## QQ Bot Callback Verification Update (2026-03-16)
- `F:/Jay_ic_tw/qq/agent-harness/bridge_server.py` now verifies official QQ callback signatures from headers:
  - `X-Signature-Ed25519`
  - `X-Signature-Timestamp`
- Official QQ callback verification uses Ed25519 over:
  - `timestamp + raw_http_body`
- `QQ_CALLBACK_SECRET` should be set to the bot/app secret used by QQ Open Platform callback verification.
- `QQ_BOT_TOKEN` / `QQ_TOKEN_HEADER` are no longer the primary QQ official callback verification path.
- The legacy token header path is retained only as a compatibility path for local manual tests or custom reverse proxy forwarding.
  2. DB state
  3. latest logs
- Do not turn inferred behavior into permanent truth unless this file or workflow documentation is updated.

---

## Manual Capture 2026-03-09
- Input records: `22`
- Matched missing in `parts_pricing`: `11`
- Already filled in `parts_pricing`: `1`
- Not found in `parts_pricing`: `10`

### Matched models
- `L78M24ABDT-TR`
- `L78M08CDT-TR`
- `L78M15CDT-TR`
- `L78M12CDT-TR`
- `L78M12ACDT-TR`
- `L78M10ABDT-TR`
- `L78M05ACDT-TR`
- `L78M09CDT-TR`
- `L78M24CDT-TR`
- `L78M12ABDT-TR`
- `L78M15ABDT-TR`

---

## Collaboration Preference
- Keep requirement updates in this file for continuity across runs.
- Record stable operational truth here.
- Record workflow-specific procedures in `docs/workflows/*.md`.
- Record agent behavior rules in `AGENTS.md`.
- Do not rely on chat history alone for persistent project memory.

---

## QQ CLI Super User Control (2026-03-14)
- QQ harness path:
  - `F:/Jay_ic_tw/qq/agent-harness`
- New optional auth policy template:
  - `F:/Jay_ic_tw/qq/agent-harness/auth_policy.example.json`
- Auth mode is opt-in:
  - when `--auth-policy-path` points to a policy with `"enforce": true`, protected actions require verified super user signature.
- Current protected action defaults include:
  - `launch`
  - `undo`
  - `redo`
  - `send-message`
  - `upsert-product`
  - `set-conversation-mode`
  - `mark-handoff`
  - `ack-human-takeover`
- Signature format:
  - `hex(hmac_sha256(secret, "{actor}|{action}|{ts}|{nonce}"))`
- Replay guard:
  - nonce is cached in-process for TTL window to reject repeated signatures.

## QQ Bot Bridge (2026-03-14)
- Bridge entrypoint:
  - `F:/Jay_ic_tw/qq/agent-harness/bridge_server.py`
- Bridge doc:
  - `F:/Jay_ic_tw/qq/agent-harness/BRIDGE.md`
- Default endpoints:
  - `GET /health`
  - `POST /webhook`
- Routing behavior:
  - normal message -> OpenAI Responses API
  - message starts with `/admin ` -> invoke `cli-anything-qq` with super user signature parameters

---

## Supplier Quote Multi-Agent Workflow (2026-03-15)
- A new additive workflow is being established for supplier-context pricing work.
- This workflow does **not** replace the current ST official price fill production objective.
- Current design doc:
  - `F:/Jay_ic_tw/docs/workflows/quote-multi-agent.md`
- Current trial-run workflow:
  - `F:/Jay_ic_tw/docs/workflows/quote-trial-run.md`
  - `F:/Jay_ic_tw/docs/workflows/refresh-quote-overrides-from-erp.md`

### Intended agent split
- `Quote Orchestrator`
  - coordinates quote requests, evidence gathering, pricing recommendation, and handoff decision
- `Supplier Sheet Parser`
  - parses supplier file input while preserving raw stock context
- `Marketplace Fetcher`
  - queries `bomman.com` and `so.szlcsc.com`
- `Trader Quote Collector`
  - adds compliant trader-reference inputs where available
- `ERP / History Reader`
  - returns internal floor / normal / historical pricing boundaries
- `QQ First-Round Pricing Agent`
  - replies only within guarded first-round scope

### Current multi-agent implementation anchors
- orchestrator entrypoint:
  - `F:/Jay_ic_tw/scripts/quote_orchestrator.py`
- task dispatcher entrypoint:
  - `F:/Jay_ic_tw/scripts/dispatch_quote_task.py`
- task timeline query:
  - `F:/Jay_ic_tw/scripts/show_quote_task_timeline.py`
- pricing decision query:
  - `F:/Jay_ic_tw/scripts/show_pricing_decision.py`
- first-round override query:
  - `F:/Jay_ic_tw/scripts/show_quote_first_round_override.py`
- acceptance check runner:
  - `F:/Jay_ic_tw/scripts/run_quote_acceptance_check.py`
- ERP-to-override generator:
  - `F:/Jay_ic_tw/scripts/generate_quote_first_round_overrides_from_erp.py`
- override smoke check:
  - `F:/Jay_ic_tw/scripts/run_quote_override_smoke_check.py`
- handoff guardrail generator:
  - `F:/Jay_ic_tw/scripts/generate_quote_handoff_guardrails.py`
- One-command refresh path:
  - `F:/Jay_ic_tw/scripts/generate_quote_first_round_overrides_from_erp.py --refresh-guardrails`
  - this now refreshes in order:
    - `quote_first_round_overrides.csv`
    - `quote_override_smoke_check_latest.json`
    - `quote_override_smoke_check_latest.csv`
    - `quote_first_round_handoff_guardrails.csv`
- supplier reader:
  - `F:/Jay_ic_tw/scripts/quote_agents/supplier_reader.py`
- market reader:
  - `F:/Jay_ic_tw/scripts/quote_agents/market_reader.py`
- ERP reader stub:
  - `F:/Jay_ic_tw/scripts/quote_agents/erp_reader.py`
- decision writer:
  - `F:/Jay_ic_tw/scripts/quote_agents/decision_writer.py`
- QQ reply preview agent:
  - `F:/Jay_ic_tw/scripts/quote_agents/qq_reply_agent.py`
  - `F:/Jay_ic_tw/scripts/qq_reply_preview.py`
- trader quote collector:
  - `F:/Jay_ic_tw/scripts/quote_agents/trader_quote_collector.py`
  - `F:/Jay_ic_tw/scripts/import_trader_quotes.py`
- QQ first-round pricing agent:
  - `F:/Jay_ic_tw/scripts/qq_first_round_agent.py`
- task queue helper:
  - `F:/Jay_ic_tw/scripts/quote_agents/task_queue.py`

### Current orchestrator scope
- current `Quote Orchestrator` is read-only against:
  - `supplier_items`
  - `market_quotes`
  - `parts_pricing`
- current output is a JSON evidence view with:
  - supplier context
  - platform quote rows
  - market summary
  - ERP stub context
  - decision stub
- current orchestrator does **not** yet:
  - trigger QQ replies
  - call external trader sources

### First hired worker: Decision Writer (2026-03-15)
- `Decision Writer` is now implemented.
- It creates and writes to:
  - `F:/Jay_ic_tw/sol.db`
  - table: `pricing_decisions`
- Current `pricing_decisions` persistence includes:
  - part number
  - batch id
  - supplier item id
  - requested qty
  - ERP summary fields
  - market summary fields
  - proposed quote
  - quote strategy
  - confidence
  - auto reply allowed flag
  - handoff reason
  - evidence JSON snapshot
- Current orchestrator can persist a decision with:
  - `--write-decision`

### Third worker: QQ Reply Agent (preview-only)
- Current QQ reply agent is preview-only.
- It reads:
  - `pricing_decisions`
  - or orchestrator evidence directly when no decision row exists yet
- It currently outputs safe reply recommendations only:
  - `auto_quote_preview`
  - `apply_then_handoff_preview`
  - `handoff_no_reply`
  - `clarify`
- It does **not** yet send QQ messages directly.

### QQ bridge preview hook
- `F:/Jay_ic_tw/qq/agent-harness/bridge_server.py` now supports:
  - `/quote-preview <model> <qty>`
  - `/quote-task <task_id>`
- This route:
  - enqueues a quote task through `scripts/dispatch_quote_task.py`
  - advances task stages:
    - `queued`
    - `evidence_ready`
    - `decision_ready`
  - pins stage execution to the same `task_id` to avoid advancing another queued task
  - returns a bridge-level `preview_summary_text` for quick manual review
  - maps action / reason into business-friendly Chinese summary text
  - returns top-level `decision_id` for direct audit lookup
  - returns `task_id` inside `preview_result`
  - returns `internal_review_text` and `suggested_customer_reply` for human-assisted send decisions
  - returns `suggested_customer_reply_mode` as:
    - `direct_send`
    - `needs_edit`
    - `do_not_send`
  - returns preview JSON in webhook response
  - does not auto-send the preview back to QQ
  - stores preview review fields in:
    - `F:/Jay_ic_tw/qq/agent-harness/soq.db`
    - table: `soq_logs`
    - column: `agent_reply` as JSON text
- This route now also logs preview events into:
  - `F:/Jay_ic_tw/qq/agent-harness/soq.db`
  - table: `soq_logs`
- Bridge also supports a query-only task audit route:
  - `/quote-task <task_id>`
  - reads:
    - `quote_tasks`
    - `quote_task_events`
  - returns task timeline JSON and summary text
  - does not auto-send QQ message

### QQ desktop live preview path
- The previously verified working QQ path is the desktop CLI harness, not the official bot webhook path.
- Live desktop entrypoint:
  - `F:/Jay_ic_tw/qq/agent-harness/cli_anything/qq/qq_cli.py`
- Verified command form:
  - `F:/Jay_ic_tw/qq/agent-harness/.venv/Scripts/python.exe -m cli_anything.qq --json --db-path F:/Jay_ic_tw/qq/agent-harness/soq.db quote-preview-live --message "STM32L412CBU6 1560 什么价格" --conversation qq_live_preview_001 --customer-id cust_demo_001`
- Current `quote-preview-live` behavior:
  - reads the latest visible QQ inquiry or accepts explicit `--message`
  - parses `model + qty`
  - calls:
    - `F:/Jay_ic_tw/scripts/run_quote_pipeline.py`
  - writes `pricing_decisions`
  - returns preview JSON and `preview_summary_text`
  - can optionally send the preview reply through desktop QQ with `--send-reply`
- Environment note:
  - use `F:/Jay_ic_tw/qq/agent-harness/.venv/Scripts/python.exe`
  - do not rely on system `py -3` for this CLI path because local system Python is missing required QQ harness dependencies such as `click`
- QQNT compatibility update:
  - current QQ client is `QQNT`
  - main window class observed:
    - `Chrome_WidgetWin_1`
  - `qq_backend.py` now includes a UIA fallback for QQNT Chromium-rendered message areas
  - `qq_cli.py` now tolerates Windows GBK console output by falling back to `ensure_ascii=True` when needed
- Desktop auto-monitor path:
  - `F:/Jay_ic_tw/qq/agent-harness/cli_anything/qq/qq_cli.py` now supports:
    - `watch-inquiries`
  - current behavior:
    - polls the active QQ window
    - picks the latest parsed inquiry
    - deduplicates repeated visible messages by message hash
    - runs `run_quote_pipeline.py`
    - auto-sends the generated reply back to current QQ chat

### Five workers status
- Worker 1: Supplier Sheet Parser
  - implemented via `vendor_platform_price_collect.py`
- Worker 2: ERP / History Reader
  - implemented via `erp_reader.py`
- Worker 3: QQ Reply Agent
  - implemented in preview-only mode
- Worker 4: Trader Quote Collector
  - implemented via manual CSV import into `trader_quotes`
- Worker 5: QQ First-Round Pricing Agent
  - implemented as guarded first-round action generator via `qq_first_round_agent.py`
- This is the current safe bridge integration path for the third worker.

### Task queue / dispatcher status
- A first runnable quote task queue now exists in:
  - `F:/Jay_ic_tw/sol.db`
  - table: `quote_tasks`
  - table: `quote_task_events`
- Current dispatcher entrypoint:
  - `F:/Jay_ic_tw/scripts/dispatch_quote_task.py`
- Current supported dispatcher modes:
  - `--enqueue`
  - `--run-next`
  - `--run-stage`
- Current task states implemented:
  - `queued`
  - `evidence_ready`
  - `decision_ready`
  - `completed`
  - `failed`
- Current execution model:
  - `supplier_market_worker` claims `queued` tasks and writes `evidence_json`
  - `pricing_worker` claims `evidence_ready` tasks and writes `decision_id`
  - `qq_preview_worker` claims `decision_ready` tasks and writes final preview result
  - `run-next` now advances the oldest available task by one stage
  - `run-stage` can also pin execution to a specific `task_id`
- Current event audit model:
  - every enqueue / claim / stage advance / completed / failed action writes into `quote_task_events`
  - QQ preview audit logs now also carry:
    - `task_id`
    - `latest_task_event_id`
    - inside `soq_logs.agent_reply` JSON
  - `show_quote_task_timeline.py` returns the full event timeline for one `task_id`
  - `show_pricing_decision.py` returns a single decision view with evidence summary

### Current acceptance / verification status
- A runnable acceptance suite now exists for the quote workflow.
- Main acceptance test anchors:
  - `F:/Jay_ic_tw/tests/quote_test_support.py`
  - `F:/Jay_ic_tw/tests/test_quote_acceptance_flow.py`
  - `F:/Jay_ic_tw/tests/test_quote_failure_modes.py`
  - `F:/Jay_ic_tw/tests/test_bridge_quote_routes.py`
- Acceptance runner:
  - `py -3 F:/Jay_ic_tw/scripts/run_quote_acceptance_check.py`
- Current verified acceptance outputs include:
  - direct quote path:
    - `STM32L412CBU6 -> auto_quote_preview`
  - handoff path:
    - `STM32F103C8T6 -> supplier_context_missing`
  - task queue relay:
    - `event_count = 7`
    - `queued -> evidence_ready -> decision_ready -> completed`
  - bridge query path:
    - `/quote-task <task_id>`
    - query-only, no QQ auto-send

### Current repository anchors
- supplier + marketplace prototype:
  - `F:/Jay_ic_tw/scripts/vendor_platform_price_collect.py`
- QQ guarded quote workflow:
  - `F:/Jay_ic_tw/qq/agent-harness/cli_anything/qq/core/quote_workflow.py`
- QQ bridge:
  - `F:/Jay_ic_tw/qq/agent-harness/bridge_server.py`

### Phase 1 implementation status
- `vendor_platform_price_collect.py` now supports:
  - supplier part normalization with `normalization_basis`
  - supplier raw stock preservation in `supplier_stock_raw`
  - structured supplier fields:
    - `supplier_stock_qty`
    - `supplier_stock_year`
    - `supplier_stock_lot`
    - `supplier_package`
    - `supplier_lead_time`
    - `supplier_stock_note`
    - `parse_confidence`
    - `parse_status`
  - per-platform evidence fields:
    - `searched_keyword`
    - `match_confidence`
    - `capture_time`
    - `raw_snapshot_path`
    - `seller_name`
    - `region`
  - per-model incremental checkpoint / resume
  - local text snapshot output under:
    - `F:/Jay_ic_tw/data/platform_snapshots/`
  - structured SQLite persistence into:
    - `F:/Jay_ic_tw/sol.db`
    - table: `supplier_items`
    - table: `market_quotes`
- Current `match_status` values observed or supported include:
  - `not_found`
  - `multiple_candidates`
  - `manual_review`
  - `blocked`
  - `fetch_error`
  - `matched_exact`

### Phase 1 structured storage notes
- `supplier_items` stores one supplier-side parsed item per batch/input context.
- `market_quotes` stores one platform result row per supplier item and source platform.
- Current persistence path is additive and does not replace CSV output.
- Current run identity is tracked by `batch_id` stored in resume state and DB rows.

### Boundary rules
- Supplier sheet input must be treated as:
  - `part number + supplier raw stock context`
- Raw supplier stock text must be preserved in outputs.
- Marketplace collection must preserve:
  - source platform
  - URL
  - capture time
  - match status
  - snapshot reference where available
- QQ auto reply must remain limited to first-round quoting and one clarification.
- Delivery, batch/date-code, source guarantee, complaint handling, or deep bargaining must hand off to human.
- Customer grading is currently not applied for the new general first-inquiry pricing path.
- Manual first-round quote overrides are stored in:
- Manual and generated first-round quote overrides are stored in:
  - `F:/Jay_ic_tw/data/quote_first_round_overrides.csv`
- ERP batch generation rule:
  - preserve existing manual rows first
  - append generated `general` rows from ERP using `taxed_sale_price`
  - generated rows use ERP `stock_qty` as `qty_min/qty_max`
  - manual rows with the same model + qty stay first and win
- Current first-round handoff guardrail output:
  - `F:/Jay_ic_tw/data/quote_first_round_handoff_guardrails.csv`
- Latest verified handoff guardrail summary:
  - total guardrail models: `6`
  - reason split:
    - `erp_requires_price_application = 4`
    - `erp_price_inversion = 2`
- Guardrail enforcement rule:
  - `F:/Jay_ic_tw/scripts/quote_orchestrator.py` now reads `quote_first_round_handoff_guardrails.csv`
  - when a model + qty matches this guardrail list, the decision must set:
    - `auto_reply_allowed = false`
    - `handoff_reason` includes `manual_handoff_required`
  - this applies even if a general first-round override price exists
- Bridge preview summary wording:
  - `F:/Jay_ic_tw/qq/agent-harness/bridge_server.py` now maps combined handoff reasons token by token
  - when `handoff_reason` includes `manual_handoff_required`, bridge summary should show:
    - `此型号已列入人工报价名单`
- Bridge management refresh route:
  - `F:/Jay_ic_tw/qq/agent-harness/bridge_server.py` now supports:
    - `/refresh-quote-inputs`
  - this route is limited to the configured `BRIDGE_SUPER_ACTOR_ID`
  - it refreshes quote input files through:
    - `scripts/generate_quote_first_round_overrides_from_erp.py --refresh-guardrails`
  - it is query-only and does not auto-send QQ messages
  - it now returns:
    - `refresh_summary_text`
  - it now writes an audit log into:
    - `F:/Jay_ic_tw/qq/agent-harness/soq.db`
    - table: `soq_logs`
    - `action_taken = refresh_quote_inputs`
- Current explicit first-round override:
  - `STM32L412CBU6`
  - qty `1560`
  - first quote `11.5`
  - inquiry type `general`
- Current explicit first-round override:
  - `LIS2DH12TR`
  - qty `8000`
  - first quote `3.3`
  - inquiry type `general`
- Override precedence fix:
  - when a general first-round override exists, `erp_missing` must not by itself force handoff
  - this preserves the verified business rule:
    - `STM32L412CBU6 + qty 1560 -> direct first quote 11.5`

### Recommended implementation order
1. stabilize supplier parser + marketplace fetcher
2. add ERP / history reader and pricing decision storage
3. add Quote Orchestrator between QQ inbound and reply path
4. add learning / review loop without silent scope expansion

## QQNT Private Chat OCR Fast Reply (2026-03-16)
- `F:/Jay_ic_tw/qq/agent-harness/cli_anything/qq/qq_cli.py` now supports:
  - `read-current-chat-ocr`
  - `watch-private-inquiries`
- current behavior:
  - brings QQ to foreground
  - OCRs the current right-side chat pane instead of relying only on QQNT accessible text
  - extracts:
    - `chat_title`
    - `chat_kind`
    - filtered current-chat visible messages
  - skips likely group chats
  - in likely 1:1 chats, detects new `model + qty` inquiry lines and runs `run_quote_pipeline.py`
- current merged OCR inquiry parsing supports:
  - `STM32G431CBT63120什么价格 -> STM32G431CBT6 + 3120`
- current pricing policy update:
  - `F:/Jay_ic_tw/scripts/quote_orchestrator.py` now allows `erp_only` direct quote when:
    - ERP context exists
    - ERP inventory row exists
    - no handoff guardrail is hit
  - this is intended for fast first reply in QQ private chats based on ERP inventory pricing
