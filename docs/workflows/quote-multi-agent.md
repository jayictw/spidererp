# Quote Multi-Agent Workflow

## Purpose

This document defines the planned multi-agent collaboration workflow for supplier-context pricing work.

This workflow is separate from the current ST official price fill workflow. It must reuse existing repository scripts and data flows where possible, and it must not break the current production crawler path.

---

## 1. Workflow Position

This workflow handles a different problem from the ST crawler.

The ST crawler flow is still:

- fill missing `st_official_price_usd`
- use existing `scripts/*.ps1` launchers
- write to current DB / dashboard pipeline

The quote multi-agent workflow is for:

- supplier sheet intake
- supplier stock context parsing
- public marketplace price collection
- ERP / history-based pricing boundaries
- guarded QQ first-round reply

It is currently a controlled design and implementation track, not a replacement for the existing production crawler objective.

---

## 2. Core Principle

Do not combine data collection, pricing policy, and customer reply into one unrestricted agent.

Use a coordinator plus specialized sub-agents with explicit boundaries:

1. data agents collect and normalize evidence
2. pricing agent derives recommendation boundaries
3. QQ reply agent only speaks within allowed first-round scope
4. human takeover handles negotiation and exceptions

---

## 3. Agent Roles

## 3.1 Main Agent: Quote Orchestrator

Responsibilities:

- receive a quoting task from QQ conversation or operator batch input
- create a per-request work item
- call the required sub-agents in order
- collect evidence from each step
- decide one of:
  - direct quote
  - ask target price
  - wait / apply / handoff to human
- persist decision and traceable evidence

Inputs:

- QQ inquiry or operator-triggered quote request
- supplier item reference or uploaded supplier list
- customer context if available

Outputs:

- pricing decision record
- handoff reason when auto quote is not allowed
- reply payload for QQ agent when auto reply is allowed

Guardrails:

- never fetch raw marketplace data directly if a dedicated sub-agent exists
- never bypass ERP boundary checks
- never allow QQ free-form negotiation outside first-round rules

## 3.2 Sub-Agent: Supplier Sheet Parser

Current repository anchor:

- `F:/Jay_ic_tw/scripts/vendor_platform_price_collect.py`

Responsibilities:

- read supplier input file (`csv`, `xlsx`, or mislabeled payload)
- detect part-number column and supplier stock-related columns
- preserve original supplier stock text
- parse supplier stock into structured fields where confidence is sufficient
- emit parse status and uncertainty markers

Required outputs:

- `supplier_part_number`
- `normalized_part_number`
- `normalization_basis`
- `supplier_stock_raw`
- `supplier_stock_qty`
- `supplier_stock_year`
- `supplier_stock_lot`
- `supplier_package`
- `supplier_lead_time`
- `supplier_stock_note`
- `parse_confidence`
- `parse_status`

Rules:

- raw supplier text must be retained
- if parsing is uncertain, keep raw text and mark `manual_review`
- normalization by inference must not be silently treated as exact truth

## 3.3 Sub-Agent: Marketplace Fetcher

Current repository anchor:

- `F:/Jay_ic_tw/scripts/vendor_platform_price_collect.py`

Initial supported sources:

- `bomman.com`
- `so.szlcsc.com`

Responsibilities:

- query one normalized model at a time
- save source platform, searched keyword, matched candidate, and URL
- mark `not_found`, `multiple_candidates`, `blocked`, `fetch_error`, or `manual_review`
- checkpoint after each processed model

Required outputs:

- `source_platform`
- `searched_keyword`
- `matched_part_number`
- `match_confidence`
- `price`
- `currency`
- `package`
- `moq`
- `stock`
- `seller_name`
- `region`
- `url`
- `capture_time`
- `match_status`
- `notes`
- `raw_snapshot_path`

Rules:

- do not treat the first text hit as final truth when multiple candidates exist
- preserve snapshot or raw reference for later audit
- write progress incrementally for resume safety

