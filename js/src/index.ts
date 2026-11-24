/*
 * The Findcheap API in TypeScript: the three calls, the search by words and
 * the feedback on a search, each a POST over fetch, the answer as the API
 * sends it. Nothing
 * is reshaped: a search answer opens with `request_id` and `search` (what
 * was searched), then `product`, `product_name`, `about_lists` (one
 * sentence saying what the two lists hold for this search), `same_product`,
 * `similar_products`, `page_is_cheapest`, `next_steps` (what can be done
 * next, each with the call that does it), `credits_used`. A search by words
 * (searchProducts) has no page: its answer is `request_id`, `search`,
 * `about_listings` (one sentence saying what the list holds), `listings`,
 * `credits_used`.
 * Reference: https://findcheap.ai/developers/docs.md
 */

export const VERSION = "0.4.0";
export const DEFAULT_BASE_URL = "https://api.findcheap.ai";
// Above the API's own walls (a search answers within 60 s, a read within 30),
// so the API's timeout envelope, not a client cut-off, is what a caller sees.
export const SEARCH_TIMEOUT_MS = 100_000;
export const EXTRACT_TIMEOUT_MS = 40_000;
export const RESOLVE_TIMEOUT_MS = 20_000;
// No search runs behind a feedback report: the same ceiling as resolve.
export const FEEDBACK_TIMEOUT_MS = 20_000;

export type Condition = "new" | "used";
export type Marketplace = "amazon" | "walmart" | "ebay" | "aliexpress" | "shein" | "flipkart" | "other_sites";

/** What was searched: the address as sent, the market the search ran in, the condition, the cap. */
export interface SearchEcho { url: string; market: string; condition: Condition; max_results: number }

/** The page as read. */
export interface Product {
  title: string | null; image: string | null; price: number | null; currency: string | null;
  brand: string | null; url: string; market: string; in_stock: boolean | null;
  /** The page's own coupon: the marketplace the page belongs to ("Amazon", "Flipkart", "eBay"; null for any other store's page), the coupon or promo code found on the page ("10% coupon", "$5 coupon"; `price` is the page's price before it) and the code to enter at checkout when the coupon is a promo code. Null when there is none. */
  retailer?: string | null; coupon?: string | null; promo_code?: string | null;
  /** What the listing costs to ship and its return terms, each null when the page's store states none: the shipping cost within the market's country without a paid membership (0 when it ships free; `price` does not include it), whether the seller accepts returns (eBay listings today), the days the buyer has, and who pays the return shipping. */
  shipping_cost?: number | null; returns_accepted?: boolean | null; return_days?: number | null;
  return_shipping_paid_by?: "buyer" | "seller" | null;
  /** In a search answer only. The units in the page product's pack (42 for a 42-count tub): the quantity each listing's normalized_price is adjusted to. Null for a single item or no count read. */
  pack_count?: number | null;
}

/** One listing elsewhere. `url` null means a `resolve_id` to pass to resolve(). */
export interface Card {
  title: string; price: number; currency: string; url: string | null; resolve_id?: string | null;
  image: string; retailer: string; rating?: number | null; ratings_count?: number | null;
  /** True at or over the page's price, false cheaper, null when the page had no price. On cards of both lists. */
  over_page_price?: boolean | null;
  unit_size?: string | null; pack_count?: number | null; normalized_price?: number | null;
  coupon?: string | null; promo_code?: string | null; price_before_discount?: number | null;
  discount_type?: "percent" | "fixed" | null; discount_value?: number | null;
  /** What the retailer charges to ship the listing within the market's country, without a paid membership: 0 when it ships free, null when unknown. `price` does not include it. */
  shipping_cost?: number | null;
  [extra: string]: unknown;
}

/**
 * What a search by words or by photo searched, as sent. One of the first three names it: `query` for words,
 * `image_url` for a photo's link, `image_file` for a photo sent as image_base64 ("sha256:" and the first 16 characters
 * of the file's SHA-256). Then the market, the price range (null when none was sent) and the cap.
 */
export interface ProductsSearchEcho {
  query?: string | null; image_url?: string | null; image_file?: string;
  market: string; min_price: number | null; max_price: number | null; max_results: number;
}

export interface ProductsSearchAnswer {
  request_id: string; search: ProductsSearchEcho;
  /** What the list holds for this search, in a sentence. Read it before the list. */
  about_listings: string;
  /** Listings that match the words, cheapest first, up to 10; empty when none was found. A listing is a Card without over_page_price and normalized_price: there is no page to compare a price with. */
  listings: Card[];
  /** 10 for a search by words, with or without listings. */
  credits_used: number;
}

