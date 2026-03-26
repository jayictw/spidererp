\# Decisions Log



\## Purpose

This file records important operational decisions for this repository.



Use this file to preserve:

\- what changed

\- why it changed

\- when it changed

\- which files or workflows were affected

\- how future operators or coding agents should interpret older naming or behavior



This file is not for temporary runtime status.

Temporary live state belongs in:

\- `data/session\_handoff.md`



Stable operational truth belongs in:

\- `data/requirements\_memory.md`



Agent behavior rules belong in:

\- `AGENTS.md`



Workflow procedures belong in:

\- `docs/workflows/\*.md`



\---



\## Decision Format

Use this format for future entries:



\### YYYY-MM-DD — Short Decision Title

\- decision:

\- reason:

\- affected files:

\- operational impact:

\- follow-up:



Keep entries short, concrete, and operationally useful.



\---



\## 2026-03-09 — Set ST crawl cadence to 1 model per 2 minutes

\- decision:

&#x20; - Set the effective ST crawl cadence to \*\*1 model per 2 minutes\*\*.

&#x20; - Set the effective rate-limit parameter to \*\*`--max-per-hour 30`\*\*.

\- reason:

&#x20; - Reduce ST blocking risk.

&#x20; - Prefer slower, more stable crawling over faster but riskier execution.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/scripts/run\_1306\_scope\_parts\_pricing\_every3min.ps1`

&#x20; - `F:/Jay\_ic\_tw/scripts/run\_parts\_pricing\_missing\_every3min.ps1`

&#x20; - `F:/Jay\_ic\_tw/scripts/run\_st0306\_every3min\_skippriced.ps1`

&#x20; - `F:/Jay\_ic\_tw/data/requirements\_memory.md`

\- operational impact:

&#x20; - All relevant crawler launch behavior must now follow the 2-minute cadence.

&#x20; - Agents must not infer current cadence from old filenames.

\- follow-up:

&#x20; - Continue to report effective cadence and rate-limit in runtime summaries.



\---



\## 2026-03-09 — Treat `every3min` filenames as historical names, not policy truth

\- decision:

&#x20; - Keep existing runner filenames for continuity, even if they still contain `every3min`.

&#x20; - Do not treat runner filename wording as authoritative for current cadence.

\- reason:

&#x20; - Renaming all files immediately is not required for safe operation.

&#x20; - Existing naming continuity may help preserve existing habits and script references.

&#x20; - Operational truth should come from repository memory and current script content.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/scripts/run\_1306\_scope\_parts\_pricing\_every3min.ps1`

&#x20; - `F:/Jay\_ic\_tw/scripts/run\_parts\_pricing\_missing\_every3min.ps1`

&#x20; - `F:/Jay\_ic\_tw/scripts/run\_st0306\_every3min\_skippriced.ps1`

&#x20; - `F:/Jay\_ic\_tw/data/requirements\_memory.md`

&#x20; - `F:/Jay\_ic\_tw/AGENTS.md`

\- operational impact:

&#x20; - Agents must check documentation and script content before assuming cadence.

&#x20; - Old file names are allowed to remain, but they are not current policy definitions.

\- follow-up:

&#x20; - Whenever a runtime report mentions cadence, state the effective value explicitly.



\---



\## 2026-03-09 — Make 1306 pricing fill the primary operational objective

\- decision:

&#x20; - Treat the 1306-model database as the primary operational target.

&#x20; - Treat filling missing `st\_official\_price\_usd` as the main scraping objective.

\- reason:

&#x20; - This defines a single clear goal for crawler work.

&#x20; - It reduces drift into unrelated scraping tasks.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/data/requirements\_memory.md`

&#x20; - `F:/Jay\_ic\_tw/AGENTS.md`

&#x20; - `F:/Jay\_ic\_tw/data/session\_handoff.md`

\- operational impact:

&#x20; - Agents should prefer work that directly advances missing ST official price coverage.

&#x20; - Secondary tasks should be evaluated against this goal.

\- follow-up:

&#x20; - Reassess only if project priorities change.



\---



\## 2026-03-09 — Use heuristic ST slug conversion instead of narrow STM32-only handling

\- decision:

&#x20; - Implement generic ST slug conversion logic for orderable parts.

&#x20; - Stop relying on STM32-only input filtering as the crawler assumption.

\- reason:

&#x20; - The project needs broader ST coverage beyond STM32-only patterns.

&#x20; - A generic heuristic path increases usable part coverage.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/scripts/st\_slug\_utils.py`

&#x20; - `F:/Jay\_ic\_tw/scripts/st0306\_st\_task.py`

&#x20; - `F:/Jay\_ic\_tw/tests/test\_st\_slug\_utils.py`

