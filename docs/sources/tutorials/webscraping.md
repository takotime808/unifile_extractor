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