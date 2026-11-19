"""Offline tests of the Python client over a local stub of the API: no network, no key, no spend.

    cd findcheap-sdks/python && python3 -m unittest -v
"""
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from findcheap import Findcheap, FindcheapApiError, FindcheapConnectionError  # noqa: E402

SEARCH = {"request_id": "r-1", "search": {"url": "https://shop.example.com/p/1", "market": "US", "condition": "new", "max_results": 3},
          "product": {"title": "Kettle", "image": None, "price": 29.99, "currency": "USD", "brand": "Acme", "url": "https://shop.example.com/p/1", "market": "US", "in_stock": True, "retailer": "Amazon", "coupon": "10% coupon", "promo_code": None, "shipping_cost": 0.0, "returns_accepted": None, "return_days": None, "return_shipping_paid_by": None, "pack_count": None},
          "product_name": "Acme Kettle",
          "about_lists": "same_product holds listings that match the original product; a different colour or pack size still counts as the same product. similar_products holds acceptable equivalent products from any brand.",
          "same_product": [{"title": "Kettle", "price": 19.0, "currency": "USD", "url": "https://w/x", "image": "i", "retailer": "eBay", "over_page_price": False}],
          "similar_products": [], "page_is_cheapest": False,
          "next_steps": [{"label": "Find pre-owned", "tool": "find_cheaper", "arguments": {"url": "https://shop.example.com/p/1", "market": "US", "condition": "used"}, "choose": None}],
          "credits_used": 10}
READ = {"request_id": "r-2", "is_product_page": True, "url": "https://shop.example.com/p/1", "market": "US", "title": "Kettle", "image": None,
        "price": 29.99, "currency": "USD", "brand": "Acme", "in_stock": True, "retailer": "eBay", "coupon": "$5 coupon", "promo_code": "SHOPNOW15", "shipping_cost": 7.36, "returns_accepted": True, "return_days": 30, "return_shipping_paid_by": "seller", "reason": None, "credits_used": 1}
RESOLVE = {"request_id": "r-3", "resolved": True, "url": "https://merchant/x", "retailer": "Walmart", "credits_used": 1}
FEEDBACK = {"request_id": "r-4", "recorded": True, "already_reported": False, "credits_refunded": 1, "refunded_today": 3, "daily_refund_cap": 100, "daily_cap_reached": False, "credits_used": 0}
seen = []