/** One thing that can be done next for the product, with the call that does it. */
export interface NextStep {
  /** The step in a few words, as a person reads it. Also the words for a button. */
  label: string;
  /** The MCP tool that runs it. On the API, find_cheaper is search(). */
  tool: string;
  /** The fields to send. */
  arguments: Record<string, unknown>;
  /** Only on a step that needs a choice, else null: the market's stores under `marketplaces`. Send the ones to keep. */
  choose: { marketplaces?: string[]; [extra: string]: unknown } | null;
}

export interface SearchAnswer {
  request_id: string; search: SearchEcho; product: Product; product_name: string | null;
  /** What the two lists hold for this search, in a sentence or two. Read it before the lists. */
  about_lists: string;
  same_product: Card[]; similar_products: Card[]; page_is_cheapest: boolean;
  /** What can be done next. Do one yourself when it serves the user's task, or offer them as next steps. */
  next_steps: NextStep[];
  credits_used: number;
}

export interface ReadAnswer extends Product {
  request_id: string; is_product_page: boolean; reason: string | null;
  /** What can be done next: the search for this product ("Find this cheaper"). Empty when the page cannot be searched. */
  next_steps: NextStep[];
  credits_used: number;
}

export interface ResolveAnswer { request_id: string; resolved: boolean; url: string | null; retailer: string | null; credits_used: number }

export interface FeedbackAnswer {
  /** This feedback call's own id, not the search's. */
  request_id: string;
  recorded: boolean;
  /** The search already had a report: the first one stands and this one changed nothing. */
  already_reported: boolean;
  /** 0 or 1: the first report on a search gives 1 credit back. */
  credits_refunded: number;
  /** Credits given back to the account for feedback so far today (UTC). */
  refunded_today: number;
  /** The most credits feedback gives back to an account in a day: 100. */
  daily_refund_cap: number;
  daily_cap_reached: boolean;
  /** Always 0: sending feedback costs nothing. */
  credits_used: number;
}

/** `objective` is one sentence on what the shopper wants, never anything personal about them. `signal` cancels the call. */
export interface SearchOptions { market?: string; marketplaces?: Marketplace[] | string[]; condition?: Condition; max_results?: number; objective?: string; signal?: AbortSignal }
export interface ExtractOptions { market?: string; objective?: string; signal?: AbortSignal }
/** A search by words or by photo: `market` is required (US, CA, AU, IN or GLOBAL: there is no address to infer it from); the rest is optional. `signal` cancels the call. */
export interface ProductsSearchOptions {
  /** The shopper's market, the country they are buying in. */
  market: string;
  /** A photo of the product, as a public https link to the image, when the shopper has a photo instead of words. Pass `null` as the query. */
  image_url?: string;
  /** A photo of the product itself, as base64 text, when there is no link to it: a JPEG, PNG or WebP of 10 MB at most. Pass `null` as the query. */
  image_base64?: string;
  /** What the shopper wants, in one sentence. Nothing personal about the shopper. */
  objective?: string;
  /** The lowest price to include, in the market's currency. */
  min_price?: number;
  /** The highest price to include, in the market's currency. */
  max_price?: number;
  /** How many listings at most, 1 to 10; 10 when omitted. The credits are the same whatever the cap. */
  max_results?: number;
  signal?: AbortSignal;
}

/** How a search went: the feedback call's rating. */
export type FeedbackRating = "good" | "partial" | "bad";
/** Which list of a search answer a card is in: one of a search by URL's two lists, or `listings`, the one list of a search by words. */
export type ListName = "same_product" | "similar_products" | "listings";
/** Why a card does not belong in its list. */
export type WrongReason = "different_product" | "not_equivalent" | "price_differs" | "unavailable" | "other";

/** In a feedback report: a card that was shown or recommended. `position` is its place in its list, counted from 1 (1 to 10). */
export interface UsefulCard { list: ListName; position: number }
/** In a feedback report: a card that does not belong in its list, with the reason. `position` counts from 1 within that list (1 to 10). */
export interface WrongCard { list: ListName; position: number; reason: WrongReason }
/** In a feedback report: a cheaper listing found elsewhere that the answer did not have. `price` may be left out. */
export interface CheaperElsewhere { url: string; price?: number | null }

/** What a feedback report carries beside its rating: send at least one of the six fields (each list takes at most 20 items). `signal` cancels the call and is no part of the report. */
export interface FeedbackOptions {
  /** The cards that were shown or recommended. */
  useful_cards?: UsefulCard[];
  /** Cards that do not belong in their list. */
  wrong_cards?: WrongCard[];
  /** Cheaper listings found elsewhere that the answer did not have. */
  cheaper_elsewhere?: CheaperElsewhere[];
  /** Short sentences: what was expected and not returned. */
  missing?: string[];
  /** One sentence: what the shopper was trying to do. The API cuts it at 300 characters. */
  goal?: string;
  /** Anything else, short. The API cuts it at 1,000 characters. */
  note?: string;
  signal?: AbortSignal;
}

