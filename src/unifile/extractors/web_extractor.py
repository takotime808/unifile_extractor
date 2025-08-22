# Copyright (c) 2025 takotime808
"""
High-quality web extraction with robust fetching, robots.txt, optional JS rendering,
sitemap discovery, and clean text extraction.

Dependencies (optional but recommended):
  - httpx>=0.27
  - beautifulsoup4, lxml
  - trafilatura (preferred main-content extractor) OR readabilipy/readability-lxml
  - tldextract
  - playwright (optional, for JS rendering: `playwright install chromium`)
"""

from __future__ import annotations

import re
import time
import math
import asyncio
import mimetypes
import contextlib
import pandas as pd
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Dict, Any

from urllib.parse import urlparse, urljoin
import urllib.robotparser as robotparser

try:
    import httpx
except Exception as e:  # pragma: no cover
    raise RuntimeError("Install httpx to use web_extractor") from e

try:
    import tldextract  # nicer host keys if available
except Exception:
    tldextract = None

try:
    # Preferred high-quality extractor
    import trafilatura
except Exception:
    trafilatura = None

# Fallbacks for readability
with contextlib.suppress(Exception):
    from readabilipy import simple_json_from_html  # type: ignore

from bs4 import BeautifulSoup  # type: ignore

# We assume unifile public API exists per README
# https://github.com/takotime808/unifile_extractor (master)
try:
    from unifile import extract_to_table  # type: ignore
except Exception:
    # If running module standalone for tests, this import may fail.
    extract_to_table = None  # type: ignore


DEFAULT_UA = (
    "unifile-extractor/0.1 (+https://github.com/takotime808/unifile_extractor)"
)

@dataclass
class FetchOptions:
    timeout: float = 20.0
    connect_timeout: float = 10.0
    max_redirects: int = 5
    max_bytes: int = 25 * 1024 * 1024  # 25 MB safety cap
    retries: int = 3
    backoff_base: float = 0.5
    http2: bool = True
    follow_redirects: bool = True
    user_agent: str = DEFAULT_UA
    render_js: bool = False  # requires playwright
    respect_robots: bool = True
    referer: Optional[str] = None
    accept: str = (
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    )
    extra_headers: Optional[Dict[str, str]] = None


def _host_key(url: str) -> str:
    if tldextract:
        parts = tldextract.extract(url)
        host = ".".join([p for p in [parts.subdomain, parts.domain, parts.suffix] if p])
    else:
        host = urlparse(url).netloc
    return host.lower()


