"""
India Phone Price Scraper — Flipkart
Works both locally (Windows Task Scheduler) and in the cloud (GitHub Actions).
Fetches current prices and saves to prices.json
"""

import json, time, random, logging, os
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# ── Logging ─────────────────────────────────────────────────────
LOG_FILE = Path(__file__).parent / "scraper_log.txt"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

OUTPUT_FILE = Path(__file__).parent / "prices.json"

# ── Phone → Flipkart search queries ─────────────────────────────
PHONE_QUERIES = {
    # Motorola
    "Moto G06 Power":               "moto g06 power",
    "Moto G35 5G":                  "moto g35 5g",
    "Moto G45 5G":                  "moto g45 5g",
    "Moto G57 Power 5G":            "moto g57 power 5g",
    "Moto G67 Power 5G":            "moto g67 power 5g",
    "Moto G86 Power 5G":            "moto g86 power 5g",
    "Moto G96 5G":                  "moto g96 5g",
    "Motorola Edge 60 Stylus":      "motorola edge 60 stylus",
    "Motorola Edge 60 Fusion":      "motorola edge 60 fusion",
    "Motorola Edge 70 Fusion":      "motorola edge 70 fusion",
    "Motorola Edge 70":             "motorola edge 70",
    "Motorola Edge 60 Pro":         "motorola edge 60 pro",
    "Motorola Signature":           "motorola signature",
    "Motorola Razr 60":             "motorola razr 60",
    "Motorola Razr 60 Ultra":       "motorola razr 60 ultra",
    # Samsung
    "Samsung A06 5G":               "samsung galaxy a06 5g",
    "Samsung A07 5G":               "samsung galaxy a07 5g",
    "Samsung A17 5G":               "samsung galaxy a17 5g",
    "Samsung F17 5G":               "samsung galaxy f17 5g",
    "Samsung M17 5G":               "samsung galaxy m17 5g",
    "Samsung F36 5G":               "samsung galaxy f36 5g",
    "Samsung M36 5G":               "samsung galaxy m36 5g",
    "Samsung S25 FE":               "samsung galaxy s25 fe",
    "Samsung S25 Plus":             "samsung galaxy s25 plus",
    "Samsung S26":                  "samsung galaxy s26",
    "Samsung S26+":                 "samsung galaxy s26 plus",
    "Samsung S26 Ultra":            "samsung galaxy s26 ultra",
    "Samsung Z Flip 7":             "samsung galaxy z flip 7",
    "Samsung Z Flip 7 FE":         "samsung galaxy z flip 7 fe",
    "Samsung Z Fold 7":             "samsung galaxy z fold 7",
    # OnePlus
    "OnePlus Nord CE 4 Lite":       "oneplus nord ce 4 lite",
    "OnePlus Nord CE 4":            "oneplus nord ce 4",
    "OnePlus Nord CE5":             "oneplus nord ce 5",
    "OnePlus Nord 4":               "oneplus nord 4",
    "OnePlus Nord 5":               "oneplus nord 5",
    "OnePlus 13R":                  "oneplus 13r",
    "OnePlus 13":                   "oneplus 13",
    "OnePlus 15 5G":                "oneplus 15 5g",
    # Realme
    "Realme 14 Pro 5G":             "realme 14 pro 5g",
    "Realme 14 Pro+ 5G":            "realme 14 pro plus 5g",
    "Realme 15 5G":                 "realme 15 5g",
    "Realme 15 Pro 5G":             "realme 15 pro 5g",
    "Realme GT 7 5G":               "realme gt 7 5g",
    "Realme GT 8 Pro 5G":           "realme gt 8 pro 5g",
    # Xiaomi/Redmi
    "Redmi Note 14 Pro 5G":         "redmi note 14 pro 5g",
    "Redmi Note 14 Pro+ 5G":        "redmi note 14 pro plus 5g",
    "Redmi Note 15 Pro 5G":         "redmi note 15 pro 5g",
    "Redmi Note 15 Pro+ 5G":        "redmi note 15 pro plus 5g",
    "POCO X7 Pro 5G":               "poco x7 pro 5g",
    "POCO F7 5G":                   "poco f7 5g",
    "Xiaomi 15":                    "xiaomi 15",
    "Xiaomi 15 Ultra":              "xiaomi 15 ultra",
    # iQOO
    "IQOO Neo 10R":                 "iqoo neo 10r",
    "IQOO Neo 10":                  "iqoo neo 10",
    "iQOO 13":                      "iqoo 13",
    "iQOO 15":                      "iqoo 15",
    # Vivo
    "Vivo T4R 5G":                  "vivo t4r 5g",
    "Vivo T4 Pro":                  "vivo t4 pro",
    "Vivo T4 Ultra":                "vivo t4 ultra",
    "Vivo V60 5G":                  "vivo v60 5g",
    "Vivo X300":                    "vivo x300",
    # OPPO
    "Oppo K13 5G":                  "oppo k13 5g",
    "Oppo F31 5G":                  "oppo f31 5g",
    "Oppo Reno 15":                 "oppo reno 15",
    "Oppo Find X8":                 "oppo find x8",
    "Oppo Find X9":                 "oppo find x9",
    # Nothing
    "CMF Phone 2 Pro":              "cmf phone 2 pro",
    "Nothing Phone 3A":             "nothing phone 3a",
    "Nothing Phone 3A Pro":         "nothing phone 3a pro",
    "Nothing Phone 3":              "nothing phone 3",
    # INFINIX
    "ZERO 40 5G":                   "infinix zero 40 5g",
    "GT 30 Pro":                    "infinix gt 30 pro",
    # Tecno
    "Tecno Pova Curve 2 5G":        "tecno pova curve 2 5g",
    "Tecno Phantom V Fold 2 5G":    "tecno phantom v fold 2 5g",
    # Apple
    "iPhone 16 128GB":              "apple iphone 16 128gb",
    "iPhone 16 Pro 256GB":          "apple iphone 16 pro 256gb",
    "iPhone 17 256GB":              "apple iphone 17 256gb",
}

