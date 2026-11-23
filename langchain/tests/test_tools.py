"""Offline tests of the LangChain tools over a local stub of the API: no network, no key, no spend.

    cd findcheap-sdks/langchain && pip install -e ".[test]" && python -m pytest
"""
import os
import re
from unittest import mock

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from langchain_findcheap import (
    FindcheapFindCheaper,
    FindcheapReadProductPage,
    FindcheapResolveListing,
    FindcheapSearchProducts,
    FindcheapSubmitFeedback,
    FindcheapToolkit,
    __version__,
)

from . import stub as api

HERE = os.path.dirname(__file__)
# The names of Findcheap's MCP server's tools, in the order it lists them.
NAMES = ["find_cheaper", "read_product_page", "resolve_listing", "search_products", "submit_feedback"]
OBJECTIVE = "A small TV for a bedroom, as cheap as possible."


@pytest.fixture()
def server():
    stub = api.Stub()
    yield stub
    stub.close()


def tools(server, **more):
    """The five tools pointed at the stub, by name."""
    kit = FindcheapToolkit(api_key=api.KEY, base_url=server.url, **more)
    return {tool.name: tool for tool in kit.get_tools()}


# ── What the toolkit holds ─────────────────────────────────────────────────

def test_the_toolkit_holds_the_five_tools_by_the_servers_names(server):
    assert [tool.name for tool in FindcheapToolkit(api_key=api.KEY).get_tools()] == NAMES


def test_every_field_a_model_can_set_is_described(server):
    for name, tool in tools(server).items():
        function = convert_to_openai_tool(tool)["function"]
        assert function["name"] == name and function["description"]
        for field, schema in function["parameters"]["properties"].items():
            assert schema.get("description"), f"{name}.{field} has no description"


def test_what_each_tool_requires(server):
    required = {name: sorted(convert_to_openai_tool(tool)["function"]["parameters"].get("required", []))
                for name, tool in tools(server).items()}
    assert required == {
        "find_cheaper": ["url"],
        "read_product_page": ["url"],
        "resolve_listing": ["resolve_id"],
        "search_products": ["market", "objective"],
        "submit_feedback": ["rating", "request_id"],
    }


# ── What goes on the wire ──────────────────────────────────────────────────

def test_find_cheaper_sends_only_what_was_given_and_answers_untouched(server):
    answer = tools(server)["find_cheaper"].invoke({"url": "https://shop.example.com/p/1"})
    path, headers, body = server.seen[-1]
    assert (path, body) == ("/v1/search", {"url": "https://shop.example.com/p/1"})
    assert answer == api.SEARCH
    assert headers["Authorization"] == f"Bearer {api.KEY}"
    # The API is told the call came through this package, then the client.
    assert re.fullmatch(rf"langchain-findcheap/{re.escape(__version__)} findcheap-python/\S+", headers["User-Agent"])


def test_find_cheaper_sends_every_option(server):
    tools(server)["find_cheaper"].invoke({"url": "https://shop.example.com/p/1", "market": "CA",
                                          "marketplaces": ["ebay", "walmart"], "condition": "used", "max_results": 3})
    assert server.seen[-1][2] == {"url": "https://shop.example.com/p/1", "market": "CA",
                                  "marketplaces": ["ebay", "walmart"], "condition": "used", "max_results": 3}


def test_an_answers_next_step_runs_as_it_is_written(server):
    """`next_steps` name a tool and its arguments in the MCP server's words;
    the same names and fields are this package's, so a step runs unchanged."""
    kit = tools(server)
    step = kit["find_cheaper"].invoke({"url": "https://shop.example.com/p/1"})["next_steps"][0]
    kit[step["tool"]].invoke(step["arguments"])
    assert server.seen[-1][2] == {"url": "https://shop.example.com/p/1", "market": "US", "condition": "used"}


def test_read_product_page(server):
    answer = tools(server)["read_product_page"].invoke({"url": "https://shop.example.com/p/1", "market": "US"})
    assert server.seen[-1][0] == "/v1/extract"
    assert server.seen[-1][2] == {"url": "https://shop.example.com/p/1", "market": "US"}
    assert answer == api.READ


def test_resolve_listing(server):
    answer = tools(server)["resolve_listing"].invoke({"resolve_id": "abc"})
    assert (server.seen[-1][0], server.seen[-1][2]) == ("/v1/resolve", {"id": "abc"})
    assert answer == api.RESOLVE


def test_search_products_by_words(server):
    answer = tools(server)["search_products"].invoke(
        {"query": "Insignia Fire TV", "market": "US", "objective": OBJECTIVE, "max_price": 200})
    assert server.seen[-1][0] == "/v1/products/search"
    assert server.seen[-1][2] == {"market": "US", "query": "Insignia Fire TV", "objective": OBJECTIVE, "max_price": 200.0}
    assert answer == api.PRODUCTS


def test_search_products_by_a_photos_link(server):
    tools(server)["search_products"].invoke(
        {"image_url": "https://example.com/tv.jpg", "market": "US", "objective": OBJECTIVE})
    assert server.seen[-1][2] == {"market": "US", "image_url": "https://example.com/tv.jpg", "objective": OBJECTIVE}


