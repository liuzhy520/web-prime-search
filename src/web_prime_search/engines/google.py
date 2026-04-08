from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import quote

from web_prime_search.config import Settings, get_settings
from web_prime_search.engines._cli import run_engine_cli
from web_prime_search.engines.google_html import (
    _apply_stealth,
    _format_exception,
    _is_blocked_page,
    _load_cookies,
    _open_browser_context,
    _resolve_browser_navigation_timeout,
    _resolve_browser_render_wait,
    _resolve_browser_timeout,
    _resolve_browser_timeout_budget,
    _save_cookies,
)
from web_prime_search.models import SearchResult
from web_prime_search.proxy import get_http_client

_CSE_ENGINE_NAME = "google"
_CSE_HOSTED_URL = "https://cse.google.com/cse"

# AJAX (no-browser) path constants
_CSE_JS_URL = "https://cse.google.com/cse.js"
_CSE_ELEMENT_URL = "https://www.googleapis.com/customsearch/v1element"
_CSE_TOK_RE = re.compile(r'"cse_tok"\s*:\s*"([^"]+)"')
_FRONTEND_KEY_RE = re.compile(r'"key"\s*:\s*"(AIza[A-Za-z0-9_\-]{30,45})"')

_RESULTS_READY_SCRIPT = """
() => Boolean(
    document.querySelector('.gsc-webResult .gs-title, .gsc-result .gs-title') ||
    document.querySelector('.gs-no-results-result') ||
    document.querySelector('.gsc-result-info')
)
"""

_DOM_EXTRACTION_SCRIPT = """
() => {
    const selectors = ['.gsc-webResult', '.gsc-result'];
    const cards = selectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)));
    const seen = new Set();

    return cards.map((card) => {
        const link = card.querySelector('a.gs-title, .gs-title a, a.gs-title');
        if (!link) {
            return null;
        }

        const href = link.href || link.getAttribute('href') || '';
        if (!href || seen.has(href)) {
            return null;
        }
        seen.add(href);

        const snippetNode = card.querySelector('.gs-snippet, .gs-bidi-start-align.gs-snippet');
        return {
            href,
            title: link.textContent || '',
            snippet: snippetNode ? (snippetNode.innerText || snippetNode.textContent || '') : '',
        };
    }).filter(Boolean);
}
"""


def _extract_cse_tok(js_text: str) -> str:
    """Extract the cse_tok value from a cse.js response."""
    m = _CSE_TOK_RE.search(js_text)
    return m.group(1) if m else ""


def _extract_frontend_key(js_text: str) -> str:
    """Extract the embedded frontend API key (AIza...) from a cse.js response."""
    m = _FRONTEND_KEY_RE.search(js_text)
    return m.group(1) if m else ""


def _parse_jsonp(text: str) -> dict:
    """Strip a JSONP wrapper and parse the inner JSON object."""
    text = text.strip()
    start = text.find("(")
    if start == -1:
        return {}
    end = text.rfind(")")
    if end <= start:
        return {}
    try:
        return json.loads(text[start + 1 : end])
    except (json.JSONDecodeError, ValueError):
        return {}


def _build_search_url(cx: str, query: str) -> str:
        encoded_query = quote(query, safe="")
        return f"{_CSE_HOSTED_URL}?cx={cx}#gsc.tab=0&gsc.q={encoded_query}&gsc.sort="


def _build_browser_settings(settings: Settings) -> Settings:
    proxy_engines: list[str] = []
    for engine in settings.proxy_engines:
        candidate = "google_html" if engine == "google" else engine
        if candidate not in proxy_engines:
            proxy_engines.append(candidate)

    return settings.model_copy(update={"proxy_engines": proxy_engines})


def _normalize_result_url(raw_url: object) -> str:
    if not isinstance(raw_url, str):
        return ""

    value = raw_url.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return ""


def _clean_result_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _build_results_from_dom_items(items: object) -> list[SearchResult]:
    return _build_results_from_items(items, url_key="href")


def _build_results_from_items(items: object, url_key: str) -> list[SearchResult]:
    if not isinstance(items, list):
        return []

    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue

        url = _normalize_result_url(item.get(url_key))
        if not url or url in seen_urls:
            continue

        title = _clean_result_text(item.get("title") or item.get("titleNoFormatting"))
        if not title:
            continue

        snippet = _clean_result_text(
            item.get("contentNoFormatting")
            or item.get("content")
            or item.get("snippet")
        )
        seen_urls.add(url)
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                source=_CSE_ENGINE_NAME,
            )
        )

    return results


async def search(
    query: str,
    max_results: int = 10,
    settings: Settings | None = None,
) -> list[SearchResult]:
    if settings is None:
        settings = get_settings()

    if not settings.google_cx:
        raise ValueError("Google CX is not configured")

    # Fast path: CSE AJAX via httpx (no browser overhead, no anti-bot risk)
    try:
        return await _search_via_ajax(query, max_results, settings)
    except Exception:
        pass

    # Fallback: Playwright browser (slower, but works when AJAX is blocked)
    return await _search_via_browser(query, max_results, settings)


