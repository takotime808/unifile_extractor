# Copyright (c) 2025 takotime808

from __future__ import annotations

import re
import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Iterable, Tuple

from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode

import httpx
from httpx import Timeout
try:
    from selectolax.parser import HTMLParser  # fast path
    _HAVE_SELECTOLAX = True
except Exception:
    from bs4 import BeautifulSoup  # fallback
    _HAVE_SELECTOLAX = False

try:
    import extruct
except Exception:
    extruct = None

try:
    from price_parser import Price
except Exception:
    Price = None

# Optional polite crawling
try:
    from reppy.robots import Robots
except Exception:
    Robots = None


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class FetchConfig:
    timeout_s: float = 20.0
    max_retries: int = 3
    backoff_s: float = 1.5
    verify_tls: bool = True
    respect_robots: bool = False
    crawl_delay_s: float = 0.0
    headers: Optional[Dict[str, str]] = None


@dataclass
class CrawlConfig:
    follow: bool = False
    max_pages: int = 1
    next_selector: Optional[str] = None  # e.g., 'a[rel="next"]'
    allow_domains: Optional[List[str]] = None


def _normalize_url(u: str) -> str:
    """Strip tracking params & normalize for dedupe."""
    parsed = urlparse(u)
    # keep stable params; drop common trackers
    qs = [(k, v) for (k, v) in parse_qsl(parsed.query) if k.lower() not in {
        "utm_source","utm_medium","utm_campaign","utm_term","utm_content","fbclid","gclid","_hsenc","_hsmi"
    }]
    new = parsed._replace(query=urlencode(qs, doseq=True), fragment="")
    return urlunparse(new)


def _can_fetch(url: str, headers: Dict[str, str]) -> Tuple[bool, float]:
    """Check robots and get crawl-delay if possible."""
    if Robots is None:
        return True, 0.0
    try:
        robots_url = urljoin(url, "/robots.txt")
        r = Robots.fetch(robots_url, headers=headers)
        ua = headers.get("User-Agent", "Mozilla/5.0")
        allowed = r.allowed(url, ua)
        delay = r.delay(ua) or 0.0
        return allowed, float(delay)
    except Exception:
        return True, 0.0


def _fetch(url: str, cfg: FetchConfig) -> httpx.Response:
    headers = {**DEFAULT_HEADERS, **(cfg.headers or {})}
    if cfg.respect_robots:
        allowed, robots_delay = _can_fetch(url, headers)
        if not allowed:
            raise PermissionError(f"Blocked by robots.txt: {url}")
        if robots_delay:
            time.sleep(max(robots_delay, cfg.crawl_delay_s))
    else:
        if cfg.crawl_delay_s:
            time.sleep(cfg.crawl_delay_s)

    last_exc = None
    for attempt in range(cfg.max_retries):
        try:
            with httpx.Client(timeout=Timeout(cfg.timeout_s), follow_redirects=True, verify=cfg.verify_tls) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code >= 500:
                    raise httpx.HTTPError(f"Server error {resp.status_code}")
                return resp
        except Exception as e:
            last_exc = e
            time.sleep(cfg.backoff_s * (attempt + 1))
    raise RuntimeError(f"Failed fetching {url}: {last_exc}")


def _parse_html(html: str):
    if _HAVE_SELECTOLAX:
        return HTMLParser(html)
    # fallback
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "lxml")


def _get_text_blocks(doc, min_len: int = 2) -> List[str]:
    """Readable text blocks with line breaks preserved."""
    if _HAVE_SELECTOLAX:
        texts = []
        for node in doc.css("p, h1, h2, h3, h4, h5, h6, li, td, caption"):
            t = (node.text() or "").strip()
            if len(t) >= min_len:
                texts.append(t)
        return texts
    else:
        blocks = doc.select("p, h1, h2, h3, h4, h5, h6, li, td, caption")
        return [b.get_text(strip=True) for b in blocks if b.get_text(strip=True)]


def _abs_urls(doc, base_url: str, selectors: Iterable[str]) -> List[str]:
    urls = []
    if _HAVE_SELECTOLAX:
        for sel in selectors:
            for n in doc.css(sel):
                href = n.attributes.get("href") or n.attributes.get("src")
                if href:
                    urls.append(urljoin(base_url, href))
    else:
        for sel in selectors:
            for n in doc.select(sel):
                href = n.get("href") or n.get("src")
                if href:
                    urls.append(urljoin(base_url, href))
    return urls


def _extract_structured(html: str, base_url: str) -> Dict:
    out = {"jsonld": [], "microdata": [], "opengraph": {}, "twitter": {}}
    if extruct:
        try:
            data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld", "microdata", "opengraph", "twitter"])
            out["jsonld"] = data.get("json-ld") or []
            out["microdata"] = data.get("microdata") or []
            out["opengraph"] = (data.get("opengraph") or [{}])[0] if data.get("opengraph") else {}
            out["twitter"] = (data.get("twitter") or [{}])[0] if data.get("twitter") else {}
        except Exception:
            pass
    return out


def _priceify(v: Optional[str]) -> Optional[Dict]:
    if not v or not Price:
        return None
    p = Price.fromstring(v)
    if p and (p.amount or p.amount_float):
        return {"raw": v, "value": p.amount_float, "currency": p.currency}
    return None


