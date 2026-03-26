\# Workflow Overview



\## Purpose

This document defines the end-to-end workflow of the project, including data acquisition, database storage, dashboard generation, manual override inputs, runtime recovery, and operator handoff.



This file is the system-level overview.

For task-specific actions, read the corresponding workflow files under `docs/workflows/`.



\---



\## 1. System Goal

The project exists to maintain a repeatable local workflow for:



1\. collecting pricing / model-related data

2\. storing structured results in the local database

3\. generating a local analysis dashboard

4\. supporting manual corrections where automation is insufficient

5\. enabling resume / recovery / troubleshooting during long-running tasks



The workflow is designed for local execution, local persistence, and operator-visible outputs.



\---



\## 2. End-to-End Flow

The primary workflow is:



\*\*task launch -> crawler execution -> structured storage -> dashboard build -> local visualization\*\*



In practical terms:



1\. an operator launches a task through a PowerShell entrypoint

2\. a Python task performs crawling / extraction / processing

3\. results are stored in `sol.db` and/or emitted to `data/`

4\. dashboard build scripts read database content

5\. dashboard HTML is generated under `dashboard/`

6\. operators open the dashboard locally in Chrome



\---



\## 3. Workflow Layers



\### 3.1 Execution Layer

Responsible for starting and running operational jobs.



Current known files:

\- `scripts/run\_st0306\_task.ps1`

\- `scripts/st0306\_st\_task.py`



Responsibilities:

\- launch crawler tasks

\- provide runtime parameters

\- enforce task-level pacing or throttling

\- determine output locations

\- handle execution entrypoints used by operators



Notes:

\- PowerShell scripts should be treated as operational entrypoints

\- Python scripts should be treated as the main implementation layer



\---



\### 3.2 Storage Layer

Responsible for persistent structured results.



Current known storage:

\- `sol.db`



Current known tables:

\- `parts\_pricing`

\- `sol\_3233`

\- `st\_lookup`



Responsibilities:

\- preserve crawler output

\- preserve normalized or queryable records

\- provide input to dashboard generation

\- act as the main structured data source for downstream analysis



Known importance:

\- `parts\_pricing` is currently a primary table for dashboard generation



\---



\### 3.3 Output / State Layer

Responsible for logs, temporary outputs, runtime coordination, and resume behavior.



Current known location:

\- `data/`



Known output categories:

\- `log`

\- `json`

\- `csv`

\- `png`

\- `resume\_state`

\- `lock`



Responsibilities:

\- store task logs

\- store intermediate exports

\- store task recovery state

\- prevent duplicate execution where locking is used

\- preserve runtime evidence for validation and triage



Notes:

\- `data/` is both an output directory and an operational state directory

\- operators should inspect `data/` when verifying runtime or diagnosing failures



\---



\### 3.4 Manual Override Layer

Responsible for operator-supplied corrections or supplemental data.



Current known file:

\- `data/recent\_orders\_manual\_overrides.csv`



Responsibilities:

\- override or supplement automatically collected data

\- allow operator correction where automation is incomplete or inaccurate

\- provide controlled manual input into the analytical pipeline



Notes:

\- manual overrides are part of the workflow, not an exception outside the system

\- future workflow files should define when and how overrides are applied



\---



\### 3.5 Dashboard Build Layer

Responsible for transforming database content into a local visual interface.



Current known file:

\- `scripts/build\_profit\_radar.py`



Responsibilities:

\- read structured data from `sol.db`

\- transform data into dashboard-ready content

\- generate `dashboard/profit\_radar.html`



Notes:

\- this layer is a view-generation layer, not the crawler itself

\- this layer should be rerun whenever the underlying dataset changes and dashboard output must be refreshed



\---



\### 3.6 Visualization Layer

Responsible for local review of results.



Current known files:

\- `dashboard/profit\_radar.html`

\- `dashboard/open\_profit\_radar\_chrome.ps1`

\- `dashboard/open\_profit\_radar\_chrome.bat`



Responsibilities:

\- provide a human-readable interface for results

\- expose analysis-oriented UI such as filtering, tabbing, calculation panels, or notes

\- provide a simple local launch path for operators



Known UI elements:

\- profit radar

\- TP calculation

\- filtering

\- list display

\- note saving

\- tab-based navigation



Notes:

\- this is currently a locally opened HTML dashboard

\- it should be treated as a generated artifact, not as the source of truth



\---



\## 4. Current Primary Workflow



\### 4.1 Launch

Start from an approved PowerShell entrypoint.



Example:

\- `scripts/run\_st0306\_task.ps1`



Expected operator intent:

\- run or restart crawler execution

\- provide required inputs and runtime parameters

\- begin a controlled collection task



\---



\### 4.2 Crawl / Process

The Python crawler / task implementation performs the main operational work.



Example:

\- `scripts/st0306\_st\_task.py`



Expected outcomes:

\- records are collected or updated

\- output evidence is written to logs / files

\- relevant structured results are saved



\---



\### 4.3 Store

Structured results are written to the database.



Current primary database:

\- `sol.db`



Expected outcomes:

\- queryable records are available for downstream use

\- the latest valid state is recoverable without relying only on logs



\---



\### 4.4 Build Dashboard

Generate the HTML dashboard from database content.



Example:

\- `scripts/build\_profit\_radar.py`



Expected outcomes:

\- fresh dashboard HTML is produced

\- current analytical state is rendered for human review



\---



\### 4.5 Review

Open the generated dashboard locally.



Examples:

\- `dashboard/open\_profit\_radar\_chrome.ps1`

\- `dashboard/open\_profit\_radar\_chrome.bat`



Expected outcomes:

\- operators can review results visually

