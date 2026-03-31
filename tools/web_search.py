"""
Tool: web_search
================
Search the web using Brave Search API.
Falls back to a DuckDuckGo scrape if no API key is set.
"""

import os
import requests
from typing import Optional

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def web_search(query: str, count: int = 5, country: str = "US") -> dict:
    """
    Search the web. Returns list of {title, url, snippet} dicts.
    
    Args:
        query:   Search string
        count:   Number of results (1-10)
        country: 2-letter country code for regional results
    """
    if not BRAVE_API_KEY:
        return _ddg_fallback(query, count)

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {
        "q": query,
        "count": min(count, 10),
        "country": country,
    }

    try:
        r = requests.get(BRAVE_ENDPOINT, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            })
        return {"results": results, "source": "brave"}
    except Exception as e:
        return {"error": str(e), "results": []}


def _ddg_fallback(query: str, count: int) -> dict:
    """Simple DuckDuckGo instant answers fallback (no API key needed)."""
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1},
            timeout=10,
        )
        data = r.json()
        results = []
        for topic in data.get("RelatedTopics", [])[:count]:
            if "Text" in topic:
                results.append({
                    "title": topic.get("Text", "")[:80],
                    "url": topic.get("FirstURL", ""),
                    "snippet": topic.get("Text", ""),
                })
        return {"results": results, "source": "duckduckgo_fallback"}
    except Exception as e:
        return {"error": str(e), "results": []}