export interface FindcheapOptions {
  /** Defaults to FINDCHEAP_API_KEY in the environment (Node). */
  apiKey?: string;
  baseUrl?: string;
  /** One timeout for every call, replacing the per-call defaults (100 s for either search, 40 s extract, 20 s resolve and feedback). */
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
 * account_service_unavailable, and the feedback call's search_not_found and feedback_off), or "http_error" when
 * the body was not the API's envelope (a proxy's page).
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

  /** Where the product on the page is sold for less (10 credits; up to 60 s). Only the options given travel. */
  search(url: string, options: SearchOptions = {}): Promise<SearchAnswer> {
    const body: Record<string, unknown> = { url };
    if (options.market !== undefined) body.market = options.market;
    if (options.marketplaces !== undefined) body.marketplaces = options.marketplaces;
    if (options.condition !== undefined && options.condition !== "new") body.condition = options.condition;
    if (options.max_results !== undefined) body.max_results = options.max_results;
    if (options.objective !== undefined) body.objective = options.objective;
    return this.post<SearchAnswer>("/v1/search", body, SEARCH_TIMEOUT_MS, options.signal);
  }

  /**
   * Listings that match a description in words, cheapest first (10 credits, with or without listings; usually about
   * 6 s, at most 60). For when there is no product page to start from; with a page's address, search() finds that
   * product for less. `query` is what the shopper is looking for, in the shopper's own words: a kind of product ("TV")
   * or a named product ("Insignia Fire TV"), one product per call. Only the options given travel.
   *
   * Or search from a photo, when the shopper has a photo of the product and no words for it: pass `null` as the query
   * and give `image_url` (a link to the photo) or `image_base64` (the photo's file itself) in the options. Send only one
   * of the three; the API refuses a call with none or with more than one. With a photo it usually takes about 15 s.
   */
  searchProducts(query: string | null, options: ProductsSearchOptions): Promise<ProductsSearchAnswer> {
    const body: Record<string, unknown> = { market: options.market };
    if (query !== null && query !== undefined) body.query = query;
    if (options.image_url !== undefined) body.image_url = options.image_url;
    if (options.image_base64 !== undefined) body.image_base64 = options.image_base64;
    if (options.objective !== undefined) body.objective = options.objective;
    if (options.min_price !== undefined) body.min_price = options.min_price;
    if (options.max_price !== undefined) body.max_price = options.max_price;
    if (options.max_results !== undefined) body.max_results = options.max_results;
    return this.post<ProductsSearchAnswer>("/v1/products/search", body, SEARCH_TIMEOUT_MS, options.signal);
  }

  /** What the page sells, without a search (1 credit; up to 30 s). */
  extract(url: string, options: ExtractOptions = {}): Promise<ReadAnswer> {
    const body: Record<string, unknown> = { url };
    if (options.market !== undefined) body.market = options.market;
    if (options.objective !== undefined) body.objective = options.objective;
    return this.post<ReadAnswer>("/v1/extract", body, EXTRACT_TIMEOUT_MS, options.signal);
  }

  /** The merchant's link for a card that came with a resolve_id (1 credit when a link came back). */
  resolve(resolveId: string, options: { signal?: AbortSignal } = {}): Promise<ResolveAnswer> {
    return this.post<ResolveAnswer>("/v1/resolve", { id: resolveId }, RESOLVE_TIMEOUT_MS, options.signal);
  }

  /**
   * How a search went, reported by the `request_id` of its answer (costs nothing; the first report on a search gives
   * 1 credit back, up to 100 credits a day). One report per search, within 20 minutes of the search. Send the rating
   * and at least one other field: only the fields given travel, and the API refuses a rating alone (400 invalid_request).
   * It works the same for a search by URL (`search`) and a search by words (`searchProducts`), whose cards are named
   * in the list `listings`.
   */
  feedback(requestId: string, rating: FeedbackRating, options: FeedbackOptions = {}): Promise<FeedbackAnswer> {
    const body: Record<string, unknown> = { rating };
    if (options.useful_cards !== undefined) body.useful_cards = options.useful_cards;
    if (options.wrong_cards !== undefined) body.wrong_cards = options.wrong_cards;
    if (options.cheaper_elsewhere !== undefined) body.cheaper_elsewhere = options.cheaper_elsewhere;
    if (options.missing !== undefined) body.missing = options.missing;
    if (options.goal !== undefined) body.goal = options.goal;
    if (options.note !== undefined) body.note = options.note;
    // The search's id is one segment of the path, so all of it is escaped: a slash becomes %2F too.
    return this.post<FeedbackAnswer>(`/v1/search/${encodeURIComponent(requestId)}/feedback`, body, FEEDBACK_TIMEOUT_MS, options.signal);
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