def test_submit_feedback_sends_cards_as_plain_objects(server):
    answer = tools(server)["submit_feedback"].invoke({
        "request_id": "r-1", "rating": "partial",
        "useful_cards": [{"list": "same_product", "position": 1}],
        "wrong_cards": [{"list": "similar_products", "position": 2, "reason": "not_equivalent"}],
        "cheaper_elsewhere": [{"url": "https://other.example/kettle"}],
        "missing": ["A listing from Walmart."], "goal": "A cheaper kettle.", "note": "Short."})
    path, _, body = server.seen[-1]
    assert path == "/v1/search/r-1/feedback"
    assert body == {
        "rating": "partial",
        "useful_cards": [{"list": "same_product", "position": 1}],
        "wrong_cards": [{"list": "similar_products", "position": 2, "reason": "not_equivalent"}],
        # A cheaper listing sent without its price goes without one.
        "cheaper_elsewhere": [{"url": "https://other.example/kettle"}],
        "missing": ["A listing from Walmart."], "goal": "A cheaper kettle.", "note": "Short."}
    assert answer == api.FEEDBACK


# ── How an answer and a refusal reach a model ──────────────────────────────

def call(name, args):
    return {"name": name, "args": args, "id": "call-1", "type": "tool_call"}


def test_a_models_tool_call_gets_the_answer_as_json_text(server):
    message = tools(server)["read_product_page"].invoke(call("read_product_page", {"url": "https://shop.example.com/p/1"}))
    assert isinstance(message, ToolMessage) and message.status == "success"
    assert '"title": "Kettle"' in message.content and '"credits_used": 1' in message.content


def test_a_refused_call_reaches_the_model_in_the_apis_words(server):
    message = tools(server)["find_cheaper"].invoke(call("find_cheaper", {"url": "https://en.wikipedia.org/wiki/Shoe"}))
    assert message.status == "error"
    assert "422 not_searchable: Not a product page. Billed as a page read: 1 credit." in message.content


def test_a_rate_limit_says_how_long_to_wait(server):
    message = tools(server)["read_product_page"].invoke(call("read_product_page", {"url": "https://slow.example/p"}))
    assert message.status == "error" and "429 rate_limited" in message.content
    assert "Retry after 7 seconds." in message.content


def test_the_api_judges_a_search_that_names_no_product(server):
    message = tools(server)["search_products"].invoke(call("search_products", {"market": "US", "objective": OBJECTIVE}))
    assert message.status == "error" and "400 invalid_request" in message.content


def test_an_api_that_cannot_be_reached_is_a_tool_error_too():
    tool = FindcheapReadProductPage(api_key=api.KEY, base_url="http://127.0.0.1:9", timeout=2)
    message = tool.invoke(call("read_product_page", {"url": "https://shop.example.com/p/1"}))
    assert message.status == "error" and "Findcheap could not be reached" in message.content


# ── The checks made before a call ──────────────────────────────────────────

def test_arguments_outside_the_apis_limits_never_leave(server):
    kit = tools(server)
    with pytest.raises(ValidationError):
        kit["find_cheaper"].invoke({"url": "https://shop.example.com/p/1", "max_results": 11})
    with pytest.raises(ValidationError):
        kit["search_products"].invoke({"query": "TV", "market": "US"})            # no objective
    with pytest.raises(ValidationError):
        kit["submit_feedback"].invoke({"request_id": "r-1", "rating": "great"})   # not one of the three
    assert server.seen == []


def test_a_long_sentence_is_sent_not_refused(server):
    """The API cuts a sentence longer than it advises; this package leaves that to the API."""
    long_objective = "A TV. " * 80
    tools(server)["search_products"].invoke({"query": "TV", "market": "US", "objective": long_objective})
    assert server.seen[-1][2]["objective"] == long_objective


# ── The key ────────────────────────────────────────────────────────────────

def test_the_key_comes_from_the_environment(server):
    with mock.patch.dict(os.environ, {"FINDCHEAP_API_KEY": api.KEY}):
        tool = FindcheapResolveListing(base_url=server.url)
    assert tool.api_key.get_secret_value() == api.KEY
    assert tool.invoke({"resolve_id": "abc"}) == api.RESOLVE
    # The key is a secret: it is not in the tool's printed form.
    assert api.KEY not in repr(tool) and api.KEY not in str(tool.model_dump())


def test_no_key_is_a_set_up_error_the_developer_sees(server):
    with mock.patch.dict(os.environ, clear=True):
        tool = FindcheapFindCheaper(base_url=server.url)
        with pytest.raises(ValueError, match="FINDCHEAP_API_KEY"):
            tool.invoke({"url": "https://shop.example.com/p/1"})
    assert server.seen == []


def test_a_ready_client_is_used_as_it_is():
    class Client:
        def __init__(self):
            self.calls = []

        def extract(self, url, *, market=None):
            self.calls.append((url, market))
            return api.READ

    client = Client()
    with mock.patch.dict(os.environ, clear=True):
        tool = FindcheapToolkit(client=client).get_tools()[1]
        assert tool.invoke({"url": "https://shop.example.com/p/1"}) == api.READ
    assert client.calls == [("https://shop.example.com/p/1", None)]


# ── The package's own facts ────────────────────────────────────────────────

def test_one_version_in_both_places():
    text = open(os.path.join(HERE, "..", "pyproject.toml"), encoding="utf-8").read()
    assert re.search(r'^version = "([^"]+)"', text, re.M).group(1) == __version__


def test_the_readme_names_every_tool():
    readme = open(os.path.join(HERE, "..", "README.md"), encoding="utf-8").read()
    for name in NAMES:
        assert f"`{name}`" in readme


def test_each_tool_class_is_exported():
    assert {cls().name for cls in (FindcheapFindCheaper, FindcheapReadProductPage, FindcheapResolveListing,
                                   FindcheapSearchProducts, FindcheapSubmitFeedback)} == set(NAMES)