\- operators can inspect pricing / analysis outputs without directly querying the database



\---



\## 5. Supporting Workflows



\### 5.1 Manual Override Workflow

This workflow exists when automatically collected information is incomplete or requires correction.



Current known artifact:

\- `data/recent\_orders\_manual\_overrides.csv`



General sequence:

1\. operator edits or updates override input

2\. override data is incorporated into the analysis pipeline

3\. dashboard output is rebuilt if needed

4\. operator verifies the effect in the dashboard



Open question:

\- exact integration timing and precedence should be documented in `manual-override.md`



\---



\### 5.2 Resume / Recovery Workflow

This workflow exists for interrupted tasks or long-running jobs.



Current known artifacts:

\- `data/resume\_state/`

\- `data/\*.log`

\- `data/\*.lock`



General sequence:

1\. inspect latest logs

2\. inspect existing lock or running state

3\. determine whether the task can resume safely

4\. continue from saved progress rather than restarting blindly



Open question:

\- exact resume policy should be documented in `recover-resume.md`



\---



\### 5.3 Runtime Triage Workflow

This workflow exists for failures, stalls, or unexpected behavior.



Typical evidence sources:

\- stdout logs

\- stderr logs

\- lock files

\- resume state

\- database freshness

\- generated dashboard recency



General sequence:

1\. inspect recent logs

2\. identify first actionable failure

3\. distinguish root cause from secondary symptoms

4\. apply minimal corrective action

5\. verify recovery using logs and outputs



Open question:

\- exact troubleshooting steps should be documented in `log-triage.md`



\---



\### 5.4 Quote Trial Run Workflow

This workflow exists for real inquiry preview and guarded quote review.

Current workflow file:

- `docs/workflows/quote-trial-run.md`

General sequence:

1\. run `/quote-preview <model> <qty>` through bridge

2\. inspect returned `decision_id` and `task_id`

3\. query decision details

4\. query task relay timeline

5\. let human decide whether to copy the suggested reply

\---

\### 5.5 ERP Refresh To Quote Inputs Workflow

This workflow exists for refreshing quote inputs after ERP import.

Current workflow file:

- `docs/workflows/refresh-quote-overrides-from-erp.md`

General sequence:

1\. import ERP workbook into `sol.db`

2\. refresh first-round override CSV

3\. refresh override smoke check outputs

4\. refresh handoff guardrail CSV

\---

\## 6. Sources of Truth

When there is conflict or uncertainty, use this order:



1\. `AGENTS.md`

2\. `data/requirements\_memory.md`

3\. `docs/workflows/\*.md`

4\. active scripts in `scripts/`

5\. database content in `sol.db`

6\. latest logs and runtime artifacts in `data/`



Rules:

\- generated dashboard HTML is not a source of truth

\- file names alone are not a source of truth for operational policy

\- logs are evidence of runtime behavior, not policy definitions

\- memory and workflow documentation should reflect current operational truth



\---



\## 7. Current Known Artifacts by Role



\### Execution

\- `scripts/run\_st0306\_task.ps1`

\- `scripts/st0306\_st\_task.py`



\### Storage

\- `sol.db`

\- tables: `parts\_pricing`, `sol\_3233`, `st\_lookup`



\### Output / Runtime State

\- `data/\*.log`

\- `data/\*.json`

\- `data/\*.csv`

\- `data/\*.png`

\- `data/resume\_state/\*`

\- `data/\*.lock`



\### Manual Input

\- `data/recent\_orders\_manual\_overrides.csv`



\### Dashboard Build

\- `scripts/build\_profit\_radar.py`



\### Dashboard Output / Launch

\- `dashboard/profit\_radar.html`

\- `dashboard/open\_profit\_radar\_chrome.ps1`

\- `dashboard/open\_profit\_radar\_chrome.bat`



\---



\## 8. What Is Already Established

The project already has:



\- an operational entrypoint

\- a crawler implementation

\- a local structured database

\- a generated dashboard

\- a local dashboard launch path

\- manual override input

\- runtime logs and recovery-related artifacts



This means the project already has a real operating workflow, even if the documentation is incomplete.



\---



\## 9. What Still Needs Documentation

The following should be added as dedicated workflow files:



\- `docs/workflows/restart-crawler.md`

\- `docs/workflows/build-dashboard.md`

\- `docs/workflows/recover-resume.md`

\- `docs/workflows/manual-override.md`

\- `docs/workflows/log-triage.md`



The following should also be maintained:



\- `AGENTS.md`

\- `data/requirements\_memory.md`

\- `data/session\_handoff.md`

\- `docs/decisions.md`



\---



\## 10. Operating Principles

Until more specific workflow documents are complete, follow these principles:



1\. prefer existing operational scripts over inventing new ones

2\. verify with logs instead of assuming success

3\. treat the database as the structured result source

4\. treat dashboard HTML as a generated view

5\. preserve resume and lock behavior

6\. keep manual overrides explicit and traceable

7\. keep documentation synchronized with operational changes



\---



\## 11. Immediate Next Steps

Recommended next documentation files to create:



1\. `docs/workflows/restart-crawler.md`

2\. `docs/workflows/build-dashboard.md`

3\. `docs/workflows/recover-resume.md`



Recommended next governance files to maintain:



1\. `AGENTS.md`

2\. `data/requirements\_memory.md`

3\. `data/session\_handoff.md`

4\. `docs/decisions.md`



\---



\## 12. Summary

This project currently operates as a local pipeline with:



\- script-based execution

\- SQLite-based structured storage

\- file-based runtime evidence and recovery artifacts

\- manual override support

\- generated HTML-based local visualization



The workflow is functional.

The main missing piece is governance documentation so that operators and local coding agents follow the same rules consistently.

