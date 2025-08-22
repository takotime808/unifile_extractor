# Copyright (c) 2025 takotime808

from __future__ import annotations

import json
import os
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Iterable
from urllib.parse import urljoin, urlparse

try:
    # Prefer a robust parser when available (lxml is already in deps)
    from bs4 import BeautifulSoup  # type: ignore
    _HAVE_BS4 = True
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore
    _HAVE_BS4 = False


def _base_row(source_path: str, unit_type: str, unit_id: int, content: str, file_type: str = "html") -> Dict[str, Any]:
    return {
        "source_path": os.path.abspath(source_path),
        "source_name": os.path.basename(source_path),
        "file_type": file_type,
        "unit_type": unit_type,
        "unit_id": unit_id,
        "content": content,
        "char_count": len(content or ""),
        "metadata": {},
        "status": "ok",
        "error": "",
    }


# --------------------------------------------------------------------------------------
# Fallback very-simple block parser (kept from previous implementation)
# --------------------------------------------------------------------------------------
class _SimpleHTMLBlockParser(HTMLParser):
    """
    Very small HTML-to-blocks parser using stdlib only.
    Captures headings <h1..h6>, paragraphs <p>, list items <li>,
    code blocks <code>/<pre>, captions <figcaption>, and tables <table>.
    """
    def __init__(self):
        super().__init__()
        self.blocks: List[Dict[str, Any]] = []
        self._tag_stack: List[str] = []
        self._buf: List[str] = []
        self._unit_id = 0
        self._in_table = False
        self._table_rows: List[List[str]] = []
        self._current_row: List[str] = []
        self._capture_text = False
        self._current_block_type: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        if tag in ("p", "li", "figcaption"):
            self._buf = []
            self._capture_text = True
            self._current_block_type = {"p": "paragraph", "li": "list_item", "figcaption": "caption"}[tag]
        elif tag in ("code", "pre"):
            self._buf = []
            self._capture_text = True
            self._current_block_type = "code"
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._buf = []
            self._capture_text = True
            self._current_block_type = "heading"
        elif tag == "table":
            self._in_table = True
            self._table_rows = []
        elif tag == "tr" and self._in_table:
            self._current_row = []
        elif tag in ("td", "th") and self._in_table:
            self._buf = []
            self._capture_text = True
            self._current_block_type = "table_cell"

    def handle_data(self, data):
        if self._capture_text:
            self._buf.append(data)

    def handle_endtag(self, tag):
        # close text blocks
        if tag in ("p", "li", "figcaption", "code", "pre", "h1", "h2", "h3", "h4", "h5", "h6"):
            if self._capture_text:
                text = "".join(self._buf).strip()
                if text:
                    self.blocks.append({"block_type": self._current_block_type, "text": text})
                self._buf = []
            self._capture_text = False
            self._current_block_type = None
        # close table cell
        if tag in ("td", "th") and self._in_table and self._capture_text:
            text = "".join(self._buf).strip()
            self._current_row.append(text)
            self._buf = []
            self._capture_text = False
            self._current_block_type = None
        # close table row
        if tag == "tr" and self._in_table:
            if self._current_row:
                self._table_rows.append(self._current_row)
            self._current_row = []
        # close table
        if tag == "table" and self._in_table:
            self.blocks.append({"block_type": "table", "table": self._table_rows})
            self._in_table = False

        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()


# --------------------------------------------------------------------------------------
# Product extraction helpers (JSON-LD + DOM heuristics)
# --------------------------------------------------------------------------------------

# Expanded normalized fields we'll emit for each product
_PRODUCT_FIELDS = [
    "name",
    "price",
    "compare_at_price",
    "currency",
    "availability",
    "url",
    "image",
    "sku",
    "brand",
    "product_id",
    "handle",
    "description",
    # light specs from titles for parts (motors, etc.)
    "kv",
    "weight_g",
    "diameter_mm",
    "cells",
]

_MONEY_RX = re.compile(r"""
    (?P<curr>USD|EUR|GBP|CAD|AUD|JPY|CHF|CNY|INR|KRW|RUB|BRL|MXN|ZAR|AED|SAR|SEK|NOK|DKK|PLN)?
    \s*
    (?P<sym>\$|€|£)?
    \s*
    (?P<num>-?\d+(?:[,\s]\d{3})*(?:\.\d+)?)
""", re.VERBOSE | re.I)

