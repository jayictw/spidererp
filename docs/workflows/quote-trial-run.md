# Quote Trial Run

## Purpose

This workflow defines how to run one real quote preview trial safely using the current multi-agent quote path.

It is an additive operator workflow for:

- one real customer inquiry
- preview-only execution
- decision review
- task timeline audit

It does not auto-send QQ messages.

---

## 1. When To Use

Use this workflow when:

- a real customer sends `part number + qty`
- you want to see the current guarded quote result
- you want evidence before deciding whether to send a human-reviewed reply

Do not use this workflow for:

- automatic negotiation
- delivery/date-code/source guarantee handling
- complaint handling
- deep bargaining

Those still require human takeover.

---

## 2. Current Entrypoints

Bridge preview route:

- `F:/Jay_ic_tw/qq/agent-harness/bridge_server.py`
- command:
  - `/quote-preview <model> <qty>`

Decision query:

- `F:/Jay_ic_tw/scripts/show_pricing_decision.py`

Task timeline query:

- `F:/Jay_ic_tw/scripts/show_quote_task_timeline.py`

First-round override query:

- `F:/Jay_ic_tw/scripts/show_quote_first_round_override.py`

---

## 3. Trial Run Steps

1. Run `/quote-preview <model> <qty>` through bridge.
2. Record returned `decision_id` and `task_id`.
3. Query the decision details with `show_pricing_decision.py`.
4. Query the worker relay timeline with `show_quote_task_timeline.py`.
5. Let a human decide whether to copy the suggested reply.

If needed, check whether a manual company first-quote rule matched:

```powershell
py -3 F:/Jay_ic_tw/scripts/show_quote_first_round_override.py --part-number STM32L412CBU6 --requested-qty 1560
```

---

## 4. Verification Checklist

The trial run is valid only if all are true:

1. bridge returns `ok = true`
2. preview returns a `task_id`
3. preview returns a `decision_id`
4. `show_pricing_decision.py` can read that decision
5. `show_quote_task_timeline.py` can read that task
6. timeline reaches `completed`
7. timeline event count is consistent with worker relay

---

## 5. Boundary Notes

- this workflow is preview-only
- bridge does not auto-send QQ message
- customer-facing reply still requires human copy/send decision
- any negotiation beyond first-round scope remains manual
