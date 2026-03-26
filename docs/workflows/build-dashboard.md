\# Build Dashboard Workflow



\## Purpose

This workflow defines the correct process for rebuilding or refreshing the local dashboard output in this repository.



Use this workflow when the operator asks to:



\- rebuild dashboard

\- 更新 dashboard

\- 重建 profit radar

\- refresh html

\- regenerate dashboard

\- rebuild profit radar

\- 更新可視化頁面



This workflow exists to ensure that dashboard rebuilds use the correct upstream data, preserve required run order, and are verified with evidence.



\---



\## Scope

This workflow applies to dashboard generation and refresh operations, especially for:



\- rebuilding `dashboard/profit\_radar.html`

\- regenerating the local analysis view from current database content

\- rebuilding after data cleanup

\- rebuilding after manual override changes

\- rebuilding after pricing data updates



It does not define crawler restart behavior except where rebuild depends on fresh crawler output.



\---



\## Read Before Acting

Before doing anything, read:



1\. `AGENTS.md`

2\. `data/requirements\_memory.md`

3\. `docs/workflows/overview.md`



Also inspect relevant scripts when the workflow requires them:



\- `scripts/build\_profit\_radar.py`

\- `scripts/clean\_lc\_data\_quality.py`



If the rebuild was requested after a crawler run, also inspect the latest relevant logs and confirm that the upstream data write is complete enough for rebuild.



\---



\## Current Known Dashboard Artifacts



\### Dashboard build script

\- `scripts/build\_profit\_radar.py`



\### Dashboard output

\- `dashboard/profit\_radar.html`



\### Dashboard launch helpers

\- `dashboard/open\_profit\_radar\_chrome.ps1`

\- `dashboard/open\_profit\_radar\_chrome.bat`



\### Known upstream database

\- `sol.db`



\### Known important upstream table

\- `parts\_pricing`



\### Known manual override input

\- `data/recent\_orders\_manual\_overrides.csv`



\---



\## When to Rebuild

Rebuild the dashboard when one or more of the following is true:



\- pricing data in `sol.db` has changed

\- crawler output relevant to dashboard content has completed or materially advanced

\- manual overrides affecting dashboard interpretation were updated

\- LC recent order cleanup was rerun

\- the user explicitly asks for a fresh dashboard

\- the current HTML is stale compared with DB or workflow state



Do not rebuild blindly if the upstream data is known to be incomplete and the user asked for a validated current view.

In that case, state the freshness limitation clearly.



\---



\## Required Pre-Action Summary

Before making a rebuild-related change or running rebuild scripts, provide a short summary containing:



1\. task understood

2\. files consulted

3\. whether upstream data appears fresh enough

4\. intended script order

5\. intended verification method

6\. anything uncertain



Example structure:



\- task: rebuild dashboard after pricing update

\- consulted: `AGENTS.md`, `requirements\_memory.md`, `build\_profit\_radar.py`

\- upstream freshness: checked latest DB/input context

\- script order: rebuild directly

\- verify by: output file timestamp + file existence + optional open step

\- uncertainty: none



This step is required to reduce rebuild mistakes.



\---



\## Operational Rules



\### 1. Dashboard HTML is a generated artifact

`dashboard/profit\_radar.html` is not the source of truth.



The source of truth is:



1\. current workflow docs

2\. `data/requirements\_memory.md`

3\. relevant script content

4\. structured DB content in `sol.db`



Do not treat an old dashboard view as authoritative if DB or workflow state has changed.



\### 2. Rebuild from approved sources only

Use the known dashboard build path.



Do not manually patch generated HTML unless the user explicitly asks for UI-level manual editing.



\### 3. Respect required cleanup order

If the rebuild involves LC recent order cleanup or related data quality changes, follow the required run order from repository memory:



1\. run `clean\_lc\_data\_quality.py`

2\. run `build\_profit\_radar.py`



Do not reverse this order.



\### 4. Manual overrides are explicit inputs

If a rebuild depends on manual overrides, state that explicitly.



