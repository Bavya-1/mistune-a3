import mistune


def md():
    return mistune.create_markdown(plugins=["table"])


def test_short_row_still_renders_table():
    out = md()("| name | role | team |\n|---|---|---|\n| ann | dev |\n| bob | ops | core |\n")
    assert "<table>" in out
    assert "|---|" not in out


def test_short_row_is_padded_to_header_width():
    out = md()("| name | role | team |\n|---|---|---|\n| ann | dev |\n| bob | ops | core |\n")
    assert out.count("<td") == 6  # two body rows x three cells


def test_extra_cell_is_dropped():
    out = md()("| a | b |\n|---|---|\n| 1 | 2 | 3 |\n")
    assert "<table>" in out
    assert out.count("<td") == 2
    assert ">3<" not in out


def test_well_formed_table_unchanged():
    out = md()("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert out.count("<th>") == 2 and out.count("<td") == 2
