\# Log Triage Workflow



\## Purpose

This workflow defines the correct process for reading, interpreting, and triaging logs in this repository.



Use this workflow when the operator asks to:



\- 看 log

\- 看 err log

\- 為什麼停了

\- why failed

\- check logs

\- investigate issue

\- 看看現在卡在哪

\- find the cause

\- 判斷有沒有真的成功啟動



This workflow exists to prevent false success reports, shallow diagnosis, and confusion between root cause and downstream symptoms.



\---



\## Scope

This workflow applies to runtime diagnosis using:



\- stdout logs

\- stderr logs

\- related process state

\- resume state

\- lock artifacts

\- build output

\- DB freshness when needed for validation



It applies to:

\- crawler launch failures

\- stalled crawler runs

\- resume/recovery confusion

\- dashboard build failures

\- unexpected partial runs

\- cases where a command executed but the task did not actually succeed



It does not replace the restart, resume, or dashboard workflows.

It supports them by providing diagnosis rules.



\---



\## Read Before Acting

Before doing anything, read:



1\. `AGENTS.md`

2\. `data/requirements\_memory.md`

3\. `docs/workflows/overview.md`

4\. `data/session\_handoff.md`



Also read the workflow file most relevant to the task context:



\- `docs/workflows/restart-crawler.md`

\- `docs/workflows/recover-resume.md`

\- `docs/workflows/build-dashboard.md`



Use those files to understand expected behavior before deciding something is broken.



\---



\## Core Triage Principles



\### 1. Logs are evidence, not decoration

Logs are one of the main evidence sources for runtime truth.

Do not ignore them.

Do not summarize them vaguely when they contain actionable detail.



\### 2. Stderr is important, but not automatically the root cause

An error line in stderr is not always the first cause.

It may be:

\- a downstream symptom

\- a cleanup-side warning

\- a retry trace

\- a non-blocking issue



Always determine whether the message is:

\- root cause

\- secondary symptom

\- noise

\- expected runtime signal



\### 3. No error line does not mean success

A task can fail or stall even when stderr is empty.



You must still inspect:

\- current process state

\- recent stdout behavior

\- timestamp freshness

\- expected progress movement



\### 4. First actionable failure matters most

When multiple messages exist, identify the first actionable failure, not the loudest one.



\### 5. Runtime context matters

The same log line can mean different things depending on whether the task is:

\- just launched

\- pacing under rate limit

\- resuming from saved state

\- skipping existing rows

\- rebuilding dashboard

\- retrying recoverably



Never read a log line in isolation from workflow context.



\---



\## Required Pre-Action Summary

Before performing deep triage, provide a short summary containing:



1\. task understood

2\. log sources being inspected

3\. current workflow context

4\. what success/failure would mean in this context

5\. anything uncertain



Example structure:



\- task: determine why main 1306 crawl appears stalled

\- sources: latest stdout/stderr logs, process list, session handoff

\- workflow context: restart/resume flow

\- failure criteria: no healthy process or no meaningful progress

\- uncertainty: latest log path not yet confirmed



This step reduces shallow diagnosis.



\---



\## Triage Procedure



\### Step 1. Identify the context

Determine which workflow context applies:



\- launch / restart triage

\- resume / recovery triage

\- crawler progress triage

\- dashboard build triage

\- lock / resume-state confusion

\- dependency failure

\- unknown / mixed context



Do not diagnose before knowing what normal behavior should look like.



\---



\### Step 2. Identify the relevant evidence sources

Collect the most relevant evidence available.



Typical sources:

\- latest stdout log

\- latest stderr log

\- current process list

\- command line of active processes

\- lock files

\- resume state files

\- dashboard output timestamp

\- DB freshness if needed

\- session handoff notes



Prioritize the sources closest to the event being investigated.



\---



\### Step 3. Confirm log freshness

Before interpreting any log, confirm:



\- which file is the latest

\- whether the file timestamp is current

\- whether the latest lines correspond to the current run

\- whether you are reading the correct flow's log



Do not diagnose from stale logs by accident.



\---



\### Step 4. Read stdout first for execution narrative

Stdout often tells the runtime story:



\- startup confirmation

\- dependency checks

\- pacing

\- scope selection

\- skip-existing behavior

\- resume index

\- progress lines

\- current model

\- clean completion markers



Use stdout to reconstruct what the task believes it is doing.



\---



\### Step 5. Read stderr for failure signals

Use stderr to find:



\- tracebacks

\- subprocess failures

\- file/path errors

\- browser/CDP connection failures

\- permission errors

\- malformed input issues

\- repeated retries that became fatal



But do not stop at "stderr has text."

Interpret whether the stderr content is blocking and primary.



\---



\### Step 6. Compare logs against expected workflow behavior

Ask:



\- does this look like healthy startup?

\- does this look like healthy pacing under current rate limit?

\- does this look like resume behavior?

\- does this look like skip-existing behavior?

\- does this look like a stale/stuck process?

\- does this look like dashboard build success?

\- does this match current operational truth?



Expected examples of healthy behavior may include:

\- rate-limit pacing lines

\- progress lines with current model

\- skip-existing summary

\- resume start index

\- normal build output

\- current file regeneration



Unexpected behavior may include:

\- immediate repeated failure loops

\- missing progress movement

\- missing output file

\- wrong scope

\- impossible cadence relative to current policy

\- dependency not found



\---



\### Step 7. Check live process state

Logs alone are not enough.



Check:

\- whether the process still exists

\- whether it is the correct script/flow

\- whether multiple overlapping runs exist

\- whether the process appears alive but frozen

\- whether the task exited after writing only a short startup sequence



This helps distinguish:

\- healthy active work

\- dead process with old logs

\- duplicate process conflict

\- stalled task



\---



\### Step 8. Classify the issue

Classify the result into one of these categories:



\#### A. Healthy

\- process exists or task completed successfully

\- logs match expected behavior

\- no blocking issue detected



\#### B. Healthy but slow / rate-limited

\- progress is slow, but expected under current cadence

\- logs show pacing or waiting

\- no blocking error exists



\#### C. Already running, no restart needed

\- user thinks it failed, but logs/processes show healthy current work



\#### D. Partial / uncertain

\- some evidence suggests progress

\- some evidence is missing or stale

\- cannot safely declare full success or clear failure yet



\#### E. Recoverable failure

\- blocking issue identified

\- minimal corrective action is possible



\#### F. Investigation needed

\- evidence conflicts

\- root cause is unclear

\- logs are stale, incomplete, or inconsistent



Do not collapse all non-success cases into "failed."



\---



\### Step 9. Identify the first actionable cause

From all observed evidence, state:



1\. the first actionable cause

2\. whether it is confirmed or inferred

3\. what downstream symptoms it created

4\. the smallest valid next action



This is the most important output of triage.



\---



\## Common Patterns to Recognize



\### Pattern 1. Successful command, unsuccessful task

Symptoms:

\- command was issued

\- no stable process remains

\- logs stop immediately

\- no meaningful progress follows



Interpretation:

\- launch command success is not runtime success



Action:

\- classify as failed or partial

\- identify why the task did not persist



\---



\### Pattern 2. Slow but healthy run

Symptoms:

\- progress appears sparse

\- cadence is slow

\- logs mention pacing / wait / rate-limit

\- process remains healthy



Interpretation:

\- likely expected under `1 model per 2 minutes`



Action:

\- classify as healthy but slow

\- do not relaunch unnecessarily



\---



\### Pattern 3. Resume looks like restart

Symptoms:

\- operator thinks the run restarted from zero

\- logs show skip-existing or resume start index



Interpretation:

\- this may actually be valid resume behavior



Action:

\- report resume facts explicitly

\- do not diagnose as failure without contradiction



\---



\### Pattern 4. Duplicate-run confusion

Symptoms:

\- multiple related processes

\- mixed logs

\- conflicting progress impressions



Interpretation:

\- overlapping runs may be distorting diagnosis



Action:

\- identify which process/log belongs to which flow

\- report duplication risk clearly



\---



\### Pattern 5. Dashboard stale, not crawler failure

Symptoms:

\- DB or crawler updated

\- dashboard still looks old

\- crawler logs may actually be healthy



Interpretation:

\- likely a rebuild / refresh issue, not a crawler failure



Action:

\- switch diagnosis to dashboard build context



\---



\### Pattern 6. Stale log mistaken for active issue

Symptoms:

\- log contains old error

\- file timestamp is old

\- current process/log shows different reality



Interpretation:

\- stale evidence



Action:

\- use current run evidence instead



\---



\## Evidence Hierarchy

When evidence conflicts, prefer this order:



1\. current process state

2\. latest relevant stdout/stderr logs for the active run

3\. resume / lock artifacts

4\. DB freshness or output artifact freshness

5\. session handoff notes

6\. historical assumptions



Do not let old assumptions override current evidence.



\---



\## Required Report Format

After triage, report in this structure:



\### Triage Result

\- healthy / healthy but slow / already running / partial / recoverable failure / investigation needed



\### Workflow Context

\- restart / resume / crawler progress / dashboard build / mixed



\### First Actionable Cause

\- confirmed or inferred cause

\- brief explanation



\### Symptoms Observed

\- key log/process symptoms only



\### Evidence

\- latest stdout log path

\- latest stderr log path

\- relevant process ids if available

\- key log lines

\- relevant timestamp or artifact evidence



\### Recommended Next Step

\- one smallest valid next action only



Do not dump raw logs without interpretation.



\---



\## What Not to Do

Do not:



\- treat any stderr text as automatic root cause

\- declare success because a command returned normally

\- diagnose from stale logs without checking timestamps

\- ignore process state

\- confuse slow pacing with failure

\- confuse resume behavior with restart failure

\- use dashboard appearance alone to diagnose crawler state

\- list many speculative causes when one actionable cause is already evident



\---



\## Minimal Safe Triage Heuristic

If time is limited, minimum safe triage still requires:



1\. identify workflow context

2\. confirm latest relevant stdout/stderr logs

3\. check current process state

4\. compare logs with expected workflow behavior

5\. identify the first actionable cause

6\. report with evidence



Anything less risks shallow or wrong diagnosis.



\---



\## Interaction with Other Workflow Files

This workflow is designed to work alongside:



\- `docs/workflows/overview.md`

\- `docs/workflows/restart-crawler.md`

\- `docs/workflows/build-dashboard.md`

\- `docs/workflows/recover-resume.md`

\- `data/session\_handoff.md`

\- `docs/decisions.md`



\---



\## Summary

A valid log triage is only complete when the agent:



\- identifies the correct workflow context

\- checks fresh stdout and stderr

\- checks live process state

\- separates root cause from symptoms

\- distinguishes healthy slow behavior from real failure

\- reports the first actionable cause with evidence