def _norm_text(x: Optional[str]) -> str:
    return " ".join((x or "").split())

def _first_not_empty(*vals: Optional[str]) -> Optional[str]:
    for v in vals:
        if v:
            v = str(v).strip()
            if v:
                return v
    return None

def _norm_price_number(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    t = s.strip()
    # Extract final numeric group if mixed text like "From $95.00"
    m = _MONEY_RX.search(t)
    if m:
        num = m.group("num").replace(",", "").replace(" ", "")
        try:
            return float(num)
        except Exception:
            return None
    # fallback: pure float
    try:
        return float(t.replace(",", ""))
    except Exception:
        return None

def _infer_currency(s: Optional[str], default: Optional[str]) -> Optional[str]:
    if not s:
        return default
    m = _MONEY_RX.search(s)
    if not m:
        return default
    curr = m.group("curr")
    sym = m.group("sym")
    if curr:
        return curr.upper()
    if sym == "$":
        # Heuristic: assume USD for lack of region; Shopify US stores do this.
        return default or "USD"
    if sym == "€":
        return default or "EUR"
    if sym == "£":
        return default or "GBP"
    return default

def _handle_from_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    try:
        path = urlparse(u).path
        # /products/<handle> or .../<handle>[/...]
        parts = [p for p in path.split("/") if p]
        if "products" in parts:
            i = parts.index("products")
            if i + 1 < len(parts):
                return parts[i + 1]
        # last segment as a fallback
        return parts[-1] if parts else None
    except Exception:
        return None

def _collect_jsonld_products(soup, base_href: str) -> List[Dict[str, Any]]:
    prods: List[Dict[str, Any]] = []
    for s in soup.find_all("script", {"type": "application/ld+json"}):
        txt = s.string or s.text
        if not txt:
            continue
        try:
            data = json.loads(txt)
        except Exception:
            continue

        def norm_product(d: Dict[str, Any]) -> Dict[str, Any]:
            offers = d.get("offers") or {}
            if isinstance(offers, list) and offers:
                offers = offers[0]
            brand = d.get("brand")
            if isinstance(brand, dict):
                brand = brand.get("name")
            price = offers.get("price") if isinstance(offers, dict) else None
            currency = offers.get("priceCurrency") if isinstance(offers, dict) else None
            availability = None
            if isinstance(offers, dict):
                avail = offers.get("availability") or ""
                availability = avail.rsplit("/", 1)[-1] if "/" in avail else avail or None

            url = urljoin(base_href, d.get("url") or "")
            image = d.get("image")
            if isinstance(image, list):
                image = image[0]
            sku = d.get("sku") or (offers.get("sku") if isinstance(offers, dict) else None)
            pid = d.get("productID") or d.get("gtin13") or d.get("gtin") or d.get("mpn")
            desc = _norm_text(d.get("description"))

            # derive handle from url
            handle = _handle_from_url(url)

            return {
                "name": _norm_text(d.get("name")),
                "price": str(price) if price is not None else None,
                "compare_at_price": None,  # often not in JSON-LD; DOM may provide
                "currency": currency,
                "availability": availability,
                "url": url,
                "image": image,
                "sku": sku,
                "brand": brand,
                "product_id": pid,
                "handle": handle,
                "description": desc,
            }

        # single product
        if isinstance(data, dict) and ("Product" in str(data.get("@type"))):
            prods.append(norm_product(data))
        # ItemList / CollectionPage with products
        elif isinstance(data, dict) and data.get("@type") in ("ItemList", "CollectionPage"):
            items = data.get("itemListElement") or data.get("mainEntity") or []
            for it in items:
                obj = it.get("item") if isinstance(it, dict) and "item" in it else it
                if isinstance(obj, dict) and ("Product" in str(obj.get("@type"))):
                    prods.append(norm_product(obj))
        # array of products
        elif isinstance(data, list):
            for d in data:
                if isinstance(d, dict) and ("Product" in str(d.get("@type"))):
                    prods.append(norm_product(d))
    return prods

def _nearest_price_el(el):
    # Look for common price nodes nearby
    near = el.find_all(["span", "div", "meta"], class_=lambda c: c and any(k in c.lower() for k in ["price", "money", "product-price"]))
    if near:
        return near
    # walk up a bit
    parent = el
    for _ in range(3):
        parent = parent.parent
        if not parent:
            break
        near = parent.find_all(["span", "div", "meta"], class_=lambda c: c and any(k in c.lower() for k in ["price", "money", "product-price"]))
        if near:
            return near
    return []

def _text_or_content(n) -> str:
    if not n:
        return ""
    if n.name == "meta":
        return n.get("content") or ""
    return n.get_text(" ")

def _extract_dom_prices(node) -> Dict[str, Optional[str]]:
    """
    Extract price / compare-at price and currency hints from a DOM node cluster.
    """
    price_text = None
    compare_text = None
    currency_hint = None

    # Common Shopify price classes/selectors
    candidates = []
    candidates += node.select(".price, .product-price, .money, [data-price], [data-product-price], meta[itemprop='price']")
    if not candidates:
        candidates = _nearest_price_el(node) or []

    texts = [_text_or_content(x) for x in candidates]
    texts = [_norm_text(t) for t in texts if _norm_text(t)]

    # Choose price & compare-at via simple heuristics
    # - prefer an element with explicit 'compare' class for compare_at
    for el in candidates:
        classes = " ".join(el.get("class") or [])
        t = _norm_text(_text_or_content(el))
        if not t:
            continue
        if "compare" in classes or "was" in classes or "sale" in classes:
            if compare_text is None:
                compare_text = t
        else:
            if price_text is None:
                price_text = t

    # Fallback if we didn't decide yet
    if price_text is None and texts:
        price_text = texts[0]
    if compare_text is None and len(texts) > 1:
        # pick the larger number as compare_at if two distinct prices appear
        nums = [(_norm_price_number(tt) or 0.0, tt) for tt in texts[:2]]
        if nums[1][0] > nums[0][0]:
            compare_text = nums[1][1]

    # Infer currency
    currency_hint = _infer_currency(price_text or compare_text, None)

    return {"price": price_text, "compare_at": compare_text, "currency": currency_hint}

def _norm_price_number(s: Optional[str]) -> Optional[float]:
    return _norm_price_number.__wrapped__(s)  # type: ignore  # silence redefinition warnings
# Actually define the function (above we used for hints)
def _norm_price_number(s: Optional[str]) -> Optional[float]:  # noqa: F811
    if s is None:
        return None
    t = s.strip()
    m = _MONEY_RX.search(t)
    if m:
        num = m.group("num").replace(",", "").replace(" ", "")
        try:
            return float(num)
        except Exception:
            return None
    try:
        return float(t.replace(",", ""))
    except Exception:
        return None

def _collect_dom_products(soup, base_href: str) -> List[Dict[str, Any]]:
    """
    Heuristics for Shopify-like collection pages:
    - product cards inside grid/list containers
    - title anchors, price spans/divs with money, availability badges, image srcs
    - sku / product-id from data attributes where available
    """
    prods: List[Dict[str, Any]] = []
    candidates = soup.select(
        ".product, .product-grid, .grid-product, .grid__item, .product-card, .productitem, ul.products li, .collection-products .product, .productgrid--item"
    )
    if not candidates:
        candidates = soup.select("a[href*='/products/']")

    seen_urls = set()

    for c in candidates:
        # find product anchor
        a = c.find("a", href=True)
        if not a:
            # maybe this candidate *is* the anchor
            if c.name == "a" and c.get("href"):
                a = c
            else:
                aa = c.select("a[href*='/products/']")
                if aa:
                    a = aa[0]
        if not a:
            continue

        href = urljoin(base_href, a.get("href"))
        if "/collections/" in href and "/products/" not in href:
            # collection link; look deeper
            aa = c.select("a[href*='/products/']")
            if aa:
                a = aa[0]
                href = urljoin(base_href, a.get("href"))

        if href in seen_urls:
            continue

        title = _norm_text(a.get_text(" "))
        if not title:
            # sometimes text is nested inside a heading/link combo
            h = c.select_one("h1, h2, h3, h4, h5, h6")
            title = _norm_text(h.get_text(" ")) if h else ""

        if not title:
            continue

        # image
        img = None
        img_el = c.find("img")
        if img_el:
            src = img_el.get("data-src") or img_el.get("data-original") or img_el.get("src")
            if src:
                img = urljoin(base_href, src)

        # prices (including compare-at)
        price_info = _extract_dom_prices(c)
        price_text = price_info["price"]
        compare_text = price_info["compare_at"]
        currency_hint = price_info["currency"]

        # availability hints
        avail = None
        txt = _norm_text(c.get_text(" "))
        for flag in ("sold out", "out of stock", "preorder", "pre-order", "backorder"):
            if flag in txt.lower():
                avail = flag.replace("-", " ")

        # sku / brand / product id from data attributes
        sku = c.get("data-sku") or c.get("data-product-sku")
        brand = c.get("data-brand") or c.get("data-vendor")
        pid = c.get("data-product-id") or c.get("data-id")

        prods.append({
            "name": title,
            "price": price_text,
            "compare_at_price": compare_text,
            "currency": currency_hint,
            "availability": avail,
            "url": href,
            "image": img,
            "sku": sku,
            "brand": brand,
            "product_id": pid,
            "handle": _handle_from_url(href),
            "description": None,
        })
        seen_urls.add(href)

    # last resort: straight anchors
    if not prods:
        for a in soup.select("a[href*='/products/']"):
            href = urljoin(base_href, a.get("href"))
            title = _norm_text(a.get_text(" "))
            if not title:
                continue
            prods.append({
                "name": title,
                "price": None,
                "compare_at_price": None,
                "currency": None,
                "availability": None,
                "url": href,
                "image": None,
                "sku": None,
                "brand": None,
                "product_id": None,
                "handle": _handle_from_url(href),
                "description": None,
            })
    return prods

def _light_specs_from_title(name: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Extract lightweight specs commonly embedded in part/motor titles.
    Returns keys compatible with _PRODUCT_FIELDS (kv, weight_g, diameter_mm, cells).
    """
    if not name:
        return {"kv": None, "weight_g": None, "diameter_mm": None, "cells": None}

    s = name

    # KV rating: e.g., 390KV, 1100 KV
    m_kv = re.search(r"(\d{2,5})\s*KV\b", s, flags=re.I)
    kv = m_kv.group(1) if m_kv else None

    # Weight in grams: e.g., 85g, 85 g
    m_w = re.search(r"(\d+(?:\.\d+)?)\s*g\b", s, flags=re.I)
    weight_g = m_w.group(1) if m_w else None

    # Diameter mm: e.g., 28mm, 40 mm
    m_d = re.search(r"(\d+(?:\.\d+)?)\s*mm\b", s, flags=re.I)
    diameter_mm = m_d.group(1) if m_d else None

    # Cell count: e.g., 6S, 12S
    m_c = re.search(r"\b(\d{1,2})\s*S\b", s, flags=re.I)
    cells = m_c.group(1) if m_c else None

    return {"kv": kv, "weight_g": weight_g, "diameter_mm": diameter_mm, "cells": cells}

def _to_table_rows_dicts(dicts: List[Dict[str, Any]], preferred_order: Iterable[str]) -> List[List[str]]:
    """
    Convert list of dicts into a 2D table with a stable header order.
    Missing values become "" (strings).
    """
    header = list(preferred_order)
    rows: List[List[str]] = [header]
    for d in dicts:
        row = []
        for col in header:
            val = d.get(col)
            row.append("" if val is None else str(val))
        rows.append(row)
    return rows


# --------------------------------------------------------------------------------------
# Public extractor
# --------------------------------------------------------------------------------------
def extract_html(path: str, enable_tables: bool = True, enable_block_types: bool = True) -> List[Dict[str, Any]]:
    """
    Extract HTML into block-level rows and (optionally) a normalized product table.

    Behavior
    --------
    1) If BeautifulSoup is available, parse the DOM and:
       - collect JSON-LD Products / ItemList
       - collect product cards (Shopify-like collections) via CSS heuristics
       - merge fields, enrich with handle/specs/currency/compare-at/availability
       - emit ONE 'table' row with product info sorted by price (asc) if parseable else by name
    2) Always produce block-level rows (heading/paragraph/list_item/code/caption).
    3) Extract any literal <table> elements into 'table' rows as before.

    Returns
    -------
    List[Dict[str, Any]] compatible with the standard schema.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    rows: List[Dict[str, Any]] = []
    unit_id = 0

    # ----------------------------------------
    # Robust path (bs4), else fallback parser
    # ----------------------------------------
    if _HAVE_BS4:
        soup = BeautifulSoup(content, "lxml")
        base_href = f"file://{os.path.abspath(path)}"

        products_ld = _collect_jsonld_products(soup, base_href)
        products_dom = _collect_dom_products(soup, base_href)

        # Merge: DOM wins for compare_at/availability/price when present; JSON-LD fills gaps
        merged: Dict[str, Dict[str, Any]] = {}

        def key_of(p: Dict[str, Any]) -> str:
            return p.get("url") or p.get("name") or id(p)  # url preferred

        for p in products_ld + products_dom:
            k = key_of(p)
            if k not in merged:
                merged[k] = p
            else:
                # Fill missing fields from the new candidate if present
                base = merged[k]
                for field in _PRODUCT_FIELDS:
                    if base.get(field) in (None, "", []):
                        base[field] = p.get(field) if p.get(field) not in (None, "", []) else base.get(field)

                # Prefer DOM compare_at/availability if present
                for f in ("compare_at_price", "availability", "price"):
                    if p.get(f):
                        base[f] = p[f]

        # Post-process: normalize currency and basic specs, ensure handle
        products: List[Dict[str, Any]] = []
        for p in merged.values():
            # Normalize currency inference from price strings if missing
            p["currency"] = _infer_currency(_first_not_empty(p.get("price"), p.get("compare_at_price")), p.get("currency"))

            # Specs from title
            specs = _light_specs_from_title(p.get("name"))
            for k, v in specs.items():
                if p.get(k) in (None, ""):
                    p[k] = v

            # Ensure handle
            if not p.get("handle"):
                p["handle"] = _handle_from_url(p.get("url"))

            products.append(p)

        # Normalize and sort products (by numeric price if available)
        for p in products:
            p["_price_num"] = _norm_price_number(p.get("price"))
        if any(pp["_price_num"] is not None for pp in products):
            products.sort(key=lambda x: (x["_price_num"] is None, x["_price_num"]))
        else:
            products.sort(key=lambda x: (x.get("name") or "").lower())
        for p in products:
            p.pop("_price_num", None)

        # Emit product table row
        if enable_tables and products:
            table_2d = _to_table_rows_dicts(products, _PRODUCT_FIELDS)
            table_txt = "\n".join("\t".join(r) for r in table_2d)
            row = _base_row(path, "table", unit_id, table_txt)
            row["metadata"] = {"block_type": "table", "table": table_2d, "kind": "products"}
            rows.append(row)
            unit_id += 1

        # Literal HTML <table> tags --> table rows (as before)
        if enable_tables:
            for t in soup.find_all("table"):
                grid: List[List[str]] = []
                for tr in t.find_all("tr"):
                    cells = tr.find_all(["th", "td"])
                    grid.append([_norm_text(c.get_text(" ")) for c in cells])
                if any(any(cell for cell in r) for r in grid):
                    txt = "\n".join("\t".join(r) for r in grid)
                    r = _base_row(path, "table", unit_id, txt)
                    r["metadata"] = {"block_type": "table", "table": grid}
                    rows.append(r)
                    unit_id += 1

        # Block-level content
        def emit_block(bt: str, text: str):
            nonlocal unit_id
            text = _norm_text(text)
            if not text:
                return
            r = _base_row(path, "block", unit_id, text)
            r["metadata"] = {"block_type": bt}
            rows.append(r)
            unit_id += 1

        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            for el in soup.select(tag):
                emit_block("heading", el.get_text(" "))

        for el in soup.select("p"):
            emit_block("paragraph", el.get_text(" "))

        for el in soup.select("li"):
            emit_block("list_item", el.get_text(" "))

        for el in soup.select("pre, code"):
            emit_block("code", el.get_text("\n"))

        for el in soup.select("figcaption"):
            emit_block("caption", el.get_text(" "))

        return rows

    # ----------------------------------------
    # Fallback: stdlib block/table parser
    # ----------------------------------------
    parser = _SimpleHTMLBlockParser()
    parser.feed(content)

    for b in parser.blocks:
        bt = b.get("block_type")
        if bt == "table":
            if enable_tables:
                row = _base_row(path, "table", unit_id, "\n".join(["\t".join(r) for r in b["table"]]))
                row["metadata"] = {"block_type": "table", "table": b["table"]}
                rows.append(row)
                unit_id += 1
        else:
            text = b.get("text", "")
            row = _base_row(path, "block", unit_id, text)
            if enable_block_types:
                row["metadata"] = {"block_type": bt}
            rows.append(row)
            unit_id += 1

    return rows
