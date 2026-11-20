"""The client: the three calls, the search by words and the feedback on a
search, each a POST over urllib, the answer as the API sends it.

Nothing is reshaped. A search answer opens with `request_id` and `search`
(what was searched), then `product`, `product_name`, `about_lists` (one
sentence saying what the two lists hold for this search), `same_product`,
`similar_products`, `page_is_cheapest`, `next_steps` (what can be done
next, each with the call that does it), `credits_used`; the TypedDicts
below name the fields for an editor, and `extra="allow"` on the API's
side means a field added later arrives here untouched. A search by words
(search_products) has no page: its answer is `request_id`, `search`,
`about_listings` (one sentence saying what the list holds), `listings`,
`credits_used`.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Literal, Optional, TypedDict

__version__ = "0.3.0"

DEFAULT_BASE_URL = "https://api.findcheap.ai"
# Above the API's own walls (a search answers within 60 s, a read within 30),
# so the API's timeout envelope, not a client cut-off, is what a caller sees.
SEARCH_TIMEOUT_S = 100.0
EXTRACT_TIMEOUT_S = 40.0
RESOLVE_TIMEOUT_S = 20.0
# No search runs behind a feedback report: the same ceiling as resolve.
FEEDBACK_TIMEOUT_S = 20.0

Condition = Literal["new", "used"]
# The feedback call's words: how the search went, which list of the answer a
# card is in (one of a search by URL's two lists, or `listings`, the one
# list of a search by words), and why a card does not belong in its list.
FeedbackRating = Literal["good", "partial", "bad"]
ListName = Literal["same_product", "similar_products", "listings"]
WrongReason = Literal["different_product", "not_equivalent", "price_differs", "unavailable", "other"]


class SearchEcho(TypedDict):
    """What was searched: the address as sent, the market the search ran in, the condition, the cap."""
    url: str
    market: str
    condition: str
    max_results: int


class Product(TypedDict):
    """The page as read."""
    title: Optional[str]
    image: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    brand: Optional[str]
    url: str
    market: str
    in_stock: Optional[bool]
    # The page's own coupon: the marketplace the page belongs to ("Amazon", "Flipkart",
    # "eBay"; None for any other store's page), the coupon or promo code found on the
    # page ("10% coupon", "$5 coupon"; `price` is the page's price before it) and the
    # code to enter at checkout when the coupon is a promo code. None when there is none.
    retailer: Optional[str]
    coupon: Optional[str]
    promo_code: Optional[str]
    # What the listing costs to ship and its return terms, each None when the page's store
    # states none: the shipping cost within the market's country without a paid membership
    # (0 when it ships free; `price` does not include it), whether the seller accepts
    # returns (eBay listings today), the days the buyer has, and who pays the return
    # shipping ("buyer" or "seller").
    shipping_cost: Optional[float]
    returns_accepted: Optional[bool]
    return_days: Optional[int]
    return_shipping_paid_by: Optional[str]
    # The units in the page product's pack (42 for a 42-count tub): the quantity each
    # listing's normalized_price is adjusted to. None for a single item or no count read.
    pack_count: Optional[int]


class Card(TypedDict, total=False):
    """One listing elsewhere. `url` None means a `resolve_id` to pass to resolve()."""
    title: str
    price: float
    currency: str
    url: Optional[str]
    resolve_id: Optional[str]
    image: str
    retailer: str
    rating: Optional[float]
    ratings_count: Optional[int]
    over_page_price: Optional[bool]   # True at or over the page's price, False cheaper, None when the page had no price
    unit_size: Optional[str]
    pack_count: Optional[int]
    normalized_price: Optional[float]
    coupon: Optional[str]
    promo_code: Optional[str]
    price_before_discount: Optional[float]
    discount_type: Optional[str]
    discount_value: Optional[float]
    shipping_cost: Optional[float]    # what the retailer charges to ship it: 0 = free, None = unknown; `price` does not include it


class ProductsSearchEcho(TypedDict):
    """What a search by words searched: the words as sent, the market, the price range, the cap."""
    query: str
    market: str
    min_price: Optional[float]        # None when none was sent
    max_price: Optional[float]        # None when none was sent
    max_results: int                  # the cap on the list: the one sent, or 10


class ProductsSearchAnswer(TypedDict):
    request_id: str
    search: ProductsSearchEcho
    about_listings: str               # what the list holds for this search; read it before the list
    # Listings that match the words, cheapest first, up to 10; empty when none was found. A listing is a
    # Card without over_page_price and normalized_price: there is no page to compare a price with.
    listings: List[Card]
    credits_used: int                 # 10 for a search by words, with or without listings


class NextStep(TypedDict):
    """One thing that can be done next for the product, with the call that does it."""
    label: str                        # the step in a few words, as a person reads it; also a button's words
    tool: str                         # the MCP tool that runs it; on the API, find_cheaper is search()
    arguments: Dict[str, Any]         # the fields to send
    choose: Optional[Dict[str, Any]]  # on a step that needs a choice: {"marketplaces": [the market's stores]}; send the ones to keep


class SearchAnswer(TypedDict):
    request_id: str
    search: SearchEcho
    product: Product
    product_name: Optional[str]
    about_lists: str                  # what the two lists hold for this search; read it before them
    same_product: List[Card]
    similar_products: List[Card]
    page_is_cheapest: bool
    next_steps: List[NextStep]        # do one yourself when it serves the user's task, or offer them as next steps
    credits_used: int


class ReadAnswer(TypedDict):
    request_id: str
    is_product_page: bool
    url: str
    market: str
    title: Optional[str]
    image: Optional[str]
    price: Optional[float]
    currency: Optional[str]
    brand: Optional[str]
    in_stock: Optional[bool]
    # The page's own coupon, as in Product above.
    retailer: Optional[str]
    coupon: Optional[str]
    promo_code: Optional[str]
    # The listing's shipping cost and return terms, as in Product above.
    shipping_cost: Optional[float]
    returns_accepted: Optional[bool]
    return_days: Optional[int]
    return_shipping_paid_by: Optional[str]
    reason: Optional[str]
    next_steps: List[NextStep]        # the search for this product ("Find this cheaper"); empty when the page cannot be searched
    credits_used: int


class ResolveAnswer(TypedDict):
    request_id: str
    resolved: bool
    url: Optional[str]
    retailer: Optional[str]
    credits_used: int


class UsefulCard(TypedDict):
    """In a feedback report: a card that was shown or recommended."""
    list: ListName                    # the list of the search answer the card is in
    position: int                     # its place in that list, counted from 1 (1 to 10)


class WrongCard(TypedDict):
    """In a feedback report: a card that does not belong in its list, with the reason."""
    list: ListName
    position: int                     # its place in that list, counted from 1 (1 to 10)
    reason: WrongReason


class CheaperElsewhere(TypedDict, total=False):
    """In a feedback report: a cheaper listing found elsewhere that the answer did not have."""
    url: str                          # the listing's address: always sent
    price: Optional[float]            # may be left out


class FeedbackAnswer(TypedDict):
    request_id: str                   # this feedback call's own id, not the search's
    recorded: bool
    already_reported: bool            # the search already had a report: the first one stands, this one changed nothing
    credits_refunded: int             # 0 or 1: the first report on a search gives 1 credit back
    refunded_today: int               # credits given back to the account for feedback so far today (UTC)
    daily_refund_cap: int             # the most credits feedback gives back to an account in a day: 100
    daily_cap_reached: bool
    credits_used: int                 # always 0: sending feedback costs nothing


class FindcheapError(Exception):
    """Anything that stopped a call: the API's answer (FindcheapApiError) or the network (FindcheapConnectionError)."""


