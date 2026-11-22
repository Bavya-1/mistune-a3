# Bare www.example.com isn't turned into a link

With the `url` plugin enabled, `https://example.com` becomes a link, but when people just type `www.example.com` in their comments it stays plain text.

```python
import mistune
md = mistune.create_markdown(plugins=["url"])
print(md("visit www.example.com for more"))
# <p>visit www.example.com for more</p>
```

GitHub and most other Markdown flavours link this. It would be great if it did here too (pointing to `http://www.example.com`), as long as normal text containing "www" in the middle of a word isn't affected.
