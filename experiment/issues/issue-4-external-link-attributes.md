# Option to open external links in a new tab safely

We render comments written by our users. We want links that point to other sites to open in a new tab, and we don't want to give those sites access to our page or pass on search ranking.

Right now `[x](https://example.com)` just gives `<a href="https://example.com">x</a>`. I can post-process the HTML with regexes but that feels fragile.

Could `HTMLRenderer` get an option, something like `HTMLRenderer(external_links=True)`, that adds `target="_blank"` and `rel="nofollow noopener"` to links with an `http://` or `https://` address? It should be off by default so existing output doesn't change, and links like `#section` or `/docs/page` should be left alone.
