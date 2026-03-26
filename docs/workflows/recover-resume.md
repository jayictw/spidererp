\# Recover / Resume Workflow



\## Purpose

This workflow defines the correct process for recovering, resuming, or safely continuing interrupted crawler work in this repository.



Use this workflow when the operator asks to:



\- 續跑

\- resume

\- recover

\- 從中斷處恢復

\- continue from last progress

\- 接著跑

\- recover interrupted run



This workflow exists to prevent blind restarts, duplicate work, corrupted resume behavior, and false assumptions about progress.



\---



\## Scope

This workflow applies to interrupted or partially completed crawler-related work, especially for:



\- 1306 scope pricing fill

\- missing pricing recovery

\- skip-priced continuation flows

\- any ST crawl that uses logs, resume state, or lock behavior to continue work



It does not define dashboard rebuild behavior except where resume completion affects downstream rebuild timing.



\---



\## Read Before Acting

Before doing anything, read:



1\. `AGENTS.md`

2\. `data/requirements\_memory.md`

3\. `docs/workflows/overview.md`

4\. `docs/workflows/restart-crawler.md`

5\. `data/session\_handoff.md`



Also inspect the relevant scripts when needed:



\- `scripts/run\_1306\_scope\_parts\_pricing\_every3min.ps1`

\- `scripts/run\_parts\_pricing\_missing\_every3min.ps1`

\- `scripts/run\_st0306\_every3min\_skippriced.ps1`

\- `scripts/st0306\_st\_task.py`



\---



\## Current Operational Defaults

Unless current memory or script content says otherwise, use these defaults:



\- effective cadence: \*\*1 model per 2 minutes\*\*

\- effective rate limit: \*\*`--max-per-hour 30`\*\*

\- filenames containing `every3min` are historical names and do not override current policy



Never infer operational truth from filename alone.



\---



\## Required Pre-Action Summary

Before making any impactful recovery or resume action, provide a short summary containing:



1\. task understood

2\. files consulted

3\. evidence being used to infer current state

4\. intended action

5\. intended verification method

6\. anything uncertain



Example structure:



\- task: resume main 1306 pricing flow

\- consulted: `AGENTS.md`, `requirements\_memory.md`, `session\_handoff.md`, latest logs

\- evidence: latest stdout/stderr log, process list, resume markers

\- intended action: continue from existing valid state

\- verify by: log tail + process check + resume facts

\- uncertainty: none



This step is required to avoid incorrect continuation from stale assumptions.



\---



\## Resume / Recovery Principles



\### 1. Recovery is not blind restart

Do not treat resume as "just start it again."



Recovery requires evidence from:

\- logs

\- process state

\- resume state

\- lock state

\- current scope / progress facts

\- session handoff, if available



\### 2. Prefer continuation from valid state

If valid progress already exists, prefer continuing from that state rather than restarting from zero.



\### 3. Duplicate-run prevention still applies

If the same flow is already alive and healthy, do not launch another copy just because the user said "resume."



\### 4. Report actual resume behavior

If the run uses skip-existing logic, resume index logic, scope filtering, or lock-mediated continuation, report that explicitly.



\### 5. Evidence beats memory when checking live runtime

Memory files define policy, but live runtime state must be verified with current evidence.



\---



\## Recovery / Resume Procedure



\### Step 1. Identify the flow to recover

Determine which flow is being resumed:



\- main 1306 scope pricing fill

\- missing pricing recovery

\- skip-priced continuation

\- another explicitly named crawler flow



If unclear, infer conservatively from:

\- session handoff

\- latest logs

\- recent operator instructions

\- known entrypoints



Do not invent a new flow.



\---



\### Step 2. Inspect current evidence

Before acting, inspect the current state using as many of these as are available:



\- latest stdout log

\- latest stderr log

\- current PowerShell processes

\- current Python processes

\- related command lines

\- resume state artifacts under `data/`

\- lock files under `data/`

\- recent session handoff notes



Goal:

\- determine whether work is already active

\- determine whether prior progress exists

\- determine whether recovery should continue, relaunch, or stop for investigation



\---



\### Step 3. Classify the situation

Classify the current state into one of these cases:



