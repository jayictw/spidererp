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

PRICE_LINE_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+[kKmM]?)\s*$")
MODEL_LINE_RE = re.compile(r"^STM32G\d{3}[A-Z0-9]+")


def normalize_model(model: str) -> str:
    return model.upper().strip()


def base_model(model: str) -> str:
    m = normalize_model(model)
    if m.endswith("TR"):
        return m[:-2]
    return m


def core2(m: str) -> str:
    # e.g., STM32G474CCT6 -> STM32G474CC ; STM32G431K8T6 -> STM32G431K8
    b = base_model(m)
    # strip package suffix like T6/U3/T3 first when present
    if re.match(r"^STM32G\d{3}[A-Z0-9]+[A-Z][0-9]$", b):
        b = b[:-2]
    mm = re.match(r"^(STM32G\d{3}[A-Z0-9]{2})", b)
    return mm.group(1) if mm else b[:10]


def candidate_slugs(model: str) -> list[str]:
    # Strict rule: derive the exact ST MCU page code and avoid broad family fallbacks
    # Example: STM32G431K6T6 -> stm32g431k6 ; STM32G474CCT6 -> stm32g474cc
    b = base_model(model)
    exact = b[:-2] if re.match(r"^STM32G\d{3}[A-Z0-9]+[A-Z][0-9]$", b) else core2(model)
    return [exact.lower()]


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


def extract_price_from_lines(lines: list[str], model: str):
    model_u = normalize_model(model)
    bm = base_model(model_u)

    idx = [i for i, ln in enumerate(lines) if model_u in ln.upper()]
    if not idx:
        idx = [i for i, ln in enumerate(lines) if bm in ln.upper()]

    for i in idx:
        # only look forward until next model row to avoid adjacent model contamination
        hi = min(len(lines), i + 35)
        for j in range(i + 1, hi):
            if j > i + 1 and MODEL_LINE_RE.match(lines[j]):
                break
            m = PRICE_LINE_RE.match(lines[j])
            if m:
                return float(m.group(1)), m.group(2), lines[j], i
    return None


async def try_one_url(page, model: str, url: str):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=120000)
        await page.wait_for_timeout(4500)
        await accept_cookies(page)
        await page.goto(url + "#sample-buy", wait_until="domcontentloaded", timeout=120000)
        await page.wait_for_timeout(6000)
    except Exception as e:
        return {"ok": False, "error": f"goto failed: {str(e)[:180]}"}

    text = await page.inner_text("body")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    hit = extract_price_from_lines(lines, model)
    if hit:
        p, qty, raw, idx = hit
        return {
            "ok": True,
            "price_usd": p,
            "qty_tier": qty,
            "raw_price_line": raw,
            "line_index": idx,
            "final_url": page.url,
            "lines_count": len(lines),
        }
    return {"ok": False, "error": "model or price line not found", "final_url": page.url}


async def fetch_model(page, model: str):
    slugs = candidate_slugs(model)
    tried = []
    for slug in slugs:
        url = f"https://www.st.com/en/microcontrollers-microprocessors/{slug}.html"
        res = await try_one_url(page, model, url)
        tried.append({"url": url, "result": res.get("error", "ok")})
        if res.get("ok"):
            res.update({"model": model, "product_url": url, "tried": tried, "error": None})
            return res
    return {
        "model": model,
        "price_usd": None,
        "qty_tier": None,
        "raw_price_line": None,
        "line_index": None,
        "final_url": page.url,
        "product_url": None,
        "tried": tried,
        "error": "all candidate urls failed",
    }


async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=False)
        context = await browser.new_context(viewport={"width": 1440, "height": 2200})
        page = await context.new_page()

        for i, model in enumerate(MODELS, 1):
            print(f"[{i}/{len(MODELS)}] start {model}", flush=True)
            rec = await fetch_model(page, model)
            results.append(rec)
            print(
                f"[{i}/{len(MODELS)}] done {model} -> price={rec.get('price_usd')} "
                f"qty={rec.get('qty_tier')} product_url={rec.get('product_url')} err={rec.get('error')}",
                flush=True,
            )

            try:
                await page.screenshot(path=str(OUTDIR / f"st_21_{model}.png"), full_page=True)
            except Exception:
                pass

            if i < len(MODELS):
                wait_s = random.randint(15, 25)
                print(f"[{i}/{len(MODELS)}] wait {wait_s}s", flush=True)
                await page.wait_for_timeout(wait_s * 1000)

        await browser.close()

    json_path = OUTDIR / "st_21_strict_results.json"
    csv_path = OUTDIR / "st_21_strict_results.csv"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

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
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in results:
            w.writerow({k: r.get(k) for k in headers})

    found = [r for r in results if r.get("price_usd") is not None]
    print("SUMMARY total", len(results), "found", len(found))
    print("OUT", json_path)
    print("OUT", csv_path)


if __name__ == "__main__":
    asyncio.run(main())
