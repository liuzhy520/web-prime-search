from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlsplit

from web_prime_search.config import Settings, get_settings
from web_prime_search.engines._cli import run_engine_cli
from web_prime_search.models import SearchResult
from web_prime_search.proxy import get_http_client

logger = logging.getLogger(__name__)

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
    "enable javascript to continue",
    "sorry/index",
    "/sorry/",
)
_STEALTH_INIT_SCRIPT = """
() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
    Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
    Object.defineProperty(navigator, 'vendor', { get: () => 'Google Inc.' });
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin' },
            { name: 'Chrome PDF Viewer' },
            { name: 'Native Client' },
        ],
    });
    window.chrome = window.chrome || { runtime: {} };

    const permissions = window.navigator.permissions;
    if (permissions && permissions.query) {
        const originalQuery = permissions.query.bind(permissions);
        permissions.query = (parameters) => {
            if (parameters && parameters.name === 'notifications') {
                return Promise.resolve({ state: Notification.permission });
            }
            return originalQuery(parameters);
        };
    }
}
"""
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

        if response.status_code == 429:
            raise ValueError("Google HTML search rate limited: HTTP 429")
        if response.status_code != 200:
            raise ValueError(f"Google HTML search error: HTTP {response.status_code}")

        html = response.text
        if _is_blocked_page(html):
            _log_blocked_page("http", html)
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

    attempts = settings.google_html_browser_attempts
    retry_delay = settings.google_html_browser_retry_delay
    last_exc: Exception | None = None
    for attempt in range(attempts):
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
            last_exc = ValueError("Google HTML browser fallback timed out")
        except PlaywrightTimeoutError as exc:
            last_exc = ValueError("Google HTML browser fallback timed out")
        except PlaywrightError as exc:
            message = str(exc).strip() or exc.__class__.__name__
            last_exc = ValueError(f"Google HTML browser fallback error: {message}")
        if attempt < attempts - 1:
            await asyncio.sleep(retry_delay)
    raise last_exc or ValueError("Google HTML browser fallback failed")


async def _run_browser_search(
    query: str,
    max_results: int,
    settings: Settings,
    async_playwright: Any,
    playwright_timeout_error: type[Exception],
) -> list[SearchResult]:
    timeout_ms = _resolve_browser_timeout(settings.engine_timeout_seconds)
    navigation_timeout_ms = _resolve_browser_navigation_timeout(timeout_ms)
    render_wait_ms = _resolve_browser_render_wait(timeout_ms)
    async with async_playwright() as playwright:
        context, browser = await _open_browser_context(playwright, settings)
        try:
            await _apply_stealth(context, settings)
            await _load_cookies(context, settings)
            existing_pages = getattr(context, "pages", None)
            if isinstance(existing_pages, list) and existing_pages:
                page = existing_pages[0]
            else:
                page = await context.new_page()

            try:
                await page.goto(
                    _build_search_url(query, max_results),
                    wait_until="domcontentloaded",
                    timeout=navigation_timeout_ms,
                )

                html = await page.content()
                if _is_blocked_page(html):
                    _log_blocked_page("browser", html)
                    raise ValueError("Google HTML search blocked by anti-bot or consent page")

                items = await page.evaluate(_BROWSER_EXTRACTION_SCRIPT)
                results = _build_results_from_browser_items(items)
                if results:
                    return results[:max_results]

                try:
                    await page.wait_for_timeout(render_wait_ms)
                except playwright_timeout_error:
                    pass

                html = await page.content()
                if _is_blocked_page(html):
                    _log_blocked_page("browser", html)
                    raise ValueError("Google HTML search blocked by anti-bot or consent page")

                items = await page.evaluate(_BROWSER_EXTRACTION_SCRIPT)
                results = _build_results_from_browser_items(items)
                if results:
                    return results[:max_results]
                return _parse_results(html)[:max_results]
            finally:
                await _save_cookies(context, settings)
                await context.close()
        finally:
            if browser is not None:
                await browser.close()


async def _open_browser_context(playwright: Any, settings: Settings) -> tuple[Any, Any | None]:
    if _should_use_persistent_profile(settings):
        profile_dir = _resolve_profile_dir(settings)
        try:
            profile_dir.mkdir(parents=True, exist_ok=True)
            context = await _launch_persistent_context(playwright, settings, profile_dir)
            return context, None
        except Exception as exc:
            logger.warning(
                "Google HTML persistent profile unavailable at %s: %s; falling back to ephemeral browser context",
                profile_dir,
                _format_exception(exc),
            )

    browser = await _launch_browser(playwright, settings)
    context = await browser.new_context(**_build_context_kwargs(settings))
    return context, browser


async def _launch_browser(playwright: Any, settings: Settings) -> Any:
    launch_kwargs = _build_launch_kwargs(settings)

    try:
        return await playwright.chromium.launch(channel="chrome", **launch_kwargs)
    except Exception:
        return await playwright.chromium.launch(**launch_kwargs)


async def _launch_persistent_context(
    playwright: Any,
    settings: Settings,
    profile_dir: Path,
) -> Any:
    launch_kwargs = _build_launch_kwargs(settings)
    context_kwargs = _build_context_kwargs(settings)

    try:
        return await playwright.chromium.launch_persistent_context(
            str(profile_dir),
            channel="chrome",
            **launch_kwargs,
            **context_kwargs,
        )
    except Exception:
        return await playwright.chromium.launch_persistent_context(
            str(profile_dir),
            **launch_kwargs,
            **context_kwargs,
        )


