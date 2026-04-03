"""
Web research for autonomous prediction agents.

Searches DuckDuckGo for evidence relevant to prediction questions.
Filters junk domains, verifies URL reachability, caches results.
Extracted from the waveStreamer fleet research pipeline.
"""

import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests

logger = logging.getLogger("wavestreamer_runner.research")

# ---------------------------------------------------------------------------
# Domain filtering
# ---------------------------------------------------------------------------

_HARD_BLOCKED = {
    "pornhub.com", "xvideos.com", "onlyfans.com", "tinder.com", "bumble.com",
    "match.com", "bet365.com", "draftkings.com", "fanduel.com", "bovada.lv",
    "naturalnews.com", "infowars.com", "breitbart.com", "zerohedge.com",
    "thegatewaypundit.com", "writesonic.com", "jasper.ai", "copy.ai",
    "bit.ly", "t.co", "goo.gl", "tinyurl.com", "ow.ly",
}

_JUNK_DOMAINS = {
    "facebook.com", "instagram.com", "tiktok.com", "twitter.com", "x.com",
    "threads.net", "reddit.com", "quora.com", "pinterest.com", "linkedin.com",
    "youtube.com", "stackoverflow.com", "stackexchange.com", "medium.com",
    "wikihow.com", "ehow.com", "amazon.com", "ebay.com", "walmart.com",
    "etsy.com", "shopify.com", "buzzfeed.com", "dailymail.co.uk",
    "thesun.co.uk", "nypost.com", "baidu.com", "sogou.com",
    "softonic.com", "filehippo.com", "sourceforge.net",
}

_STOP_WORDS = {
    "the", "a", "an", "of", "in", "for", "to", "and", "or", "by", "at",
    "on", "is", "it", "be", "as", "was", "that", "this", "with", "from",
    "are", "were", "been", "has", "have", "had", "not", "but", "its",
    "than", "their", "they", "which", "would", "about", "into", "more",
    "other", "some", "such", "any", "only", "could", "will", "does",
    "should", "before", "after", "who", "what", "when", "where", "how",
    "why", "may", "can", "do", "did",
}


def _is_blocked(url: str) -> bool:
    """Check if URL domain is hard-blocked or junk."""
    try:
        host = urlparse(url).hostname or ""
        if host.startswith("www."):
            host = host[4:]
        for blocked in _HARD_BLOCKED:
            if host == blocked or host.endswith("." + blocked):
                return True
        for junk in _JUNK_DOMAINS:
            if host == junk or host.endswith("." + junk):
                return True
    except Exception:
        return True
    return False


def _is_bare_domain(url: str) -> bool:
    """Return True if URL is a homepage with no meaningful path."""
    try:
        path = (urlparse(url).path or "").rstrip("/")
        return path == ""
    except Exception:
        return False


# ---------------------------------------------------------------------------
# DuckDuckGo search
# ---------------------------------------------------------------------------

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})


def _search_ddg(query: str, max_results: int = 8) -> list[dict]:
    """Search DuckDuckGo HTML and parse results."""
    url = "https://html.duckduckgo.com/html/?q=" + requests.utils.quote(query)
    try:
        resp = _SESSION.get(url, timeout=15)
        if resp.status_code != 200:
            return []
        return _parse_ddg_html(resp.text, max_results)
    except Exception as e:
        logger.debug("DDG search failed: %s", e)
        return []


def _parse_ddg_html(html: str, max_results: int) -> list[dict]:
    """Extract search results from DuckDuckGo HTML response."""
    results = []
    parts = html.split("result__a")
    for part in parts[1:]:
        if len(results) >= max_results:
            break

        # Extract URL
        href_idx = part.find('href="')
        if href_idx == -1:
            continue
        url_start = href_idx + 6
        url_end = part.find('"', url_start)
        if url_end == -1:
            continue
        raw_url = part[url_start:url_end]
        actual_url = _extract_ddg_url(raw_url)
        if not actual_url or not actual_url.startswith("http"):
            continue

        # Extract title
        title_start = part.find(">")
        title_end = part.find("</a>")
        title = ""
        if title_start != -1 and title_end != -1 and title_start < title_end:
            title = _strip_html(part[title_start + 1:title_end])

        # Extract snippet
        snippet = ""
        snippet_idx = part.find("result__snippet")
        if snippet_idx != -1:
            remaining = part[snippet_idx:]
            snip_start = remaining.find(">")
            if snip_start != -1:
                remaining = remaining[snip_start + 1:]
                snip_end = remaining.find("</")
                if snip_end > 0:
                    snippet = _strip_html(remaining[:snip_end])

        if title or snippet:
            results.append({
                "title": title.strip(),
                "url": actual_url,
                "snippet": snippet.strip()[:350],
            })

    return results


def _extract_ddg_url(raw: str) -> str:
    """Extract actual URL from DuckDuckGo redirect."""
    if "uddg=" in raw:
        parts = raw.split("uddg=")
        if len(parts) > 1:
            decoded = parts[1]
            amp = decoded.find("&")
            if amp != -1:
                decoded = decoded[:amp]
            try:
                return requests.utils.unquote(decoded)
            except Exception:
                pass
    if raw.startswith("//"):
        return "https:" + raw
    return raw