\#### Case A. Already running and healthy

Symptoms:

\- relevant process exists

\- logs are advancing or reflect healthy pacing

\- no blocking error is visible



Action:

\- do not relaunch

\- report `already running`

\- provide evidence and current progress facts



\#### Case B. Not running, but recoverable state exists

Symptoms:

\- relevant process is gone

\- logs / resume markers / skip summaries indicate prior valid progress

\- no evidence suggests the state is invalid



Action:

\- relaunch the correct approved entrypoint

\- continue from recoverable state

\- verify resumed behavior with logs



\#### Case C. Not running, but state is unclear

Symptoms:

\- no valid active process

\- logs are stale or ambiguous

\- resume / lock artifacts are inconsistent

\- last failure is not understood



Action:

\- do not fake recovery confidence

\- inspect failure evidence first

\- possibly switch to triage workflow before resuming



\#### Case D. Running but unhealthy

Symptoms:

\- process exists

\- logs show repeated error / stuck behavior / no useful progress

\- resume is not the real issue; health is



Action:

\- treat as investigation first

\- do not classify as successfully resumed

\- use minimal corrective action only after identifying the first actionable problem



\---



\### Step 4. Determine the approved entrypoint

Choose the correct existing entrypoint based on the flow:



\#### Main 1306 scope pricing fill

\- `scripts/run\_1306\_scope\_parts\_pricing\_every3min.ps1`



\#### Missing pricing recovery

\- `scripts/run\_parts\_pricing\_missing\_every3min.ps1`



\#### Skip-priced continuation

\- `scripts/run\_st0306\_every3min\_skippriced.ps1`



If uncertain:

1\. use `data/requirements\_memory.md`

2\. use recent session handoff

3\. use latest log naming/context

4\. prefer the most specific existing runner



Do not invent a new resume wrapper.



\---



\### Step 5. Inspect resume-related artifacts

Before relaunching, inspect any available artifacts that indicate recoverability:



\- latest logs

\- skip-existing summary

\- remain count

\- resume start index

\- current model snapshot

\- `resume\_state` files

\- `lock` files



Purpose:

\- understand whether the system can safely continue

\- understand whether prior work already filtered completed items

\- avoid duplicate or regressive work



If lock state or resume state is suspicious, report that explicitly.



\---



\### Step 6. Verify dependencies before relaunch

Before relaunching a recoverable flow, verify relevant dependencies.



Typical checks may include:



\- selected entrypoint exists

\- underlying Python task exists

\- output/log path is writable

\- required browser / CDP / VDP target is available if needed

\- input sources still exist

\- there is no conflicting active task



Do not skip dependency verification just because this is a resume.



\---



\### Step 7. Relaunch only if justified

Relaunch the correct approved entrypoint only when:



\- the same flow is not already running

\- recoverable state exists or restart is explicitly justified

\- dependencies are available

\- there is no blocking unresolved error that makes relaunch pointless



Rules:

\- do not restart blindly

\- do not change cadence or rate-limit silently

\- do not bypass the standard runner unless explicitly asked



\---



\### Step 8. Verify resumed behavior

After relaunch, verify that the task is truly continuing.



At minimum inspect:



\- latest stdout log path

\- latest stderr log path

\- latest log tail

\- related running process list



Look specifically for evidence such as:

\- resumed index

\- skip-existing summary

\- reduced remain count

\- next current model line

\- healthy pacing lines

\- no immediate blocking failure



Do not claim `resumed successfully` without evidence.



\---



\### Step 9. Report current resume facts

Report as many of the following as are available:



\- whether the flow was already running or relaunched

\- selected entrypoint

\- effective cadence

\- effective rate limit

\- active scope

\- skip-existing summary

\- remain count

\- resume start index

\- current progress line

\- current model

\- stdout log path

\- stderr log path

\- any blocker or uncertainty



If a fact is not verified, say so explicitly.



\---



\## Standard Verification Checklist

A recovery / resume is only considered valid if most of the following are true:



\- the intended flow was correctly identified

\- current runtime evidence was inspected

\- duplicate-run risk was checked

\- resume-related artifacts were inspected if available