async def _robots_allowed(url: str, client: httpx.AsyncClient, ua: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = await client.get(robots_url)
        if resp.status_code >= 400:
            return True  # assume allowed if robots not available
        rp = robotparser.RobotFileParser()
        rp.parse(resp.text.splitlines())
        return rp.can_fetch(ua, url)
    except Exception:
        return True  # be permissive on network/parse errors


async def _fetch_bytes(
    url: str, client: httpx.AsyncClient, opts: FetchOptions
) -> Tuple[bytes, Dict[str, Any]]:
    # retry with exponential backoff + jitter
    exc: Optional[Exception] = None
    for attempt in range(opts.retries + 1):
        try:
            headers = {
                "User-Agent": opts.user_agent,
                "Accept": opts.accept,
            }
            if opts.referer:
                headers["Referer"] = opts.referer
            if opts.extra_headers:
                headers.update(opts.extra_headers)

            resp = await client.get(
                url,
                follow_redirects=opts.follow_redirects,
                timeout=httpx.Timeout(
                    opts.timeout,
                    connect=opts.connect_timeout,
                ),
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.content
            if opts.max_bytes and len(data) > opts.max_bytes:
                raise ValueError(
                    f"Response exceeds max_bytes ({len(data)} > {opts.max_bytes})"
                )
            meta = {
                "final_url": str(resp.request.url),
                "status_code": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "content_length": len(data),
                "headers": dict(resp.headers),
            }
            return data, meta
        except Exception as e:  # retry
            exc = e
            if attempt == opts.retries:
                break
            # exponential backoff with jitter
            delay = opts.backoff_base * (2 ** attempt) + (0.1 * math.sin(time.time()))
            await asyncio.sleep(max(0.05, delay))
    assert exc is not None
    raise exc


def _guess_ext(ct: str, final_url: str) -> str:
    # prioritize content-type
    if ct:
        # e.g., 'text/html; charset=utf-8'
        main = ct.split(";")[0].strip().lower()
        ext = mimetypes.guess_extension(main) or ""
        if ext:
            return ext
    # fallback to URL
    path = urlparse(final_url).path
    guess = mimetypes.guess_extension(
        mimetypes.guess_type(path)[0] or ""
    ) or (path.split(".")[-1] if "." in path else "")
    if guess and not guess.startswith("."):
        guess = "." + guess
    return guess or ".html"


def _extract_html_text(html: str, url: str) -> Tuple[str, Dict[str, Any]]:
    """
    Best-effort readable text extraction:
      1) trafilatura.extract (if available)
      2) readability JSON (readabilipy)
      3) BeautifulSoup get_text fallback
    Returns (text, extra_meta)
    """
    title = None
    if trafilatura:
        with contextlib.suppress(Exception):
            res = trafilatura.extract(html, include_comments=False, include_tables=True)
            if res:
                # Try to get title too:
                with contextlib.suppress(Exception):
                    title = trafilatura.bare_extraction(html, url=url).get("title")
                return res.strip(), {"title": title}
    # Readability fallback
    with contextlib.suppress(Exception):
        sj = simple_json_from_html(html, use_readability=True)
        content = (sj.get("plain_text") or "").strip()
        title = sj.get("title")
        if content:
            return content, {"title": title}

    # Bare bones BS4 fallback
    soup = BeautifulSoup(html, "lxml")
    # kill scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else None)
    text = soup.get_text(separator="\n")
    # normalize whitespace / newlines
    text = re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()
    return text, {"title": title}


async def _maybe_render_js(url: str, html_bytes: bytes) -> bytes:
    """
    If playwright is installed and rendering is requested, render the page to get
    post-hydration HTML. Otherwise, return the original HTML bytes.
    """
    try:
        from playwright.async_api import async_playwright  # type: ignore
    except Exception:
        return html_bytes

    # Minimal render: load, wait for networkidle, get content
    async with async_playwright() as p:  # type: ignore
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        html = await page.content()
        await browser.close()
        return html.encode("utf-8", errors="ignore")


async def extract_from_url(
    url: str,
    *,
    opts: Optional[FetchOptions] = None,
) -> pd.DataFrame:
    """
    Extracts from a single URL into the Unifile standardized table.

    - HTML --> readable text row (unit_type='file', unit_id='body')
    - Non-HTML --> routes bytes+filename to extract_to_table (PDFs, docs, images, etc.)
    """
    opts = opts or FetchOptions()

    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    async with httpx.AsyncClient(http2=opts.http2, limits=limits) as client:
        if opts.respect_robots:
            allowed = await _robots_allowed(url, client, opts.user_agent)
            if not allowed:
                return pd.DataFrame(
                    [
                        {
                            "source_path": url,
                            "source_name": urlparse(url).path.split("/")[-1] or url,
                            "file_type": "url",
                            "unit_type": "file",
                            "unit_id": "body",
                            "content": "",
                            "char_count": 0,
                            "metadata": {"note": "Blocked by robots.txt"},
                            "status": "error",
                            "error": "robots_disallowed",
                        }
                    ]
                )

        data, meta = await _fetch_bytes(url, client, opts)

        ct = meta.get("content_type", "").lower()
        final_url = meta.get("final_url", url)
        ext = _guess_ext(ct, final_url)

        is_html = "text/html" in ct or ext in (".html", ".htm")
        if is_html:
            html_bytes = data
            if opts.render_js:
                with contextlib.suppress(Exception):
                    html_bytes = await _maybe_render_js(final_url, data)
            text, extra_meta = _extract_html_text(html_bytes.decode("utf-8", "ignore"), final_url)
            row = {
                "source_path": final_url,
                "source_name": urlparse(final_url).path.split("/")[-1] or "index.html",
                "file_type": "html",
                "unit_type": "file",
                "unit_id": "body",
                "content": text,
                "char_count": len(text),
                "metadata": {
                    **meta,
                    **(extra_meta or {}),
                },
                "status": "ok",
                "error": "",
            }
            return pd.DataFrame([row])

        # Non-HTML: reuse core pipeline if import available
        if extract_to_table:
            # Feed bytes with a guessed filename so downstream pickers work
            filename = (urlparse(final_url).path.split("/")[-1] or f"download{ext}") or f"download{ext}"
            return extract_to_table(data, filename=filename)
        else:
            # Minimal graceful degradation: create a single row with no parsing
            row = {
                "source_path": final_url,
                "source_name": urlparse(final_url).path.split("/")[-1] or f"download{ext}",
                "file_type": (ext or "").lstrip("."),
                "unit_type": "file",
                "unit_id": "body",
                "content": "",
                "char_count": 0,
                "metadata": meta,
                "status": "ok",
                "error": "",
            }
            return pd.DataFrame([row])


async def extract_many(
    urls: Iterable[str],
    *,
    concurrency: int = 5,
    opts: Optional[FetchOptions] = None,
    per_host_delay: float = 0.0,
) -> pd.DataFrame:
    """
    Concurrently extract many URLs with optional per-host politeness delays.
    """
    opts = opts or FetchOptions()
    sem = asyncio.Semaphore(concurrency)
    last_visit: Dict[str, float] = {}

    async def _run(u: str) -> pd.DataFrame:
        async with sem:
            if per_host_delay > 0:
                host = _host_key(u)
                now = time.time()
                wait = max(0.0, (last_visit.get(host, 0) + per_host_delay) - now)
                if wait > 0:
                    await asyncio.sleep(wait)
                last_visit[host] = time.time()
            try:
                return await extract_from_url(u, opts=opts)
            except Exception as e:
                return pd.DataFrame(
                    [
                        {
                            "source_path": u,
                            "source_name": urlparse(u).path.split("/")[-1] or u,
                            "file_type": "url",
                            "unit_type": "file",
                            "unit_id": "body",
                            "content": "",
                            "char_count": 0,
                            "metadata": {},
                            "status": "error",
                            "error": repr(e),
                        }
                    ]
                )

    frames = await asyncio.gather(*[_run(u) for u in urls])
    return pd.concat(frames, ignore_index=True)


async def discover_sitemap_urls(seed_url: str, client: Optional[httpx.AsyncClient] = None) -> List[str]:
    """
    Best-effort sitemap discovery: robots.txt, <link rel="sitemap">, /sitemap.xml
    Returns a list of candidate sitemap URLs (not parsed).
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(http2=True, follow_redirects=True)
    assert client is not None

    results: List[str] = []
    parsed = urlparse(seed_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    # robots.txt
    with contextlib.suppress(Exception):
        r = await client.get(urljoin(base, "/robots.txt"), timeout=10.0)
        if r.status_code < 400:
            # find Sitemap: lines
            for line in r.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    results.append(line.split(":", 1)[1].strip())

    # HTML link hints
    with contextlib.suppress(Exception):
        r = await client.get(seed_url, timeout=10.0)
        if r.status_code < 400 and "text/html" in r.headers.get("content-type", ""):
            soup = BeautifulSoup(r.text, "lxml")
            for link in soup.select('link[rel="sitemap"]'):
                href = link.get("href")
                if href:
                    results.append(urljoin(seed_url, href))

    # Default path
    results.append(urljoin(base, "/sitemap.xml"))

    # Deduplicate
    out = []
    seen = set()
    for u in results:
        if u not in seen:
            seen.add(u)
            out.append(u)
    if own_client:
        await client.aclose()
    return out
