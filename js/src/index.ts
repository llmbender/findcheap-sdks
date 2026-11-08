/*
 * The Findcheap API in TypeScript: three POSTs over fetch, the answer as
 * the API sends it. Nothing is reshaped: a search answer opens with
 * `request_id` and `search` (what was searched), then `product`,
 * `product_name`, `same_product`, `similar_products`, `page_is_cheapest`,
 * `credits_used`. Reference: https://findcheap.ai/developers/docs.md
 */

export const VERSION = "0.1.0";
export const DEFAULT_BASE_URL = "https://api.findcheap.ai";
// Above the API's own walls (a search answers within 90 s, a read within 30),
// so the API's timeout envelope, not a client cut-off, is what a caller sees.
export const SEARCH_TIMEOUT_MS = 100_000;
export const EXTRACT_TIMEOUT_MS = 40_000;
export const RESOLVE_TIMEOUT_MS = 20_000;

export type Condition = "new" | "used";
export type Marketplace = "amazon" | "walmart" | "ebay" | "aliexpress" | "shein" | "flipkart" | "other_sites";

/** What was searched: the address as sent, the market the search ran in, the condition, the cap. */
export interface SearchEcho { url: string; market: string; condition: Condition; max_results: number }

/** The page as read. */
export interface Product {
  title: string | null; image: string | null; price: number | null; currency: string | null;
  brand: string | null; url: string; market: string; in_stock: boolean | null;
}

/** One listing elsewhere. `url` null means a `resolve_id` to pass to resolve(). */
export interface Card {
  title: string; price: number; currency: string; url: string | null; resolve_id?: string | null;
  image: string; retailer: string; rating?: number | null; ratings_count?: number | null;
  /** same_product cards only: true at or over the page's price, false cheaper, null when the page had no price. */
  over_page_price?: boolean | null;
  unit_size?: string | null; pack_count?: number | null; normalized_price?: number | null;
  coupon?: string | null; promo_code?: string | null; price_before_discount?: number | null;
  discount_type?: "percent" | "fixed" | null; discount_value?: number | null;
  [extra: string]: unknown;
}

export interface SearchAnswer {
  request_id: string; search: SearchEcho; product: Product; product_name: string | null;
  same_product: Card[]; similar_products: Card[]; page_is_cheapest: boolean; credits_used: number;
}

export interface ReadAnswer extends Product {
  request_id: string; is_product_page: boolean; reason: string | null; credits_used: number;
}

export interface ResolveAnswer { request_id: string; resolved: boolean; url: string | null; retailer: string | null; credits_used: number }

export interface SearchOptions { market?: string; marketplaces?: Marketplace[] | string[]; condition?: Condition; max_results?: number; signal?: AbortSignal }
export interface ExtractOptions { market?: string; signal?: AbortSignal }

export interface FindcheapOptions {
  /** Defaults to FINDCHEAP_API_KEY in the environment (Node). */
  apiKey?: string;
  baseUrl?: string;
  /** One timeout for every call, replacing the per-call defaults (100 s search, 40 s extract, 20 s resolve). */
  timeoutMs?: number;
  /** A fetch to use instead of the global one (tests, polyfills). */
  fetch?: typeof fetch;
}

/** Anything that stopped a call: the API's answer (FindcheapApiError) or the network (FindcheapConnectionError). */
export class FindcheapError extends Error {}

/**
 * The API answered an error: its envelope's type, message, credits_used and request_id, plus the HTTP status.
 * `type` is one of the reference's (invalid_request, invalid_url, unknown_market, unauthorized, credits_exhausted,
 * account_suspended, not_searchable, refused, rate_limited, unreachable, timeout, search_failed,
 * account_service_unavailable), or "http_error" when the body was not the API's envelope (a proxy's page).
 */
export class FindcheapApiError extends FindcheapError {
  constructor(
    public readonly status: number,
    public readonly type: string,
    message: string,
    public readonly credits_used: number = 0,
    public readonly request_id: string | null = null,
    /** The 429's Retry-After, in seconds; null otherwise. */
    public readonly retry_after: number | null = null,
  ) {
    super(`${status} ${type}: ${message}`);
    this.name = "FindcheapApiError";
  }
  /** The API's sentence alone, without the status and type. */
  get detail(): string { return this.message.replace(`${this.status} ${this.type}: `, ""); }
}

