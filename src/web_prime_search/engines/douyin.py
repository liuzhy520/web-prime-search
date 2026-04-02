from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

import httpx

from web_prime_search.config import Settings, get_settings
from web_prime_search.models import SearchResult
from web_prime_search.proxy import get_http_client


async def search(
    query: str,
    max_results: int = 10,
    settings: Settings | None = None,
) -> list[SearchResult]:
    if settings is None:
        settings = get_settings()

    if not settings.volcengine_api_key:
        raise ValueError("Volcengine API key is not configured")
    if not settings.volcengine_web_search_model:
        raise ValueError("Volcengine web search model is not configured")

    client = get_http_client("douyin", settings)
    try:
        try:
            response = await client.post(
                settings.volcengine_responses_url,
                headers={
                    "Authorization": f"Bearer {settings.volcengine_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.volcengine_web_search_model,
                    "stream": False,
                    "tools": [{"type": "web_search"}],
                    "input": query,
                },
            )
        except httpx.TimeoutException as exc:
            raise ValueError("Volcengine API request timed out") from exc

        if response.status_code != 200:
            raise ValueError(
                f"Douyin search error: {_extract_error_message(response)}"
            )

        payload = response.json()
        response_summary = _extract_output_summary(payload)
        results = _parse_reference_results(payload.get("references"))
        if not results:
            results = _parse_output_annotation_results(payload)
        if not results:
            results = _parse_action_detail_results(payload)

        if response_summary:
            for result in results:
                result.summary = response_summary

        return results[:max_results]
    finally:
        await client.aclose()


def _extract_error_message(response: Any) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"

    message = None
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        message = error.get("message") or error.get("type")
    elif isinstance(error, str):
        message = error

    if message is None and isinstance(payload, dict):
        raw_message = payload.get("message")
        if isinstance(raw_message, str) and raw_message:
            message = raw_message

    if message:
        return f"HTTP {response.status_code}: {message}"
    return f"HTTP {response.status_code}"


def _parse_reference_results(references: object) -> list[SearchResult]:
    if not isinstance(references, list):
        return []
    return _build_search_results(references)


def _parse_output_annotation_results(payload: object) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []

    output = payload.get("output")
    if not isinstance(output, list):
        return []

    collected: list[object] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            annotations = content_item.get("annotations")
            if isinstance(annotations, list):
                collected.extend(annotations)

    if not collected:
        return []
    return _build_search_results(collected)


def _extract_output_summary(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    output = payload.get("output")
    if not isinstance(output, list):
        return None

    snippets: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str) and text.strip():
                snippets.append(text.strip())

    if not snippets:
        return None

    return _shorten_text("\n\n".join(snippets), limit=480)


def _parse_action_detail_results(payload: object) -> list[SearchResult]:
    if not isinstance(payload, dict):
        return []

    detail_collections: list[object] = []
    if isinstance(payload.get("action_details"), list):
        detail_collections.append(payload["action_details"])

    for usage_key in ("bot_usage", "usage"):
        usage = payload.get(usage_key)
        if isinstance(usage, dict) and isinstance(usage.get("action_details"), list):
            detail_collections.append(usage["action_details"])

    for details in detail_collections:
        if not isinstance(details, list):
            continue
        for detail in details:
            if not isinstance(detail, dict):
                continue
            tool_details = detail.get("tool_details")
            if not isinstance(tool_details, list):
                continue
            for tool_detail in tool_details:
                if not isinstance(tool_detail, dict):
                    continue
                items = _extract_results_from_output(tool_detail.get("output"))
                if items:
                    return _build_search_results(items)

    return []


def _extract_results_from_output(output: object) -> list[object]:
    candidates = [output]
    while candidates:
        current = candidates.pop(0)
        if isinstance(current, dict):
            results = current.get("results")
            if isinstance(results, list):
                return results
            candidates.extend(current.values())
        elif isinstance(current, list):
            candidates.extend(current)
    return []


def _build_search_results(items: list[object]) -> list[SearchResult]:
    results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        raw_url = item.get("url")
        if not isinstance(raw_url, str) or not raw_url:
            continue
        if raw_url in seen_urls:
            continue
        seen_urls.add(raw_url)

        raw_title = item.get("title") or item.get("site_name")
        title = raw_title if isinstance(raw_title, str) and raw_title else raw_url

        snippet = ""
        for key in ("summary", "snippet", "content", "text"):
            value = item.get(key)
            if isinstance(value, str) and value:
                snippet = _shorten_text(value)
                break

        results.append(
            SearchResult(
                title=title,
                url=raw_url,
                snippet=snippet,
                source="douyin",
                timestamp=_normalize_timestamp(
                    item.get("publish_time") or item.get("published_at")
                ),
            )
        )

    return results


def _shorten_text(text: str, *, limit: int = 360) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _normalize_timestamp(value: object) -> str | None:
    if value in (None, "", 0):
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
    return str(value)
