from __future__ import annotations

from typing import Any
import re
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlsplit

from web_prime_search.config import Settings, get_settings
from web_prime_search.models import SearchResult
from web_prime_search.proxy import get_http_client

_SEARCH_URL = "https://www.google.com/search"
_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
_ANCHOR_PATTERN = re.compile(
    r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?:(?!</a>).)*?<h3[^>]*>(?P<title>.*?)</h3>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_PATTERNS = (
    re.compile(
        r'<div[^>]*class="[^"]*\bVwiC3b\b[^"]*"[^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r'<span[^>]*class="[^"]*\baCOpRe\b[^"]*"[^>]*>(.*?)</span>',
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r'<div[^>]*class="[^"]*\bs3v9rd\b[^"]*"[^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r'<div[^>]*class="[^"]*\bMUxGbd\b[^"]*"[^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    ),
)
_BLOCK_MARKERS = (
    "unusual traffic",
    "detected unusual traffic",
    "before you continue to google search",
    "consent.google.com",
    'id="captcha-form"',
    "httpservice/retry/enablejs",
    "/sorry/",
)
_BROWSER_EXTRACTION_SCRIPT = """
() => {
    const selectors = ['div.VwiC3b', 'span.aCOpRe', 'div.s3v9rd', 'div.MUxGbd'];
    const headings = Array.from(document.querySelectorAll('a h3'));
    return headings.map((heading) => {
        const anchor = heading.closest('a');
        if (!anchor) {
            return null;
        }

        let scope = anchor.closest('div');
        let snippet = '';
        for (let depth = 0; depth < 4 && scope && !snippet; depth += 1) {
            for (const selector of selectors) {
                const node = scope.querySelector(selector);
                if (node && node.innerText) {
                    snippet = node.innerText;
                    break;
                }
            }
            scope = scope.parentElement;
        }

        return {
            href: anchor.href || anchor.getAttribute('href') || '',
            title: heading.innerText || heading.textContent || '',
            snippet,
        };
    }).filter(Boolean);
}
"""


async def search(
    query: str,
    max_results: int = 10,
    settings: Settings | None = None,
) -> list[SearchResult]:
    if settings is None:
        settings = get_settings()

    http_error: ValueError | None = None
    http_results = []

    try:
        http_results = await _search_via_http(query, max_results, settings)
    except ValueError as exc:
        http_error = exc

    if http_results:
        return http_results[:max_results]

    try:
        browser_results = await _search_via_browser(query, max_results, settings)
    except ValueError as exc:
        if http_error is not None:
            raise ValueError(f"{http_error}; browser fallback failed: {exc}") from exc
        return []

    if browser_results:
        return browser_results[:max_results]
    if http_error is not None:
        raise http_error
    return []


async def _search_via_http(
    query: str,
    max_results: int,
    settings: Settings,
) -> list[SearchResult]:
    client = get_http_client("google_html", settings)
    try:
        response = await client.get(
            _SEARCH_URL,
            params={
                "q": query,
                "num": min(max_results, 100),
                "hl": "zh-CN",
            },
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
        )

        if response.status_code != 200:
            raise ValueError(f"Google HTML search error: HTTP {response.status_code}")

        html = response.text
        if _is_blocked_page(html):
            raise ValueError("Google HTML search blocked by anti-bot or consent page")

        return _parse_results(html)
    finally:
        await client.aclose()


async def _search_via_browser(
    query: str,
    max_results: int,
    settings: Settings,
) -> list[SearchResult]:
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise ValueError("Playwright browser fallback is not installed") from exc

    timeout_ms = _resolve_browser_timeout(settings.engine_timeout_seconds)
    try:
        async with async_playwright() as playwright:
            browser = await _launch_browser(playwright, settings)
            try:
                context = await browser.new_context(
                    locale="zh-CN",
                    ignore_https_errors=True,
                    user_agent=_BROWSER_USER_AGENT,
                )
                await context.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = window.chrome || { runtime: {} };
                    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                    """
                )
                page = await context.new_page()
                try:
                    await page.goto(
                        _build_search_url(query, max_results),
                        wait_until="domcontentloaded",
                        timeout=timeout_ms,
                    )
                    try:
                        await page.wait_for_selector("a h3", timeout=max(1000, timeout_ms // 2))
                    except PlaywrightTimeoutError:
                        pass
                    try:
                        await page.wait_for_load_state(
                            "networkidle",
                            timeout=max(1000, timeout_ms // 2),
                        )
                    except PlaywrightTimeoutError:
                        pass

                    html = await page.content()
                    if _is_blocked_page(html):
                        raise ValueError("Google HTML search blocked by anti-bot or consent page")

                    items = await page.evaluate(_BROWSER_EXTRACTION_SCRIPT)
                    results = _build_results_from_browser_items(items)
                    if results:
                        return results[:max_results]
                    return _parse_results(html)[:max_results]
                finally:
                    await context.close()
            finally:
                await browser.close()
    except ValueError:
        raise
    except PlaywrightTimeoutError as exc:
        raise ValueError("Google HTML browser fallback timed out") from exc
    except PlaywrightError as exc:
        message = str(exc).strip() or exc.__class__.__name__
        raise ValueError(f"Google HTML browser fallback error: {message}") from exc


async def _launch_browser(playwright: Any, settings: Settings) -> Any:
    launch_kwargs: dict[str, Any] = {
        "headless": True,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    if "google_html" in settings.proxy_engines:
        launch_kwargs["proxy"] = {"server": settings.proxy_url}

    try:
        return await playwright.chromium.launch(channel="chrome", **launch_kwargs)
    except Exception:
        return await playwright.chromium.launch(**launch_kwargs)


def _is_blocked_page(html: str) -> bool:
    lowered = html.lower()
    return any(marker in lowered for marker in _BLOCK_MARKERS)


def _parse_results(html: str) -> list[SearchResult]:
    matches = list(_ANCHOR_PATTERN.finditer(html))
    results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for index, match in enumerate(matches):
        url = _normalize_google_href(unescape(match.group("href")))
        if not url or url in seen_urls:
            continue

        title = _clean_html_text(match.group("title"))
        if not title:
            continue

        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(html)
        block = html[match.start():next_start]
        seen_urls.add(url)
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=_extract_snippet(block),
                source="google_html",
            )
        )

    return results


def _build_results_from_browser_items(items: object) -> list[SearchResult]:
    if not isinstance(items, list):
        return []

    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue

        url = _normalize_google_href(str(item.get("href") or ""))
        if not url or url in seen_urls:
            continue

        title = _clean_html_text(str(item.get("title") or ""))
        if not title:
            continue

        snippet = _clean_html_text(str(item.get("snippet") or ""))
        seen_urls.add(url)
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source="google_html",
            )
        )
    return results


def _normalize_google_href(raw_href: str) -> str:
    parsed = urlsplit(raw_href)
    if parsed.path == "/url":
        candidates = parse_qs(parsed.query).get("q") or parse_qs(parsed.query).get("url")
        if not candidates:
            return ""
        raw_href = candidates[0]
        parsed = urlsplit(raw_href)

    raw_href = unquote(raw_href)
    parsed = urlsplit(raw_href)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    if parsed.netloc.endswith("google.com") or parsed.netloc.endswith(".google.com"):
        return ""
    return raw_href


def _extract_snippet(block: str) -> str:
    for pattern in _SNIPPET_PATTERNS:
        match = pattern.search(block)
        if match:
            snippet = _clean_html_text(match.group(1))
            if snippet:
                return snippet
    return ""


def _clean_html_text(value: str) -> str:
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\\1>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _build_search_url(query: str, max_results: int) -> str:
    return (
        f"{_SEARCH_URL}?q={quote_plus(query)}&num={min(max_results, 100)}&hl=zh-CN"
    )


def _resolve_browser_timeout(timeout_seconds: float) -> int:
    if timeout_seconds <= 0:
        return 30000
    return max(1000, int(timeout_seconds * 1000))