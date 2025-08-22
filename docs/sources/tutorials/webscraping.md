# Web Scraping with Unifile

This tutorial shows how to use the new **web scraping and crawling options** available in the `unifile` CLI.

---

## 1. Basic extraction from a URL (no crawling)
```bash
unifile https://www.kdedirect.com/collections/uas-multi-rotor-brushless-motors
```
This is shorthand for:
```bash
unifile extract https://www.kdedirect.com/collections/uas-multi-rotor-brushless-motors
```

---

## 2. Follow pagination with a CSS selector
```bash
unifile extract https://www.kdedirect.com/collections/uas-multi-rotor-brushless-motors/products \
  --follow \
  --max-pages 3 \
  --next-selector 'a[rel="next"]'
```
- Starts at `/products`  
- Follows up to **3 pages** by finding the link that matches `a[rel="next"]`.

---

## 3. Respect robots.txt and throttle requests
```bash
unifile extract https://www.kdedirect.com/collections/uas-multi-rotor-brushless-motors/articles \
  --follow \
  --max-pages 5 \
  --next-selector '.pagination-next' \
  --respect-robots \
  --delay 2
```
- Checks `robots.txt` before fetching.  
- Sleeps at least **2 seconds** between requests.  
- Limits to **5 pages max**.


---

## 4. Add custom request headers (cookies, user agent, etc.)
```bash
unifile extract https://www.kdedirect.com/collections/uas-multi-rotor-brushless-motors/account \
  --header "User-Agent: MyScraper/1.0" \
  --header "Cookie: sessionid=abc123"
```
- Sends a custom UA string.  
- Includes a session cookie to access logged-in pages. 


---

## 5. Combine all features (crawl 3 pages on "Books to Scrape")
```bash
unifile extract "https://books.toscrape.com/catalogue/page-1.html" \
  --follow \
  --max-pages 3 \
  --next-selector ".next > a" \
  --delay 1.0 \
  --header "User-Agent: Mozilla/5.0 (compatible; UnifileBot/1.0)" \
  --out results.csv
```
- Walks through search results up to 10 pages.  
- Uses `a.next` as the pagination selector.  
- Polite crawling with 1.5s delay and robots compliance.  
- Saves standardized table to `results.csv`.

---

## 6. Single-page (no crawl) with longer timeouts
```bash
unifile extract "https://www.python.org/" \
  --timeout 30 --connect-timeout 15 --retries 2 \
  --out python_org.jsonl
```

----
----
## More Detailed Tutorial

This tutorial shows how to extract readable text from web pages into a standardized table (a `pandas.DataFrame` on the Python side, or JSONL/CSV/Parquet from the CLI).

Unifile focuses on **robust text extraction** from HTML you fetch. For structured, field-by-field scraping you can post-process the extracted text or combine with your favorite parsers.

> ⚖️ **Be responsible**: honor websites' Terms of Service; add rate limits and respectful headers; and cache when appropriate.

---

### Prerequisites

Create a virtual environment and install Unifile:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev,test,docs]           # core dev + docs setup
# For web pages, install the web extras:
pip install -e .[web]                     # baseline (selectors/metadata helpers)
# Or, for stronger main-content extraction:
pip install -e .[web-plus]                # adds trafilatura/readability fallback
# For JavaScript-rendered pages:
pip install -e .[web-js]                  # adds Playwright
```

> The distribution name is **`unifile`**; the module you import is `unifile`. CLI entry points are `unifile` and `unifile-extract`. 

---

### Option A — CLI: single URL to JSONL/CSV/Parquet

Fetch a well-known, static page and extract it:

```bash
# Save an HTML file (stable target)
curl -L https://www.python.org -o python.html

# Extract to JSONL and also produce an HTML view highlighting extracted blocks
unifile extract python.html   --out results.jsonl   --html-export extracted.html   --max-rows 200 --max-colwidth 160
```

You can also point the CLI directly at a URL:

```bash
unifile extract "https://www.python.org" --out python.jsonl
```

Convert to CSV:

```bash
unifile extract "https://www.python.org" --out python.csv
```

> Tip: run `unifile list-types --one-per-line` to see supported inputs; `--out` extension controls format (`.jsonl`, `.csv`, `.parquet`, `.html`). 

---

### Option B — Python API: fetch with `httpx`, extract with `unifile`

```python
from unifile import extract_to_table
import httpx

url = "https://www.python.org"
r = httpx.get(url, timeout=30)
r.raise_for_status()

# Pass bytes + a filename hint
df = extract_to_table(r.content, filename="python.html")
print(df[["unit_type", "unit_id", "char_count"]].head())

# Save results
df.to_json("python.jsonl", orient="records", lines=True)
df.to_csv("python.csv", index=False)
```

---

### Handling JavaScript-heavy pages (Playwright)

If a page requires JS rendering, use Playwright to load it, then feed the rendered HTML to Unifile.

```python
# pip install -e .[web-js]
from unifile import extract_to_table
from playwright.sync_api import sync_playwright

url = "https://news.ycombinator.com"  # demo; generally loads without JS but used here as an example

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    html = page.content()
    browser.close()

df = extract_to_table(html.encode("utf-8"), filename="page.html")
df.to_parquet("page.parquet", index=False)
print(df.head())
```

---

### Bulk extraction from a list of URLs

**CLI one-liner (bash):**

```bash
# urls.txt should contain one URL per line
while IFS= read -r url; do
  unifile extract "$url" --out "out/$(echo "$url" | sed 's~https\?://~~; s~/~_~g').jsonl"
done < urls.txt
```

**Python loop:**

```python
from unifile import extract_to_table
import httpx, pandas as pd

urls = [
    "https://www.python.org",
    "https://www.rfc-editor.org/rfc/rfc2616"  # stable text-heavy page
]

rows = []
with httpx.Client(timeout=30, headers={"User-Agent": "unifile-tutorial/1.0"}) as client:
    for url in urls:
        r = client.get(url)
        r.raise_for_status()
        df = extract_to_table(r.content, filename="page.html")
        df["source_url"] = url
        rows.append(df)

all_df = pd.concat(rows, ignore_index=True)
all_df.to_csv("bulk.csv", index=False)
print("Wrote", len(all_df), "rows")
```

---

### Interpreting the output

All extraction results share a consistent schema:

- `source_path` (or URL/label), `source_name`, `file_type`,  
- `unit_type` (e.g., `file`, `page`, `segment`, etc.), `unit_id`,  
- `content` (plain text), `char_count`, `metadata`, `status`, `error`.

This makes downstream filtering or chunking straightforward—e.g., filter to `status == 'ok'` and non-empty `content`. See the README for the full schema description. 

---

### Troubleshooting

- **403/blocked**: add a descriptive `User-Agent`, retries, and backoff; respect `robots.txt`.
- **JS-only content**: use the Playwright path above (`pip install -e .[web-js]`).
- **Huge pages**: use `--max-rows` / `--max-colwidth` (CLI) or slice the DataFrame.
- **Encoding issues**: Unifile applies heuristics; if needed, decode to Unicode yourself before passing bytes.

---

### Next steps

- Use `--html-export` to generate a side-by-side "what was extracted" report for QA.
- Combine Unifile with your own parsing/regex/LLM pipeline for structured fields.
