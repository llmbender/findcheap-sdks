# findcheap

The Findcheap API in Python: where the product on a page is sold for less. Standard library only, Python 3.9+.

```bash
pip install findcheap
export FINDCHEAP_API_KEY=fc_live_...   # from https://findcheap.ai/signin?next=/dashboard/keys
```

```python
from findcheap import Findcheap, FindcheapApiError

fc = Findcheap()  # reads FINDCHEAP_API_KEY; or Findcheap(api_key="fc_live_...")

answer = fc.search("https://www.jlab.com/products/jbuds-lux-anc-headphones", max_results=3)
print(answer["product"]["title"], "read in", answer["search"]["market"])
for card in answer["same_product"]:
    print(card["price"], card["currency"], card["retailer"], card["url"] or card["resolve_id"])

page = fc.extract("https://www.jlab.com/products/jbuds-lux-anc-headphones")
if page["is_product_page"]:
    print(page["title"], page["price"], page["currency"])

link = fc.resolve(answer["similar_products"][0]["resolve_id"])  # for a card whose url is None
```

Every answer opens with `request_id` and closes with `credits_used`. A failed call raises `FindcheapApiError` with `.status`, `.type`, `.message`, `.credits_used`, `.request_id` and `.retry_after` (seconds, on a 429); a call that never reached the API raises `FindcheapConnectionError`. Both subclass `FindcheapError`.

Timeouts sit above the API's own ceilings (a search answers within 90 seconds, a read within 30): 100, 40 and 20 seconds for search, extract and resolve, or one `timeout=` for all three.

The reference, with every field: https://findcheap.ai/developers/docs.md.
