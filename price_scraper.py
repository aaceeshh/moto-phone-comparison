"""
Motorola India Price Scraper — Full Version (Moto + Competition)
================================================================
Reads ALL model names from index.html. Runs in 4 daily batches.
Add any model to the HTML and it auto-scrapes from next run.
"""
import json, re, sys, time, datetime, os, urllib.request, urllib.parse

HTML_URL      = "https://raw.githubusercontent.com/aaceeshh/moto-phone-comparison/main/index.html"
PRICES_FILE   = "prices.json"
BATCH_SIZE    = 63
REQUEST_DELAY = 5
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def get_all_models_from_html():
    print("Fetching model list from index.html...")
    req = urllib.request.Request(HTML_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")
    all_models = []
    for m in re.findall(r'\{model:"([^"]+)"', html):
        all_models.append({"name": m, "type": "moto", "brand": "Motorola"})
    comp_start = html.find("const COMP={")
    comp_end   = html.find("\nconst BC=", comp_start)
    if comp_start > 0 and comp_end > 0:
        comp_block = html[comp_start:comp_end]
        for brand_match in re.finditer(r'"([A-Za-z]+)":\{', comp_block):
            brand = brand_match.group(1)
            pos = brand_match.end()
            depth = 1
            block_chars = []
            while pos < len(comp_block) and depth > 0:
                ch = comp_block[pos]
                if ch == '{': depth += 1
                elif ch == '}': depth -= 1
                if depth > 0: block_chars.append(ch)
                pos += 1
            block = "".join(block_chars)
            for m in re.findall(r'"([^"]+)":\[', block):
                all_models.append({"name": m, "type": "comp", "brand": brand})
    moto_c = sum(1 for m in all_models if m["type"]=="moto")
    comp_c = sum(1 for m in all_models if m["type"]=="comp")
    print(f"Found {len(all_models)} models: {moto_c} Moto + {comp_c} Competition")
    return all_models

def load_existing_prices():
    if os.path.exists(PRICES_FILE):
        try:
            with open(PRICES_FILE,"r",encoding="utf-8") as f:
                data = json.load(f)
            existing = {p["model"]: p for p in data.get("phones",[])}
            print(f"Loaded {len(existing)} existing prices")
            return existing
        except: pass
    return {}

def get_flipkart_price(name, brand=""):
    query = f"{brand} {name}" if brand and brand not in ("Motorola","Unknown") else f"Motorola {name}"
    query = re.sub(r'\b(128GB|256GB|512GB|1TB|2TB)\b','',query).strip()
    url = "https://www.flipkart.com/search?q=" + urllib.parse.quote(query)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            try:
                import gzip
                html = gzip.decompress(raw).decode("utf-8","ignore") if resp.info().get("Content-Encoding")=="gzip" else raw.decode("utf-8","ignore")
            except:
                html = raw.decode("utf-8","ignore")
    except Exception as e:
        return None, str(e)
    prices = []
    for p in re.findall(r'₹\s*([\d,]+)', html):
        try:
            v = int(p.replace(",",""))
            if 1000 < v < 500000: prices.append(v)
        except: pass
    for p in re.findall(r'"finalPrice"\s*:\s*(\d+)', html):
        try:
            v = int(p)
            if 1000 < v < 500000: prices.append(v)
        except: pass
    if prices: return min(prices), None
    return None, "No price found"

def run_batch(all_models, batch_num, existing):
    start = batch_num * BATCH_SIZE
    end   = min(start + BATCH_SIZE, len(all_models))
    batch = all_models[start:end]
    print(f"\nBatch {batch_num}: models {start+1}–{end} of {len(all_models)}")
    scraped = dict(existing)
    failed  = []
    for i, model in enumerate(batch, 1):
        name, brand, mtype = model["name"], model["brand"], model["type"]
        print(f"[{i}/{len(batch)}] {mtype.upper()} | {brand} | {name}")
        price, err = get_flipkart_price(name, brand)
        if price:
            print(f"  ✅ ₹{price:,}")
            scraped[name] = {"model":name,"brand":brand,"type":mtype,"price":f"₹{price:,}","price_num":price,"source":"flipkart","scraped_at":datetime.datetime.now(IST).isoformat()}
        else:
            print(f"  ⚠️  {err}")
            failed.append(name)
            if name not in scraped:
                scraped[name] = {"model":name,"brand":brand,"type":mtype,"price":None,"price_num":None,"source":"not_found","scraped_at":datetime.datetime.now(IST).isoformat()}
        if i < len(batch): time.sleep(REQUEST_DELAY)
    return scraped, failed

def write_prices_json(scraped, all_models, failed):
    phones = list(scraped.values())
    found  = sum(1 for p in phones if p.get("price_num"))
    total  = len(all_models)
    output = {
        "last_updated":  datetime.datetime.now(IST).strftime("%d %b %Y %H:%M IST"),
        "total_models":  total,
        "prices_found":  found,
        "prices_missing":total - found,
        "coverage_pct":  round(found/total*100,1) if total else 0,
        "failed_models": failed,
        "phones":        phones
    }
    with open(PRICES_FILE,"w",encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n✅ prices.json: {found}/{total} prices ({output['coverage_pct']}%)")

if __name__ == "__main__":
    batch_num = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print("="*60)
    print(f"Price Scraper — Batch {batch_num} | {datetime.datetime.now(IST).strftime('%d %b %Y %H:%M IST')}")
    print("="*60)
    all_models = get_all_models_from_html()
    existing   = load_existing_prices()
    scraped, failed = run_batch(all_models, batch_num, existing)
    write_prices_json(scraped, all_models, failed)
    print("Done.")
