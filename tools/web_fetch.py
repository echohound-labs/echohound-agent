"""
Tool: web_fetch
===============
Fetch and extract readable content from a URL.
Strips HTML down to clean markdown/text.
"""

import requests
from urllib.parse import urlparse
from typing import Optional


def web_fetch(url: str, max_chars: int = 8000) -> dict:
    """
    Fetch a URL and return clean readable text.

    Args:
        url:       Full HTTP/HTTPS URL
        max_chars: Maximum characters to return (truncates beyond this)

    Returns:
        dict with 'text', 'url', 'title', 'status'
    """
    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://"}

    headers = {
        "User-Agent": "EchoHound/1.0 (AI Agent; +https://github.com/echohound)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        r.raise_for_status()

        content_type = r.headers.get("content-type", "")
        if "json" in content_type:
            text = r.text[:max_chars]
            return {"url": r.url, "text": text, "status": r.status_code, "type": "json"}

        # Parse HTML → readable text
        text = _extract_text(r.text)
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[truncated at {max_chars} chars]"

        return {
            "url": r.url,
            "text": text,
            "status": r.status_code,
            "type": "html",
        }

    except requests.exceptions.Timeout:
        return {"error": "Request timed out", "url": url}
    except requests.exceptions.ConnectionError:
        return {"error": "Connection failed", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}


def _extract_text(html: str) -> str:
    """Minimal HTML → text extraction without external deps."""
    import re

    # Remove scripts, styles, nav, footer
    for tag in ["script", "style", "nav", "footer", "header", "aside"]:
        html = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Convert common block elements to newlines
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", html, flags=re.IGNORECASE)

    # Strip remaining tags
    html = re.sub(r"<[^>]+>", "", html)

    # Decode common HTML entities
    entities = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
                 "&#39;": "'", "&nbsp;": " "}
    for ent, char in entities.items():
        html = html.replace(ent, char)

    # Collapse whitespace
    lines = [line.strip() for line in html.splitlines()]
    lines = [l for l in lines if l]
    return "\n".join(lines)
