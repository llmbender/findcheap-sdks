# findcheap

The Findcheap API in Python: where the product on a page is sold for less. Standard library only, Python 3.9+.

```bash
pip install findcheap
export FINDCHEAP_API_KEY=fc_live_...   # from https://findcheap.ai/signin?next=/dashboard/keys
```

```python
from findcheap import Findcheap, FindcheapApiError

fc = Findcheap()  # reads FINDCHEAP_API_KEY; or Findcheap(api_key="fc_live_...")

answer = fc.search("https://findcheap.ai/sample-product", max_results=3)
print(answer["product"]["title"], "read in", answer["search"]["market"])
for card in answer["same_product"]:
    print(card["price"], card["currency"], card["retailer"], card["url"] or card["resolve_id"])

page = fc.extract("https://findcheap.ai/sample-product")
if page["is_product_page"]:
    print(page["title"], page["price"], page["currency"])

link = fc.resolve(answer["similar_products"][0]["resolve_id"])  # for a card whose url is None
```

Every answer opens with `request_id` and closes with `credits_used`. A failed call raises `FindcheapApiError` with `.status`, `.type`, `.message`, `.credits_used`, `.request_id` and `.retry_after` (seconds, on a 429); a call that never reached the API raises `FindcheapConnectionError`. Both subclass `FindcheapError`.

Timeouts sit above the API's own ceilings (a search answers within 60 seconds, a read within 30): 100, 40 and 20 seconds for search, extract and resolve, 20 for feedback, or one `timeout=` for every call.

The reference, with every field: https://findcheap.ai/developers/docs.md.

## Search by words

`search_products` finds products from a description in words, for when there is no product page to start from:

```python
found = fc.search_products("Insignia 32 inch Fire TV", market="US", max_price=200)
print(found["about_listings"])
for card in found["listings"]:
    print(card["price"], card["currency"], card["retailer"], card["url"] or card["resolve_id"])
```

It answers up to 10 listings that match the words, cheapest first, and costs 10 credits, with or without listings. `market` is required: there is no address to infer it from. `objective` (what the shopper wants, in one sentence), `min_price`, `max_price` and `max_results` are optional.

## Feedback on a search

`feedback` reports how a search went, by the `request_id` of its answer:

```python
report = fc.feedback(
    answer["request_id"], "partial",
    useful_cards=[{"list": "same_product", "position": 1}],
    wrong_cards=[{"list": "similar_products", "position": 2, "reason": "not_equivalent"}],
    note="The second similar listing is a smaller size.",
)
print(report["credits_refunded"], "credit back,", report["refunded_today"], "of", report["daily_refund_cap"], "today")
```

Send the rating (`"good"`, `"partial"` or `"bad"`) and at least one other field: `useful_cards` (the cards that were shown or recommended), `wrong_cards` (cards that do not belong in their list, each with a `reason`: `different_product`, `not_equivalent`, `price_differs`, `unavailable` or `other`), `cheaper_elsewhere` (cheaper listings found elsewhere that the answer did not have, each a `url` and optionally its `price`), `missing` (short sentences: what was expected and not returned), `goal` (one sentence: what the shopper was trying to do) or `note` (anything else, short). A card is named by its `list` (`same_product` or `similar_products`) and its `position` in that list, counted from 1.

The limits: one report per search, within 20 minutes of the search. The first report on a search gives 1 credit back, up to 100 credits a day per account. Sending feedback costs nothing. A second report on the same search changes nothing: the first one stands and the answer says `already_reported`. A refused report raises `FindcheapApiError` like any other call: `search_not_found` (404) when the account made no search with this id in the last 20 minutes, `feedback_off` (403) when feedback is switched off for the account, `invalid_request` (400) for a rating with no other field.
