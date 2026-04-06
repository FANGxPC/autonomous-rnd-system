"""
Research tools:
- search_web_snippets: metasearch via `ddgs` (no API key; replaces deprecated duckduckgo-search).
- search_arxiv: arXiv Atom API (optional fallback). https://info.arxiv.org/help/api/index.html
"""

from __future__ import annotations

import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover
    DDGS = None  # type: ignore[misc, assignment]

_ATOM = "{http://www.w3.org/2005/Atom}"


def _run_ddgs_text(
    q: str,
    n: int,
    *,
    backend: str,
) -> list[dict[str, str]]:
    if DDGS is None:
        return []
    try:
        timeout = int(os.getenv("WEB_SEARCH_TIMEOUT", "30").strip() or "30")
    except ValueError:
        timeout = 30
    timeout = max(5, min(timeout, 120))
    gen = DDGS(timeout=timeout).text(q, max_results=n, backend=backend)
    return list(gen) if gen is not None else []


def search_web_snippets(query: str, max_results: int | None = None) -> str:
    """
    Web metasearch via the `ddgs` library (no API key). Returns titles, URLs, and snippets.

    Args:
        query: Keywords or short phrase (not an essay).
        max_results: Default from env WEB_SEARCH_MAX_RESULTS or 8.

    Returns:
        Formatted bullet list for the agent, or an error string.
    """
    q = (query or "").strip()
    if not q:
        return "❌ Web search: empty query."

    if DDGS is None:
        return "❌ Web search: install `ddgs` with: pip install ddgs"

    n = max_results
    if n is None:
        try:
            n = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "8").strip() or "8")
        except ValueError:
            n = 8
    n = max(1, min(n, 15))

    primary_backend = (os.getenv("WEB_SEARCH_BACKEND", "auto").strip() or "auto")
    if primary_backend != "auto":
        attempts = [primary_backend, "bing", "duckduckgo", "auto"]
    else:
        attempts = ["auto", "bing", "duckduckgo"]

    hits: list[dict[str, str]] = []
    err: str | None = None
    seen_backends: set[str] = set()
    for be in attempts:
        if be in seen_backends:
            continue
        seen_backends.add(be)
        try:
            hits = _run_ddgs_text(q, n, backend=be)
        except Exception as e:
            err = str(e)
            hits = []
        if hits:
            break

    if not hits and err:
        return f"❌ Web search failed: {err}"
    if not hits:
        short = " ".join(q.split()[:6])
        if short != q:
            try:
                hits = _run_ddgs_text(short, n, backend="bing")
            except Exception:
                pass
    if not hits:
        return (
            f"No web results for query: {q!r}. "
            "Try shorter keywords or set WEB_SEARCH_BACKEND=bing in .env."
        )

    lines: list[str] = [f"🌐 Web results ({len(hits)}) for: {q}\n"]
    for i, h in enumerate(hits, 1):
        title = (h.get("title") or "Untitled").strip()
        href = (h.get("href") or h.get("url") or "").strip()
        body = (h.get("body") or h.get("snippet") or "").strip()
        if len(body) > 400:
            body = body[:397] + "…"
        lines.append(f"{i}. **{title}**")
        if href:
            lines.append(f"   URL: {href}")
        if body:
            lines.append(f'   Snippet: "{body}"')
        lines.append("")

    return "\n".join(lines).strip()


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return " ".join(el.text.split())


def search_arxiv(query: str, max_results: int | None = None) -> str:
    """
    Search arXiv for papers matching the query. Returns titles, authors snippet, and abs links.

    Args:
        query: Topic or keywords, e.g. 'RISC-V processor design'
        max_results: Override default (from env ARXIV_MAX_RESULTS or 5).

    Returns:
        Formatted summary string for the agent (or an error message).
    """
    q = (query or "").strip()
    if not q:
        return "❌ arXiv search: empty query."

    n = max_results
    if n is None:
        try:
            n = int(os.getenv("ARXIV_MAX_RESULTS", "5").strip() or "5")
        except ValueError:
            n = 5
    n = max(1, min(n, 15))

    safe = re.sub(r"[^\w\s\-+.]", " ", q)[:200].strip()
    encoded = urllib.parse.quote(safe)
    url = (
        f"http://export.arxiv.org/api/query?"
        f"search_query=all:{encoded}&start=0&max_results={n}"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "autonomous-rnd-system/1.0 (research; +mailto:local)"},
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        return f"❌ arXiv HTTP error: {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return f"❌ arXiv network error: {e.reason}"
    except TimeoutError:
        return "❌ arXiv request timed out."

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return f"❌ arXiv response parse error: {e}"

    entries = root.findall(f"{_ATOM}entry")
    if not entries:
        return f"No arXiv papers found for query: {q!r}"

    lines: list[str] = [f"📚 arXiv results ({len(entries)} papers) for: {q}\n"]
    for i, ent in enumerate(entries, 1):
        title = _text(ent.find(f"{_ATOM}title"))
        aid = _text(ent.find(f"{_ATOM}id"))
        published = _text(ent.find(f"{_ATOM}published"))[:10]
        authors: list[str] = []
        for a in ent.findall(f"{_ATOM}author"):
            name_el = a.find(f"{_ATOM}name")
            if name_el is not None and name_el.text:
                authors.append(name_el.text.strip())
        auth_s = ", ".join(authors[:4])
        if len(authors) > 4:
            auth_s += ", et al."
        summary_el = ent.find(f"{_ATOM}summary")
        blurb = _text(summary_el)[:240] + ("…" if summary_el is not None and len(_text(summary_el)) > 240 else "")

        lines.append(f"{i}. **{title}**")
        if published:
            lines.append(f"   Published: {published}")
        if auth_s:
            lines.append(f"   Authors: {auth_s}")
        if aid:
            lines.append(f"   URL: {aid}")
        if blurb:
            lines.append(f"   Abstract: {blurb}")
        lines.append("")

    return "\n".join(lines).strip()
