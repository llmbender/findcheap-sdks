# findcheap

The Findcheap API in JavaScript and TypeScript: where the product on a page is sold for less. Node 18+ or a browser with `fetch`; no dependencies.

```bash
npm install findcheap
export FINDCHEAP_API_KEY=fc_live_...   # from https://findcheap.ai/signin?next=/dashboard/keys
```

```ts
import { Findcheap, FindcheapApiError } from "findcheap";

const fc = new Findcheap(); // reads FINDCHEAP_API_KEY; or new Findcheap({ apiKey: "fc_live_..." })

const answer = await fc.search("https://www.jlab.com/products/jbuds-lux-anc-headphones", { max_results: 3 });
console.log(answer.product.title, "read in", answer.search.market);
for (const card of answer.same_product) console.log(card.price, card.currency, card.retailer, card.url ?? card.resolve_id);

const page = await fc.extract("https://www.jlab.com/products/jbuds-lux-anc-headphones");
if (page.is_product_page) console.log(page.title, page.price, page.currency);

const link = await fc.resolve(answer.similar_products[0].resolve_id!); // for a card whose url is null
```

Every answer opens with `request_id` and closes with `credits_used`. A failed call throws `FindcheapApiError` with `status`, `type`, `message`, `credits_used`, `request_id` and `retry_after` (seconds, on a 429); a call that never reached the API throws `FindcheapConnectionError`. Both extend `FindcheapError`.

Timeouts sit above the API's own ceilings (a search answers within 90 seconds, a read within 30): 100, 40 and 20 seconds for search, extract and resolve, or one `timeoutMs` for all three. Pass your own `signal` to cancel a call.

The reference, with every field: https://findcheap.ai/developers/docs.md.
