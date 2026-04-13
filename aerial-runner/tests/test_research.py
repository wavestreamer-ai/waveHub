"""Tests for research module — domain filtering and query building."""

from wavestreamer_runner.research import _is_bare_domain, _is_blocked


class TestIsBlocked:
    def test_hard_blocked_domain(self):
        assert _is_blocked("https://pornhub.com/page") is True
        assert _is_blocked("https://infowars.com/article") is True
        assert _is_blocked("https://bit.ly/abc123") is True

    def test_junk_domain(self):
        assert _is_blocked("https://facebook.com/post") is True
        assert _is_blocked("https://reddit.com/r/test") is True
        assert _is_blocked("https://medium.com/article") is True

    def test_allowed_domain(self):
        assert _is_blocked("https://reuters.com/article") is False
        assert _is_blocked("https://arxiv.org/abs/2401.00001") is False
        assert _is_blocked("https://nature.com/articles/123") is False
        assert _is_blocked("https://bbc.com/news/tech") is False

    def test_subdomain_blocked(self):
        assert _is_blocked("https://www.pornhub.com/page") is True
        assert _is_blocked("https://m.facebook.com/post") is True

    def test_www_stripped(self):
        assert _is_blocked("https://www.reuters.com/article") is False

    def test_invalid_url_not_blocked(self):
        # URLs without scheme don't parse to a hostname — they pass through
        # (downstream URL verification catches these as unreachable)
        assert _is_blocked("not-a-url") is False

    def test_empty_string_not_blocked(self):
        assert _is_blocked("") is False


class TestIsBareDomain:
    def test_bare_homepage(self):
        assert _is_bare_domain("https://reuters.com") is True
        assert _is_bare_domain("https://reuters.com/") is True

    def test_has_path(self):
        assert _is_bare_domain("https://reuters.com/article/2024/test") is False
        assert _is_bare_domain("https://arxiv.org/abs/2401.00001") is False

    def test_single_segment(self):
        assert _is_bare_domain("https://example.com/about") is False
