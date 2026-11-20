/* Offline tests of the JS client over a local stub of the API: no network, no key, no spend.   npm test */
import assert from "node:assert/strict";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { after, before, test } from "node:test";
import { Findcheap, FindcheapApiError, FindcheapConnectionError } from "../src/index.ts";

const SEARCH = { request_id: "r-1", search: { url: "https://shop.example.com/p/1", market: "US", condition: "new", max_results: 3 },
  product: { title: "Kettle", image: null, price: 29.99, currency: "USD", brand: "Acme", url: "https://shop.example.com/p/1", market: "US", in_stock: true, retailer: "Amazon", coupon: "10% coupon", promo_code: null, shipping_cost: 0, returns_accepted: null, return_days: null, return_shipping_paid_by: null, pack_count: null },
  product_name: "Acme Kettle",
  about_lists: "same_product holds listings that match the original product; a different colour or pack size still counts as the same product. similar_products holds acceptable equivalent products from any brand.",
  same_product: [{ title: "Kettle", price: 19, currency: "USD", url: "https://w/x", image: "i", retailer: "eBay", over_page_price: false }],
  similar_products: [], page_is_cheapest: false,
  next_steps: [{ label: "Find pre-owned", tool: "find_cheaper", arguments: { url: "https://shop.example.com/p/1", market: "US", condition: "used" }, choose: null }],
  credits_used: 10 };
const READ = { request_id: "r-2", is_product_page: true, url: "https://shop.example.com/p/1", market: "US", title: "Kettle", image: null, price: 29.99, currency: "USD", brand: "Acme", in_stock: true, retailer: "eBay", coupon: "$5 coupon", promo_code: "SHOPNOW15", shipping_cost: 7.36, returns_accepted: true, return_days: 30, return_shipping_paid_by: "seller", reason: null, credits_used: 1 };
const RESOLVE = { request_id: "r-3", resolved: true, url: "https://merchant/x", retailer: "Walmart", credits_used: 1 };
const PRODUCTS = { request_id: "r-5", search: { query: "Insignia Fire TV", market: "US", min_price: null, max_price: 200, max_results: 10 },
  about_listings: "listings holds listings that match the words you searched for, cheapest first.",
  listings: [{ title: "Insignia 32in Fire TV", price: 65, currency: "USD", url: "https://w/tv", image: "i", retailer: "eBay", rating: 100, ratings_count: 39 },
    { title: "Insignia F50 Fire TV", price: 149.99, currency: "USD", url: null, resolve_id: "abc", image: "i", retailer: "Best Buy" }],
  credits_used: 10 };
const NO_PRODUCTS = { request_id: "r-6", search: { query: "a product no store carries", market: "IN", min_price: null, max_price: null, max_results: 10 },
  about_listings: "No listing that matches the words was found in this market.", listings: [], credits_used: 10 };
const FEEDBACK = { request_id: "r-4", recorded: true, already_reported: false, credits_refunded: 1, refunded_today: 3, daily_refund_cap: 100, daily_cap_reached: false, credits_used: 0 };
const seen: { path: string; headers: IncomingMessage["headers"]; body: Record<string, unknown> }[] = [];

function send(res: ServerResponse, status: number, payload: unknown, headers: Record<string, string> = {}) {
  res.writeHead(status, { "Content-Type": "application/json", ...headers });
  res.end(JSON.stringify(payload));
}
const server = createServer((req, res) => {
  let raw = "";
  req.on("data", (c) => (raw += c));
  req.on("end", () => {
    const body = JSON.parse(raw) as Record<string, unknown>;
    seen.push({ path: req.url ?? "", headers: req.headers, body });
    if (req.headers.authorization !== "Bearer fc_live_test") return send(res, 401, { error: { type: "unauthorized", message: "No key.", credits_used: 0, request_id: "e-0" } });
    if (body.url === "https://en.wikipedia.org/wiki/Shoe") return send(res, 422, { error: { type: "not_searchable", message: "Not a product page. Billed as a page read: 1 credit.", credits_used: 1, request_id: "e-1" } });
    if (body.url === "https://slow.example/p") return send(res, 429, { error: { type: "rate_limited", message: "Wait.", credits_used: 0, request_id: "e-2" } }, { "Retry-After": "7" });
    if (body.url === "https://proxy.example/p") { res.writeHead(502, { "Content-Type": "text/html" }); return res.end("<html>Bad Gateway</html>"); }
    if (body.url === "https://hang.example/p") return; // never answers: the client's timeout fires
    // The feedback call carries the search's id in its path. Two ids stand for its own two refusals,
    // and a body holding the rating alone is refused in the API's words.
    if (req.url === "/v1/search/r-old/feedback") return send(res, 404, { error: { type: "search_not_found", message: "No search with this id in the last 20 minutes.", credits_used: 0, request_id: "e-3" } });
    if (req.url === "/v1/search/r-off/feedback") return send(res, 403, { error: { type: "feedback_off", message: "Feedback is switched off for this account.", credits_used: 0, request_id: "e-4" } });
    if (req.url?.startsWith("/v1/search/") && req.url.endsWith("/feedback")) {
      if (Object.keys(body).join() === "rating") return send(res, 400, { error: { type: "invalid_request", message: "Send the rating and at least one other field.", credits_used: 0, request_id: "e-5" } });
      return send(res, 200, FEEDBACK);
    }
    // The search by words: words that match nothing answer an empty list (a 200, charged), and a market
    // the API does not serve is refused in its own words.
    if (req.url === "/v1/products/search") {
      if (body.market === "ZZ") return send(res, 400, { error: { type: "unknown_market", message: "market must be one of US, CA, AU, IN, GLOBAL.", credits_used: 0, request_id: "e-6" } });
      return send(res, 200, body.query === "a product no store carries" ? NO_PRODUCTS : PRODUCTS);
    }
    send(res, 200, ({ "/v1/search": SEARCH, "/v1/extract": READ, "/v1/resolve": RESOLVE } as Record<string, unknown>)[req.url ?? ""]);
  });
});
let base = "";
before(async () => {
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", () => r()));
  const address = server.address();
  base = `http://127.0.0.1:${typeof address === "object" && address ? address.port : 0}`;
});
after(() => server.close());
const client = () => new Findcheap({ apiKey: "fc_live_test", baseUrl: base });

