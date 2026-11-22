# Citing the same footnote twice creates duplicate HTML ids

If I reference one footnote from two places in a document, the output contains two elements with the same `id`.

```python
import mistune
md = mistune.create_markdown(plugins=["footnotes"])
print(md("""First claim[^1] and later the same source again[^1].

[^1]: The source.
"""))
```

Output has `id="fnref-1"` twice. My HTML validator complains about the duplicate id, and the little back-arrow in the footnote can only jump to one of the two places.

I'd expect every id in the page to be unique.
