/* Offline tests of the JS client over a local stub of the API: no network, no key, no spend.   npm test */
import assert from "node:assert/strict";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { after, before, test } from "node:test";
import { Findcheap, FindcheapApiError, FindcheapConnectionError } from "../src/index.ts";

const SEARCH = { request_id: "r-1", search: { url: "https://shop.example.com/p/1", market: "US", condition: "new", max_results: 3 },
  product: { title: "Kettle", image: null, price: 29.99, currency: "USD", brand: "Acme", url: "https://shop.example.com/p/1", market: "US", in_stock: true },
  product_name: "Acme Kettle", same_product: [{ title: "Kettle", price: 19, currency: "USD", url: "https://w/x", image: "i", retailer: "eBay", over_page_price: false }],
  similar_products: [], page_is_cheapest: false, credits_used: 10 };
const READ = { request_id: "r-2", is_product_page: true, url: "https://shop.example.com/p/1", market: "US", title: "Kettle", image: null, price: 29.99, currency: "USD", brand: "Acme", in_stock: true, reason: null, credits_used: 1 };
const RESOLVE = { request_id: "r-3", resolved: true, url: "https://merchant/x", retailer: "Walmart", credits_used: 1 };
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
  assert.deepEqual(Object.keys(out), ["request_id", "search", "product", "product_name", "same_product", "similar_products", "page_is_cheapest", "credits_used"]);
  assert.equal(out.credits_used, 10);
});

test("search options travel as the API takes them", async () => {
  await client().search("https://shop.example.com/p/1", { market: "in", marketplaces: ["amazon", "flipkart"], condition: "used" });
  assert.deepEqual(seen.at(-1)!.body, { url: "https://shop.example.com/p/1", market: "in", marketplaces: ["amazon", "flipkart"], condition: "used" });
});

test("extract and resolve", async () => {
  assert.equal((await client().extract("https://shop.example.com/p/1", { market: "US" })).title, "Kettle");
  assert.deepEqual(seen.at(-1)!.body, { url: "https://shop.example.com/p/1", market: "US" });
  assert.equal((await client().resolve("abc")).retailer, "Walmart");
  assert.equal(seen.at(-1)!.path, "/v1/resolve");
  assert.deepEqual(seen.at(-1)!.body, { id: "abc" });
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

test("no server, or the client's timeout, is a connection error", async () => {
  await assert.rejects(new Findcheap({ apiKey: "fc_live_test", baseUrl: "http://127.0.0.1:9", timeoutMs: 2000 }).resolve("x"), FindcheapConnectionError);
  await assert.rejects(new Findcheap({ apiKey: "fc_live_test", baseUrl: base, timeoutMs: 200 }).extract("https://hang.example/p"), FindcheapConnectionError);
});

test("no key anywhere is an error at construction", () => {
  delete process.env.FINDCHEAP_API_KEY;
  assert.throws(() => new Findcheap({ baseUrl: base }), /FINDCHEAP_API_KEY/);
});
