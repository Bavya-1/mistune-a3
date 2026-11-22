import re

import mistune

TEXT = "First claim[^1] and again[^1].\n\n[^1]: The source.\n"


def render(text=TEXT):
    return mistune.create_markdown(plugins=["footnotes"])(text)


def ids(html):
    return re.findall(r'\bid="([^"]*)"', html)


def test_all_ids_unique():
    found = ids(render())
    assert len(found) == len(set(found)), found


def test_both_references_still_link_to_the_definition():
    out = render()
    assert out.count('href="#fn-1"') == 2
    assert 'id="fn-1"' in out


def test_single_reference_output_unchanged():
    out = render("One[^1].\n\n[^1]: Note.\n")
    assert out.count('id="fnref-1"') == 1
    assert 'href="#fnref-1"' in out


def test_two_footnotes_have_distinct_ids():
    out = render("A[^1] B[^2] C[^1].\n\n[^1]: one\n\n[^2]: two\n")
    found = ids(out)
    assert len(found) == len(set(found)), found
