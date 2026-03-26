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


def infer_product_slug(model: str) -> str:
    s = model.upper().replace("TR", "")
    m = re.match(r"^(STM32G\d{3}[A-Z]{1,2})", s)
    if m:
        return m.group(1).lower()
    return s[:10].lower()


async def accept_cookies(page) -> None:
    for sel in [
        "#onetrust-accept-btn-handler",
        "button:has-text('Accept All Cookies')",
        "button:has-text('Accept all')",
    ]:
        try:
            loc = page.locator(sel).first
            if await loc.count() and await loc.is_visible():
                await loc.click(timeout=2000)
                await page.wait_for_timeout(800)
                return
        except Exception:
            pass


async def goto_search_or_product(page, model: str) -> None:
    search = (
        "https://search.st.com/?activeSource=%22Search%22"
        f"&queryText=%22{model}%22&language=%22en%22&pageSearch=1&pageXRef=1"
    )
    try:
        await page.goto(search, wait_until="domcontentloaded", timeout=90000)
    except Exception:
        pass
    await page.wait_for_timeout(2500)
    await accept_cookies(page)

    for token in [model, model.replace("TR", "")]:
        try:
            loc = page.locator(f"a:has-text('{token}')").first
            if await loc.count() and await loc.is_visible():
                href = await loc.get_attribute("href")
                if href and href.startswith("http"):
                    await page.goto(href, wait_until="domcontentloaded", timeout=90000)
                else:
                    await loc.click(timeout=5000)
                await page.wait_for_timeout(2500)
                return
        except Exception:
            pass

    try:
        links = await page.eval_on_selector_all(
            'a[href*="/en/microcontrollers-microprocessors/"]',
            "els => els.map(e => e.href).filter(Boolean)",
        )
        if links:
            await page.goto(links[0], wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(2500)
            return
    except Exception:
        pass

    slug = infer_product_slug(model)
    direct = f"https://www.st.com/en/microcontrollers-microprocessors/{slug}.html"
    await page.goto(direct, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(2500)


async def extract_price_for_model(page, model: str) -> dict:
    if "#sample-buy" not in page.url:
        try:
            await page.goto(
                page.url.split("#")[0] + "#sample-buy",
                wait_until="domcontentloaded",
                timeout=90000,
            )
            await page.wait_for_timeout(3500)
        except Exception:
            pass

    text = await page.inner_text("body")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    model_up = model.upper()
    idxs = [i for i, ln in enumerate(lines) if model_up in ln.upper()]
    if not idxs and model_up.endswith("TR"):
        base = model_up[:-2]
        idxs = [i for i, ln in enumerate(lines) if base in ln.upper()]

    best = None
    for i in idxs:
        lo = max(0, i - 2)
        hi = min(len(lines), i + 8)
        for w in lines[lo:hi]:
            m = PRICE_LINE_RE.match(w)
            if m:
                best = (float(m.group(1)), m.group(2), w)
                break
        if best:
            break

    if not best:
        for i, ln in enumerate(lines):
            if "Budgetary Price" in ln:
                for j in range(i + 1, min(i + 120, len(lines))):
                    m = PRICE_LINE_RE.match(lines[j])
                    if m:
                        best = (float(m.group(1)), m.group(2), lines[j])
                        break
                if best:
                    break

    return {
        "model": model,
        "final_url": page.url,
        "price_usd": best[0] if best else None,
        "qty_tier": best[1] if best else None,
        "raw_price_line": best[2] if best else None,
        "matched_lines_count": len(idxs),
    }


async def main() -> None:
    results = []
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 2200})
        page = await context.new_page()

        for i, model in enumerate(MODELS, 1):
            print(f"[{i}/{len(MODELS)}] start {model}", flush=True)
            rec = {"model": model, "error": None}
            try:
                await goto_search_or_product(page, model)
                await accept_cookies(page)
                data = await extract_price_for_model(page, model)
                rec.update(data)
                print(
                    f"[{i}/{len(MODELS)}] done {model} -> "
                    f"price={data.get('price_usd')} qty={data.get('qty_tier')} "
                    f"url={data.get('final_url')}",
                    flush=True,
                )
            except Exception as e:
                rec.update(
                    {
                        "final_url": page.url,
                        "price_usd": None,
                        "qty_tier": None,
                        "raw_price_line": None,
                        "matched_lines_count": 0,
                        "error": str(e)[:300],
                    }
                )
                print(f"[{i}/{len(MODELS)}] error {model}: {e}", flush=True)

            results.append(rec)
            snap = OUTDIR / f"st_query_{model}.png"
            try:
                await page.screenshot(path=str(snap), full_page=True)
            except Exception:
                pass

            if i < len(MODELS):
                wait_s = random.randint(15, 25)
                print(f"[{i}/{len(MODELS)}] wait {wait_s}s", flush=True)
                await page.wait_for_timeout(wait_s * 1000)

        await browser.close()

    json_path = OUTDIR / "st_g4_prices_results.json"
    csv_path = OUTDIR / "st_g4_prices_results.csv"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    headers = [
        "model",
        "price_usd",
        "qty_tier",
        "raw_price_line",
        "final_url",
        "matched_lines_count",
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