class Stub(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append((self.path, dict(self.headers), body))
        if self.headers.get("Authorization") != "Bearer fc_live_test":
            return self._send(401, {"error": {"type": "unauthorized", "message": "No key.", "credits_used": 0, "request_id": "e-0"}})
        if body.get("url") == "https://en.wikipedia.org/wiki/Shoe":
            return self._send(422, {"error": {"type": "not_searchable", "message": "Not a product page. Billed as a page read: 1 credit.", "credits_used": 1, "request_id": "e-1"}})
        if body.get("url") == "https://slow.example/p":
            return self._send(429, {"error": {"type": "rate_limited", "message": "Wait.", "credits_used": 0, "request_id": "e-2"}}, {"Retry-After": "7"})
        if body.get("url") == "https://proxy.example/p":
            self.send_response(502); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(b"<html>Bad Gateway</html>"); return
        # The feedback call carries the search's id in its path. Two ids stand for its own two refusals,
        # and a body holding the rating alone is refused in the API's words.
        if self.path == "/v1/search/r-old/feedback":
            return self._send(404, {"error": {"type": "search_not_found", "message": "No search with this id in the last 20 minutes.", "credits_used": 0, "request_id": "e-3"}})
        if self.path == "/v1/search/r-off/feedback":
            return self._send(403, {"error": {"type": "feedback_off", "message": "Feedback is switched off for this account.", "credits_used": 0, "request_id": "e-4"}})
        if self.path.startswith("/v1/search/") and self.path.endswith("/feedback"):
            if set(body) == {"rating"}:
                return self._send(400, {"error": {"type": "invalid_request", "message": "Send the rating and at least one other field.", "credits_used": 0, "request_id": "e-5"}})
            return self._send(200, FEEDBACK)
        answer = {"/v1/search": SEARCH, "/v1/extract": READ, "/v1/resolve": RESOLVE}[self.path]
        self._send(200, answer)

    def _send(self, status, payload, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, *a):  # quiet
        pass


class ClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.fc = Findcheap(api_key="fc_live_test", base_url=cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_search_sends_only_what_was_given_and_returns_the_answer_as_is(self):
        seen.clear()
        out = self.fc.search("https://shop.example.com/p/1", max_results=3)
        path, headers, body = seen[-1]
        self.assertEqual(path, "/v1/search")
        self.assertEqual(body, {"url": "https://shop.example.com/p/1", "max_results": 3})
        self.assertEqual(headers["Authorization"], "Bearer fc_live_test")
        self.assertTrue(headers["User-Agent"].startswith("findcheap-python/"))
        self.assertEqual(list(out), ["request_id", "search", "product", "product_name", "about_lists", "same_product", "similar_products", "page_is_cheapest", "next_steps", "credits_used"])
        self.assertEqual(out["next_steps"][0]["arguments"]["condition"], "used")
        self.assertEqual(out["credits_used"], 10)

    def test_search_options_travel_as_the_api_takes_them(self):
        seen.clear()
        self.fc.search("https://shop.example.com/p/1", market="in", marketplaces=["amazon", "flipkart"], condition="used")
        self.assertEqual(seen[-1][2], {"url": "https://shop.example.com/p/1", "market": "in", "marketplaces": ["amazon", "flipkart"], "condition": "used"})

    def test_extract_and_resolve(self):
        self.assertEqual(self.fc.extract("https://shop.example.com/p/1", market="US")["title"], "Kettle")
        self.assertEqual(seen[-1][2], {"url": "https://shop.example.com/p/1", "market": "US"})
        self.assertEqual(self.fc.resolve("abc")["retailer"], "Walmart")
        self.assertEqual(seen[-1][0], "/v1/resolve")
        self.assertEqual(seen[-1][2], {"id": "abc"})

    def test_feedback_goes_to_the_searchs_path_with_only_what_was_given(self):
        seen.clear()
        out = self.fc.feedback("r-1", "good", note="The first listing was the one to buy.")
        path, headers, body = seen[-1]
        self.assertEqual(path, "/v1/search/r-1/feedback")
        self.assertEqual(body, {"rating": "good", "note": "The first listing was the one to buy."})
        self.assertEqual(headers["Authorization"], "Bearer fc_live_test")
        self.assertEqual(list(out), ["request_id", "recorded", "already_reported", "credits_refunded", "refunded_today", "daily_refund_cap", "daily_cap_reached", "credits_used"])
        self.assertEqual(out, FEEDBACK)

    def test_feedback_fields_travel_as_the_api_takes_them(self):
        seen.clear()
        self.fc.feedback("r-1", "partial", useful_cards=[{"list": "same_product", "position": 1}],
                         wrong_cards=[{"list": "similar_products", "position": 2, "reason": "not_equivalent"}],
                         cheaper_elsewhere=[{"url": "https://other.example/p/9", "price": 17.5}, {"url": "https://other.example/p/10"}],
                         missing=["A listing from the brand's own store."], goal="Buy this kettle for less than the page's price.",
                         note="The second similar listing is a smaller size.")
        self.assertEqual(seen[-1][2], {
            "rating": "partial", "useful_cards": [{"list": "same_product", "position": 1}],
            "wrong_cards": [{"list": "similar_products", "position": 2, "reason": "not_equivalent"}],
            "cheaper_elsewhere": [{"url": "https://other.example/p/9", "price": 17.5}, {"url": "https://other.example/p/10"}],
            "missing": ["A listing from the brand's own store."], "goal": "Buy this kettle for less than the page's price.",
            "note": "The second similar listing is a smaller size."})

    def test_feedback_escapes_the_request_id_in_the_path(self):
        seen.clear()
        self.fc.feedback("r 1/x?y", "good", note="ok")
        self.assertEqual(seen[-1][0], "/v1/search/r%201%2Fx%3Fy/feedback")

    def test_feedback_lists_travel_as_given_so_a_bare_sentence_is_not_split_into_letters(self):
        # `missing` is a list of sentences. One sentence passed bare must reach the API as it is,
        # for the API to judge, never as a list of its letters.
        seen.clear()
        self.fc.feedback("r-1", "bad", missing="No listing from Amazon.")
        self.assertEqual(seen[-1][2], {"rating": "bad", "missing": "No listing from Amazon."})

    def test_the_envelope_becomes_an_api_error_with_its_fields(self):
        with self.assertRaises(FindcheapApiError) as cm:
            self.fc.search("https://en.wikipedia.org/wiki/Shoe")
        e = cm.exception
        self.assertEqual((e.status, e.type, e.credits_used, e.request_id, e.retry_after), (422, "not_searchable", 1, "e-1", None))
        self.assertIn("Billed as a page read", e.message)
        self.assertEqual(str(e), "422 not_searchable: Not a product page. Billed as a page read: 1 credit.")

    def test_a_429_carries_retry_after(self):
        with self.assertRaises(FindcheapApiError) as cm:
            self.fc.extract("https://slow.example/p")
        self.assertEqual((cm.exception.type, cm.exception.retry_after), ("rate_limited", 7))

    def test_a_body_that_is_not_the_envelope_is_http_error(self):
        with self.assertRaises(FindcheapApiError) as cm:
            self.fc.extract("https://proxy.example/p")
        self.assertEqual((cm.exception.status, cm.exception.type, cm.exception.credits_used), (502, "http_error", 0))

    def test_a_wrong_key_is_unauthorized(self):
        with self.assertRaises(FindcheapApiError) as cm:
            Findcheap(api_key="fc_live_wrong", base_url=self.base).resolve("x")
        self.assertEqual(cm.exception.type, "unauthorized")

    def test_feedback_with_the_rating_alone_travels_as_given_and_the_api_refuses_it(self):
        seen.clear()
        with self.assertRaises(FindcheapApiError) as cm:
            self.fc.feedback("r-1", "bad")
        self.assertEqual(seen[-1][2], {"rating": "bad"})
        e = cm.exception
        self.assertEqual((e.status, e.type, e.message), (400, "invalid_request", "Send the rating and at least one other field."))

    def test_feedback_on_a_search_that_is_not_found_is_search_not_found(self):
        with self.assertRaises(FindcheapApiError) as cm:
            self.fc.feedback("r-old", "good", note="Sent too late.")
        e = cm.exception
        self.assertEqual((e.status, e.type, e.credits_used, e.request_id, e.retry_after), (404, "search_not_found", 0, "e-3", None))
        self.assertEqual(str(e), "404 search_not_found: No search with this id in the last 20 minutes.")

    def test_feedback_switched_off_for_the_account_is_feedback_off(self):
        with self.assertRaises(FindcheapApiError) as cm:
            self.fc.feedback("r-off", "good", note="The first listing was the one to buy.")
        e = cm.exception
        self.assertEqual((e.status, e.type, e.credits_used, e.request_id, e.retry_after), (403, "feedback_off", 0, "e-4", None))
        self.assertEqual(e.message, "Feedback is switched off for this account.")

    def test_no_server_is_a_connection_error(self):
        with self.assertRaises(FindcheapConnectionError):
            Findcheap(api_key="fc_live_test", base_url="http://127.0.0.1:9", timeout=2).resolve("x")

    def test_no_key_anywhere_is_a_value_error(self):
        os.environ.pop("FINDCHEAP_API_KEY", None)
        with self.assertRaises(ValueError):
            Findcheap()


if __name__ == "__main__":
    unittest.main()