test("search sends only what was given and returns the answer as is", async () => {
  const out = await client().search("https://shop.example.com/p/1", { max_results: 3 });
  const last = seen.at(-1)!;
  assert.equal(last.path, "/v1/search");
  assert.deepEqual(last.body, { url: "https://shop.example.com/p/1", max_results: 3 });
  assert.equal(last.headers.authorization, "Bearer fc_live_test");
  assert.match(String(last.headers["user-agent"]), /^findcheap-js\//);
  assert.deepEqual(Object.keys(out), ["request_id", "search", "product", "product_name", "about_lists", "same_product", "similar_products", "page_is_cheapest", "next_steps", "credits_used"]);
  assert.equal(out.next_steps[0].arguments.condition, "used");
  assert.equal(out.credits_used, 10);
});

test("search options travel as the API takes them", async () => {
  await client().search("https://shop.example.com/p/1", { market: "in", marketplaces: ["amazon", "flipkart"], condition: "used" });
  assert.deepEqual(seen.at(-1)!.body, { url: "https://shop.example.com/p/1", market: "in", marketplaces: ["amazon", "flipkart"], condition: "used" });
});

test("searchProducts sends the words and the market and returns the answer as is", async () => {
  const out = await client().searchProducts("Insignia Fire TV", { market: "US" });
  const last = seen.at(-1)!;
  assert.equal(last.path, "/v1/products/search");
  assert.deepEqual(last.body, { query: "Insignia Fire TV", market: "US" });
  assert.equal(last.headers.authorization, "Bearer fc_live_test");
  assert.deepEqual(Object.keys(out), ["request_id", "search", "about_listings", "listings", "credits_used"]);
  assert.deepEqual(out.listings.map((c) => c.retailer), ["eBay", "Best Buy"]);
  assert.equal(out.listings[1].url, null);
  assert.equal(out.listings[1].resolve_id, "abc");
  assert.equal(out.credits_used, 10);
});

test("searchProducts options travel as the API takes them; the caller's signal is no part of the body", async () => {
  await client().searchProducts("TV", { market: "in", objective: "A TV for a small bedroom.", min_price: 50, max_price: 200, max_results: 3, signal: new AbortController().signal });
  assert.deepEqual(seen.at(-1)!.body, { query: "TV", market: "in", objective: "A TV for a small bedroom.", min_price: 50, max_price: 200, max_results: 3 });
});

test("searchProducts with nothing found is an empty list, not an error; a market that is not served is unknown_market", async () => {
  const out = await client().searchProducts("a product no store carries", { market: "IN" });
  assert.deepEqual(out.listings, []);
  assert.equal(out.about_listings, "No listing that matches the words was found in this market.");
  assert.equal(out.credits_used, 10);
  await assert.rejects(client().searchProducts("TV", { market: "ZZ" }), (e: unknown) =>
    e instanceof FindcheapApiError && e.status === 400 && e.type === "unknown_market" && e.credits_used === 0);
});

test("extract and resolve", async () => {
  assert.equal((await client().extract("https://shop.example.com/p/1", { market: "US" })).title, "Kettle");
  assert.deepEqual(seen.at(-1)!.body, { url: "https://shop.example.com/p/1", market: "US" });
  assert.equal((await client().resolve("abc")).retailer, "Walmart");
  assert.equal(seen.at(-1)!.path, "/v1/resolve");
  assert.deepEqual(seen.at(-1)!.body, { id: "abc" });
});

test("feedback goes to the search's path with only what was given and returns the answer as is", async () => {
  const out = await client().feedback("r-1", "good", { note: "The first listing was the one to buy." });
  const last = seen.at(-1)!;
  assert.equal(last.path, "/v1/search/r-1/feedback");
  assert.deepEqual(last.body, { rating: "good", note: "The first listing was the one to buy." });
  assert.equal(last.headers.authorization, "Bearer fc_live_test");
  assert.deepEqual(Object.keys(out), ["request_id", "recorded", "already_reported", "credits_refunded", "refunded_today", "daily_refund_cap", "daily_cap_reached", "credits_used"]);
  assert.deepEqual(out, FEEDBACK);
});

test("feedback fields travel as the API takes them; the caller's signal is no part of the body", async () => {
  await client().feedback("r-1", "partial", {
    useful_cards: [{ list: "same_product", position: 1 }],
    wrong_cards: [{ list: "similar_products", position: 2, reason: "not_equivalent" }],
    cheaper_elsewhere: [{ url: "https://other.example/p/9", price: 17.5 }, { url: "https://other.example/p/10" }],
    missing: ["A listing from the brand's own store."],
    goal: "Buy this kettle for less than the page's price.",
    note: "The second similar listing is a smaller size.",
    signal: new AbortController().signal,
  });
  assert.deepEqual(seen.at(-1)!.body, {
    rating: "partial",
    useful_cards: [{ list: "same_product", position: 1 }],
    wrong_cards: [{ list: "similar_products", position: 2, reason: "not_equivalent" }],
    cheaper_elsewhere: [{ url: "https://other.example/p/9", price: 17.5 }, { url: "https://other.example/p/10" }],
    missing: ["A listing from the brand's own store."],
    goal: "Buy this kettle for less than the page's price.",
    note: "The second similar listing is a smaller size.",
  });
});

test("feedback escapes the request id in the path", async () => {
  await client().feedback("r 1/x?y", "good", { note: "ok" });
  assert.equal(seen.at(-1)!.path, "/v1/search/r%201%2Fx%3Fy/feedback");
});

test("the envelope becomes an api error with its fields", async () => {
  const e = await client().search("https://en.wikipedia.org/wiki/Shoe").catch((x) => x as FindcheapApiError);
  assert.ok(e instanceof FindcheapApiError);
  assert.deepEqual([e.status, e.type, e.credits_used, e.request_id, e.retry_after], [422, "not_searchable", 1, "e-1", null]);
  assert.equal(e.message, "422 not_searchable: Not a product page. Billed as a page read: 1 credit.");
  assert.equal(e.detail, "Not a product page. Billed as a page read: 1 credit.");
});

test("a 429 carries retry_after; a body that is not the envelope is http_error; a wrong key is unauthorized", async () => {
  const slow = await client().extract("https://slow.example/p").catch((x) => x as FindcheapApiError);
  assert.deepEqual([slow.type, slow.retry_after], ["rate_limited", 7]);
  const proxy = await client().extract("https://proxy.example/p").catch((x) => x as FindcheapApiError);
  assert.deepEqual([proxy.status, proxy.type, proxy.credits_used], [502, "http_error", 0]);
  const wrong = await new Findcheap({ apiKey: "fc_live_wrong", baseUrl: base }).resolve("x").catch((x) => x as FindcheapApiError);
  assert.equal(wrong.type, "unauthorized");
});

test("feedback with the rating alone travels as given and the API refuses it", async () => {
  const e = await client().feedback("r-1", "bad").catch((x) => x as FindcheapApiError);
  assert.ok(e instanceof FindcheapApiError);
  assert.deepEqual(seen.at(-1)!.body, { rating: "bad" });
  assert.deepEqual([e.status, e.type, e.detail], [400, "invalid_request", "Send the rating and at least one other field."]);
});

test("feedback on a search that is not found is search_not_found; switched off for the account is feedback_off", async () => {
  const late = await client().feedback("r-old", "good", { note: "Sent too late." }).catch((x) => x as FindcheapApiError);
  assert.ok(late instanceof FindcheapApiError);
  assert.deepEqual([late.status, late.type, late.credits_used, late.request_id, late.retry_after], [404, "search_not_found", 0, "e-3", null]);
  assert.equal(late.message, "404 search_not_found: No search with this id in the last 20 minutes.");
  const off = await client().feedback("r-off", "good", { note: "The first listing was the one to buy." }).catch((x) => x as FindcheapApiError);
  assert.ok(off instanceof FindcheapApiError);
  assert.deepEqual([off.status, off.type, off.credits_used, off.request_id, off.retry_after], [403, "feedback_off", 0, "e-4", null]);
  assert.equal(off.detail, "Feedback is switched off for this account.");
});

test("no server, or the client's timeout, is a connection error", async () => {
  await assert.rejects(new Findcheap({ apiKey: "fc_live_test", baseUrl: "http://127.0.0.1:9", timeoutMs: 2000 }).resolve("x"), FindcheapConnectionError);
  await assert.rejects(new Findcheap({ apiKey: "fc_live_test", baseUrl: base, timeoutMs: 200 }).extract("https://hang.example/p"), FindcheapConnectionError);
});

test("no key anywhere is an error at construction", () => {
  delete process.env.FINDCHEAP_API_KEY;
  assert.throws(() => new Findcheap({ baseUrl: base }), /FINDCHEAP_API_KEY/);
});
