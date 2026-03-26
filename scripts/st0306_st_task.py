import argparse
import asyncio
import csv
import json
import os
import random
import re
import sqlite3
import time
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from playwright.async_api import async_playwright
from playwright.async_api import Error as PlaywrightError
from st_slug_utils import st_part_to_product_slug


MODEL_LINE_RE = re.compile(r"^[A-Z0-9][A-Z0-9-]{5,}$", re.IGNORECASE)
PRICE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+[kKmM]?)\s*$")
STATUS_RE = re.compile(
    r"\b(Active|In production|Preview|NRND|Not Recommended for New Design|Obsolete)\b",
    re.IGNORECASE,
)

# Common ST product categories used as direct URL fallback when search listing
# cannot be resolved reliably.
DIRECT_CATEGORY_FALLBACKS = [
    "power-management",
    "amplifiers-and-comparators",
    "audio-ics",
    "interfaces-and-transceivers",
    "memories",
    "sensors",
    "protection-devices",
    "automotive-analog-and-power",
    "motor-drivers",
    "microcontrollers-microprocessors",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch ST status/price from ST0306 model list with local Chrome."
    )
    parser.add_argument(
        "--xlsx",
        default=r"C:/Users/PC/Desktop/ST0306.xlsx",
        help="Input xlsx path, first column contains models.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"F:/Jay_ic_tw/data",
        help="Output directory for json/csv.",
    )
    parser.add_argument(
        "--max-per-hour",
        type=int,
        default=45,
        help="Maximum task starts per hour.",
    )
    parser.add_argument(
        "--start-jitter-max-seconds",
        type=int,
        default=1800,
        help="Random startup delay in [0, N] seconds.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome headless. Default false.",
    )
    parser.add_argument(
        "--goto-timeout-seconds",
        type=int,
        default=180,
        help="Navigation timeout seconds for slow ST responses.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=4,
        help="Retries per model when network/protocol is unstable.",
    )
    parser.add_argument(
        "--chrome-profile-dir",
        default=r"F:/Jay_ic_tw/chrome_cookie_profile",
        help="Chrome profile directory for reusing cookies/session.",
    )
    parser.add_argument(
        "--use-cookie-profile",
        action="store_true",
        help="Use persistent Chrome profile (recommended for ST).",
    )
    parser.add_argument(
        "--only-model",
        default="",
        help="Run only one model (exact match), e.g. STM32G473VET6.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of models to run after filtering.",
    )
    parser.add_argument(
        "--failed-models-out",
        default="",
        help="Optional path to write failed models (one model per line).",
    )
    parser.add_argument(
        "--connect-existing-chrome",
        action="store_true",
        help="Connect to an already-open Chrome via CDP (recommended).",
    )
    parser.add_argument(
        "--cdp-endpoint",
        default="http://127.0.0.1:9222",
        help="CDP endpoint when using --connect-existing-chrome.",
    )
    parser.add_argument(
        "--db-path",
        default=r"F:/Jay_ic_tw/sol.db",
        help="SQLite DB path for skipping models that already have ST official price.",
    )
    parser.add_argument(
        "--skip-existing-st-price",
        action="store_true",
        help="Skip models already having st_official_price_usd in parts_pricing.",
    )
    parser.add_argument(
        "--max-consecutive-errors",
        type=int,
        default=10,
        help="Pause task when consecutive errors exceed this value.",
    )
    parser.add_argument(
        "--lock-file",
        default=r"F:/Jay_ic_tw/data/st0306_task.lock",
        help="Single-instance lock file path.",
    )
    parser.add_argument(
        "--resume-state-file",
        default=r"F:/Jay_ic_tw/data/st0306_resume_state.json",
        help="Checkpoint file for resume progress.",
    )
    parser.add_argument(
        "--cdp-reconnect-attempts",
        type=int,
        default=3,
        help="Reconnect attempts when CDP/browser session is interrupted.",
    )
    parser.add_argument(
        "--close-tab-after-each",
        action="store_true",
        help="Close working tab after each model (keeps Chrome window open).",
    )
    parser.add_argument(
        "--done-models-file",
        default="",
        help="Optional file to persist completed models; models in this file will be skipped.",
    )
    return parser.parse_args()