## 3.4 Sub-Agent: Trader Quote Collector

Responsibilities:

- collect competitor or trader quote references through compliant means
- support human-assisted entry where automation is not safe or allowed

Rules:

- do not design around bypassing login, CAPTCHA, or access controls
- when a source is not automatable within policy, downgrade to manual-assist mode

## 3.5 Sub-Agent: ERP / History Reader

Responsibilities:

- read internal pricing boundaries
- return lowest allowed quote, normal quote, recent deal price, and customer tier
- expose internal reasons that affect quoting boundaries

Required outputs:

- `erp_floor_price`
- `erp_normal_price`
- `last_deal_price`
- `customer_tier`
- `customer_style`
- `internal_notes`

Rules:

- internal pricing boundaries are authoritative over public market temptation
- if ERP facts are missing, orchestrator must lower confidence or handoff

## 3.6 Sub-Agent: QQ First-Round Pricing Agent

Current repository anchor:

- `F:/Jay_ic_tw/qq/agent-harness/cli_anything/qq/core/quote_workflow.py`
- `F:/Jay_ic_tw/qq/agent-harness/bridge_server.py`

Responsibilities:

- send one clarification if model or qty is missing
- send auto quote only when orchestrator says auto reply is allowed
- send fixed apply / wait wording before handoff when approval is required
- stop after handoff

Allowed automatic scope:

- model + quantity + first-round price reply
- ask customer target price when policy permits

Disallowed automatic scope:

- delivery negotiation
- date code / batch commitment
- source guarantee
- complaint handling
- deep bargaining below floor
- quality dispute

---

## 4. Data Flow

The intended flow is:

1. request enters from QQ or operator batch
2. Quote Orchestrator creates request context
3. Supplier Sheet Parser extracts supplier-side facts
4. Marketplace Fetcher collects public price references
5. Trader Quote Collector adds market reference when available
6. ERP / History Reader returns internal quote boundaries
7. Quote Orchestrator computes recommendation and action
8. QQ First-Round Pricing Agent sends guarded reply or marks human handoff
9. results are written to traceable storage

---

## 5. Suggested Storage Model

Use separate tables or equivalent persisted artifacts for each stage.

## 5.1 `supplier_items`

One row per supplier input item.

Suggested fields:

- `supplier_item_id`
- `batch_id`
- `supplier_name`
- `supplier_part_number`
- `normalized_part_number`
- `normalization_basis`
- `supplier_stock_raw`
- `supplier_stock_qty`
- `supplier_stock_year`
- `supplier_stock_lot`
- `supplier_package`
- `supplier_lead_time`
- `supplier_stock_note`
- `parse_confidence`
- `parse_status`
- `created_at`

## 5.2 `market_quotes`

One row per source-platform result.

Suggested fields:

- `market_quote_id`
- `supplier_item_id`
- `source_platform`
- `searched_keyword`
- `matched_part_number`
- `match_confidence`
- `price`
- `currency`
- `package`
- `moq`
- `stock`
- `seller_name`
- `region`
- `url`
- `capture_time`
- `match_status`
- `notes`
- `raw_snapshot_path`

## 5.3 `pricing_decisions`

One row per orchestrated quote decision.

Suggested fields:

- `decision_id`
- `qq_conversation_id`
- `customer_id`
- `supplier_item_id`
- `normalized_part_number`
- `requested_qty`
- `erp_floor_price`
- `erp_normal_price`
- `last_deal_price`
- `market_low_price`
- `market_median_price`
- `trader_reference_price`
- `proposed_quote`
- `quote_strategy`
- `confidence`
- `auto_reply_allowed`
- `handoff_reason`
- `created_at`

---

## 6. State Machine

Recommended request states:

