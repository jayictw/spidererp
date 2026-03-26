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
    # examples:
    # STM32G431KBT6 -> stm32g431kb
    # STM32G431KBT6TR -> stm32g431kb
    # STM32G473VET6 -> stm32g473ve
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


async def get_price(page, model: str, retries: int = 3) -> dict:
    slug = infer_product_slug(model)
    url = f"https://www.st.com/en/microcontrollers-microprocessors/{slug}.html"

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=120000)
            await page.wait_for_timeout(4500)
            await accept_cookies(page)
            await page.goto(page.url.split("#")[0] + "#sample-buy", wait_until="domcontentloaded", timeout=120000)
            await page.wait_for_timeout(5000)

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
                # fallback for page where row lookup is hard
                for i, ln in enumerate(lines):
                    if "Budgetary Price" in ln:
                        for j in range(i + 1, min(i + 150, len(lines))):
                            m = PRICE_LINE_RE.match(lines[j])
                            if m:
                                best = (float(m.group(1)), m.group(2), lines[j])
                                break
                        if best:
                            break

            return {
                "model": model,
                "product_url": page.url.split("#")[0],
                "price_usd": best[0] if best else None,
                "qty_tier": best[1] if best else None,
                "raw_price_line": best[2] if best else None,
                "matched_lines_count": len(idxs),
                "error": None,
            }
        except Exception as e:
            last_err = str(e)[:300]
            await page.wait_for_timeout(2500)

    return {
        "model": model,
        "product_url": url,
        "price_usd": None,
        "qty_tier": None,
        "raw_price_line": None,
        "matched_lines_count": 0,
        "error": last_err,
    }


async def main() -> None:
    results = []
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1400, "height": 2200})
        page = await context.new_page()

        for i, model in enumerate(MODELS, 1):
            print(f"[{i}/{len(MODELS)}] start {model}", flush=True)
            rec = await get_price(page, model, retries=3)
            results.append(rec)
            print(
                f"[{i}/{len(MODELS)}] done {model} -> price={rec.get('price_usd')} "
                f"qty={rec.get('qty_tier')} err={rec.get('error')}",
                flush=True,
            )

            try:
                await page.screenshot(path=str(OUTDIR / f"st_direct_{model}.png"), full_page=True)
            except Exception:
                pass

            if i < len(MODELS):
                wait_s = random.randint(15, 25)
                print(f"[{i}/{len(MODELS)}] wait {wait_s}s", flush=True)
                await page.wait_for_timeout(wait_s * 1000)

        await browser.close()

    json_path = OUTDIR / "st_g4_prices_direct_results.json"
    csv_path = OUTDIR / "st_g4_prices_direct_results.csv"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    headers = [
        "model",
        "price_usd",
        "qty_tier",
        "raw_price_line",
        "product_url",
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

