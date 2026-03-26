\# Restart Crawler Workflow



\## Purpose

This workflow defines the correct process for restarting or launching a crawler task in this repository.



Use this workflow when the operator asks to:



\- 開啟抓取

\- 重啟抓取

\- 用新節奏啟動

\- relaunch crawler

\- restart task

\- start the 1306 flow

\- continue the pricing fill flow



This workflow exists to prevent duplicate runs, stale assumptions, and false success reports.



\---



\## Scope

This workflow applies to crawler-related launch and restart operations, especially for:



\- 1306 scope pricing fill

\- missing pricing recovery

\- skip-priced continuation flows

\- ST crawling tasks that depend on the current repository rules



It does not define dashboard rebuild steps except where post-launch verification references downstream artifacts.



\---



\## Read Before Acting

Before doing anything, read:



1\. `AGENTS.md`

2\. `data/requirements\_memory.md`

3\. `docs/workflows/overview.md`



If the requested task clearly maps to a known entrypoint, also inspect the relevant script before launch.



Common relevant entrypoints:



\- `scripts/run\_1306\_scope\_parts\_pricing\_every3min.ps1`

\- `scripts/run\_parts\_pricing\_missing\_every3min.ps1`

\- `scripts/run\_st0306\_every3min\_skippriced.ps1`

\- `scripts/st0306\_st\_task.py`



\---



\## When to Use Which Entrypoint



\### Main 1306 scope pricing fill

Use:

\- `scripts/run\_1306\_scope\_parts\_pricing\_every3min.ps1`



Use this when:

\- the goal is to continue or restart the main 1306 pricing fill flow

\- the user refers to the primary target scope

\- the user wants the main scraping run reopened under the current cadence



\### Missing pricing recovery

Use:

\- `scripts/run\_parts\_pricing\_missing\_every3min.ps1`



Use this when:

\- the task is specifically to backfill missing pricing

\- the user refers to missing rows or recovery for unfilled records



\### Skip-priced continuation

Use:

\- `scripts/run\_st0306\_every3min\_skippriced.ps1`



Use this when:

\- the task should continue crawling while skipping already priced rows

\- the user explicitly refers to skip-priced behavior



\### If uncertain

If multiple entrypoints appear plausible:



1\. use `data/requirements\_memory.md` to determine current operational truth

2\. prefer the most specific existing entrypoint

3\. state the assumption before launch



Do not invent a new launch path.



\---



\## Current Operational Defaults

Unless current memory or script content says otherwise, use these defaults:



\- effective cadence: \*\*1 model per 2 minutes\*\*

\- effective rate limit: \*\*`--max-per-hour 30`\*\*

\- current naming caveat: filenames may still contain `every3min` even though effective cadence is 2 minutes



Never infer cadence from filename alone.



\---



\## Pre-Action Summary Requirement

Before making any impactful restart or launch action, provide a short summary containing:



1\. task understood

2\. files consulted

3\. intended entrypoint

4\. intended verification method

5\. anything uncertain



Example structure:



\- task: restart main 1306 pricing flow

\- consulted: `AGENTS.md`, `requirements\_memory.md`, relevant runner

\- entrypoint: `run\_1306\_scope\_parts\_pricing\_every3min.ps1`

\- verify by: process check + latest stdout/stderr logs

\- uncertainty: none



This step is mandatory because it reduces drift.



\---



\## Restart / Launch Procedure



\### Step 1. Confirm the requested flow

Determine exactly which flow is being requested:



\- main 1306 scope flow

\- missing pricing recovery

\- skip-priced continuation

\- another explicitly named crawler flow



Do not proceed until the intended operational path is clear from repository context.



\---



\### Step 2. Inspect current operational truth

Check:



\- current cadence

\- current rate-limit rule

\- current primary objective

\- current naming caveats

\- any recent dated update in `data/requirements\_memory.md`



If the documented requirement conflicts with assumptions based on filename, the documented requirement wins.



\---



\### Step 3. Inspect for residual running tasks

Before launching anything, inspect for:



\- related PowerShell processes

\- related Python processes

\- known crawler task process names or command lines

\- related lock state if applicable

\- signs that the same flow is already active



Purpose:

\- avoid duplicate runs

\- avoid corrupting resume logic

\- avoid operator confusion



\### Required rule

If the same flow is already running, do \*\*not\*\* launch another identical task.

Report the existing running state instead.



\---



\### Step 4. Inspect required dependencies

Before launch, verify the dependencies relevant to the chosen flow.



Typical checks may include:



\- entrypoint script exists

\- called Python task exists

\- output directory is writable

\- log destination is writable

\- required browser / CDP / VDP target is available when the flow depends on it

\- relevant DB or input file exists when needed



Do not skip this step for convenience.



\---



\### Step 5. Launch the correct entrypoint

Launch only the selected approved entrypoint.



Rules:

\- do not invent a new wrapper

\- do not manually bypass the production runner unless explicitly instructed

\- do not silently change cadence or rate-limit during launch

\- do not mix multiple flows into one ad hoc command



If launch parameters must differ from a previous run, that change must already be reflected in memory or be explicitly reported.



\---



\### Step 6. Verify actual startup

After launch, verify that the run actually started.