- `received`
- `input_profiled`
- `supplier_parsed`
- `market_fetched`
- `erp_loaded`
- `decision_ready`
- `auto_quoted`
- `clarification_sent`
- `handoff_pending`
- `handoff_done`
- `blocked`

Rules:

- each transition should be logged
- a failed sub-step should not erase previous evidence
- resume should continue from the latest durable checkpoint

Current minimal implementation:

- `F:/Jay_ic_tw/sol.db`
  - table: `quote_tasks`
- `F:/Jay_ic_tw/scripts/dispatch_quote_task.py`
  - supports:
    - `--enqueue`
    - `--run-next`
    - `--run-stage`
- current implemented task states:
  - `queued`
  - `evidence_ready`
  - `decision_ready`
  - `completed`
  - `failed`
- current behavior:
  - `supplier_market_worker` advances `queued -> evidence_ready`
  - `pricing_worker` advances `evidence_ready -> decision_ready`
  - `qq_preview_worker` advances `decision_ready -> completed`
  - `run-next` advances the oldest available task by one stage

---

## 7. Handoff Rules

The orchestrator should hand off to human when any of the following is true:

- model cannot be identified reliably
- quantity cannot be identified after one clarification
- ERP boundary is missing
- supplier parse is low-confidence and affects pricing meaningfully
- marketplace returns only ambiguous candidates
- customer asks about batch / year / source / complaint / guarantee
- requested target price is below floor or approval threshold

The QQ agent must not negotiate through these conditions.

---

## 8. Existing Repository Components to Reuse

Use these as the current base instead of inventing replacements:

- supplier + marketplace prototype:
  - `F:/Jay_ic_tw/scripts/vendor_platform_price_collect.py`
- QQ guarded quote logic:
  - `F:/Jay_ic_tw/qq/agent-harness/cli_anything/qq/core/quote_workflow.py`
- QQ bridge entrypoint:
  - `F:/Jay_ic_tw/qq/agent-harness/bridge_server.py`
- QQ local store:
  - `F:/Jay_ic_tw/qq/agent-harness/cli_anything/qq/utils/soq_store.py`

Current implementation gap:

- today the supplier parser and marketplace fetcher are partially combined in one prototype script
- today the QQ quote workflow still reads local product rules directly, without a full Quote Orchestrator layer
- ERP / history reader and pricing decision persistence are not yet formalized in this repository

---

## 9. Recommended Implementation Phases

## Phase 1: Supplier + Marketplace Pipeline

Goal:

- stabilize supplier sheet parsing
- retain raw stock context
- query `bomman.com` and `so.szlcsc.com`
- write resumable result rows with evidence

## Phase 2: Pricing Boundary Layer

Goal:

- add ERP / history reader
- generate pricing recommendation and confidence
- persist `pricing_decisions`

## Phase 3: Orchestrated QQ Reply

Goal:

- insert Quote Orchestrator between QQ inbound message and reply path
- allow QQ auto reply only from orchestrator-approved decisions

## Phase 4: Learning / Review Loop

Goal:

- analyze logs for alias patterns, parsing misses, and recurring handoff reasons
- produce review suggestions without silently expanding permissions

---

## 10. Reporting Requirements

Any run or batch execution in this workflow should report:

### Result

- success / failed / partial / already running

### Action Taken

- script or workflow used
- whether a new process was launched
- whether docs / memory were updated

### Current Facts

- input file and detected columns
- current supported platforms
- checkpoint / resume location
- parse status summary
- match status summary
- handoff status if relevant

### Evidence

- output file or table path
- event table path when task queue is used
- resume state path
- lock path
- latest useful log lines
- snapshot references if available

### Next Recommendation

- one small next step only

---

## 11. Conflict Notes

If this workflow ever conflicts with the current ST crawler production path:

1. `AGENTS.md` controls
2. `data/requirements_memory.md` controls next
3. the existing ST production entrypoints remain primary for live crawler work
4. this quote workflow must be implemented as an additive path, not a silent replacement