&#x20; - `F:/Jay\_ic\_tw/data/requirements\_memory.md`

\- operational impact:

&#x20; - ST URL generation is now heuristic and broader.

&#x20; - Fallback and manual dictionary overrides remain allowed.

\- follow-up:

&#x20; - Continue to refine only when concrete failures appear.



\---



\## 2026-03-09 — Query `SM6T\*` and `M24C\*` families one model at a time

\- decision:

&#x20; - Do not use batch-style series query for `SM6T\*` and `M24C\*` families.

&#x20; - Treat these families as fine-grained branches and query per model.

\- reason:

&#x20; - Series-level querying is too coarse for these families.

&#x20; - Fine-grained querying reduces mismatch risk.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/data/requirements\_memory.md`

&#x20; - relevant crawler/query logic as applicable

\- operational impact:

&#x20; - Agents should avoid broad family-series assumptions for these families.

&#x20; - Model-level querying is the correct operational approach.

\- follow-up:

&#x20; - Apply the same thinking to other families only when evidence supports it.



\---



\## 2026-03-09 — Apply LC recent-order data quality clamps before dashboard rebuild

\- decision:

&#x20; - Enforce cleaning rules for:

&#x20;   - `recent\_orders`

&#x20;   - `lc\_recent\_orders\_extracted`

&#x20; - Clamp values into `0..100`.

&#x20; - Round decimals to integer.

&#x20; - Treat values above `100` as extraction noise.

\- reason:

&#x20; - Prevent dashboard regressions caused by noisy extracted values.

&#x20; - Keep recent-order metrics within a meaningful and controlled range.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/scripts/clean\_lc\_data\_quality.py`

&#x20; - `F:/Jay\_ic\_tw/scripts/build\_profit\_radar.py`

&#x20; - `F:/Jay\_ic\_tw/data/requirements\_memory.md`

\- operational impact:

&#x20; - Cleanup is a required upstream step before dashboard rebuild when relevant.

&#x20; - Agents must not rebuild the dashboard first if this cleanup is required.

\- follow-up:

&#x20; - Preserve the required run order in workflow documentation.



\---



\## 2026-03-09 — Require manual truth overrides to live in a dedicated CSV

\- decision:

&#x20; - Store manual truth overrides in:

&#x20;   - `F:/Jay\_ic\_tw/data/recent\_orders\_manual\_overrides.csv`

\- reason:

&#x20; - Manual corrections must remain explicit, reviewable, and traceable.

&#x20; - This avoids burying manual truth inside ad hoc code edits or chat-only notes.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/data/recent\_orders\_manual\_overrides.csv`

&#x20; - `F:/Jay\_ic\_tw/data/requirements\_memory.md`

&#x20; - `F:/Jay\_ic\_tw/docs/workflows/build-dashboard.md`

\- operational impact:

&#x20; - Agents should treat manual overrides as an explicit input layer.

&#x20; - Rebuilds affected by overrides should report that fact.

\- follow-up:

&#x20; - Keep future manual corrections in the same explicit location.



\---



\## 2026-03-09 — Require cleanup before dashboard rebuild when LC data quality is involved

\- decision:

&#x20; - Required run order:

&#x20;   1. `clean\_lc\_data\_quality.py`

&#x20;   2. `build\_profit\_radar.py`

\- reason:

&#x20; - Avoid rebuilding dashboard views from stale or noisy LC recent-order values.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/scripts/clean\_lc\_data\_quality.py`

&#x20; - `F:/Jay\_ic\_tw/scripts/build\_profit\_radar.py`

&#x20; - `F:/Jay\_ic\_tw/data/requirements\_memory.md`

&#x20; - `F:/Jay\_ic\_tw/docs/workflows/build-dashboard.md`

\- operational impact:

&#x20; - Agents must follow the cleanup-first rebuild path when relevant.

&#x20; - Skipping cleanup in those situations is operationally incorrect.

\- follow-up:

&#x20; - Keep this run order visible in both workflow and memory files.



\---



\## 2026-03-09 — Establish repository governance files for local Codex control

\- decision:

&#x20; - Create a lightweight repository control plane using:

&#x20;   - `AGENTS.md`

&#x20;   - `data/requirements\_memory.md`

&#x20;   - `data/session\_handoff.md`

&#x20;   - `docs/workflows/overview.md`

&#x20;   - `docs/workflows/restart-crawler.md`

&#x20;   - `docs/workflows/build-dashboard.md`

&#x20;   - `docs/workflows/recover-resume.md`

&#x20;   - `docs/workflows/log-triage.md`

&#x20;   - `docs/decisions.md`

\- reason:

