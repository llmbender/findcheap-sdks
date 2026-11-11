---
name: findcheap
description: Find where the product on a page is sold for less with the Findcheap API (search, extract, resolve) or its MCP server. Use when a task involves a product page's address and a price, a cheaper alternative, the same product elsewhere, or reading what a product page sells. Covers the key, the three calls, the answer header, timing, errors and credits.
---

# Build with Findcheap

Findcheap takes a product page's address and answers where that product is sold for less: the same brand and model elsewhere (`same_product`) and acceptable equivalents (`similar_products`), cheapest first, each with price, retailer, link and any coupon. It also reads a product page without searching, and resolves a card's merchant link.

The reference: https://findcheap.ai/developers/docs.md. The MCP server: https://findcheap.ai/developers/mcp.md. OpenAPI spec: https://api.findcheap.ai/v1/openapi.json.

## If you were asked to set Findcheap up

Do these in order, telling the user what you are doing:

1. Ask the user for their API key, or point them at https://findcheap.ai/signin?next=/dashboard/keys to create one (a free account, no card). Never ask them to paste it into chat if a secret store is at hand; an environment variable is fine.
2. Store it as `FINDCHEAP_API_KEY` in the project's environment or secret store, never in code or a commit.
3. In a Python or JavaScript project install the SDK (`pip install findcheap` or `npm install findcheap`); otherwise use curl as below.
4. Run the smoke test under Setup.
5. Run one search on a product page the user names, with `max_results` 3, and show them the header (`product`, `search`) and the cheapest listings.
6. Point them at the reference for the rest: https://findcheap.ai/developers/docs.md.

## Setup

1. The key is created at https://findcheap.ai/signin?next=/dashboard/keys (a free account: 1,000 credits a month, no card). It begins with `fc_live_` and is shown once.
2. Keep it in the environment as `FINDCHEAP_API_KEY` (or in the project's secret store). Never print it, never write it into code or a commit, never put it in a URL. It travels only in the `Authorization: Bearer` header.
3. Smoke-test the key with a page read (1 credit). The address is Findcheap's sample product page, a copy of a real product page that does not change:

```bash
curl -s https://api.findcheap.ai/v1/extract \
  -H "Authorization: Bearer $FINDCHEAP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://findcheap.ai/sample-product"}'
```

A `401` means the key is missing or wrong; a `200` with `is_product_page: true` means you are set.

## The three calls

All are `POST https://api.findcheap.ai/v1/<call>` with a JSON body and a JSON answer. In Python or JavaScript, the official clients do the HTTP: `pip install findcheap` / `npm install findcheap`, then `Findcheap().search(url, max_results=3)` / `new Findcheap().search(url, { max_results: 3 })`; a failed call is a `FindcheapApiError` carrying the envelope's fields (https://github.com/llmbender/findcheap-sdks).

| Call | Body | Answers | Credits | Time |
| --- | --- | --- | --- | --- |
| `/v1/search` | `url`, optional `market`, `marketplaces`, `condition` (`new` / `used`), `max_results` (1–10) | the header, `product`, `same_product`, `similar_products`, `page_is_cheapest` | 10 | up to 90 s, usually 15–30 |
| `/v1/extract` | `url`, optional `market` | `is_product_page`, title, image, price, currency, brand, in_stock, `reason` | 1 | up to 30 s, median 4 |
| `/v1/resolve` | `id` (a card's `resolve_id`) | `resolved`, `url`, `retailer` | 1 when a link came back, else 0 | about 1 s |

Set the HTTP client's timeout above the call's ceiling: 100 s for a search, 40 s for a read. `market` is the shopper's country (US, CA, AU, IN, GLOBAL); omit it and the address decides (`.in` → IN, `.ca` → CA, else US). Ask for `max_results: 3` when only the cheapest few matter; the credits are the same.

## Reading a search answer

The answer is ordered so the header comes first. Read it before the cards:

```json
{
  "request_id": "…",
  "search": { "url": "<as sent>", "market": "US", "condition": "new", "max_results": 10 },
  "product": { "title": "…", "brand": "…", "price": 99.99, "currency": "USD", "url": "<as read>", "market": "US", "image": "…", "in_stock": true },
  "product_name": "JLab JBuds Lux ANC",
  "same_product": [ { "title": "…", "price": 67.5, "currency": "USD", "retailer": "Amazon", "url": "…", "over_page_price": false, "coupon": null, "promo_code": null } ],
  "similar_products": [ { "title": "…", "price": 49.99, "retailer": "Walmart", "url": null, "resolve_id": "7c1f…" } ],
  "page_is_cheapest": false,
  "credits_used": 10
}
```

- Check `product.title`, `product.brand` and `search.market` against what the user meant before trusting a card.
- `same_product` cards carry `over_page_price`: `false` is cheaper than the page, `true` the same or more, `null` when the page had no price. `page_is_cheapest` says whether the page already had the lowest price found.
- A card whose `url` is `null` carries a `resolve_id`: call `/v1/resolve` with it to get the merchant's link (1 credit), soon after the search; ids expire within about two hours.
- `price` on a card is after any coupon or promo code; `price_before_discount`, `coupon` and `promo_code` say what was applied.
- `condition: "used"` searches secondhand copies; it is not available in India and is refused for grocery and consumable products.

## Errors and credits

Every error is an HTTP status with one shape: `{"error": {"type", "message", "credits_used", "request_id"}}`.

- `422 not_searchable` or `refused`: the page was read but not searched; it costs 1 credit (a page read). Every other error costs 0.
- `429 rate_limited`: wait the `Retry-After` seconds. Limits are per account per minute (Free: 5 searches, 30 other calls).
- `402 credits_exhausted`: the period's credits are spent; the message names the reset date.
- `502 unreachable` and `504 timeout` are safe to retry; `500 search_failed` with backoff.
- Every answer and every error carries `credits_used`, what the call cost, and `request_id`, the call's id on the account's ledger; keep the id when reporting a problem.

## The MCP server instead of the API

For an assistant in a conversation (Claude, Claude Code, Cursor), connect `https://mcp.findcheap.ai/mcp` (Streamable HTTP) with the same key in the `Authorization` header, or sign in with a Findcheap account from Claude.ai. The tools `find_cheaper`, `read_product_page` and `resolve_listing` take the same parameters and return the same JSON as the API, with progress notifications while a search runs.

```bash
claude mcp add --transport http findcheap https://mcp.findcheap.ai/mcp \
  --header "Authorization: Bearer $FINDCHEAP_API_KEY"
```
