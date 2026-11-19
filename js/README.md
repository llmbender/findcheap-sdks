# findcheap

The Findcheap API in JavaScript and TypeScript: where the product on a page is sold for less. Node 18+ or a browser with `fetch`; no dependencies.

```bash
npm install findcheap
export FINDCHEAP_API_KEY=fc_live_...   # from https://findcheap.ai/signin?next=/dashboard/keys
```

```ts
import { Findcheap, FindcheapApiError } from "findcheap";

const fc = new Findcheap(); // reads FINDCHEAP_API_KEY; or new Findcheap({ apiKey: "fc_live_..." })

const answer = await fc.search("https://findcheap.ai/sample-product", { max_results: 3 });
console.log(answer.product.title, "read in", answer.search.market);
for (const card of answer.same_product) console.log(card.price, card.currency, card.retailer, card.url ?? card.resolve_id);

const page = await fc.extract("https://findcheap.ai/sample-product");
if (page.is_product_page) console.log(page.title, page.price, page.currency);

const link = await fc.resolve(answer.similar_products[0].resolve_id!); // for a card whose url is null
```

Every answer opens with `request_id` and closes with `credits_used`. A failed call throws `FindcheapApiError` with `status`, `type`, `message`, `credits_used`, `request_id` and `retry_after` (seconds, on a 429); a call that never reached the API throws `FindcheapConnectionError`. Both extend `FindcheapError`.

Timeouts sit above the API's own ceilings (a search answers within 60 seconds, a read within 30): 100, 40 and 20 seconds for search, extract and resolve, 20 for feedback, or one `timeoutMs` for every call. Pass your own `signal` to cancel a call.

The reference, with every field: https://findcheap.ai/developers/docs.md.

## Feedback on a search

`feedback` reports how a search went, by the `request_id` of its answer:

```ts
const report = await fc.feedback(answer.request_id, "partial", {
  useful_cards: [{ list: "same_product", position: 1 }],
  wrong_cards: [{ list: "similar_products", position: 2, reason: "not_equivalent" }],
  note: "The second similar listing is a smaller size.",
});
console.log(report.credits_refunded, "credit back,", report.refunded_today, "of", report.daily_refund_cap, "today");
```

Send the rating (`"good"`, `"partial"` or `"bad"`) and at least one other field: `useful_cards` (the cards that were shown or recommended), `wrong_cards` (cards that do not belong in their list, each with a `reason`: `different_product`, `not_equivalent`, `price_differs`, `unavailable` or `other`), `cheaper_elsewhere` (cheaper listings found elsewhere that the answer did not have, each a `url` and optionally its `price`), `missing` (short sentences: what was expected and not returned), `goal` (one sentence: what the shopper was trying to do) or `note` (anything else, short). A card is named by its `list` (`same_product` or `similar_products`) and its `position` in that list, counted from 1.

The limits: one report per search, within 20 minutes of the search. The first report on a search gives 1 credit back, up to 100 credits a day per account. Sending feedback costs nothing. A second report on the same search changes nothing: the first one stands and the answer says `already_reported`. A refused report throws `FindcheapApiError` like any other call: `search_not_found` (404) when the account made no search with this id in the last 20 minutes, `feedback_off` (403) when feedback is switched off for the account, `invalid_request` (400) for a rating with no other field.