Report:

\- whether manual override data was part of the effective input context

\- whether the rebuild was intended to reflect that update



\### 5. Verify build success with evidence

Do not claim success because the script executed.

A rebuild is only valid if the output artifact was regenerated and evidence supports that result.



\---



\## Build Procedure



\### Step 1. Confirm rebuild intent

Determine which of the following applies:



\- standard dashboard refresh

\- rebuild after crawler updates

\- rebuild after cleanup

\- rebuild after manual override change

\- rebuild to validate current local view

\- rebuild as part of troubleshooting



State the intended rebuild type before proceeding.



\---



\### Step 2. Inspect upstream freshness

Check whether the dashboard should reflect current DB/data state.



Typical evidence may include:



\- latest crawler logs

\- recent DB-related work completed

\- known changes to `parts\_pricing`

\- recent edits to manual override CSV

\- known cleanup requirement before rebuild



If the user wants the freshest possible dashboard and upstream data is stale or incomplete, report that before rebuilding.



\---



\### Step 3. Determine required script order

Choose the correct execution order.



\### Standard rebuild

Use:

\- `scripts/build\_profit\_radar.py`



\### Rebuild after LC data cleanup or recent order correction

Use:

1\. `scripts/clean\_lc\_data\_quality.py`

2\. `scripts/build\_profit\_radar.py`



\### If uncertain

Use `data/requirements\_memory.md` and current script context.

Do not invent a new build path.



\---



\### Step 4. Verify dependencies

Before rebuild, verify relevant dependencies.



Typical checks may include:



\- build script exists

\- cleanup script exists when required

\- `sol.db` exists

\- dashboard output directory exists and is writable

\- manual override CSV exists when the requested rebuild depends on it

\- Python environment is available if the scripts depend on it



Do not skip this step when the rebuild matters operationally.



\---



\### Step 5. Run required scripts

Run only the approved script path for the requested rebuild.



Rules:

\- do not manually edit generated output instead of rebuilding

\- do not combine unrelated operational changes into the rebuild step

\- do not skip the cleanup step when repository memory says it is required

\- do not silently change dashboard generation logic during an operational rebuild



\---



\### Step 6. Verify generated output

After the rebuild, verify all relevant evidence.



At minimum inspect:



\- whether `dashboard/profit\_radar.html` exists

\- whether its timestamp changed as expected

\- whether file size is non-trivial and plausible

\- whether the build command completed without blocking errors

\- whether output messages indicate successful generation



Optional but useful:

\- open the dashboard locally using the known helper script

\- visually confirm that the page loads



Do not claim success without output evidence.



\---



\### Step 7. Report current dashboard facts

Report as many of the following as are available:



\- build path used

\- whether cleanup was run first

\- whether manual override input was relevant

\- dashboard output path

\- output timestamp

\- output size if useful

\- relevant build log/output lines

\- any known freshness limitation of upstream data



If something is not verified, say so explicitly.



\---



\## Standard Verification Checklist

A dashboard rebuild is only considered valid if most of the following are true:



\- the correct script path was used

\- required cleanup order was followed if applicable

\- `sol.db` or required inputs were available

\- `dashboard/profit\_radar.html` exists after rebuild

\- output timestamp is current or updated as expected

\- output size appears plausible

\- build output shows successful generation or at least no blocking error

\- the reported result matches upstream data freshness expectations



\---



\## Required Report Format

After performing the workflow, report in this structure:



\### Result

\- success / failed / partial



\### Action Taken

\- script or script order used

\- whether cleanup was run

\- whether dashboard was regenerated

\- whether files were changed



\### Current Facts

\- dashboard output path

\- output timestamp

\- output size if useful

\- whether manual override input was relevant

\- whether upstream data freshness was confirmed



\### Evidence

\- build command output summary

\- relevant file existence / timestamp evidence

\- any useful log or console lines



\### Next Recommendation

\- one small next step only



Do not produce vague rebuild success messages.



\---



\## Rebuild Scenarios