\- the correct approved entrypoint was used when relaunch was needed

\- logs show actual continuation or healthy new runtime behavior

\- stderr is empty, understood, or non-blocking

\- reported facts reflect evidence rather than assumption



\---



\## Required Report Format

After performing the workflow, report in this structure:



\### Result

\- success / already running / partial / failed



\### Action Taken

\- selected entrypoint

\- whether a new process was launched

\- whether an existing process was reused

\- whether investigation was needed before resume



\### Current Facts

\- effective cadence

\- effective rate limit

\- active scope

\- resume / skip summary

\- remain count

\- resume start index

\- current progress line

\- current model if visible



\### Evidence

\- stdout log path

\- stderr log path

\- relevant process ids if available

\- relevant lock / resume artifact notes

\- latest useful log lines



\### Next Recommendation

\- one small next step only



Do not use vague resume language.



\---



\## Duplicate-Run Rule

The following rule is strict:



\- do not launch a second identical flow just because the user asked to resume



If an equivalent flow is already active:

\- classify as `already running`

\- provide current evidence

\- report the latest progress facts

\- explain that relaunch was skipped to avoid duplication



\---



\## Lock / Resume-State Handling

If lock or resume-state artifacts exist, do not ignore them.



Explicitly note when observed:



\- lock file present

\- lock file stale

\- resume marker present

\- resume marker missing

\- resume behavior inferred from logs rather than files

\- lock / resume evidence is inconsistent



If evidence is inconsistent, do not overstate confidence.



\---



\## Common Failure Cases



\### Case 1. Operator says resume, but the task is already healthy

Symptoms:

\- process exists

\- logs are moving

\- no blocker is visible



Action:

\- do not relaunch

\- report `already running`



\### Case 2. Process died, but valid progress exists

Symptoms:

\- no active process

\- logs/resume evidence show valid prior progress



Action:

\- relaunch correct runner

\- verify continuation evidence



\### Case 3. Resume markers exist, but state is inconsistent

Symptoms:

\- log says one thing

\- lock/resume file suggests another

\- last completion point is unclear



Action:

\- report ambiguity

\- investigate before blindly continuing



\### Case 4. Relaunch succeeds, but the task restarts from the wrong place

Symptoms:

\- expected resume behavior does not appear

\- progress facts look like a cold start

\- skip-existing or resume index does not appear as expected



Action:

\- treat as partial or failed

\- report mismatch explicitly

\- do not pretend resume worked as intended



\### Case 5. Immediate repeated failure after relaunch

Symptoms:

\- process starts then stops

\- same blocking error repeats



Action:

\- stop calling it a resume problem

\- switch to failure triage

\- identify the first actionable failure



\---



\## What Not to Do

Do not:



\- restart blindly without checking evidence

\- treat resume as a synonym for relaunch

\- ignore duplicate active tasks

\- ignore lock or resume artifacts

\- claim success without log evidence

\- silently change operational parameters during recovery

\- hide uncertainty when recovery state is ambiguous

\- use dashboard appearance as proof that resume succeeded



\---



\## Minimal Safe Resume Heuristic

If time is limited, the minimum safe resume still requires:



1\. read `AGENTS.md`

2\. read `data/requirements\_memory.md`

3\. inspect `data/session\_handoff.md`

4\. inspect latest logs and active processes

5\. determine whether the flow is already running

6\. inspect resume / lock indicators if available

7\. relaunch only if justified

8\. verify resumed behavior with logs

9\. report with evidence



Anything less risks false resume claims.



\---



\## Interaction with Other Workflow Files

This workflow is designed to work alongside:



\- `docs/workflows/overview.md`

\- `docs/workflows/restart-crawler.md`

\- `docs/workflows/build-dashboard.md`

\- `docs/workflows/log-triage.md`

\- `data/session\_handoff.md`

\- `docs/decisions.md`



\---



\## Summary

A recovery / resume is only valid when the agent:



\- identifies the correct flow

\- checks live evidence first

\- avoids duplicate runs

\- respects current documented cadence and limits

\- uses the correct existing entrypoint

\- verifies actual continuation behavior with logs and process state

\- reports concrete resume facts instead of guessing

