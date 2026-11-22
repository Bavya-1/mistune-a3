# Intended reading of the vague issue: headings get stable, readable ids
# (GitHub-style slugs) when the toc hook is used.
import re

import mistune
from mistune.toc import add_toc_hook


def md(**kw):
    m = mistune.create_markdown()
    add_toc_hook(m, **kw)
    return m


def test_heading_id_is_slug_of_text():
    out = md()("# Hello World\n")
    assert 'id="hello-world"' in out


def test_duplicate_headings_get_unique_ids():
    out = md()("# Setup\n\n## Setup\n")
    found = re.findall(r'\bid="([^"]*)"', out)
    assert len(found) == 2 and len(set(found)) == 2
    assert "setup" in found


def test_punctuation_is_removed_from_slug():
    out = md()("# What's new? (v2)\n")
    assert 'id="whats-new-v2"' in out


def test_custom_heading_id_function_still_honoured():
    out = md(heading_id=lambda tok, i: f"sec-{i}")("# A\n")
    assert 'id="sec-0"' in out