def parse_product_like(doc, html: str, url: str) -> Dict:
    """Try to map common ecommerce fields from HTML / structured data."""
    meta = {"url": url, "title": None, "description": None, "images": [], "brand": None,
            "sku": None, "mpn": None, "category": None, "availability": None,
            "price": None, "breadcrumbs": []}

    # Title & description
    if _HAVE_SELECTOLAX:
        t = doc.css_first("meta[property='og:title']") or doc.css_first("title")
        d = doc.css_first("meta[name='description']")
        meta["title"] = (t.attributes.get("content") if t and t.tag == "meta" else (t.text() if t else None)) or None
        meta["description"] = (d.attributes.get("content") if d else None)
        imgs = [n.attributes.get("content") for n in doc.css("meta[property='og:image']") if n.attributes.get("content")]
        if not imgs:
            imgs = [n.attributes.get("src") for n in doc.css("img") if n.attributes.get("src")]
        meta["images"] = [urljoin(url, i) for i in imgs][:10]
    else:
        import bs4
        tmeta = doc.find("meta", {"property": "og:title"})
        meta["title"] = (tmeta.get("content") if tmeta else None) or (doc.title.string.strip() if doc.title else None)
        dmeta = doc.find("meta", {"name": "description"})
        meta["description"] = dmeta.get("content") if dmeta else None
        imgs = [m.get("content") for m in doc.find_all("meta", {"property": "og:image"}) if m.get("content")]
        if not imgs:
            imgs = [i.get("src") for i in doc.find_all("img") if i.get("src")]
        meta["images"] = [urljoin(url, i) for i in imgs][:10]

    # Structured data --> lift Product/Offer
    sd = _extract_structured(html, url)
    product_nodes = []
    for j in sd.get("jsonld", []):
        t = j.get("@type")
        if isinstance(t, list):
            is_product = any(x.lower() == "product" for x in [str(x).lower() for x in t])
        else:
            is_product = (str(t).lower() == "product")
        if is_product:
            product_nodes.append(j)

    # Pull best candidate
    node = product_nodes[0] if product_nodes else None
    if node:
        meta["brand"] = (node.get("brand") or {}).get("name") if isinstance(node.get("brand"), dict) else node.get("brand")
        meta["sku"] = node.get("sku")
        meta["mpn"] = node.get("mpn")
        meta["category"] = node.get("category")
        offers = node.get("offers")
        if isinstance(offers, dict):
            meta["availability"] = offers.get("availability") or offers.get("availabilityStarts")
            meta["price"] = _priceify(offers.get("priceCurrency") + " " + offers.get("price") if offers.get("price") else offers.get("price"))
        elif isinstance(offers, list) and offers:
            o = offers[0]
            meta["availability"] = o.get("availability")
            meta["price"] = _priceify(o.get("priceCurrency") + " " + o.get("price") if o.get("price") else o.get("price"))

    # Breadcrumbs
    for j in sd.get("jsonld", []):
        if (j.get("@type") == "BreadcrumbList") and isinstance(j.get("itemListElement"), list):
            crumbs = []
            for it in j["itemListElement"]:
                name = (it.get("item") or {}).get("name") if isinstance(it.get("item"), dict) else it.get("name")
                if name:
                    crumbs.append(name)
            if crumbs:
                meta["breadcrumbs"] = crumbs
                break

    return meta


def extract_html_page(url: str,
                      fetch_cfg: Optional[FetchConfig] = None,
                      crawl_cfg: Optional[CrawlConfig] = None) -> Dict[str, any]:
    fetch_cfg = fetch_cfg or FetchConfig()
    crawl_cfg = crawl_cfg or CrawlConfig()

    visited = set()
    queue = [_normalize_url(url)]
    pages = []
    while queue and len(pages) < max(1, crawl_cfg.max_pages):
        cur = queue.pop(0)
        if cur in visited:
            continue
        visited.add(cur)

        resp = _fetch(cur, fetch_cfg)
        html = resp.text
        doc = _parse_html(html)

        # Canonical
        canonical = None
        if _HAVE_SELECTOLAX:
            c = doc.css_first("link[rel='canonical']")
            canonical = c.attributes.get("href") if c else None
        else:
            l = doc.find("link", {"rel": "canonical"})
            canonical = l.get("href") if l else None
        if canonical:
            canonical = _normalize_url(urljoin(cur, canonical))

        # Text blocks
        blocks = _get_text_blocks(doc)

        # Product-like fields
        product_meta = parse_product_like(doc, html, cur)

        pages.append({
            "url": cur,
            "canonical": canonical or cur,
            "content": "\n\n".join(blocks),
            "metadata": product_meta
        })

        # Pagination: discover "next"
        if crawl_cfg.follow and crawl_cfg.next_selector:
            next_candidates = _abs_urls(doc, cur, [crawl_cfg.next_selector])
            for nxt in next_candidates:
                n = _normalize_url(nxt)
                if n.startswith(("http://", "https://")):
                    if (not crawl_cfg.allow_domains) or (urlparse(n).hostname in (crawl_cfg.allow_domains or [])):
                        if n not in visited:
                            queue.append(n)

    return {"pages": pages}
