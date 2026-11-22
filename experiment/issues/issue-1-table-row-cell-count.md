# Table disappears when a row has fewer cells than the header

I'm rendering user-written docs with the table plugin and a lot of my users forget the last cell in a row. When that happens the whole table turns into a paragraph of raw pipes and dashes instead of a table.

```python
import mistune
md = mistune.create_markdown(plugins=["table"])
print(md("""| name | role | team |
|------|------|------|
| ann  | dev  |
| bob  | ops  | core |
"""))
```

I expected a table with an empty last cell for ann, like GitHub shows it. Instead I get `<p>| name | role | team | ...` with everything as text.

Same thing happens the other way round if a row has one cell too many.

Version: current main.