\### Scenario 1. Standard dashboard refresh after DB update

Use when:

\- pricing data was updated

\- the user wants a current dashboard



Action:

\- verify upstream freshness

\- run `build\_profit\_radar.py`

\- verify `profit\_radar.html`



\### Scenario 2. Rebuild after recent order data cleanup

Use when:

\- LC recent orders were corrected or re-cleaned

\- dashboard should reflect cleaned values



Action:

1\. run `clean\_lc\_data\_quality.py`

2\. run `build\_profit\_radar.py`

3\. verify output artifact



\### Scenario 3. Rebuild after manual override update

Use when:

\- `recent\_orders\_manual\_overrides.csv` was changed

\- dashboard should reflect those overrides



Action:

\- confirm whether cleanup is also required

\- run required scripts in the correct order

\- report that manual override input was part of the rebuild context



\### Scenario 4. Rebuild during troubleshooting

Use when:

\- the operator suspects the dashboard is stale or broken

\- there is uncertainty whether HTML matches current DB content



Action:

\- inspect upstream freshness

\- rebuild from approved script path

\- compare resulting artifact timestamp and presence

\- do not assume the old page was correct



\---



\## Common Failure Cases



\### Case 1. Build command completes but output is stale

Symptoms:

\- script exits without obvious error

\- output timestamp did not meaningfully change

\- HTML still appears old



Action:

\- treat as partial or failed

\- inspect build logic and file target

\- verify whether the script wrote to the expected path



\### Case 2. Cleanup step was skipped when required

Symptoms:

\- dashboard rebuild ran

\- LC-related values remain inconsistent

\- known run order from memory was not followed



Action:

\- rerun with correct order:

&#x20; 1. `clean\_lc\_data\_quality.py`

&#x20; 2. `build\_profit\_radar.py`



\### Case 3. Manual override changes not reflected

Symptoms:

\- override CSV was updated

\- dashboard still reflects old values



Action:

\- confirm whether the build pipeline actually consumes the override-relevant data

\- rerun with proper upstream preparation

\- report any uncertainty in pipeline linkage



\### Case 4. Output file exists but page is broken

Symptoms:

\- HTML file is generated

\- local page does not render properly



Action:

\- distinguish build success from UI correctness

\- report generated artifact status separately from rendering issue

\- investigate UI-level error without rewriting generated output by hand unless requested



\### Case 5. Upstream data is not fresh

Symptoms:

\- crawler has not completed

\- DB content is stale

\- user expects newest pricing in dashboard



Action:

\- report freshness limitation clearly

\- rebuild only if the user still wants the latest currently available local view



\---



\## What Not to Do

Do not:



\- manually edit generated dashboard HTML instead of rebuilding

\- use stale dashboard appearance as proof of current DB truth

\- skip required cleanup order

\- claim success without verifying output artifact

\- fold unrelated code changes into a routine rebuild

\- infer data freshness from HTML alone

\- hide that a rebuild used stale upstream data



\---



\## Minimal Safe Build Heuristic

If time is limited, the minimum safe rebuild still requires:



1\. read `AGENTS.md`

2\. read `data/requirements\_memory.md`

3\. identify whether cleanup is required

4\. verify input/database presence

5\. run the correct script order

6\. verify `dashboard/profit\_radar.html` exists and is current

7\. report with evidence



Anything less risks false-positive rebuild reports.



\---



\## Interaction with Other Workflow Files

This workflow is designed to work alongside:



\- `docs/workflows/overview.md`

\- `docs/workflows/restart-crawler.md`

\- `docs/workflows/recover-resume.md`

\- `docs/workflows/log-triage.md`

\- `data/session\_handoff.md`

\- `docs/decisions.md`



\---



\## Summary

A dashboard rebuild is only valid when the agent:



\- verifies upstream data context

\- follows the correct script order

\- respects cleanup requirements

\- regenerates `dashboard/profit\_radar.html` from approved sources

\- confirms output evidence instead of relying on assumption

