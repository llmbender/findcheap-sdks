"""A local stub of the Findcheap API for the tests: offline, no network beyond
this machine, no key, no spend. It answers the five calls with fixed answers,
refuses a few fixed inputs the way the API does, and keeps what it was sent."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

KEY = "fc_live_test"

SEARCH = {
    "request_id": "r-1",
    "search": {"url": "https://shop.example.com/p/1", "market": "US", "condition": "new", "max_results": 10},
    "product": {"title": "Kettle", "image": None, "price": 29.99, "currency": "USD", "brand": "Acme",
                "url": "https://shop.example.com/p/1", "market": "US", "in_stock": True, "retailer": "Amazon",
                "coupon": None, "promo_code": None, "shipping_cost": 0.0, "returns_accepted": None,
                "return_days": None, "return_shipping_paid_by": None, "pack_count": None},
    "product_name": "Acme Kettle",
    "about_lists": "same_product holds listings that match the original product. similar_products holds "
                   "acceptable equivalent products from any brand.",
    "same_product": [{"title": "Kettle", "price": 19.0, "currency": "USD", "url": "https://w/x", "image": "i",
                      "retailer": "eBay", "over_page_price": False}],
    "similar_products": [{"title": "Other kettle", "price": 15.0, "currency": "USD", "url": None,
                          "resolve_id": "abc", "image": "i", "retailer": "Best Buy", "over_page_price": False}],
    "page_is_cheapest": False,
    "next_steps": [{"label": "Find pre-owned", "tool": "find_cheaper",
                    "arguments": {"url": "https://shop.example.com/p/1", "market": "US", "condition": "used"},
                    "choose": None}],
    "credits_used": 10,
}
READ = {"request_id": "r-2", "is_product_page": True, "url": "https://shop.example.com/p/1", "market": "US",
        "title": "Kettle", "image": None, "price": 29.99, "currency": "USD", "brand": "Acme", "in_stock": True,
        "retailer": "eBay", "coupon": None, "promo_code": None, "shipping_cost": 7.36, "returns_accepted": True,
        "return_days": 30, "return_shipping_paid_by": "seller", "reason": None, "next_steps": [], "credits_used": 1}
RESOLVE = {"request_id": "r-3", "resolved": True, "url": "https://merchant/x", "retailer": "Walmart", "credits_used": 1}
PRODUCTS = {"request_id": "r-5",
            "search": {"query": "Insignia Fire TV", "market": "US", "min_price": None, "max_price": 200.0, "max_results": 10},
            "about_listings": "listings holds listings that match the words you searched for, cheapest first.",
            "listings": [{"title": "Insignia 32in Fire TV", "price": 65.0, "currency": "USD", "url": "https://w/tv",
                          "image": "i", "retailer": "eBay"}],
            "credits_used": 10}
FEEDBACK = {"request_id": "r-4", "recorded": True, "already_reported": False, "credits_refunded": 1,
            "refunded_today": 3, "daily_refund_cap": 100, "daily_cap_reached": False, "credits_used": 0}


def _error(type_, message, credits_used=0, request_id="e-0"):
    return {"error": {"type": type_, "message": message, "credits_used": credits_used, "request_id": request_id}}


class Stub:
    """One stub server on a free local port. `seen` holds every request as
    (path, headers, body), oldest first."""

    def __init__(self):
        seen = self.seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append((self.path, dict(self.headers), body))
                if self.headers.get("Authorization") != f"Bearer {KEY}":
                    return self._send(401, _error("unauthorized", "No key."))
                if body.get("url") == "https://en.wikipedia.org/wiki/Shoe":
                    return self._send(422, _error("not_searchable", "Not a product page. Billed as a page read: 1 credit.", 1))
                if body.get("url") == "https://slow.example/p":
                    return self._send(429, _error("rate_limited", "Wait."), {"Retry-After": "7"})
                if self.path == "/v1/products/search" and ("query" in body) == ("image_url" in body):
                    return self._send(400, _error("invalid_request", "Send query or image_url, one of the two."))
                if self.path.startswith("/v1/search/") and self.path.endswith("/feedback"):
                    if set(body) == {"rating"}:
                        return self._send(400, _error("invalid_request", "Send the rating and at least one other field."))
                    return self._send(200, FEEDBACK)
                answers = {"/v1/search": SEARCH, "/v1/extract": READ, "/v1/resolve": RESOLVE,
                           "/v1/products/search": PRODUCTS}
                if self.path in answers:
                    return self._send(200, answers[self.path])
                return self._send(404, _error("not_found", "No such call."))

            def _send(self, status, payload, headers=None):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                for name, value in (headers or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):   # keep the test output quiet
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self):
        self._server.shutdown()
        self._server.server_close()