def _strip_html(s: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    clean = re.sub(r"<[^>]+>", "", s)
    return " ".join(clean.split())


# ---------------------------------------------------------------------------
# URL verification
# ---------------------------------------------------------------------------

def _verify_urls(articles: list[dict], timeout: float = 5.0, max_workers: int = 5) -> list[dict]:
    """Check URLs are reachable. Parallel HEAD requests."""
    if not articles:
        return []

    def check(url: str) -> bool:
        try:
            resp = _SESSION.head(url, timeout=timeout, allow_redirects=True)
            return resp.status_code < 400 or resp.status_code in (403, 405)
        except Exception:
            return False

    verified = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(check, a["url"]): a for a in articles}
        for future in as_completed(futures):
            if future.result():
                verified.append(futures[future])

    return verified


# ---------------------------------------------------------------------------
# Relevance filter
# ---------------------------------------------------------------------------

def _extract_topic_terms(question: str) -> set[str]:
    """Extract topic-specific terms from a question (proper nouns, numbers, key words)."""
    terms = set()
    # Proper nouns (capitalized words)
    for w in re.findall(r"\b[A-Z][a-zA-Z]+\b", question):
        if len(w) >= 3 and w.lower() not in _STOP_WORDS:
            terms.add(w.lower())
    # Numbers and percentages
    for w in re.findall(r"\b\d+%?\b", question):
        terms.add(w)
    # Remaining meaningful words
    for w in question.lower().split():
        w = re.sub(r"[^\w]", "", w)
        if len(w) >= 4 and w not in _STOP_WORDS:
            terms.add(w)
    return terms


def _filter_relevant(articles: list[dict], question: str) -> list[dict]:
    """Keep only articles topically relevant to the question."""
    terms = _extract_topic_terms(question)
    if not terms:
        return articles

    relevant = []
    for a in articles:
        text = (a.get("title", "") + " " + a.get("snippet", "")).lower()
        matches = sum(1 for t in terms if t in text)
        if matches >= 2:
            relevant.append(a)

    if not relevant:
        # Relax to 1 match
        for a in articles:
            text = (a.get("title", "") + " " + a.get("snippet", "")).lower()
            if any(t in text for t in terms):
                relevant.append(a)

    return relevant if relevant else articles


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[list[dict], float]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = 1800  # 30 minutes


def _get_cached(query: str) -> list[dict] | None:
    with _cache_lock:
        entry = _cache.get(query)
        if entry and (time.time() - entry[1]) < _CACHE_TTL:
            return entry[0]
    return None


def _set_cached(query: str, articles: list[dict]) -> None:
    with _cache_lock:
        if len(_cache) > 200:
            # Evict oldest 50
            sorted_keys = sorted(_cache, key=lambda k: _cache[k][1])
            for k in sorted_keys[:50]:
                del _cache[k]
        _cache[query] = (articles, time.time())


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

_consecutive_failures = 0
_disabled_until = 0.0
_BREAKER_THRESHOLD = 2
_BACKOFF_SECS = 300.0  # 5 min

_research_enabled = os.getenv("RESEARCH_DISABLED", "").strip() not in ("1", "true", "yes")


def _is_disabled() -> bool:
    if not _research_enabled:
        return True
    if _disabled_until and time.time() < _disabled_until:
        return True
    return False


def _record_failure() -> None:
    global _consecutive_failures, _disabled_until
    _consecutive_failures += 1
    if _consecutive_failures >= _BREAKER_THRESHOLD:
        _disabled_until = time.time() + _BACKOFF_SECS
        logger.warning("Research circuit breaker tripped — disabled for %ds", _BACKOFF_SECS)


def _record_success() -> None:
    global _consecutive_failures, _disabled_until
    _consecutive_failures = 0
    _disabled_until = 0.0


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------

def _build_query(question: str, context: str = "") -> str:
    """Build a search query from the prediction question."""
    q = question
    # Remove question prefixes
    for prefix in ("Will ", "Is ", "Are ", "Has ", "Have ", "Does ", "Do ",
                    "Can ", "Should ", "Could ", "Would ", "Did ", "May ", "Might "):
        q = q.removeprefix(prefix)
    q = q.rstrip("?!")

    # Remove stop words
    words = [w for w in q.split() if w.lower() not in _STOP_WORDS and len(w) >= 2]
    if words:
        q = " ".join(words)

    if len(q) > 120:
        q = q[:120]
    return q


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def research_question(question: str, context: str = "", max_results: int = 8) -> list[dict]:
    """Search the web for evidence relevant to a prediction question.

    Returns list of {"title", "url", "snippet"} dicts, verified and relevant.
    """
    if _is_disabled():
        logger.debug("Research disabled — skipping")
        return []

    query = _build_query(question, context)

    # Check cache
    cached = _get_cached(query)
    if cached is not None:
        return cached

    # Search DuckDuckGo
    articles = _search_ddg(query, max_results)

    # Retry with simpler query if too few results
    if len(articles) < 3:
        alt = question.split("?")[0].strip()[:50]
        if alt and alt != query:
            articles.extend(_search_ddg(alt, max_results))

    # Track circuit breaker
    if not articles:
        _record_failure()
    else:
        _record_success()

    # Deduplicate
    seen = set()
    unique = []
    for a in articles:
        url = a.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        if _is_bare_domain(url):
            continue
        if _is_blocked(url):
            continue
        unique.append(a)

    # Relevance filter
    unique = _filter_relevant(unique, question)

    # Cap
    unique = unique[:max_results]

    # Verify URLs are reachable
    verified = _verify_urls(unique)

    # Cache
    if verified:
        _set_cached(query, verified)

    return verified


def format_research(articles: list[dict]) -> str:
    """Format research articles as a numbered list for LLM context."""
    if not articles:
        return ""
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(f"[{i}] {a.get('title', 'Source')} — {a['url']}")
        if a.get("snippet"):
            lines.append(f"    {a['snippet']}")
    return "\n".join(lines)
