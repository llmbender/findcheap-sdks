"""The client: three POSTs over urllib, the answer as the API sends it.

Nothing is reshaped. A search answer opens with `request_id` and `search`
(what was searched), then `product`, `product_name`, `about_lists` (one
sentence saying what the two lists hold for this search), `same_product`,
`similar_products`, `page_is_cheapest`, `next_steps` (what can be done
next, each with the call that does it), `credits_used`; the TypedDicts
below name the fields for an editor, and `extra="allow"` on the API's
side means a field added later arrives here untouched.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List, Literal, Optional, TypedDict

__version__ = "0.1.0"

DEFAULT_BASE_URL = "https://api.findcheap.ai"
# Above the API's own walls (a search answers within 60 s, a read within 30),
# so the API's timeout envelope, not a client cut-off, is what a caller sees.
SEARCH_TIMEOUT_S = 100.0
EXTRACT_TIMEOUT_S = 40.0
RESOLVE_TIMEOUT_S = 20.0

Condition = Literal["new", "used"]


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
    reason: Optional[str]
    credits_used: int


class ResolveAnswer(TypedDict):
    request_id: str
    resolved: bool
    url: Optional[str]
    retailer: Optional[str]
    credits_used: int


class FindcheapError(Exception):
    """Anything that stopped a call: the API's answer (FindcheapApiError) or the network (FindcheapConnectionError)."""


class FindcheapApiError(FindcheapError):
    """The API answered an error: its envelope's type, message, credits_used and request_id, plus the HTTP status.

    `type` is one of the reference's: invalid_request, invalid_url, unknown_market, unauthorized,
    credits_exhausted, account_suspended, not_searchable, refused, rate_limited, unreachable,
    timeout, search_failed, account_service_unavailable — or "http_error" when the body was not
    the API's envelope (a proxy's page). `retry_after` is the 429's header, in seconds, else None.
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
    given, replaces the per-call defaults (100 s search, 40 s extract, 20 s resolve)."""

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

    def extract(self, url: str, *, market: Optional[str] = None) -> ReadAnswer:
        """What the page sells, without a search (1 credit; up to 30 s)."""
        body: Dict[str, Any] = {"url": url}
        if market is not None:
            body["market"] = market
        return self._post("/v1/extract", body, EXTRACT_TIMEOUT_S)  # type: ignore[return-value]

    def resolve(self, resolve_id: str) -> ResolveAnswer:
        """The merchant's link for a card that came with a resolve_id (1 credit when a link came back)."""
        return self._post("/v1/resolve", {"id": resolve_id}, RESOLVE_TIMEOUT_S)  # type: ignore[return-value]

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