At minimum inspect:



\- latest stdout log path

\- latest stderr log path if present

\- recent tail lines from the latest log

\- related running process list



Do not declare success just because the launch command returned without error.



\---



\### Step 7. Extract current runtime facts

From logs or current state, report as many of the following as are available:



\- effective cadence

\- effective rate limit

\- active scope

\- skip-existing summary

\- removed / remain summary

\- resume start index

\- current item progress line

\- current model being processed

\- log path

\- err log path



If a fact is unavailable, say so explicitly instead of guessing.



\---



\### Step 8. Decide outcome

Classify the result as one of:



\- success

\- already running

\- partial

\- failed



Use evidence, not impression.



\---



\## Standard Verification Checklist

A crawler restart is only considered valid if most of the following are true:



\- the correct production entrypoint was used

\- no duplicate run was created

\- relevant dependency checks passed

\- a new or existing valid process was confirmed

\- latest logs exist

\- logs show active work, waiting, rate-limit pacing, or explicit startup behavior

\- stderr is empty or non-blocking, or the issue is understood

\- reported facts match current operational truth



\---



\## Required Report Format

After performing the workflow, report in this structure:



\### Result

\- success / failed / already running / partial



\### Action Taken

\- selected entrypoint

\- whether a new process was launched

\- whether an existing process was reused

\- whether files were changed



\### Current Facts

\- effective cadence

\- effective rate limit

\- active scope

\- resume / skip summary

\- current progress line

\- current model if visible



\### Evidence

\- stdout log path

\- stderr log path

\- relevant process ids if available

\- latest useful log lines



\### Next Recommendation

\- one small next step only



This format is required because vague restart reports are not reliable enough for ongoing operations.



\---



\## Duplicate-Run Policy

The following rule is strict:



\- do not start a second identical crawler flow if the first is already active



If a similar process is found, determine:



1\. whether it is the same flow

2\. whether it is healthy

3\. whether the user asked to replace it or merely restart because they thought it was down



If it is already healthy, report:

\- already running

\- current evidence

\- latest logs

\- whether restart was skipped to avoid duplication



\---



\## Resume / Recovery Interaction

When a restarted flow uses resume behavior, do not hide it.



Explicitly report when observed:



\- resume state detected

\- start index resumed

\- already existing rows were skipped

\- remaining count reduced

\- lock files were present or cleared

\- the run continued rather than starting from zero



This is important because restart behavior is often actually recovery behavior.



\---



\## Naming Caveat Reminder

Some runner names still contain `every3min`.



This does \*\*not\*\* override the current operational truth.



Current documented effective cadence:

\- \*\*1 model per 2 minutes\*\*

\- \*\*`--max-per-hour 30`\*\*



The repository may keep old filenames for continuity.

Policy must follow memory and actual script content.



\---



\## Common Failure Cases



\### Case 1. Launch command succeeds but task is not really running

Symptoms:

\- command returns normally

\- no stable process exists

\- no meaningful new log lines appear



Action:

\- treat as failed or partial

\- inspect stderr and log tail

\- identify the first actionable failure



\### Case 2. Duplicate process risk

Symptoms:

\- an existing related PowerShell or Python task is already active

\- a new identical launch would overlap



Action:

\- do not relaunch

\- report already running

\- show evidence



\### Case 3. Browser / CDP dependency unavailable

Symptoms:

\- crawler depends on an existing Chrome/CDP target

\- dependency check fails



Action:

\- report failed or partial

\- do not fake startup success

\- identify missing dependency clearly



\### Case 4. Resume / lock state causes confusion

Symptoms:

\- logs show resume index or skip-existing behavior

\- operator thinks a full restart happened



Action:

\- explain that the current run resumed or skipped existing work

\- report actual runtime state



\### Case 5. Filename suggests old policy

Symptoms:

\- script name contains `every3min`

\- actual configured rule is 2-minute cadence



Action:

\- follow documented current truth

\- report the naming caveat if relevant



\---



\## What Not to Do

Do not:



\- create a new launcher just to restart faster

\- infer current cadence from filename alone

\- relaunch blindly without checking processes

\- report success without log evidence

\- hide resume / skip behavior

\- silently change operational parameters

\- mix unrelated cleanup with an operational restart

\- use the dashboard as proof that crawler launch succeeded



\---



\## Minimal Safe Restart Heuristic

If time is limited, the minimum safe restart still requires:



1\. read `AGENTS.md`

2\. read `data/requirements\_memory.md`

3\. identify the correct entrypoint

4\. check for duplicate running tasks

5\. verify dependencies

6\. launch or skip launch

7\. inspect latest stdout/stderr logs

8\. report with evidence



Anything less risks false positives.



\---



\## Expected Future Companion Files

This workflow is designed to work alongside:



\- `docs/workflows/build-dashboard.md`

\- `docs/workflows/recover-resume.md`

\- `docs/workflows/log-triage.md`

\- `data/session\_handoff.md`

\- `docs/decisions.md`



\---



\## Summary

A restart is only valid when the agent:



\- chooses the correct existing entrypoint

\- avoids duplicate runs

\- respects current documented cadence and limits

\- verifies actual runtime behavior with logs and processes

\- reports concrete runtime facts instead of vague success language

