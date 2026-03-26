import asyncio
import csv
import json
import random
import re
from pathlib import Path

from playwright.async_api import async_playwright


MODELS = [
    "STM32G431K6T6",
    "STM32G431K8T6",
    "STM32G431KBT6",
    "STM32G431KBT6TR",
    "STM32G431KBU3",
    "STM32G431RBT3",
    "STM32G431RBT3TR",
    "STM32G431RBT6",
    "STM32G431VBT6",
    "STM32G473CEU6",
    "STM32G473RCT6",
    "STM32G473RET3",
    "STM32G473VCT6",
    "STM32G473VET3",
    "STM32G473VET6",
    "STM32G474CBT6",
    "STM32G474CCT6",
    "STM32G474CET6",
    "STM32G474QET6",
    "STM32G474RBT3",
    "STM32G491VET6",
]

OUTDIR = Path(r"F:/Jay_ic_tw/data")
OUTDIR.mkdir(parents=True, exist_ok=True)
JSON_OUT = OUTDIR / "st_21_isolated_results.json"
CSV_OUT = OUTDIR / "st_21_isolated_results.csv"

PRICE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+[kKmM]?)\s*$")
MODEL_RE = re.compile(r"^STM32G\d{3}[A-Z0-9]+")


def base_model(m: str) -> str:
    m = m.upper().strip()
    return m[:-2] if m.endswith("TR") else m


def slug_from_model(model: str) -> str:
    b = base_model(model)
    if re.match(r"^STM32G\d{3}[A-Z0-9]+[A-Z][0-9]$", b):
        b = b[:-2]
    # strict: use exact page code only
    mm = re.match(r"^(STM32G\d{3}[A-Z0-9]{2})", b)
    return (mm.group(1) if mm else b[:10]).lower()


async def accept_cookies(page):
    for sel in [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept All Cookies')",
        "button:has-text('Accept all')",
    ]:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                await loc.click(timeout=2500)
                await page.wait_for_timeout(1000)
                return
        except Exception:
            pass


def extract_price(lines: list[str], model: str):
    model_u = model.upper()
    bm = base_model(model_u)
    idx = [i for i, ln in enumerate(lines) if model_u in ln.upper()]
    if not idx:
        idx = [i for i, ln in enumerate(lines) if bm in ln.upper()]
    for i in idx:
        for j in range(i + 1, min(i + 35, len(lines))):
            if j > i + 1 and MODEL_RE.match(lines[j]):
                break
            m = PRICE_RE.match(lines[j])
            if m:
                return float(m.group(1)), m.group(2), lines[j], i
    return None


async def fetch_one(playwright, model: str):
    slug = slug_from_model(model)
    url = f"https://www.st.com/en/microcontrollers-microprocessors/{slug}.html"
    result = {
        "model": model,
        "product_url": url,
        "final_url": None,
        "price_usd": None,
        "qty_tier": None,
        "raw_price_line": None,
        "line_index": None,
        "error": None,
    }
    browser = None
    try:
        browser = await playwright.chromium.launch(channel="chrome", headless=False)
        page = await browser.new_page(viewport={"width": 1440, "height": 2200})
        await page.goto(url + "#sample-buy", wait_until="domcontentloaded", timeout=120000)
        await page.wait_for_timeout(7000)
        await accept_cookies(page)
        await page.wait_for_timeout(1500)
        result["final_url"] = page.url

        text = await page.inner_text("body")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        hit = extract_price(lines, model)
        if hit:
            p, qty, raw, idx = hit
            result["price_usd"] = p
            result["qty_tier"] = qty
            result["raw_price_line"] = raw
            result["line_index"] = idx
        else:
            result["error"] = "model or price not found in page text"

        try:
            await page.screenshot(path=str(OUTDIR / f"st_iso_{model}.png"), full_page=True)
        except Exception:
            pass
    except Exception as e:
        result["error"] = str(e)[:300]
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
    return result


def persist(results: list[dict]):
    JSON_OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    headers = [
        "model",
        "price_usd",
        "qty_tier",
        "raw_price_line",
        "product_url",
        "final_url",
        "line_index",
        "error",
    ]
    with CSV_OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k) for k in headers})


async def main():
    results = []
    async with async_playwright() as p:
        for i, model in enumerate(MODELS, 1):
            print(f"[{i}/{len(MODELS)}] start {model}", flush=True)
            rec = await fetch_one(p, model)
            results.append(rec)
            persist(results)
            print(
                f"[{i}/{len(MODELS)}] done {model} -> price={rec.get('price_usd')} "
                f"qty={rec.get('qty_tier')} err={rec.get('error')}",
                flush=True,
            )
            if i < len(MODELS):
                wait_s = random.randint(15, 25)
                print(f"[{i}/{len(MODELS)}] wait {wait_s}s", flush=True)
                await asyncio.sleep(wait_s)

    found = [r for r in results if r.get("price_usd") is not None]
    print("SUMMARY total", len(results), "found", len(found))
    print("OUT", JSON_OUT)
    print("OUT", CSV_OUT)


if __name__ == "__main__":
    asyncio.run(main())