class FindcheapApiError(FindcheapError):
    """The API answered an error: its envelope's type, message, credits_used and request_id, plus the HTTP status.

    `type` is one of the reference's: invalid_request, invalid_url, unknown_market, unauthorized,
    credits_exhausted, account_suspended, not_searchable, refused, rate_limited, unreachable,
    timeout, search_failed, account_service_unavailable, and the feedback call's search_not_found
    and feedback_off — or "http_error" when the body was not the API's envelope (a proxy's page).
    `retry_after` is the 429's header, in seconds, else None.
    """

    def __init__(self, status: int, type_: str, message: str, credits_used: int = 0,
                 request_id: Optional[str] = None, retry_after: Optional[int] = None):
        super().__init__(f"{status} {type_}: {message}")
        self.status, self.type, self.message = status, type_, message
        self.credits_used, self.request_id, self.retry_after = credits_used, request_id, retry_after


class FindcheapConnectionError(FindcheapError):
    """The call never got an answer: no connection, a DNS failure, or the client's own timeout."""


class Findcheap:
    """The client. `api_key` defaults to the FINDCHEAP_API_KEY environment variable; `timeout`, when
    given, replaces the per-call defaults (100 s for either search, 40 s extract, 20 s resolve and feedback)."""

    def __init__(self, api_key: Optional[str] = None, *, base_url: str = DEFAULT_BASE_URL,
                 timeout: Optional[float] = None, user_agent: Optional[str] = None):
        key = api_key or os.environ.get("FINDCHEAP_API_KEY")
        if not key:
            raise ValueError("Findcheap needs an API key: pass api_key=... or set FINDCHEAP_API_KEY "
                             "(create one at https://findcheap.ai/signin?next=/dashboard/keys).")
        self._key = key
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._user_agent = user_agent or f"findcheap-python/{__version__}"

    # ── The three calls ──────────────────────────────────────────────

    def search(self, url: str, *, market: Optional[str] = None, marketplaces: Optional[List[str]] = None,
               condition: Condition = "new", max_results: Optional[int] = None) -> SearchAnswer:
        """Where the product on the page is sold for less (10 credits; up to 60 s). Only the options
        given travel in the body, so the API's defaults apply to the rest."""
        body: Dict[str, Any] = {"url": url}
        if market is not None:
            body["market"] = market
        if marketplaces is not None:
            body["marketplaces"] = list(marketplaces)
        if condition != "new":
            body["condition"] = condition
        if max_results is not None:
            body["max_results"] = max_results
        return self._post("/v1/search", body, SEARCH_TIMEOUT_S)  # type: ignore[return-value]

    def search_products(self, query: str, *, market: str, objective: Optional[str] = None,
                        min_price: Optional[float] = None, max_price: Optional[float] = None,
                        max_results: Optional[int] = None) -> ProductsSearchAnswer:
        """Listings that match a description in words, cheapest first (10 credits, with or without
        listings; usually about 6 s, at most 60). For when there is no product page to start from; with
        a page's address, search() finds that product for less.

        `query` is what the shopper is looking for, in the shopper's own words: a kind of product ("TV")
        or a named product ("Insignia Fire TV"), one product per call, with everything the shopper asked
        for (the brand, the model, a size, a colour). `market` is the shopper's country (US, CA, AU, IN or
        GLOBAL) and is required: there is no address to infer it from. `objective` is one sentence on
        what the shopper wants, never anything personal about them. `min_price` and `max_price` are in
        the market's currency. Only the options given travel in the body."""
        body: Dict[str, Any] = {"query": query, "market": market}
        if objective is not None:
            body["objective"] = objective
        if min_price is not None:
            body["min_price"] = min_price
        if max_price is not None:
            body["max_price"] = max_price
        if max_results is not None:
            body["max_results"] = max_results
        return self._post("/v1/products/search", body, SEARCH_TIMEOUT_S)  # type: ignore[return-value]

    def extract(self, url: str, *, market: Optional[str] = None) -> ReadAnswer:
        """What the page sells, without a search (1 credit; up to 30 s)."""
        body: Dict[str, Any] = {"url": url}
        if market is not None:
            body["market"] = market
        return self._post("/v1/extract", body, EXTRACT_TIMEOUT_S)  # type: ignore[return-value]

    def resolve(self, resolve_id: str) -> ResolveAnswer:
        """The merchant's link for a card that came with a resolve_id (1 credit when a link came back)."""
        return self._post("/v1/resolve", {"id": resolve_id}, RESOLVE_TIMEOUT_S)  # type: ignore[return-value]

    # ── Feedback on a search ─────────────────────────────────────────

    def feedback(self, request_id: str, rating: FeedbackRating, *,
                 useful_cards: Optional[List[UsefulCard]] = None, wrong_cards: Optional[List[WrongCard]] = None,
                 cheaper_elsewhere: Optional[List[CheaperElsewhere]] = None, missing: Optional[List[str]] = None,
                 goal: Optional[str] = None, note: Optional[str] = None) -> FeedbackAnswer:
        """How a search went, reported by the `request_id` of its answer (costs nothing; the first report
        on a search gives 1 credit back, up to 100 credits a day). One report per search, within 20
        minutes of the search. Send the rating and at least one other field: only the fields given
        travel in the body, and the API refuses a rating alone (400 invalid_request). It works the
        same for a search by URL (`search`) and a search by words (`search_products`), whose cards
        are named in the list `listings`.

        `useful_cards` are the cards that were shown or recommended, `wrong_cards` the cards that do not
        belong in their list, `cheaper_elsewhere` cheaper listings found elsewhere that the answer did
        not have, `missing` short sentences on what was expected and not returned (each list at most 20
        items). `goal` is one sentence on what the shopper was trying to do (the API cuts it at 300
        characters); `note` is anything else, short (cut at 1,000)."""
        body: Dict[str, Any] = {"rating": rating}
        # The lists travel as they were given, without the list() copy search() makes: list() would
        # turn one sentence passed bare as `missing` into its letters, a report the API could take.
        if useful_cards is not None:
            body["useful_cards"] = useful_cards
        if wrong_cards is not None:
            body["wrong_cards"] = wrong_cards
        if cheaper_elsewhere is not None:
            body["cheaper_elsewhere"] = cheaper_elsewhere
        if missing is not None:
            body["missing"] = missing
        if goal is not None:
            body["goal"] = goal
        if note is not None:
            body["note"] = note
        # The search's id is one segment of the path, so all of it is escaped: with safe="" a
        # slash becomes %2F too.
        path = f"/v1/search/{urllib.parse.quote(request_id, safe='')}/feedback"
        return self._post(path, body, FEEDBACK_TIMEOUT_S)  # type: ignore[return-value]

    # ── The wire ─────────────────────────────────────────────────────

    def _post(self, path: str, body: Dict[str, Any], default_timeout: float) -> Dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self._base + path, data=data, method="POST",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
                     "Accept": "application/json", "User-Agent": self._user_agent})
        timeout = self._timeout if self._timeout is not None else default_timeout
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise _api_error(exc) from None
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
            raise FindcheapConnectionError(f"Findcheap could not be reached: {exc}") from exc


def _api_error(exc: urllib.error.HTTPError) -> FindcheapApiError:
    """The API's envelope as an exception; a body that is not the envelope (a proxy's page) is
    "http_error" with the status's reason."""
    raw = exc.read()
    try:
        error = json.loads(raw.decode("utf-8")).get("error") or {}
    except (ValueError, UnicodeDecodeError):
        error = {}
    retry_after = exc.headers.get("Retry-After") if exc.headers else None
    return FindcheapApiError(
        exc.code, str(error.get("type") or "http_error"),
        str(error.get("message") or exc.reason or f"HTTP {exc.code}"),
        credits_used=int(error.get("credits_used") or 0), request_id=error.get("request_id"),
        retry_after=int(retry_after) if retry_after and str(retry_after).isdigit() else None)
