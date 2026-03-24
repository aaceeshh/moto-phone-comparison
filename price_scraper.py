"""
Motorola India Price Scraper — Full Version (Moto + Competition)
================================================================
Reads ALL model names from Firebase-hosted index.html.
Runs in 4 daily batches via GitHub Actions to avoid Flipkart blocks.
Add any model to the HTML and it auto-scrapes from next run.

Batch schedule (IST):
  Batch 0 — 06:00 AM  (models   1– 63)
  Batch 1 — 09:00 AM  (models  64–126)
  Batch 2 — 12:00 PM  (models 127–189)
  Batch 3 — 03:00 PM  (models 190–252)
"""

import json
import re
import sys
import time
import datetime
import os
import urllib.request
import urllib.parse

# ── CONFIG ────────────────────────────────────────────────────────
HTML_URL      = "https://phone-dashboard-5c4dd.web.app/index.html"
PRICES_FILE   = "prices.json"
BATCH_SIZE    = 63
REQUEST_DELAY = 5
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "identity",
}


# ── STEP 1: EXTRACT ALL MODELS FROM HTML ─────────────────────────
def get_all_models_from_html():
    """
    Downloads index.html from Firebase and extracts every
    Moto + competition model name. Self-updating — any new
    model added to the HTML is automatically included.
    """
    print(f"Fetching model list from: {HTML_URL}")
    try:
        req = urllib.request.Request(HTML_URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"ERROR: Could not fetch HTML: {e}")
        sys.exit(1)

    if len(html) < 1000:
        print(f"ERROR: HTML too short ({len(html)} chars) — fetch likely failed.")
        sys.exit(1)

    all_models = []

    # ── Moto models: {model:"Motorola Signature", ...} ──
    moto_models = re.findall(r'\{model:"([^"]+)"', html)
    for m in moto_models:
        all_models.append({"name": m, "type": "moto", "brand": "Motorola"})

    # ── Competition models from COMP object ──
    comp_start = html.find("const COMP={")
    comp_end   = html.find("\nconst BC=", comp_start)

    if comp_start > 0 and comp_end > 0:
        comp_block = html[comp_start:comp_end]
        # Walk through each brand block carefully
        for brand_match in re.finditer(r'"([A-Za-z]+)":\{', comp_block):
            brand = brand_match.group(1)
            pos   = brand_match.end()
            depth = 1
            chars = []
            while pos < len(comp_block) and depth > 0:
                ch = comp_block[pos]
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                if depth > 0:
                    chars.append(ch)
                pos += 1
            block = "".join(chars)
            for m in re.findall(r'"([^"]+)":\[', block):
                all_models.append({"name": m, "type": "comp", "brand": brand})
    else:
        # Fallback if COMP block markers shift
        print("WARNING: COMP block not found via primary method, using fallback.")
        for m in re.findall(r'"([^"]+)":\[\{v:', html):
            all_models.append({"name": m, "type": "comp", "brand": "Unknown"})

    moto_c = sum(1 for m in all_models if m["type"] == "moto")
    comp_c = sum(1 for m in all_models if m["type"] == "comp")

    if len(all_models) == 0:
        print("ERROR: No models extracted from HTML. Aborting.")
        sys.exit(1)

    print(f"Found {len(all_models)} models total: "
          f"{moto_c} Moto + {comp_c} Competition")
    return all_models


