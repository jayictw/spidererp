# Refresh Quote Overrides From ERP

## Purpose

This workflow defines the operator path after a new ERP workbook has been imported.

It keeps the first-round quote inputs and handoff guardrails synchronized from the current ERP data.

---

## 1. When To Use

Use this workflow when:

- a new ERP workbook has been imported into `sol.db`
- you want to refresh general first-round quote overrides
- you want to refresh the latest smoke check outputs
- you want to refresh the handoff guardrail list

---

## 2. Current Entrypoints

ERP import:

- `F:/Jay_ic_tw/scripts/import_erp_contents.py`

One-command refresh:

- `F:/Jay_ic_tw/scripts/generate_quote_first_round_overrides_from_erp.py --refresh-guardrails`

Outputs refreshed by this command:

- `F:/Jay_ic_tw/data/quote_first_round_overrides.csv`
- `F:/Jay_ic_tw/data/quote_override_smoke_check_latest.json`
- `F:/Jay_ic_tw/data/quote_override_smoke_check_latest.csv`
- `F:/Jay_ic_tw/data/quote_first_round_handoff_guardrails.csv`

---

## 3. Operator Steps

1. Import the latest ERP workbook:

```powershell
py -3 F:/Jay_ic_tw/scripts/import_erp_contents.py
```

2. Refresh overrides, smoke check, and guardrails together:

```powershell
py -3 F:/Jay_ic_tw/scripts/generate_quote_first_round_overrides_from_erp.py --db-path F:/Jay_ic_tw/sol.db --soq-db-path F:/Jay_ic_tw/qq/agent-harness/soq.db --output F:/Jay_ic_tw/data/quote_first_round_overrides.csv --refresh-guardrails --smoke-json-output F:/Jay_ic_tw/data/quote_override_smoke_check_latest.json --smoke-csv-output F:/Jay_ic_tw/data/quote_override_smoke_check_latest.csv --guardrail-output F:/Jay_ic_tw/data/quote_first_round_handoff_guardrails.csv
```

3. If needed, inspect the refreshed handoff list:

```powershell
Get-Content F:/Jay_ic_tw/data/quote_first_round_handoff_guardrails.csv
```

---

## 4. Verification Checklist

The refresh is valid only if all are true:

1. ERP import completes without error
2. override CSV is rewritten
3. smoke check JSON exists
4. smoke check CSV exists
5. handoff guardrail CSV exists
6. command output includes refreshed counts

---

## 5. Current Expected Result

Latest verified result:

- `written_rows = 12`
- `direct_quote_count = 6`
- `handoff_count = 6`
- `guardrail_count = 6`

---

## 6. Boundary Notes

- this workflow refreshes pricing input files only
- it does not auto-send QQ replies
- it does not change ERP source data
- manual rows in `quote_first_round_overrides.csv` still stay first and win