# ── Headers ──────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.flipkart.com/",
}

# ── Price Fetcher ─────────────────────────────────────────────────
def fetch_flipkart_price(model_name: str, query: str) -> dict:
    search_url = (
        f"https://www.flipkart.com/search"
        f"?q={requests.utils.quote(query)}"
        f"&otracker=search&marketplace=FLIPKART"
    )
    result = {
        "model": model_name,
        "price": None,
        "price_num": None,
        "url": search_url,
        "source": "Flipkart",
        "status": "error",
        "updated": datetime.now().strftime("%d %b %Y %H:%M IST"),
    }
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        price_selectors = [
            "div._30jeq3._1_WHN1",
            "div._30jeq3",
            "div.Nx9bqj",
            "div._25b18c ._30jeq3",
        ]
        price_text = None
        for sel in price_selectors:
            el = soup.select_one(sel)
            if el:
                price_text = el.get_text(strip=True)
                break

        if price_text:
            cleaned = price_text.replace("₹", "").replace(",", "").strip()
            try:
                price_num = int(float(cleaned))
                result["price"]     = f"₹{price_num:,}"
                result["price_num"] = price_num
                result["status"]    = "ok"
                log.info(f"  ✓  {model_name:45s}  ₹{price_num:,}")
            except ValueError:
                log.warning(f"  ⚠  {model_name}: parse error — '{price_text}'")
                result["status"] = "parse_error"
        else:
            log.warning(f"  ⚠  {model_name}: price element not found")
            result["status"] = "not_found"

    except requests.exceptions.Timeout:
        log.error(f"  ✗  {model_name}: timeout")
        result["status"] = "timeout"
    except requests.exceptions.HTTPError as e:
        log.error(f"  ✗  {model_name}: HTTP error {e}")
        result["status"] = f"http_error"
    except Exception as e:
        log.error(f"  ✗  {model_name}: {e}")
        result["status"] = "error"

    return result

# ── Load existing prices (fallback) ──────────────────────────────
def load_existing() -> dict:
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {item["model"]: item for item in data.get("phones", [])}
    return {}

# ── Main ─────────────────────────────────────────────────────────
def main():
    log.info("=" * 65)
    log.info(f"Price scraper started — {datetime.now().strftime('%d %b %Y %H:%M')}")
    log.info(f"Running on: {'GitHub Actions' if os.getenv('GITHUB_ACTIONS') else 'Local machine'}")
    log.info("=" * 65)

    existing = load_existing()
    results  = []
    total    = len(PHONE_QUERIES)

    for idx, (model, query) in enumerate(PHONE_QUERIES.items(), 1):
        log.info(f"[{idx:02d}/{total}] {model}")
        data = fetch_flipkart_price(model, query)

        # Fallback to cached price if scrape failed
        if data["status"] != "ok" and model in existing:
            old = existing[model]
            data["price"]     = old.get("price",     data["price"])
            data["price_num"] = old.get("price_num", data["price_num"])
            data["status"]    = "cached_" + data["status"]
            log.info(f"       Using cached: {data['price']}")

        results.append(data)

        # Polite delay — avoids IP blocks
        # Shorter on GitHub Actions (faster network), longer locally
        if os.getenv("GITHUB_ACTIONS"):
            time.sleep(random.uniform(2, 4))
        else:
            time.sleep(random.uniform(3, 7))

    # Write output
    output = {
        "last_updated": datetime.now().strftime("%d %b %Y %H:%M IST"),
        "source": "Flipkart.com",
        "total_scraped": sum(1 for r in results if r["status"] == "ok"),
        "total_models": total,
        "phones": results,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    ok    = sum(1 for r in results if r["status"] == "ok")
    log.info("-" * 65)
    log.info(f"Done. {ok}/{total} prices fetched successfully.")
    log.info(f"Output: {OUTPUT_FILE}")
    log.info("=" * 65)

if __name__ == "__main__":
    main()