/** The call never got an answer: no connection, a DNS failure, or the client's own timeout. */
export class FindcheapConnectionError extends FindcheapError {
  constructor(message: string, public readonly cause?: unknown) { super(message); this.name = "FindcheapConnectionError"; }
}

export class Findcheap {
  private readonly key: string;
  private readonly base: string;
  private readonly timeoutMs?: number;
  private readonly fetchFn: typeof fetch;

  constructor(options: FindcheapOptions = {}) {
    const key = options.apiKey ?? (typeof process !== "undefined" ? process.env?.FINDCHEAP_API_KEY : undefined);
    if (!key) {
      throw new Error("Findcheap needs an API key: pass { apiKey } or set FINDCHEAP_API_KEY (create one at https://findcheap.ai/signin?next=/dashboard/keys).");
    }
    this.key = key;
    this.base = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/$/, "");
    this.timeoutMs = options.timeoutMs;
    this.fetchFn = options.fetch ?? globalThis.fetch;
    if (!this.fetchFn) throw new Error("Findcheap needs fetch: Node 18+, a browser, or pass { fetch }.");
  }

  /** Where the product on the page is sold for less (10 credits; up to 90 s). Only the options given travel. */
  search(url: string, options: SearchOptions = {}): Promise<SearchAnswer> {
    const body: Record<string, unknown> = { url };
    if (options.market !== undefined) body.market = options.market;
    if (options.marketplaces !== undefined) body.marketplaces = options.marketplaces;
    if (options.condition !== undefined && options.condition !== "new") body.condition = options.condition;
    if (options.max_results !== undefined) body.max_results = options.max_results;
    return this.post<SearchAnswer>("/v1/search", body, SEARCH_TIMEOUT_MS, options.signal);
  }

  /** What the page sells, without a search (1 credit; up to 30 s). */
  extract(url: string, options: ExtractOptions = {}): Promise<ReadAnswer> {
    const body: Record<string, unknown> = { url };
    if (options.market !== undefined) body.market = options.market;
    return this.post<ReadAnswer>("/v1/extract", body, EXTRACT_TIMEOUT_MS, options.signal);
  }

  /** The merchant's link for a card that came with a resolve_id (1 credit when a link came back). */
  resolve(resolveId: string, options: { signal?: AbortSignal } = {}): Promise<ResolveAnswer> {
    return this.post<ResolveAnswer>("/v1/resolve", { id: resolveId }, RESOLVE_TIMEOUT_MS, options.signal);
  }

  private async post<T>(path: string, body: Record<string, unknown>, defaultTimeoutMs: number, signal?: AbortSignal): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(new Error("timeout")), this.timeoutMs ?? defaultTimeoutMs);
    const onAbort = () => controller.abort(signal?.reason);
    signal?.addEventListener("abort", onAbort, { once: true });
    const headers: Record<string, string> = { Authorization: `Bearer ${this.key}`, "Content-Type": "application/json", Accept: "application/json" };
    // Browsers set their own User-Agent and refuse this header; Node sends it.
    if (typeof window === "undefined") headers["User-Agent"] = `findcheap-js/${VERSION}`;
    let response: Response;
    try {
      response = await this.fetchFn(this.base + path, { method: "POST", headers, body: JSON.stringify(body), signal: controller.signal });
    } catch (cause) {
      throw new FindcheapConnectionError(`Findcheap could not be reached: ${(cause as Error)?.message ?? String(cause)}`, cause);
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
    }
    const text = await response.text();
    if (!response.ok) throw apiError(response, text);
    return JSON.parse(text) as T;
  }
}

/** The API's envelope as an error; a body that is not the envelope (a proxy's page) is "http_error". */
function apiError(response: Response, text: string): FindcheapApiError {
  let error: Record<string, unknown> = {};
  try { error = (JSON.parse(text) as { error?: Record<string, unknown> }).error ?? {}; } catch { /* not the envelope */ }
  const retry = response.headers.get("Retry-After");
  return new FindcheapApiError(
    response.status,
    typeof error.type === "string" ? error.type : "http_error",
    typeof error.message === "string" ? error.message : (response.statusText || `HTTP ${response.status}`),
    typeof error.credits_used === "number" ? error.credits_used : 0,
    typeof error.request_id === "string" ? error.request_id : null,
    retry && /^\d+$/.test(retry) ? Number(retry) : null,
  );
}
