import json
import sqlite3
import csv
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DB = BASE / 'sol.db'
OUT = BASE / 'dashboard' / 'profit_radar.html'
RECENT_ORDERS_OVERRIDES = BASE / 'data' / 'recent_orders_manual_overrides.csv'
SUPPLIER_INVENTORY_RAW = '''
STM32L412CBU6	319,800
STM32L011E4Y6TR	300,000
STM32L100R8T6	256,320
STM32L052R8T6	236,160
STM32L052R8T6	168,960
STM32F412GDIE0	160,543
STM32G051F8Y6TR	135,000
STM32F217IGH6	97,776
STM32C031G6U6	85,260
STM32G030F6P6TR	260,000
STM32F051K6T6TR	72,000
STM32C011F6P3TR	67,500
STM32F437ZIT6	59,760
STM32H750IBK6	55,440
STM32G070CBT6	402,000
STM32F102CBT6	31,500
STM32F102C8T6	31,500
STM32F102C8T6	27,000
STM32H730ZBI6	24,960
STM32H750XBH6	12,138
STM32G031K8T3TR	12,000
STM32G071KBU6N	11,760
STM32H563ZGT6	11,160
'''

QUERY_RADAR = '''
SELECT
  model,
  st_official_price_usd,
  lc_price_cny_tax,
  COALESCE(lc_price_usd_ex_tax, lc_price_cny_tax / tax_factor / usd_fx_rate) AS lc_price_usd_ex_tax,
  CASE
    WHEN COALESCE(lc_recent_orders_extracted, recent_orders) IS NULL THEN NULL
    WHEN COALESCE(lc_recent_orders_extracted, recent_orders) < 0 THEN 0
    WHEN COALESCE(lc_recent_orders_extracted, recent_orders) > 100 THEN 100
    ELSE CAST(ROUND(COALESCE(lc_recent_orders_extracted, recent_orders)) AS INTEGER)
  END AS recent_orders,
  tax_factor,
  usd_fx_rate
FROM parts_pricing
WHERE st_official_price_usd IS NOT NULL
  AND COALESCE(lc_price_usd_ex_tax, lc_price_cny_tax / tax_factor / usd_fx_rate) IS NOT NULL
'''

QUERY_TP = '''
SELECT
  model,
  st_official_price_usd,
  lc_price_cny_tax,
  CASE
    WHEN COALESCE(lc_recent_orders_extracted, recent_orders) IS NULL THEN NULL
    WHEN COALESCE(lc_recent_orders_extracted, recent_orders) < 0 THEN 0
    WHEN COALESCE(lc_recent_orders_extracted, recent_orders) > 100 THEN 100
    ELSE CAST(ROUND(COALESCE(lc_recent_orders_extracted, recent_orders)) AS INTEGER)
  END AS recent_orders,
  tax_factor,
  usd_fx_rate
FROM parts_pricing
WHERE model IS NOT NULL
'''

conn = sqlite3.connect(DB)
radar_rows = conn.execute(QUERY_RADAR).fetchall()
tp_rows = conn.execute(QUERY_TP).fetchall()
conn.close()


