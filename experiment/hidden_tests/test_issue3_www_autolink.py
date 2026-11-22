import mistune


def md():
    return mistune.create_markdown(plugins=["url"])


def test_www_is_linked_with_http_scheme():
    out = md()("visit www.example.com for more")
    assert '<a href="http://www.example.com">www.example.com</a>' in out


def test_trailing_punctuation_not_part_of_link():
    out = md()("see www.example.com/page.")
    assert 'href="http://www.example.com/page"' in out
    assert out.rstrip().endswith("</a>.</p>")


def test_www_inside_a_word_not_linked():
    out = md()("awww.example.com is not a link")
    assert "<a " not in out


def test_https_urls_unchanged():
    out = md()("https://example.com")
    assert '<a href="https://example.com">https://example.com</a>' in out
