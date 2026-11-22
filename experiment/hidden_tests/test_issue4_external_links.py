import mistune
from mistune import HTMLRenderer


def md(**kw):
    return mistune.create_markdown(renderer=HTMLRenderer(escape=False, **kw))


def test_default_output_unchanged():
    assert md()("[x](https://example.com)") == '<p><a href="https://example.com">x</a></p>\n'


def test_https_and_http_links_get_attributes():
    for url in ("https://example.com", "http://example.com"):
        out = md(external_links=True)(f"[x]({url})")
        assert 'target="_blank"' in out
        assert "nofollow" in out and "noopener" in out


def test_internal_links_left_alone():
    for url in ("#section", "/docs/page", "page.html"):
        out = md(external_links=True)(f"[x]({url})")
        assert "target=" not in out and "rel=" not in out


def test_mailto_left_alone():
    out = md(external_links=True)("[x](mailto:a@b.co)")
    assert "target=" not in out