async def _search_via_ajax(
    query: str,
    max_results: int,
    settings: Settings,
) -> list[SearchResult]:
    """Fetch CSE results via the undocumented v1element JSONP endpoint.

    The CSE widget embeds a frontend API key and a per-session ``cse_tok``
    inside ``cse.js``.  We extract both with a lightweight httpx request and
    use them to call the same endpoint the widget would call, receiving JSONP
    with standard result objects.

    Raises ``ValueError`` on any failure so the caller can fall back to the
    Playwright browser path.
    """
    client = get_http_client("google", settings)
    try:
        js_resp = await client.get(
            _CSE_JS_URL,
            params={"cx": settings.google_cx, "hl": "en"},
        )
        if js_resp.status_code != 200:
            raise ValueError(
                f"Google CSE JS fetch failed: HTTP {js_resp.status_code}"
            )

        cse_tok = _extract_cse_tok(js_resp.text)
        frontend_key = _extract_frontend_key(js_resp.text)

        if not cse_tok or not frontend_key:
            raise ValueError(
                "Google CSE: could not extract cse_tok or key from cse.js"
            )

        results_resp = await client.get(
            _CSE_ELEMENT_URL,
            params={
                "key": frontend_key,
                "cx": settings.google_cx,
                "q": query,
                "num": min(max_results, 10),
                "hl": "en",
                "cse_tok": cse_tok,
                "rsz": "filtered_cse",
                "source": "gcsc",
                "gfns": "0",
                "callback": "google.search.cse.api0",
            },
        )
        if results_resp.status_code != 200:
            raise ValueError(
                f"Google CSE element API failed: HTTP {results_resp.status_code}"
            )

        data = _parse_jsonp(results_resp.text)
        raw_results = data.get("results") or []

        if not isinstance(raw_results, list):
            raise ValueError("Google CSE AJAX: unexpected response shape")

        # Empty results with no cursor metadata = blocked/malformed response
        if not raw_results and not data.get("cursor"):
            raise ValueError("Google CSE AJAX: empty response with no cursor")

        return _build_results_from_items(raw_results, url_key="unescapedUrl")[
            :max_results
        ]
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
        raise ValueError("Playwright browser support is not installed") from exc

    try:
        return await asyncio.wait_for(
            _run_browser_search(
                query=query,
                max_results=max_results,
                settings=settings,
                async_playwright=async_playwright,
                playwright_timeout_error=PlaywrightTimeoutError,
            ),
            timeout=_resolve_browser_timeout_budget(settings.engine_timeout_seconds),
        )
    except ValueError:
        raise
    except asyncio.TimeoutError as exc:
        raise ValueError("Google CSE search timed out") from exc
    except PlaywrightTimeoutError as exc:
        raise ValueError("Google CSE search timed out") from exc
    except PlaywrightError as exc:
        raise ValueError(
            f"Google CSE search error: {_format_exception(exc)}"
        ) from exc


async def _run_browser_search(
    query: str,
    max_results: int,
    settings: Settings,
    async_playwright: Any,
    playwright_timeout_error: type[Exception],
) -> list[SearchResult]:
    browser_settings = _build_browser_settings(settings)
    timeout_ms = _resolve_browser_timeout(settings.engine_timeout_seconds)
    navigation_timeout_ms = _resolve_browser_navigation_timeout(timeout_ms)
    render_wait_ms = _resolve_browser_render_wait(timeout_ms)

    async with async_playwright() as playwright:
        context, browser = await _open_browser_context(playwright, browser_settings)
        try:
            await _apply_stealth(context, browser_settings)
            await _load_cookies(context, browser_settings)

            existing_pages = getattr(context, "pages", None)
            if isinstance(existing_pages, list) and existing_pages:
                page = existing_pages[0]
            else:
                page = await context.new_page()

            try:
                await page.goto(
                    _build_search_url(settings.google_cx, query),
                    wait_until="domcontentloaded",
                    timeout=navigation_timeout_ms,
                )

                try:
                    await page.wait_for_function(
                        _RESULTS_READY_SCRIPT,
                        timeout=navigation_timeout_ms,
                    )
                except playwright_timeout_error:
                    await _submit_search(page, query, navigation_timeout_ms, playwright_timeout_error)
                    try:
                        await page.wait_for_function(
                            _RESULTS_READY_SCRIPT,
                            timeout=navigation_timeout_ms,
                        )
                    except playwright_timeout_error:
                        pass

                try:
                    await page.wait_for_timeout(render_wait_ms)
                except playwright_timeout_error:
                    pass

                html = await page.content()
                if _is_blocked_page(html):
                    raise ValueError("Google CSE search blocked by anti-bot or consent page")

                items = await page.evaluate(_DOM_EXTRACTION_SCRIPT)
                return _build_results_from_dom_items(items)[:max_results]
            finally:
                await _save_cookies(context, browser_settings)
                await context.close()
        finally:
            if browser is not None:
                await browser.close()


async def _submit_search(
    page: Any,
    query: str,
    timeout_ms: int,
    playwright_timeout_error: type[Exception],
) -> None:
    try:
        await page.wait_for_selector("input.gsc-input[name='search']", timeout=timeout_ms)
        await page.fill("input.gsc-input[name='search']", query)
        await page.click("button.gsc-search-button, .gsc-search-button-v2", timeout=timeout_ms)
    except playwright_timeout_error:
        return


def main(argv: list[str] | None = None) -> int:
    return run_engine_cli("google", search, argv)


if __name__ == "__main__":
    raise SystemExit(main())