def load_models_from_xlsx_first_col(xlsx_path: Path) -> list[str]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(xlsx_path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                parts = [t.text or "" for t in si.findall(".//m:t", ns)]
                shared.append("".join(parts))

        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        out = []
        for c in sheet.findall(".//m:sheetData/m:row/m:c", ns):
            ref = c.attrib.get("r", "")
            if not ref.startswith("A"):
                continue
            t = c.attrib.get("t")
            val = ""
            if t == "s":
                v = c.find("m:v", ns)
                if v is not None and v.text and v.text.isdigit():
                    idx = int(v.text)
                    if 0 <= idx < len(shared):
                        val = shared[idx]
            elif t == "inlineStr":
                node = c.find("m:is/m:t", ns)
                val = (node.text or "") if node is not None else ""
            else:
                v = c.find("m:v", ns)
                val = (v.text or "") if v is not None else ""

            m = val.strip().upper()
            if not m or m in {"???", "??", "MODEL"}:
                continue
            out.append(m)
    return out


def base_model(model: str) -> str:
    m = model.upper().strip()
    if m.endswith("TR"):
        m = m[:-2]
    return m


def slug_from_model(model: str) -> str:
    return st_part_to_product_slug(base_model(model))


async def accept_cookies(page) -> None:
    selectors = [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept All Cookies')",
        "button:has-text('Accept all')",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                await loc.click(timeout=2000)
                await page.wait_for_timeout(900)
                return
        except Exception:
            pass


async def open_sample_buy_section(page, sample_buy_url: str, goto_timeout_ms: int) -> None:
    # ST pages sometimes ignore hash navigation until tab is explicitly clicked.
    await page.goto(sample_buy_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
    await page.wait_for_timeout(2500)

    tab_selectors = [
        "a[href='#sample-buy']",
        "a[href*='sample-buy']",
        "button:has-text('Sample & Buy')",
        "a:has-text('Sample & Buy')",
    ]
    for sel in tab_selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                await loc.click(timeout=3000)
                await page.wait_for_timeout(2800)
                break
        except Exception:
            pass

    # Ensure anchor/hash state is set even if tab click is not exposed.
    try:
        await page.evaluate("() => { if (!location.hash || location.hash !== '#sample-buy') location.hash = '#sample-buy'; }")
        await page.wait_for_timeout(2000)
    except Exception:
        pass


async def resolve_product_url(page, model: str, goto_timeout_ms: int) -> str:
    model_u = model.upper().strip()
    base_u = base_model(model_u)

    # 1) Try ST search page first (category-agnostic).
    search_url = (
        "https://search.st.com/?activeSource=%22Search%22"
        f"&queryText=%22{model_u}%22&language=%22en%22&pageSearch=1&pageXRef=1"
    )
    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
        await page.wait_for_timeout(4500)
        await accept_cookies(page)
        await page.wait_for_timeout(1200)
        candidates = await page.eval_on_selector_all(
            "a[href]",
            """els => {
              const out = [];
              for (const e of els) {
                const href = e.href || '';
                const txt = (e.textContent || '').trim();
                if (!href) continue;
                if (!href.startsWith('https://www.st.com/en/')) continue;
                if (!href.endsWith('.html')) continue;
                if (href.includes('/resource/')) continue;
                out.push({ href, txt });
              }
              return out;
            }""",
        )
        if candidates:
            def rank(c):
                href_u = c["href"].upper()
                txt_u = (c.get("txt") or "").upper()
                score = 0
                if model_u in txt_u:
                    score += 6
                if base_u in txt_u:
                    score += 4
                if model_u in href_u:
                    score += 3
                if base_u in href_u:
                    score += 2
                if "/MICROCONTROLLERS-MICROPROCESSORS/" in href_u:
                    score += 1
                return score

            best = max(candidates, key=rank)
            if rank(best) > 0:
                return best["href"]
            return candidates[0]["href"]
    except Exception:
        pass

    # 2) Fallback: keep existing MCU rule for STM32 only.
    slug = slug_from_model(model_u)
    if model_u.startswith("STM32"):
        return f"https://www.st.com/en/microcontrollers-microprocessors/{slug}.html"

    # 3) Direct category probing fallback for non-STM32 parts.
    for cat in DIRECT_CATEGORY_FALLBACKS:
        candidate = f"https://www.st.com/en/{cat}/{slug}.html"
        try:
            resp = await page.goto(candidate, wait_until="domcontentloaded", timeout=min(goto_timeout_ms, 45000))
            if resp is not None and resp.status >= 400:
                continue
            url_u = (page.url or "").upper()
            if "CHROME-ERROR://" in url_u or "SEARCH.ST.COM" in url_u:
                continue
            body = (await page.inner_text("body"))[:12000].upper()
            if model_u in body or base_u in body:
                return page.url
            if "SAMPLE & BUY" in body and slug.upper().replace("-", "") in body.replace("-", ""):
                return page.url
        except Exception:
            continue
    return search_url


def extract_status_price(lines: list[str], model: str) -> tuple[str | None, float | None, str | None]:
    model_u = model.upper()
    base_u = base_model(model_u)
    idxs = [i for i, ln in enumerate(lines) if model_u in ln.upper()]
    if not idxs:
        idxs = [i for i, ln in enumerate(lines) if base_u in ln.upper()]

    for i in idxs:
        status = None
        price = None
        qty = None
        # Status often appears on the same line as the orderable part number.
        m_status_head = STATUS_RE.search(lines[i])
        if m_status_head:
            status = m_status_head.group(1)
        hi = min(len(lines), i + 60)
        for j in range(i + 1, hi):
            cur = lines[j].strip()
            if (
                j > i + 1
                and MODEL_LINE_RE.match(cur)
                and cur.upper() not in {model_u, base_u}
                and any(ch.isdigit() for ch in cur)
            ):
                break
            if status is None:
                m_status = STATUS_RE.search(cur)
                if m_status:
                    status = m_status.group(1)
            if price is None:
                m_price = PRICE_RE.match(cur)
                if m_price:
                    price = float(m_price.group(1))
                    qty = m_price.group(2)
            if status is not None and price is not None:
                return status, price, qty
    return None, None, None


async def fetch_one(context, model: str, goto_timeout_ms: int, retries: int, shared_page=None) -> dict:
    slug = slug_from_model(model)
    base_url = f"https://www.st.com/en/microcontrollers-microprocessors/{slug}.html"
    url = f"{base_url}#sample-buy"
    rec = {
        "model": model,
        "slug": slug,
        "url": url,
        "product_url": None,
        "status": None,
        "price_usd": None,
        "qty_tier": None,
        "error": None,
    }
    last_error = None
    for attempt in range(1, max(1, retries) + 1):
        page = shared_page if shared_page is not None else await context.new_page()
        try:
            resolved_url = await resolve_product_url(page, model, goto_timeout_ms)
            rec["product_url"] = resolved_url
            # Slow-site strategy: load product page first, then jump to sample-buy.
            await page.goto(resolved_url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
            await page.wait_for_timeout(random.randint(6000, 10000))
            await accept_cookies(page)
            await page.wait_for_timeout(random.randint(1200, 2200))
            await open_sample_buy_section(page, resolved_url + "#sample-buy", goto_timeout_ms)
            await page.wait_for_timeout(random.randint(9000, 14000))

            lines = [ln.strip() for ln in (await page.inner_text("body")).splitlines() if ln.strip()]
            status, price, qty = extract_status_price(lines, model)
            rec["status"] = status
            rec["price_usd"] = price
            rec["qty_tier"] = qty
            if status is None and price is None:
                last_error = "status/price not found"
            else:
                rec["error"] = None
                return rec
        except Exception as exc:
            last_error = str(exc).splitlines()[0][:280]
        finally:
            if shared_page is None and not page.is_closed():
                await page.close()

        if attempt < retries:
            backoff = min(70, 10 * attempt + random.randint(4, 10))
            await asyncio.sleep(backoff)

    rec["error"] = last_error or "unknown error"
    return rec


def save_results(results: list[dict], output_dir: Path, stamp: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"st0306_results_{stamp}.json"
    csv_path = output_dir / f"st0306_results_{stamp}.csv"

    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    headers = ["model", "slug", "url", "status", "price_usd", "qty_tier", "error"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for row in results:
            w.writerow({k: row.get(k) for k in headers})
    return json_path, csv_path


def write_failed_models(results: list[dict], out_path: Path) -> None:
    failed = []
    for r in results:
        # For downstream DB update, treat missing price as failed.
        if r.get("price_usd") is None:
            m = (r.get("model") or "").strip().upper()
            if m:
                failed.append(m)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(failed), encoding="utf-8")


def load_models_with_st_price(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT UPPER(TRIM(model))
            FROM parts_pricing
            WHERE st_official_price_usd IS NOT NULL
            """
        )
        return {row[0] for row in cur.fetchall() if row and row[0]}
    finally:
        conn.close()


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock(lock_path: Path) -> None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return
    except FileExistsError:
        pass

    # stale lock recovery
    try:
        txt = lock_path.read_text(encoding="utf-8").strip()
        old_pid = int(txt) if txt.isdigit() else 0
    except Exception:
        old_pid = 0
    if old_pid and _is_pid_alive(old_pid):
        raise RuntimeError(f"another task is running (pid={old_pid}), lock={lock_path}")
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass
    fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))


def release_lock(lock_path: Path) -> None:
    try:
        if lock_path.exists():
            txt = lock_path.read_text(encoding="utf-8").strip()
            if not txt or txt == str(os.getpid()):
                lock_path.unlink(missing_ok=True)
    except Exception:
        pass


def load_resume_index(state_file: Path) -> int:
    if not state_file.exists():
        return 0
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        idx = int(data.get("next_index", 0))
        return max(0, idx)
    except Exception:
        return 0


def load_done_models(done_file: Path) -> set[str]:
    if not done_file.exists():
        return set()
    return {
        x.strip().upper()
        for x in done_file.read_text(encoding="utf-8").splitlines()
        if x.strip()
    }


def save_done_models(done_file: Path, done_models: set[str]) -> None:
    done_file.parent.mkdir(parents=True, exist_ok=True)
    done_file.write_text("\n".join(sorted(done_models)), encoding="utf-8")


def save_resume_index(state_file: Path, next_index: int) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "next_index": max(0, int(next_index)),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def connect_cdp_context(playwright, endpoint: str, viewport: dict) -> tuple[object, object]:
    browser = await playwright.chromium.connect_over_cdp(endpoint)
    if browser.contexts:
        context = browser.contexts[0]
    else:
        context = await browser.new_context(viewport=viewport)
    return browser, context


async def run(args: argparse.Namespace) -> None:
    lock_path = Path(args.lock_file)
    acquire_lock(lock_path)
    xlsx = Path(args.xlsx)
    try:
        if not xlsx.exists():
            raise FileNotFoundError(f"xlsx not found: {xlsx}")

        models = load_models_from_xlsx_first_col(xlsx)
        if not models:
            raise RuntimeError("no models found in xlsx first column")
        if args.only_model:
            target = args.only_model.strip().upper()
            models = [m for m in models if m == target]
            if not models:
                raise RuntimeError(f"only-model not found in xlsx: {target}")
        if args.limit > 0:
            models = models[: args.limit]
        if args.skip_existing_st_price:
            priced = load_models_with_st_price(Path(args.db_path))
            before = len(models)
            models = [m for m in models if m.upper() not in priced]
            print(f"[skip-existing] removed={before-len(models)} remain={len(models)}")

        done_models: set[str] = set()
        done_file: Path | None = None
        if args.done_models_file:
            done_file = Path(args.done_models_file)
            done_models = load_done_models(done_file)
            before = len(models)
            models = [m for m in models if m.upper() not in done_models]
            print(f"[skip-done] removed={before-len(models)} remain={len(models)}")

        resume_file = Path(args.resume_state_file)
        start_idx = load_resume_index(resume_file)
        if start_idx > len(models):
            print(f"[resume] start_index={start_idx} out_of_range, reset to 0")
            start_idx = 0
            save_resume_index(resume_file, 0)
        if start_idx > 0:
            print(f"[resume] start_index={start_idx}")
            models = models[start_idx:]
        base_index = start_idx

        jitter = random.randint(0, max(0, args.start_jitter_max_seconds))
        print(f"[startup] random delay: {jitter}s")
        if jitter > 0:
            await asyncio.sleep(jitter)

        interval_s = 3600.0 / max(1, args.max_per_hour)
        print(f"[rate-limit] max_per_hour={args.max_per_hour}, min_interval={interval_s:.2f}s")
        print(f"[models] total={len(models)}")
        if not models:
            return

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results: list[dict] = []
        next_start_at = time.monotonic()
        consecutive_errors = 0

        goto_timeout_ms = max(30, args.goto_timeout_seconds) * 1000
        async with async_playwright() as p:
            browser = None
            context = None
            use_shared_page = False

            if args.connect_existing_chrome:
                browser = await p.chromium.connect_over_cdp(args.cdp_endpoint)
                if browser.contexts:
                    context = browser.contexts[0]
                else:
                    context = await browser.new_context(viewport={"width": 1440, "height": 2200})
                use_shared_page = True
            elif args.use_cookie_profile:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=args.chrome_profile_dir,
                    channel="chrome",
                    headless=args.headless,
                    viewport={"width": 1440, "height": 2200},
                    args=["--disable-http2"],
                )
            else:
                browser = await p.chromium.launch(
                    channel="chrome",
                    headless=args.headless,
                    args=["--disable-http2"],
                )
                context = await browser.new_context(viewport={"width": 1440, "height": 2200})

            shared_page = None
            if use_shared_page:
                shared_page = await context.new_page()
            try:
                for i, model in enumerate(models, 1):
                    now = time.monotonic()
                    if now < next_start_at:
                        await asyncio.sleep(next_start_at - now)
                    start_at = time.monotonic()
                    next_start_at = start_at + interval_s

                    print(f"[{i}/{len(models)}] start {model}")
                    rec = None
                    model_page = shared_page
                    if use_shared_page and args.close_tab_after_each:
                        model_page = await context.new_page()
                    reconnect_ok = False
                    for reconnect_round in range(max(1, args.cdp_reconnect_attempts)):
                        try:
                            rec = await fetch_one(
                                context=context,
                                model=model,
                                goto_timeout_ms=goto_timeout_ms,
                                retries=max(1, args.retries),
                                shared_page=model_page,
                            )
                            reconnect_ok = True
                            break
                        except PlaywrightError as e:
                            msg = str(e)
                            if args.connect_existing_chrome and (
                                "Target page, context or browser has been closed" in msg
                                or "has been closed" in msg
                                or "connect_over_cdp" in msg
                            ):
                                print(f"[reconnect] model={model} attempt={reconnect_round+1}")
                                try:
                                    if shared_page is not None and not shared_page.is_closed():
                                        await shared_page.close()
                                except Exception:
                                    pass
                                try:
                                    if browser is not None:
                                        await browser.close()
                                except Exception:
                                    pass
                                await asyncio.sleep(2 + reconnect_round * 2)
                                browser, context = await connect_cdp_context(
                                    playwright=p,
                                    endpoint=args.cdp_endpoint,
                                    viewport={"width": 1440, "height": 2200},
                                )
                                use_shared_page = True
                                shared_page = await context.new_page()
                                model_page = shared_page if not args.close_tab_after_each else await context.new_page()
                                continue
                            raise
                    if not reconnect_ok or rec is None:
                        rec = {
                            "model": model,
                            "slug": slug_from_model(model),
                            "url": f"https://www.st.com/en/microcontrollers-microprocessors/{slug_from_model(model)}.html#sample-buy",
                            "status": None,
                            "price_usd": None,
                            "qty_tier": None,
                            "error": "cdp reconnect exhausted",
                        }
                    results.append(rec)
                    if rec.get("price_usd") is None:
                        consecutive_errors += 1
                    else:
                        consecutive_errors = 0
                    print(
                        f"[{i}/{len(models)}] done {model} "
                        f"status={rec.get('status')} price={rec.get('price_usd')} err={rec.get('error')} "
                        f"consecutive_errors={consecutive_errors}"
                    )
                    if consecutive_errors >= max(1, args.max_consecutive_errors):
                        print(
                            f"[pause] consecutive_errors={consecutive_errors} "
                            f">= max_consecutive_errors={args.max_consecutive_errors}, stop now"
                        )
                        break

                    if i % 10 == 0 or i == len(models):
                        save_results(results, Path(args.output_dir), stamp)
                    # checkpoint after each model
                    save_resume_index(resume_file, base_index + i)
                    if done_file is not None:
                        done_models.add(model.upper())
                        save_done_models(done_file, done_models)
                    if (
                        args.connect_existing_chrome
                        and args.close_tab_after_each
                        and model_page is not None
                        and not model_page.is_closed()
                    ):
                        await model_page.close()
            finally:
                if shared_page is not None and not shared_page.is_closed():
                    await shared_page.close()
                if not args.connect_existing_chrome and context is not None:
                    await context.close()
                if browser:
                    await browser.close()

        json_path, csv_path = save_results(results, Path(args.output_dir), stamp)
        if args.failed_models_out:
            write_failed_models(results, Path(args.failed_models_out))
        print(f"[out] {json_path}")
        print(f"[out] {csv_path}")

        target = next((r for r in results if r["model"] == "STM32G473VET6"), None)
        if target:
            print(
                "[target] STM32G473VET6 "
                f"status={target.get('status')} price={target.get('price_usd')} qty={target.get('qty_tier')}"
            )
    finally:
        release_lock(lock_path)


def main() -> None:
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