# ── STEP 2: LOAD EXISTING PRICES.JSON ────────────────────────────
def load_existing_prices():
    """
    Loads existing prices.json so batch runs merge into it
    rather than overwriting prices scraped by earlier batches.
    """
    if os.path.exists(PRICES_FILE):
        try:
            with open(PRICES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            existing = {p["model"]: p for p in data.get("phones", [])}
            print(f"Loaded {len(existing)} existing prices from {PRICES_FILE}")
            return existing
        except Exception as e:
            print(f"Warning: Could not load existing prices: {e}")
    print("No existing prices.json found — starting fresh.")
    return {}


# ── STEP 3: SCRAPE FLIPKART PRICE ────────────────────────────────
def get_flipkart_price(name, brand=""):
    """
    Searches Flipkart for a model and returns the lowest price found.
    Uses brand name in query for better accuracy on competition models.
    """
    # Build search query
    if brand and brand not in ("Motorola", "Unknown"):
        query = f"{brand} {name}"
    else:
        query = f"Motorola {name}"

    # Remove storage suffixes for cleaner search
    query = re.sub(r'\b(128GB|256GB|512GB|1TB|2TB)\b', '', query).strip()

    url = "https://www.flipkart.com/search?q=" + urllib.parse.quote(query)

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw  = resp.read()
            html = raw.decode("utf-8", errors="ignore")
    except Exception as e:
        return None, f"Request failed: {e}"

    prices = []

    # Pattern 1: ₹59,999 (most common on Flipkart)
    for p in re.findall(r'₹\s*([\d,]+)', html):
        try:
            v = int(p.replace(",", "").replace(" ", ""))
            if 1000 < v < 500000:
                prices.append(v)
        except:
            pass

    # Pattern 2: "finalPrice":59999
    for p in re.findall(r'"finalPrice"\s*:\s*(\d+)', html):
        try:
            v = int(p)
            if 1000 < v < 500000:
                prices.append(v)
        except:
            pass

    # Pattern 3: data-price attribute
    for p in re.findall(r'data-price="(\d+)"', html):
        try:
            v = int(p)
            if 1000 < v < 500000:
                prices.append(v)
        except:
            pass

    if prices:
        return min(prices), None

    return None, "No price found on page"


# ── STEP 4: RUN BATCH ─────────────────────────────────────────────
def run_batch(all_models, batch_num, existing):
    """
    Scrapes one batch of models and merges results with existing prices.
    Batch size auto-adjusts if total model count grows beyond 252.
    """
    total      = len(all_models)
    batch_size = max(BATCH_SIZE, -(-total // 4))  # ceiling division by 4
    start      = batch_num * batch_size
    end        = min(start + batch_size, total)

    if start >= total:
        print(f"Batch {batch_num}: nothing to do (only {total} models total).")
        return dict(existing), []

    batch = all_models[start:end]
    print(f"\nBatch {batch_num}: scraping models {start + 1}–{end} of {total}")
    print("-" * 55)

    scraped = dict(existing)
    failed  = []

    for i, model in enumerate(batch, 1):
        name  = model["name"]
        brand = model["brand"]
        mtype = model["type"]

        print(f"[{i}/{len(batch)}] {mtype.upper()} | {brand} | {name}")
        price, err = get_flipkart_price(name, brand)

        if price:
            print(f"  ✅ ₹{price:,}")
            scraped[name] = {
                "model":      name,
                "brand":      brand,
                "type":       mtype,
                "price":      f"₹{price:,}",
                "price_num":  price,
                "source":     "flipkart",
                "scraped_at": datetime.datetime.now(IST).isoformat()
            }
        else:
            print(f"  ⚠️  {err or 'Not found — will use MOP from HTML'}")
            failed.append(name)
            # Preserve any existing price rather than blanking it
            if name not in scraped:
                scraped[name] = {
                    "model":      name,
                    "brand":      brand,
                    "type":       mtype,
                    "price":      None,
                    "price_num":  None,
                    "source":     "not_found",
                    "scraped_at": datetime.datetime.now(IST).isoformat()
                }

        if i < len(batch):
            time.sleep(REQUEST_DELAY)

    return scraped, failed


# ── STEP 5: WRITE PRICES.JSON ─────────────────────────────────────
def write_prices_json(scraped_dict, all_models, failed):
    """
    Writes the fully merged prices.json with summary metadata.
    """
    phones = list(scraped_dict.values())
    found  = sum(1 for p in phones if p.get("price_num"))
    total  = len(all_models)

    output = {
        "last_updated":   datetime.datetime.now(IST).strftime("%d %b %Y %H:%M IST"),
        "total_models":   total,
        "prices_found":   found,
        "prices_missing": total - found,
        "coverage_pct":   round(found / total * 100, 1) if total else 0,
        "failed_models":  failed,
        "phones":         phones
    }

    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅ {PRICES_FILE} written successfully")
    print(f"   Coverage : {found}/{total} ({output['coverage_pct']}%)")
    if failed:
        sample = ', '.join(failed[:5])
        more   = f" + {len(failed) - 5} more" if len(failed) > 5 else ""
        print(f"   Missing  : {sample}{more}")
        print("   (These will fall back to MOP prices in the HTML)")


# ── MAIN ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    batch_num = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    print("=" * 60)
    print(f"Motorola India Price Scraper — Batch {batch_num}")
    print(f"Time : {datetime.datetime.now(IST).strftime('%d %b %Y %H:%M IST')}")
    print(f"HTML : {HTML_URL}")
    print("=" * 60)

    # Step 1: Get all models from Firebase HTML (auto-picks up new models)
    all_models = get_all_models_from_html()

    # Step 2: Load existing prices so batches merge correctly
    existing = load_existing_prices()

    # Step 3: Scrape this batch
    scraped, failed = run_batch(all_models, batch_num, existing)

    # Step 4: Write merged prices.json
    write_prices_json(scraped, all_models, failed)

    print("\nDone.")