recent_overrides = {}
if RECENT_ORDERS_OVERRIDES.exists():
    with RECENT_ORDERS_OVERRIDES.open(encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            model = (row.get('model') or '').strip().upper()
            value = (row.get('recent_orders') or '').strip()
            if not model or not value:
                continue
            try:
                recent_overrides[model] = max(0, min(100, int(float(value))))
            except ValueError:
                continue

radar = []
for model, st_price, lc_cny, lc_usd, orders, tax_factor, fx in radar_rows:
    if st_price is None or lc_usd is None:
        continue
    if float(st_price) <= 0 or float(lc_usd) <= 0:
        continue
    ratio = float(lc_usd) / float(st_price)
    category = 'market_dump' if ratio <= 0.5 else ('windfall' if ratio > 1.0 else 'normal')
    normalized_orders = int(orders) if orders is not None else 0
    normalized_orders = recent_overrides.get(str(model).strip().upper(), normalized_orders)
    radar.append({
        'model': model,
        'st_price_usd': round(float(st_price), 6),
        'lc_price_usd_ex_tax': round(float(lc_usd), 6),
        'recent_orders': normalized_orders,
        'ratio': round(float(ratio), 6),
        'category': category,
    })

tp_map = {}
for model, st_price, lc_cny, orders, tax_factor, fx in tp_rows:
    if not model:
        continue
    m = str(model).strip()
    normalized_orders = int(orders) if orders is not None else None
    normalized_orders = recent_overrides.get(m.upper(), normalized_orders)
    tp_map[m.upper()] = {
        'model': m,
        'platform_price_cny_tax': float(lc_cny) if lc_cny is not None else None,
        'st_price_usd': float(st_price) if st_price is not None else None,
        'recent_orders': normalized_orders,
        'tax_factor': float(tax_factor) if tax_factor is not None else 1.13,
        'usd_fx_rate': float(fx) if fx is not None else 7.0,
    }

radar_json = json.dumps(radar, ensure_ascii=False)
tp_json = json.dumps(tp_map, ensure_ascii=False)

supplier_seed_rows = []
for raw_line in SUPPLIER_INVENTORY_RAW.strip().splitlines():
    line = raw_line.strip()
    if not line:
        continue
    parts = re.split(r'\s+', line)
    if len(parts) < 2:
        continue
    model = parts[0].strip()
    qty_txt = ''.join(parts[1:]).replace(',', '')
    try:
        qty = int(float(qty_txt))
    except ValueError:
        continue
    supplier_seed_rows.append({'model': model, 'stock_qty': max(0, qty)})
supplier_seed_json = json.dumps(supplier_seed_rows, ensure_ascii=False)

html = f'''<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>採購分析台</title>
  <style>
    :root {{ --bg:#0b0b0c; --panel:#141416; --ink:#f5f7fa; --muted:#a0a7b0; --line:#2a2d31; --danger:#ff6b6b; --ok:#58d68d; --tab:#1b1e22; --tabactive:#ffffff; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif; color:var(--ink); background:linear-gradient(180deg,#080809 0%,#0f1012 100%); }}
    .wrap {{ width:min(1360px,94vw); margin:20px auto 44px; display:grid; gap:12px; }}
    .hero {{ background:linear-gradient(120deg,#111317 0%,#171a1f 58%,#1f2329 100%); color:#f2f4f8; border:1px solid #2a2d31; border-radius:16px; padding:18px 20px; }}
    .title {{ font-size:28px; font-weight:800; margin:0; }} .subtitle {{ margin-top:6px; color:#b7bec8; font-size:14px; }}
    .tabs {{ display:flex; gap:8px; }}
    .tabbtn {{ border:1px solid #31353a; background:var(--tab); color:#dbe1e8; border-radius:10px; padding:10px 16px; font-weight:700; cursor:pointer; }}
    .tabbtn.active {{ background:var(--tabactive); color:#0e1116; border-color:#ffffff; }}
    .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:12px; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:12px; }}
    .k {{ color:var(--muted); font-size:12px; }} .v {{ font-weight:800; font-size:26px; margin-top:4px; }}
    .filters {{ display:grid; grid-template-columns:2fr 1fr 1fr; gap:10px; }}
    input,select,textarea,button {{ border:1px solid #32363b; border-radius:10px; padding:10px 11px; font-size:14px; background:#0f1114; color:#eef2f6; }}
    button {{ cursor:pointer; font-weight:700; }}
    .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; }} th,td {{ text-align:left; padding:7px 6px; border-bottom:1px solid #24282d; }} th {{ color:#c9d1da; font-weight:700; background:#181c21; position:sticky; top:0; }}
    .tbl-wrap {{ max-height:440px; overflow:auto; border:1px solid #272b30; border-radius:10px; }}
    .tag {{ font-size:11px; font-weight:700; padding:2px 7px; border-radius:999px; display:inline-block; }} .tag.market_dump {{ background:#13221a; color:var(--ok); }} .tag.normal {{ background:#1d2126; color:#d3d9e0; }} .tag.windfall {{ background:#2a1719; color:var(--danger); }}
    .hidden {{ display:none; }}
    .tp-top {{ display:grid; grid-template-columns:2fr 1fr 1fr 1fr auto; gap:8px; align-items:end; }}
    .tp-note {{ display:grid; grid-template-columns:1fr 1fr 1fr auto auto auto; gap:8px; align-items:end; margin-top:10px; }}
    .tp-top input, .tp-note input, .tp-note select {{ max-width: 150px; }}
    #tpBulkModels {{ width: 100%; max-width: 480px; }}
    .tp-cell-input {{ width: 95px; }}
    #memoName {{ max-width: 260px; width: 100%; }}
    #memoSelect {{ max-width: 380px; width: 100%; }}
    .status {{ color:#b7c0ca; font-size:12px; min-height:18px; }}
    .inv-top {{ display:grid; grid-template-columns:2fr 1fr auto; gap:8px; align-items:end; }}
    .inv-tools {{ display:grid; grid-template-columns:2fr auto auto; gap:8px; margin-top:10px; align-items:end; }}
    .inv-summary {{ display:flex; gap:14px; flex-wrap:wrap; margin-top:10px; font-size:12px; color:#b7c0ca; }}
    .inv-input-sm {{ width: 120px; }}
    .inv-input-xs {{ width: 92px; }}
    @media (max-width:1080px) {{ .filters,.tp-top,.tp-note,.inv-top,.inv-tools {{ grid-template-columns:1fr; }} .grid2 {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1 class="title">採購分析台</h1>
      <div class="subtitle">分頁 1: 利潤雷達（清單） | 分頁 2: TP計算（批量 + 備忘保存）</div>
    </section>

    <section class="tabs panel">
      <button class="tabbtn active" id="tabRadarBtn">利潤雷達</button>
      <button class="tabbtn" id="tabTpBtn">TP計算</button>
      <button class="tabbtn" id="tabInvBtn">供應商庫存</button>
    </section>

    <section id="tabRadar" class="tabcontent">
      <section class="cards">
        <article class="card"><div class="k">可分析型號</div><div class="v" id="kTotal">0</div></article>
        <article class="card"><div class="k">市場到掛 (<=0.5)</div><div class="v" id="kDump">0</div></article>
        <article class="card"><div class="k">暴利型號 (>1.0)</div><div class="v" id="kWindfall">0</div></article>
        <article class="card"><div class="k">高熱度 (成交>=50)</div><div class="v" id="kHot">0</div></article>
      </section>

      <section class="panel filters">
        <input id="search" placeholder="搜尋型號，如 STM32F103" />
        <select id="cat"><option value="all">全部分類</option><option value="market_dump">市場到掛 (<=0.5)</option><option value="normal">正常區間 (0.5~1.0)</option><option value="windfall">暴利 (>1.0)</option></select>
        <input id="minOrders" type="number" min="0" step="1" value="0" placeholder="最低成交單量" />
      </section>

      <section class="grid2">
        <section class="panel"><h3>到掛型號（可利潤）</h3><div class="tbl-wrap"><table><thead><tr><th>型號</th><th>折扣比</th><th>成交</th><th>ST($)</th><th>平台未稅($)</th></tr></thead><tbody id="dumpRows"></tbody></table></div></section>
        <section class="panel"><h3>暴利型號</h3><div class="tbl-wrap"><table><thead><tr><th>型號</th><th>折扣比</th><th>成交</th><th>ST($)</th><th>平台未稅($)</th></tr></thead><tbody id="windfallRows"></tbody></table></div></section>
      </section>

      <section class="panel"><h3>全量清單（前 120）</h3><div class="tbl-wrap"><table><thead><tr><th>型號</th><th>分類</th><th>折扣比</th><th>成交</th><th>ST($)</th><th>平台未稅($)</th></tr></thead><tbody id="allRows"></tbody></table></div></section>
    </section>

    <section id="tabTP" class="tabcontent hidden">
      <section class="panel">
        <h3>TP 批量計算</h3>
        <div class="tp-top">
          <div>
            <div class="k">批量輸入型號（每行一個）</div>
            <textarea id="tpBulkModels" rows="5" placeholder="STM32F103C8T6\nSTM32G030C8T6TR"></textarea>
          </div>
          <div>
            <div class="k">手動匯率</div>
            <input id="tpFxGlobal" type="number" step="0.0001" value="7" />
          </div>
          <div>
            <div class="k">TP利潤率(%)</div>
            <input id="tpMargin" type="number" step="0.01" value="15" />
          </div>
          <button id="tpBuildBtn">生成計算表</button>
        </div>

        <div class="tp-note">
          <div>
            <div class="k">備忘名稱</div>
            <input id="memoName" placeholder="例如 2026-03-06 ST報價A" />
          </div>
          <div>
            <div class="k">備忘日期</div>
            <input id="memoDate" type="date" />
          </div>
          <div>
            <div class="k">已保存備忘</div>
            <select id="memoSelect"><option value="">請選擇</option></select>
          </div>
          <button id="memoSaveBtn">保存備忘</button>
          <button id="memoLoadBtn">載入備忘</button>
          <button id="memoDeleteBtn">刪除備忘</button>
        </div>
        <div class="status" id="memoStatus"></div>
      </section>

      <section class="panel">
        <h3>計算結果</h3>
        <div class="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>型号</th>
                <th>平台价</th>
                <th>ST官网价</th>
                <th>熱度</th>
                <th>匯率</th>
                <th>TP（美金）</th>
                <th>TP（人民币）</th>
                <th>出貨價(USD)</th>
                <th>出貨價(RMB含稅)</th>
                <th>利潤率(%)</th>
              </tr>
            </thead>
            <tbody id="tpRows"></tbody>
          </table>
        </div>
      </section>
    </section>

    <section id="tabINV" class="tabcontent hidden">
      <section class="panel">
        <h3>供應商庫存報價</h3>
        <div class="inv-top">
          <div>
            <div class="k">搜尋型號</div>
            <input id="invSearch" placeholder="搜尋型號，如 STM32F103" />
          </div>
          <div>
            <div class="k">預設匯率 (USD/CNY)</div>
            <input id="invGlobalFx" type="number" step="0.0001" value="7" />
          </div>
          <button id="invAddRowBtn">新增空白列</button>
        </div>
        <div class="inv-tools">
          <div>
            <div class="k">快速匯入（每行: 型號,庫存數量）</div>
            <textarea id="invBulkInput" rows="3" placeholder="STM32F103C8T6,120&#10;STM32G030C8T6TR,80"></textarea>
          </div>
          <button id="invImportBtn">匯入/追加</button>
          <button id="invSaveBtn">保存</button>
        </div>
        <div class="status" id="invStatus"></div>
        <div class="inv-summary">
          <div>筆數: <b id="invCount">0</b></div>
          <div>均毛利率(%): <b id="invMarginAvg">0.00</b></div>
        </div>
      </section>
      <section class="panel">
        <div class="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>型號</th>
                <th>庫存數量</th>
                <th>供應商報價(USD)</th>
                <th>供應商報價(RMB含稅)</th>
                <th>成本(含稅人民币)</th>
                <th>對客戶報價(USD)</th>
                <th>對客戶報價(RMB)</th>
                <th>匯率</th>
                <th>毛利率(%)</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody id="invRows"></tbody>
          </table>
        </div>
      </section>
    </section>
  </main>

  <script>
    const RADAR = {radar_json};
    const TP_MAP = {tp_json};
    const MEMO_KEY = 'tp_calc_memos_v1';
    const INV_KEY = 'supplier_inventory_quotes_v1';
    const INV_SEED = {supplier_seed_json};

    const fmt=(n,d=3)=> (n==null||Number.isNaN(n)?'-':Number(n).toFixed(d));
    const tag=c=> c==='market_dump'?'市場到掛':(c==='windfall'?'暴利':'正常');

    const tabRadarBtn = document.getElementById('tabRadarBtn');
    const tabTpBtn = document.getElementById('tabTpBtn');
    const tabInvBtn = document.getElementById('tabInvBtn');
    const tabRadar = document.getElementById('tabRadar');
    const tabTP = document.getElementById('tabTP');
    const tabINV = document.getElementById('tabINV');

    function switchTab(name) {{
      const onRadar = name === 'radar';
      const onTP = name === 'tp';
      const onINV = name === 'inv';
      tabRadar.classList.toggle('hidden', !onRadar);
      tabTP.classList.toggle('hidden', !onTP);
      tabINV.classList.toggle('hidden', !onINV);
      tabRadarBtn.classList.toggle('active', onRadar);
      tabTpBtn.classList.toggle('active', onTP);
      tabInvBtn.classList.toggle('active', onINV);
    }}
    tabRadarBtn.addEventListener('click', () => switchTab('radar'));
    tabTpBtn.addEventListener('click', () => switchTab('tp'));
    tabInvBtn.addEventListener('click', () => switchTab('inv'));

    // Radar section
    const els = {{
      total: document.getElementById('kTotal'),
      dump: document.getElementById('kDump'),
      windfall: document.getElementById('kWindfall'),
      hot: document.getElementById('kHot'),
      search: document.getElementById('search'),
      cat: document.getElementById('cat'),
      minOrders: document.getElementById('minOrders'),
      dumpRows: document.getElementById('dumpRows'),
      windfallRows: document.getElementById('windfallRows'),
      allRows: document.getElementById('allRows'),
    }};
    const filtered=()=>{{
      const q=els.search.value.trim().toLowerCase();
      const c=els.cat.value;
      const min=Number(els.minOrders.value||0);
      return RADAR.filter(r=>(!q||r.model.toLowerCase().includes(q))&&(c==='all'||r.category===c)&&((r.recent_orders||0)>=min));
    }};
    function renderKpi(rows){{ els.total.textContent=rows.length; els.dump.textContent=rows.filter(r=>r.category==='market_dump').length; els.windfall.textContent=rows.filter(r=>r.category==='windfall').length; els.hot.textContent=rows.filter(r=>(r.recent_orders||0)>=50).length; }}
    function renderRows(rows){{
      const dump = rows.filter(r=>r.category==='market_dump').sort((a,b)=>a.ratio-b.ratio).slice(0,90);
      const windfall = rows.filter(r=>r.category==='windfall').sort((a,b)=>b.ratio-a.ratio).slice(0,90);
      const all = [...rows].sort((a,b)=>(b.recent_orders||0)-(a.recent_orders||0)).slice(0,120);
      els.dumpRows.innerHTML = dump.map(r=>`<tr><td>${{r.model}}</td><td>${{fmt(r.ratio,3)}}</td><td>${{r.recent_orders||0}}</td><td>${{fmt(r.st_price_usd,4)}}</td><td>${{fmt(r.lc_price_usd_ex_tax,4)}}</td></tr>`).join('') || '<tr><td colspan="5">無資料</td></tr>';
      els.windfallRows.innerHTML = windfall.map(r=>`<tr><td>${{r.model}}</td><td>${{fmt(r.ratio,3)}}</td><td>${{r.recent_orders||0}}</td><td>${{fmt(r.st_price_usd,4)}}</td><td>${{fmt(r.lc_price_usd_ex_tax,4)}}</td></tr>`).join('') || '<tr><td colspan="5">無資料</td></tr>';
      els.allRows.innerHTML = all.map(r=>`<tr><td>${{r.model}}</td><td><span class="tag ${{r.category}}">${{tag(r.category)}}</span></td><td>${{fmt(r.ratio,3)}}</td><td>${{r.recent_orders||0}}</td><td>${{fmt(r.st_price_usd,4)}}</td><td>${{fmt(r.lc_price_usd_ex_tax,4)}}</td></tr>`).join('') || '<tr><td colspan="6">無資料</td></tr>';
    }}
    function renderRadar(){{ const rows=filtered(); renderKpi(rows); renderRows(rows); }}
    ['input','change'].forEach(evt=>{{ els.search.addEventListener(evt,renderRadar); els.cat.addEventListener(evt,renderRadar); els.minOrders.addEventListener(evt,renderRadar); }});

    // TP batch section
    const tpBulkModels = document.getElementById('tpBulkModels');
    const tpFxGlobal = document.getElementById('tpFxGlobal');
    const tpMargin = document.getElementById('tpMargin');
    const tpBuildBtn = document.getElementById('tpBuildBtn');
    const tpRows = document.getElementById('tpRows');

    const memoName = document.getElementById('memoName');
    const memoDate = document.getElementById('memoDate');
    const memoSelect = document.getElementById('memoSelect');
    const memoSaveBtn = document.getElementById('memoSaveBtn');
    const memoLoadBtn = document.getElementById('memoLoadBtn');
    const memoDeleteBtn = document.getElementById('memoDeleteBtn');
    const memoStatus = document.getElementById('memoStatus');
    const FIXED_TAX_FACTOR = 1.13;

    function status(msg) {{ memoStatus.textContent = msg; }}
    function todayStr() {{ const d = new Date(); return d.toISOString().slice(0,10); }}
    memoDate.value = todayStr();

    function parseModels(text) {{
      return Array.from(new Set(
        text.split(/\\r?\\n|,|;|\\s+/).map(x=>x.trim()).filter(Boolean)
      ));
    }}

    function resolveTpRecord(rawModel) {{
      const key = (rawModel || '').trim().toUpperCase();
      if (!key) return null;
      // Packaging-equivalent rule: prefer non-TR record when TR/non-TR both exist.
      if (key.endsWith('TR')) {{
        const base = key.slice(0, -2);
        if (TP_MAP[base]) return TP_MAP[base];
      }}
      if (TP_MAP[key]) return TP_MAP[key];
      if (!key.endsWith('TR') && TP_MAP[key + 'TR']) return TP_MAP[key + 'TR'];
      return null;
    }}

    function buildRowsFromInputs(models, fx, marginPct) {{
      const m = Number(marginPct || 0) / 100;
      return models.map(raw => {{
        const rec = resolveTpRecord(raw);
        const platform = rec && rec.platform_price_cny_tax != null ? Number(rec.platform_price_cny_tax) : null;
        const st = rec && rec.st_price_usd != null ? Number(rec.st_price_usd) : null;
        const heat = rec && rec.recent_orders != null ? rec.recent_orders : null;

        // default TP: platform no-tax USD + margin
        let tpUsd = null;
        let tpCny = null;
        if (platform != null && FIXED_TAX_FACTOR > 0 && fx > 0) {{
          const baseUsd = platform / FIXED_TAX_FACTOR / fx;
          tpUsd = baseUsd * (1 + m);
          tpCny = tpUsd * fx * FIXED_TAX_FACTOR;
        }}

        const shipUsd = tpUsd;
        const marginDisplay = shipUsd != null && tpUsd != null && tpUsd > 0
          ? ((shipUsd - tpUsd) / tpUsd) * 100
          : null;

        return {{
          model: rec ? rec.model : raw,
          platform_price_cny_tax: platform,
          st_price_usd: st,
          recent_orders: heat,
          tax_factor: FIXED_TAX_FACTOR,
          fx_rate: fx,
          tp_usd: tpUsd,
          tp_cny: tpCny,
          ship_usd: shipUsd,
          margin_pct: marginDisplay,
          matched: !!rec,
        }};
      }});
    }}

    function renderTpTable(rows) {{
      if (!rows.length) {{
        tpRows.innerHTML = '<tr><td colspan="10">請先輸入型號並點擊「生成計算表」</td></tr>';
        return;
      }}
      tpRows.innerHTML = rows.map((r, i) => `
        <tr data-i="${{i}}">
          <td>${{r.model}}</td>
          <td><input class="platformcny tp-cell-input" type="text" inputmode="decimal" value="${{r.platform_price_cny_tax==null?'':Number(r.platform_price_cny_tax.toFixed(6))}}" /></td>
          <td>${{r.st_price_usd==null?'-':fmt(r.st_price_usd,4)}}</td>
          <td>${{r.recent_orders==null?'-':r.recent_orders}}</td>
          <td><input class="fx tp-cell-input" type="number" step="0.0001" value="${{r.fx_rate}}" /></td>
          <td><input class="tpusd tp-cell-input" type="number" step="0.0001" value="${{r.tp_usd==null?'':Number(r.tp_usd.toFixed(6))}}" /></td>
          <td><input class="tpcny tp-cell-input" type="number" step="0.0001" value="${{r.tp_cny==null?'':Number(r.tp_cny.toFixed(6))}}" /></td>
          <td><input class="shipusd tp-cell-input" type="number" step="0.0001" value="${{(r.ship_usd==null?(r.tp_usd==null?'':Number(r.tp_usd.toFixed(6))):Number(r.ship_usd.toFixed(6)))}}" /></td>
          <td><input class="shipcny tp-cell-input" type="number" step="0.0001" value="${{(r.ship_usd==null?(r.tp_cny==null?'':Number(r.tp_cny.toFixed(6))):Number((r.ship_usd * r.fx_rate * FIXED_TAX_FACTOR).toFixed(6)))}}" /></td>
          <td class="marginpct">${{(r.margin_pct==null?(r.tp_usd!=null?0:'-'):Number(r.margin_pct.toFixed(2)))}}</td>
        </tr>`).join('');
    }}

    function collectCurrentTable() {{
      const trs = Array.from(tpRows.querySelectorAll('tr[data-i]'));
      return trs.map(tr => {{
        const tds = tr.querySelectorAll('td');
        return {{
          model: tds[0].textContent.trim(),
          platform_price_cny_tax: tr.querySelector('.platformcny').value === '' ? null : Number(tr.querySelector('.platformcny').value),
          st_price_usd: tds[2].textContent.trim()==='-' ? null : Number(tds[2].textContent.trim()),
          recent_orders: tds[3].textContent.trim()==='-' ? null : Number(tds[3].textContent.trim()),
          tax_factor: FIXED_TAX_FACTOR,
          fx_rate: Number(tr.querySelector('.fx').value),
          tp_usd: tr.querySelector('.tpusd').value === '' ? null : Number(tr.querySelector('.tpusd').value),
          tp_cny: tr.querySelector('.tpcny').value === '' ? null : Number(tr.querySelector('.tpcny').value),
          ship_usd: tr.querySelector('.shipusd').value === '' ? null : Number(tr.querySelector('.shipusd').value),
          ship_cny_tax: tr.querySelector('.shipcny').value === '' ? null : Number(tr.querySelector('.shipcny').value),
          margin_pct: tr.querySelector('.marginpct').textContent.trim() === '-' ? null : Number(tr.querySelector('.marginpct').textContent.trim()),
        }};
      }});
    }}

    function calcMarginPct(tpUsd, shipUsd) {{
      if (!Number.isFinite(tpUsd) || !Number.isFinite(shipUsd) || tpUsd <= 0) return null;
      return ((shipUsd - tpUsd) / tpUsd) * 100;
    }}

    function refreshRowCalculated(tr, sourceClass) {{
      const fxEl = tr.querySelector('.fx');
      const usdEl = tr.querySelector('.tpusd');
      const cnyEl = tr.querySelector('.tpcny');
      const shipEl = tr.querySelector('.shipusd');
      const shipCnyEl = tr.querySelector('.shipcny');
      const marginEl = tr.querySelector('.marginpct');

      const tax = FIXED_TAX_FACTOR;
      const fx = Number(fxEl.value);
      if (!Number.isFinite(tax) || !Number.isFinite(fx) || tax <= 0 || fx <= 0) {{
        marginEl.textContent = '-';
        return;
      }}

      if (sourceClass === 'tpusd') {{
        const usd = Number(usdEl.value);
        if (Number.isFinite(usd)) cnyEl.value = Number((usd * fx * tax).toFixed(6));
      }}
      if (sourceClass === 'tpcny') {{
        const cny = Number(cnyEl.value);
        if (Number.isFinite(cny)) usdEl.value = Number((cny / tax / fx).toFixed(6));
      }}
      if (sourceClass === 'fx') {{
        const usd = Number(usdEl.value);
        const cny = Number(cnyEl.value);
        if (Number.isFinite(usd)) cnyEl.value = Number((usd * fx * tax).toFixed(6));
        else if (Number.isFinite(cny)) usdEl.value = Number((cny / tax / fx).toFixed(6));
      }}
      if (sourceClass === 'shipusd') {{
        const shipUsd = Number(shipEl.value);
        if (Number.isFinite(shipUsd)) shipCnyEl.value = Number((shipUsd * fx * tax).toFixed(6));
      }}
      if (sourceClass === 'shipcny') {{
        const shipCny = Number(shipCnyEl.value);
        if (Number.isFinite(shipCny)) shipEl.value = Number((shipCny / tax / fx).toFixed(6));
      }}
      if (sourceClass === 'fx') {{
        const shipUsd = Number(shipEl.value);
        const shipCny = Number(shipCnyEl.value);
        if (Number.isFinite(shipUsd)) shipCnyEl.value = Number((shipUsd * fx * tax).toFixed(6));
        else if (Number.isFinite(shipCny)) shipEl.value = Number((shipCny / tax / fx).toFixed(6));
      }}

      const tpUsd = Number(usdEl.value);
      const shipUsd = Number(shipEl.value);
      const mp = calcMarginPct(tpUsd, shipUsd);
      marginEl.textContent = mp == null ? '-' : Number(mp.toFixed(2));
    }}

    function bindTpRowEvents() {{
      tpRows.addEventListener('input', (e) => {{
        const tr = e.target.closest('tr[data-i]');
        if (!tr) return;
        const cls = e.target.classList;
        if (cls.contains('tpusd')) refreshRowCalculated(tr, 'tpusd');
        else if (cls.contains('tpcny')) refreshRowCalculated(tr, 'tpcny');
        else if (cls.contains('fx')) refreshRowCalculated(tr, 'fx');
        else if (cls.contains('shipusd')) refreshRowCalculated(tr, 'shipusd');
        else if (cls.contains('shipcny')) refreshRowCalculated(tr, 'shipcny');
      }});
    }}

    tpBuildBtn.addEventListener('click', () => {{
      const models = parseModels(tpBulkModels.value);
      const fx = Number(tpFxGlobal.value || 7);
      const margin = Number(tpMargin.value || 0);
      if (!models.length) {{ status('請先輸入型號'); return; }}
      const rows = buildRowsFromInputs(models, fx, margin);
      renderTpTable(rows);
      const hit = rows.filter(r => r.platform_price_cny_tax != null).length;
      status(`已生成 ${{rows.length}} 筆，匹配到平台價格 ${{hit}} 筆`);
    }});

    function readMemos() {{
      try {{ return JSON.parse(localStorage.getItem(MEMO_KEY) || '[]'); }} catch {{ return []; }}
    }}
    function writeMemos(arr) {{ localStorage.setItem(MEMO_KEY, JSON.stringify(arr)); }}
    function refreshMemoSelect() {{
      const memos = readMemos();
      memoSelect.innerHTML = '<option value="">請選擇</option>' + memos.map(m => `<option value="${{m.id}}">${{m.date}} | ${{m.name}}</option>`).join('');
    }}

    memoSaveBtn.addEventListener('click', () => {{
      const name = memoName.value.trim() || '未命名備忘';
      const date = memoDate.value || todayStr();
      const modelsText = tpBulkModels.value;
      const table = collectCurrentTable();
      if (!modelsText.trim()) {{ status('保存前請先輸入型號'); return; }}
      const memos = readMemos();
      const sameIdx = memos.findIndex(x => (x.name || '').trim() === name);
      const id = sameIdx >= 0 ? memos[sameIdx].id : `memo_${{Date.now()}}`;
      const nextMemo = {{ id, name, date, fx: tpFxGlobal.value, margin: tpMargin.value, modelsText, table }};
      if (sameIdx >= 0) memos.splice(sameIdx, 1);
      memos.unshift(nextMemo);
      writeMemos(memos);
      refreshMemoSelect();
      memoSelect.value = id;
      status(sameIdx >= 0 ? '同名備忘已覆蓋' : '備忘已保存');
    }});

    memoLoadBtn.addEventListener('click', () => {{
      const id = memoSelect.value;
      if (!id) {{ status('請先選擇備忘'); return; }}
      const memos = readMemos();
      const m = memos.find(x => x.id === id);
      if (!m) {{ status('找不到備忘'); return; }}
      memoName.value = m.name || '';
      memoDate.value = m.date || todayStr();
      tpFxGlobal.value = m.fx || 7;
      tpMargin.value = m.margin || 0;
      tpBulkModels.value = m.modelsText || '';
      if (Array.isArray(m.table) && m.table.length) renderTpTable(m.table);
      status('備忘已載入');
      switchTab('tp');
    }});

    memoDeleteBtn.addEventListener('click', () => {{
      const id = memoSelect.value;
      if (!id) {{ status('請先選擇備忘'); return; }}
      const memos = readMemos().filter(x => x.id !== id);
      writeMemos(memos);
      refreshMemoSelect();
      status('備忘已刪除');
    }});

    // Supplier inventory section
    const invSearch = document.getElementById('invSearch');
    const invGlobalFx = document.getElementById('invGlobalFx');
    const invAddRowBtn = document.getElementById('invAddRowBtn');
    const invBulkInput = document.getElementById('invBulkInput');
    const invImportBtn = document.getElementById('invImportBtn');
    const invSaveBtn = document.getElementById('invSaveBtn');
    const invStatus = document.getElementById('invStatus');
    const invRowsEl = document.getElementById('invRows');
    const invCount = document.getElementById('invCount');
    const invMarginAvg = document.getElementById('invMarginAvg');

    let invRows = [];

    function invMsg(msg) {{ invStatus.textContent = msg; }}
    function parseNum(v) {{
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    }}
    function invDefaultRow(model = '', stockQty = 0) {{
      const fx = parseNum(invGlobalFx.value) || 7;
      return {{
        model,
        stock_qty: stockQty || 0,
        supplier_quote_cny: null,
        supplier_quote_usd: null,
        customer_quote_usd: null,
        customer_quote_cny: null,
        fx_rate: fx,
      }};
    }}
    function invNormalizeRow(r) {{
      const fx = parseNum(r.fx_rate) || (parseNum(invGlobalFx.value) || 7);
      const tax = FIXED_TAX_FACTOR;
      const stock = Math.max(0, parseNum(r.stock_qty) || 0);
      let supUsd = parseNum(r.supplier_quote_usd);
      if (supUsd == null && parseNum(r.supplier_quote_cny) != null && fx > 0 && tax > 0) {{
        // Backward-compat: convert previously saved RMB quote into USD input.
        supUsd = parseNum(r.supplier_quote_cny) / fx / tax;
      }}
      let cusUsd = parseNum(r.customer_quote_usd);
      let cusCny = parseNum(r.customer_quote_cny);
      if (cusUsd != null && (cusCny == null || !Number.isFinite(cusCny))) cusCny = cusUsd * fx;
      if (cusCny != null && (cusUsd == null || !Number.isFinite(cusUsd)) && fx > 0) cusUsd = cusCny / fx;
      const supplierQuoteCnyTaxUnit = (supUsd == null) ? null : (supUsd * fx * tax);
      const costTax = supplierQuoteCnyTaxUnit;
      // Gross margin uses quote currency parity (USD) to avoid tax-basis mismatch.
      const marginPct = (supUsd == null || cusUsd == null || cusUsd <= 0) ? null : ((cusUsd - supUsd) / cusUsd) * 100;
      return {{
        model: (r.model || '').trim(),
        stock_qty: stock,
        supplier_quote_usd: supUsd,
        customer_quote_usd: cusUsd,
        customer_quote_cny: cusCny,
        fx_rate: fx,
        _supplier_quote_cny_tax_unit: supplierQuoteCnyTaxUnit,
        _cost_tax: costTax,
        _margin_pct: marginPct,
      }};
    }}
    function invReadStore() {{
      try {{
        const raw = JSON.parse(localStorage.getItem(INV_KEY) || '{{}}');
        if (raw && Array.isArray(raw.rows)) {{
          invGlobalFx.value = raw.global_fx || invGlobalFx.value;
          return raw.rows.map(invNormalizeRow);
        }}
      }} catch {{}}
      if (INV_SEED.length) {{
        return INV_SEED.map(x => invNormalizeRow(invDefaultRow(x.model, x.stock_qty)));
      }}
      return [];
    }}
    function invWriteStore() {{
      localStorage.setItem(INV_KEY, JSON.stringify({{
        global_fx: invGlobalFx.value,
        rows: invRows.map(r => ({{
          model: r.model,
          stock_qty: r.stock_qty,
          supplier_quote_usd: r.supplier_quote_usd,
          customer_quote_usd: r.customer_quote_usd,
          customer_quote_cny: r.customer_quote_cny,
          fx_rate: r.fx_rate
        }}))
      }}));
    }}
    function invRender() {{
      const q = invSearch.value.trim().toLowerCase();
      const shown = invRows
        .map((r, idx) => ({{ idx, row: invNormalizeRow(r) }}))
        .filter(x => !q || x.row.model.toLowerCase().includes(q));
      const validMargins = shown.map(x => x.row._margin_pct).filter(v => v != null && Number.isFinite(v));
      const avgMargin = validMargins.length ? (validMargins.reduce((a,b)=>a+b,0) / validMargins.length) : 0;
      invRowsEl.innerHTML = shown.map(x => {{
        const r = x.row;
        return `<tr data-idx="${{x.idx}}">
          <td><input class="imodel" value="${{r.model}}" /></td>
          <td><input class="istock inv-input-sm" type="number" step="1" min="0" value="${{r.stock_qty}}" /></td>
          <td><input class="isupusd inv-input-sm" type="text" inputmode="decimal" value="${{r.supplier_quote_usd==null?'':Number(r.supplier_quote_usd.toFixed(6))}}" /></td>
          <td>${{r._supplier_quote_cny_tax_unit==null?'-':fmt(r._supplier_quote_cny_tax_unit,4)}}</td>
          <td>${{r._cost_tax==null?'-':fmt(r._cost_tax,4)}}</td>
          <td><input class="icusd inv-input-sm" type="text" inputmode="decimal" value="${{r.customer_quote_usd==null?'':Number(r.customer_quote_usd.toFixed(6))}}" /></td>
          <td><input class="icny inv-input-sm" type="text" inputmode="decimal" value="${{r.customer_quote_cny==null?'':Number(r.customer_quote_cny.toFixed(6))}}" /></td>
          <td><input class="ifx inv-input-xs" type="number" step="0.0001" value="${{Number(r.fx_rate.toFixed(6))}}" /></td>
          <td>${{r._margin_pct==null?'-':fmt(r._margin_pct,2)}}</td>
          <td><button class="idel" type="button">刪除</button></td>
        </tr>`;
      }}).join('') || '<tr><td colspan="10">無資料</td></tr>';

      invCount.textContent = shown.length;
      invMarginAvg.textContent = avgMargin.toFixed(2);
    }}
    function invUpdateByInput(tr, sourceCls) {{
      const idx = Number(tr.getAttribute('data-idx'));
      if (!Number.isInteger(idx) || !invRows[idx]) return;
      const r = invRows[idx];
      r.model = tr.querySelector('.imodel').value.trim();
      r.stock_qty = parseNum(tr.querySelector('.istock').value) || 0;
      r.supplier_quote_usd = tr.querySelector('.isupusd').value === '' ? null : parseNum(tr.querySelector('.isupusd').value);
      r.fx_rate = parseNum(tr.querySelector('.ifx').value) || (parseNum(invGlobalFx.value) || 7);

      if (sourceCls === 'icusd') {{
        const usd = tr.querySelector('.icusd').value === '' ? null : parseNum(tr.querySelector('.icusd').value);
        r.customer_quote_usd = usd;
        r.customer_quote_cny = usd == null ? null : usd * r.fx_rate;
      }} else if (sourceCls === 'icny') {{
        const cny = tr.querySelector('.icny').value === '' ? null : parseNum(tr.querySelector('.icny').value);
        r.customer_quote_cny = cny;
        r.customer_quote_usd = (cny == null || r.fx_rate <= 0) ? null : cny / r.fx_rate;
      }} else {{
        r.customer_quote_usd = tr.querySelector('.icusd').value === '' ? null : parseNum(tr.querySelector('.icusd').value);
        r.customer_quote_cny = tr.querySelector('.icny').value === '' ? null : parseNum(tr.querySelector('.icny').value);
        if (sourceCls === 'ifx') {{
          if (r.customer_quote_usd != null) r.customer_quote_cny = r.customer_quote_usd * r.fx_rate;
          else if (r.customer_quote_cny != null && r.fx_rate > 0) r.customer_quote_usd = r.customer_quote_cny / r.fx_rate;
        }}
      }}
      invRows[idx] = invNormalizeRow(r);
      invRender();
    }}
    function invImportBulk() {{
      const lines = (invBulkInput.value || '').split(/\\r?\\n/).map(x => x.trim()).filter(Boolean);
      if (!lines.length) {{
        invMsg('請先輸入型號與庫存');
        return;
      }}
      let added = 0;
      lines.forEach(line => {{
        const parts = line.split(/[\\t,]/).map(x => x.trim());
        const model = (parts[0] || '').trim();
        if (!model) return;
        const stock = Math.max(0, parseNum(parts[1]) || 0);
        const exists = invRows.find(r => r.model.toUpperCase() === model.toUpperCase());
        if (exists) {{
          exists.stock_qty = stock;
        }} else {{
          invRows.push(invDefaultRow(model, stock));
          added += 1;
        }}
      }});
      invRender();
      invMsg(`匯入完成，新增 ${{added}} 筆`);
    }}

    invRows = invReadStore();
    invRender();
    invSearch.addEventListener('input', invRender);
    invAddRowBtn.addEventListener('click', () => {{
      invRows.unshift(invDefaultRow());
      invRender();
      invMsg('已新增空白列');
    }});
    invImportBtn.addEventListener('click', invImportBulk);
    invSaveBtn.addEventListener('click', () => {{
      invWriteStore();
      invMsg('供應商庫存已保存');
    }});
    invGlobalFx.addEventListener('change', () => {{
      const fx = parseNum(invGlobalFx.value) || 7;
      invRows = invRows.map(r => ({{ ...r, fx_rate: fx }}));
      invRender();
    }});
    invRowsEl.addEventListener('change', (e) => {{
      const tr = e.target.closest('tr[data-idx]');
      if (!tr) return;
      const cls = e.target.classList;
      if (cls.contains('icusd')) invUpdateByInput(tr, 'icusd');
      else if (cls.contains('icny')) invUpdateByInput(tr, 'icny');
      else if (cls.contains('ifx')) invUpdateByInput(tr, 'ifx');
      else invUpdateByInput(tr, 'other');
    }});
    invRowsEl.addEventListener('click', (e) => {{
      if (!e.target.classList.contains('idel')) return;
      const tr = e.target.closest('tr[data-idx]');
      if (!tr) return;
      const idx = Number(tr.getAttribute('data-idx'));
      if (!Number.isInteger(idx)) return;
      invRows.splice(idx, 1);
      invRender();
    }});

    bindTpRowEvents();
    refreshMemoSelect();
    renderRadar();
    switchTab('radar');
  </script>
</body>
</html>'''

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding='utf-8')
print(f'Generated {OUT} | radar_records={len(radar)} | tp_models={len(tp_map)}')