&#x20; - Reduce drift, forgetfulness, and ad hoc behavior from local coding agents.

&#x20; - Externalize rules, stable memory, handoff state, and operational procedures into the repo.

\- affected files:

&#x20; - all files listed above

\- operational impact:

&#x20; - Local Codex now has persistent repository guidance instead of relying on chat history.

&#x20; - High-frequency operations now have explicit SOPs.

\- follow-up:

&#x20; - Keep these files updated when operational truth changes.



\---



\## 2026-03-09 — Separate stable memory, session state, workflows, and decisions

\- decision:

&#x20; - Use:

&#x20;   - `data/requirements\_memory.md` for stable operational truth

&#x20;   - `data/session\_handoff.md` for live current state

&#x20;   - `docs/workflows/\*.md` for procedural workflows

&#x20;   - `docs/decisions.md` for rationale and history

\- reason:

&#x20; - Different information types should not be mixed together.

&#x20; - This makes future maintenance and agent reading more reliable.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/data/requirements\_memory.md`

&#x20; - `F:/Jay\_ic\_tw/data/session\_handoff.md`

&#x20; - `F:/Jay\_ic\_tw/docs/workflows/\*.md`

&#x20; - `F:/Jay\_ic\_tw/docs/decisions.md`

\- operational impact:

&#x20; - Agents should know where to read and where to write each type of information.

&#x20; - Stable rules are less likely to be polluted by temporary runtime notes.

\- follow-up:

&#x20; - Preserve this separation when adding future documents.



\---



\## 2026-03-09 — Require evidence-based reporting for launch, resume, and build actions

\- decision:

&#x20; - Launch, resume, and rebuild actions must be reported using runtime evidence instead of assumption.

\- reason:

&#x20; - A command returning successfully is not sufficient proof of operational success.

&#x20; - The project depends on logs, process state, and generated artifacts for trustworthy validation.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/AGENTS.md`

&#x20; - `F:/Jay\_ic\_tw/docs/workflows/restart-crawler.md`

&#x20; - `F:/Jay\_ic\_tw/docs/workflows/recover-resume.md`

&#x20; - `F:/Jay\_ic\_tw/docs/workflows/build-dashboard.md`

&#x20; - `F:/Jay\_ic\_tw/docs/workflows/log-triage.md`

\- operational impact:

&#x20; - Agents must verify with logs, process state, timestamps, or output artifacts.

&#x20; - Vague success claims are not acceptable.

\- follow-up:

&#x20; - Keep report formats concrete and evidence-based.



\---



\## Notes for Future Entries

When adding a new decision:

\- prefer one decision per entry

\- name the decision clearly

\- list affected files explicitly

\- explain the operational impact, not just the technical change

\- keep the follow-up small and concrete



\---



\## 2026-03-15 - Establish additive multi-agent workflow for supplier-context quoting

\- decision:

&#x20; - Establish a dedicated multi-agent workflow for supplier-context quoting.

&#x20; - Keep this workflow separate from the current ST official price fill production flow.

&#x20; - Use a `Quote Orchestrator` plus bounded sub-agents instead of one unrestricted quoting agent.

\- reason:

&#x20; - Supplier quoting depends on multiple evidence sources:

&#x20;   - supplier raw stock context

&#x20;   - marketplace prices

&#x20;   - internal ERP / history boundaries

&#x20;   - guarded QQ reply logic

&#x20; - Mixing these concerns in one agent would reduce traceability and control.

&#x20; - The repository already contains reusable building blocks that should be composed rather than replaced.

\- affected files:

&#x20; - `F:/Jay\_ic\_tw/docs/workflows/quote-multi-agent.md`

&#x20; - `F:/Jay\_ic\_tw/data/requirements\_memory.md`

&#x20; - existing implementation anchors referenced by the workflow:

&#x20;   - `F:/Jay\_ic\_tw/scripts/vendor_platform_price_collect.py`

&#x20;   - `F:/Jay\_ic\_tw/qq/agent-harness/cli_anything/qq/core/quote_workflow.py`

&#x20;   - `F:/Jay\_ic\_tw/qq/agent-harness/bridge_server.py`

\- operational impact:

&#x20; - Future work on supplier quoting should follow the new bounded multi-agent split.

&#x20; - Supplier input must be treated as `part number + supplier raw stock context`, not part number alone.

&#x20; - QQ auto reply remains a narrow first-round interface and must not become the data collection layer.

&#x20; - Existing ST crawler launchers and production objective remain unchanged.

\- follow-up:

&#x20; - Implement Phase 1 by hardening `vendor_platform_price_collect.py` toward the documented supplier parser + marketplace fetcher contract.