async def _apply_stealth(context: Any, settings: Settings) -> None:
    if not settings.google_html_stealth:
        return

    try:
        await context.add_init_script(_STEALTH_INIT_SCRIPT)
    except Exception as exc:
        logger.warning(
            "Google HTML stealth init script failed: %s",
            _format_exception(exc),
        )


async def _load_cookies(context: Any, settings: Settings) -> None:
    cookie_file = _resolve_cookie_file(settings)
    if cookie_file is None:
        return

    try:
        payload = json.loads(cookie_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Google HTML cookie preload skipped for %s: %s",
            cookie_file,
            _format_exception(exc),
        )
        return

    cookies = _normalize_cookie_payload(payload)
    if not cookies:
        return

    try:
        await context.add_cookies(cookies)
    except Exception as exc:
        logger.warning(
            "Google HTML cookie preload failed for %s: %s",
            cookie_file,
            _format_exception(exc),
        )


async def _save_cookies(context: Any, settings: Settings) -> None:
    cookie_file = _resolve_cookie_file(settings)
    if cookie_file is None:
        return

    try:
        cookies = await context.cookies()
        normalized = _normalize_cookie_payload(cookies)
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        cookie_file.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning(
            "Google HTML cookie persistence failed for %s: %s",
            cookie_file,
            _format_exception(exc),
        )


def _build_launch_kwargs(settings: Settings) -> dict[str, Any]:
    args = ["--disable-blink-features=AutomationControlled"]
    if settings.google_html_stealth:
        args.extend(
            [
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-dev-shm-usage",
                "--no-default-browser-check",
            ]
        )

    launch_kwargs: dict[str, Any] = {
        "headless": True,
        "args": args,
    }
    if "google_html" in settings.proxy_engines:
        launch_kwargs["proxy"] = {"server": settings.proxy_url}
    return launch_kwargs


def _build_context_kwargs(settings: Settings) -> dict[str, Any]:
    headers = {
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "DNT": "1",
    }
    if settings.google_html_stealth:
        headers["Upgrade-Insecure-Requests"] = "1"

    return {
        "locale": "zh-CN",
        "ignore_https_errors": True,
        "user_agent": _BROWSER_USER_AGENT,
        "timezone_id": "Asia/Shanghai",
        "viewport": {"width": 1366, "height": 900},
        "screen": {"width": 1366, "height": 900},
        "color_scheme": "light",
        "extra_http_headers": headers,
    }


def _should_use_persistent_profile(settings: Settings) -> bool:
    return settings.google_html_persist_profile or bool(settings.google_html_profile_dir.strip())


def _resolve_profile_dir(settings: Settings) -> Path:
    configured = settings.google_html_profile_dir.strip()
    if configured:
        return Path(configured).expanduser()
    return _default_profile_dir()


def _resolve_cookie_file(settings: Settings) -> Path | None:
    configured = settings.google_html_cookie_file.strip()
    if not configured:
        return None
    return Path(configured).expanduser()


def _default_profile_dir() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Caches"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))
    return base / "web-prime-search" / "google-html-profile"


def _normalize_cookie_payload(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []

    now = time.time()
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "")
        domain = str(item.get("domain") or "").strip().lower()
        path = str(item.get("path") or "/") or "/"
        if not name or not value or not _is_google_cookie_domain(domain):
            continue

        expires = _normalize_cookie_expiry(item.get("expires"))
        if expires is not None and expires > 0 and expires < now:
            continue

        key = (name, domain, path)
        if key in seen:
            continue
        seen.add(key)

        cookie: dict[str, Any] = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
            "httpOnly": bool(item.get("httpOnly", False)),
            "secure": bool(item.get("secure", True)),
        }
        if expires is not None:
            cookie["expires"] = expires

        same_site = _normalize_same_site(item.get("sameSite"))
        if same_site is not None:
            cookie["sameSite"] = same_site

        normalized.append(cookie)

    return normalized


def _normalize_cookie_expiry(value: object) -> float | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _normalize_same_site(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().capitalize()
    if normalized in {"Lax", "None", "Strict"}:
        return normalized
    return None


def _is_google_cookie_domain(domain: str) -> bool:
    normalized = domain.lstrip(".")
    return normalized == "google.com" or normalized.endswith(".google.com")


def _blocked_marker(html: str) -> str | None:
    lowered = html.lower()
    for marker in _BLOCK_MARKERS:
        if marker in lowered:
            return marker
    return None


def _log_blocked_page(mode: str, html: str) -> None:
    marker = _blocked_marker(html)
    if marker is None:
        return
    logger.warning("Google HTML %s path hit blocked page marker: %s", mode, marker)


def _format_exception(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


def _is_blocked_page(html: str) -> bool:
    return _blocked_marker(html) is not None


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
    return int(_resolve_browser_timeout_budget(timeout_seconds) * 1000)


def _resolve_browser_timeout_budget(timeout_seconds: float) -> float:
    if timeout_seconds <= 0:
        return 30.0
    return max(5.0, timeout_seconds - 2.0)


def _resolve_browser_step_timeout(timeout_ms: int) -> int:
    return max(1000, timeout_ms // 3)


def _resolve_browser_navigation_timeout(timeout_ms: int) -> int:
    return min(timeout_ms, max(3000, timeout_ms // 2))


def _resolve_browser_render_wait(timeout_ms: int) -> int:
    return min(1500, max(500, timeout_ms // 10))


def main(argv: list[str] | None = None) -> int:
    return run_engine_cli("google_html", search, argv)


if __name__ == "__main__":
    raise SystemExit(main())